"""Pinterest-Pins aus den echten Shop-Daten (läuft am Ende von build.py).

Schreibt dist/pins/<slug>.jpg (1000x1500) und dist/pins/pins.json (Titel, Text, Link, Board, Alt-Text).
Vorschau aller Pins: /pruefen/pins/ (nur intern, noindex).

Zwei Zielgruppen, ein Versprechen: „Süßigkeiten aus aller Welt entdecken – und sehen, wo's am günstigsten ist.“
Formate (jeweils ein klarer Hebel):
  entdecken  Neugier/Neuheit: „Hast du DAS schon probiert?“ – 4 Sorten einer Welt
  vergleich  Verlustangst: „Gleiche Packung. 4 Shops.“ – Preisspanne mit Datum
  guenstig   geringes Risiko: „Japan-Snacks unter 3 €“ – 6 Sorten
  anlass     konkreter Anlass: Filmabend, Mitbringsel, Adventskalender, Halloween …
  quiz       Selbsttest: „Welcher Snack-Typ bist du?“
Regeln: „Anzeige“ auf jedem Pin, keine Kaufaufforderung, keine Ansprache von Kindern, Preise nur mit Datum,
nur Produkte aus Partner-Feeds (Bilder mit Feed-Erlaubnis), nichts Erfundenes.
"""
import io
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "generator" / "fonts"
W, H = 1000, 1500
BG, FG, VIO, PINK, ORA, MINT, WHITE = "#EAF6F1", "#2B2350", "#6248E8", "#FF8FB1", "#FFB547", "#9EE3C6", "#FFFFFF"
DOMAIN = "naschpass.oneflowsolution.de"

# Themenwelt -> (Board, Überschrift-Wort, Suchbegriffe für Titel/Beschreibung)
WELTEN = {
    "japan": ("Japanische & asiatische Süßigkeiten", "aus Japan & Asien", "japanische Süßigkeiten, asiatische Snacks, Mochi, Pocky, Ramune"),
    "usa": ("Amerikanische Süßigkeiten", "aus den USA", "amerikanische Süßigkeiten, US Snacks, Reese's, Takis, Candy"),
    "mexiko": ("Mexikanische Süßigkeiten", "aus Mexiko", "mexikanische Süßigkeiten, scharfe Snacks, Chili Candy"),
    "skandinavien": ("Lakritz & Süßes aus Skandinavien", "aus Skandinavien", "Lakritz, Salmiak, skandinavische Süßigkeiten"),
    "italien": ("Italienische Süßigkeiten", "aus Italien", "italienische Süßigkeiten, Panettone, Cantucci, Torrone"),
    "schweiz": ("Schweizer Schokolade", "aus der Schweiz", "Schweizer Schokolade, Pralinen, Lindt, Toblerone"),
    "sauer-scharf": ("Saure & scharfe Snacks", "sauer & scharf", "saure Süßigkeiten, scharfe Chips, Sour Candy"),
}
ANLASS = {
    "filmabend": ("Snacks für den Filmabend", "FILMABEND?", "Snacks, die auf den Tisch gehören", "Filmabend Snacks, Knabberzeug, Chips, Popcorn"),
    "mitbringsel": ("Süße Mitbringsel & Danke-Geschenke", "KLEINES DANKE?", "Süße Mitbringsel, die gut ankommen", "Mitbringsel, kleine Geschenke, Pralinen, Danke"),
    "adventskalender": ("Adventskalender aus aller Welt", "ADVENTSKALENDER", "24 Türchen, aber mal anders", "Adventskalender Süßigkeiten, Adventskalender für Erwachsene"),
    "halloween": ("Halloween-Süßigkeiten", "HALLOWEEN", "Süßes für die Gruselparty", "Halloween Süßigkeiten, Halloween Party Snacks"),
    "geburtstag": ("Süße Geburtstagsideen", "GEBURTSTAG?", "Süße Ideen zum Verschenken", "Geburtstagsgeschenk Süßigkeiten, Naschbox"),
}
SPAR_BOARD = "Snacks günstiger finden – Preisvergleich"
try:
    BRANDS = {k.lower(): v.get("welt") for k, v in json.loads((HERE / "brands.json").read_text(encoding="utf-8"))["brands"].items()}
except Exception:
    BRANDS = {}
# Welche Herkunft eine Entdecken-Welt wirklich zeigen soll (sonst landen z. B. Nacho-Chips aus Österreich bei „Mexiko“)
ECHT = {"japan": {"japan", "korea", "asien"}, "usa": {"usa"}, "mexiko": {"mexiko"}, "skandinavien": {"skandinavien"},
        "italien": {"italien"}, "schweiz": {"schweiz"}}


def font(name, size, weight=None):
    f = ImageFont.truetype(str(FONTS / name), size)
    if weight:
        try:
            f.set_variation_by_axes([min(max(size, 14), 32), weight])
        except Exception:
            pass
    return f


def anton(s):
    return font("Anton-Regular.ttf", s)


def inter(s, w=500):
    return font("Inter.ttf", s, w)


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(d, text, maxw, maxlines, start, mn, fn=anton):
    s = start
    while s > mn:
        f = fn(s)
        ls = wrap(d, text, f, maxw)
        if len(ls) <= maxlines and all(d.textlength(x, font=f) <= maxw for x in ls):
            return f, ls
        s -= 4
    f = fn(mn)
    return f, wrap(d, text, f, maxw)[:maxlines]


def rrect(img, box, r, fill, outline=None, width=0):
    ImageDraw.Draw(img).rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def shadow(img, box, r=36, off=10, blur=18, alpha=60):
    x0, y0, x1, y1 = box
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + off, x1, y1 + off), r, fill=(43, 35, 80, alpha))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))


def paste_fit(img, pic, box, pad=18):
    x0, y0, x1, y1 = box
    p = pic.copy()
    p.thumbnail((x1 - x0 - 2 * pad, y1 - y0 - 2 * pad), Image.LANCZOS)
    img.alpha_composite(p, (x0 + (x1 - x0 - p.width) // 2, y0 + (y1 - y0 - p.height) // 2))


def card(img, box, pic, label=None, tag=None):
    shadow(img, box)
    rrect(img, box, 36, WHITE)
    x0, y0, x1, y1 = box
    lab_h = 0
    d = ImageDraw.Draw(img)
    if label:
        f, ls = fit(d, label, x1 - x0 - 40, 2, 30, 22, lambda s: inter(s, 650))
        lab_h = len(ls) * int(f.size * 1.2) + 26
        y = y1 - lab_h + 10
        for ln in ls:
            d.text(((x0 + x1) // 2, y), ln, font=f, fill=FG, anchor="ma")
            y += int(f.size * 1.2)
    if pic:
        paste_fit(img, pic, (x0, y0, x1, y1 - lab_h))
    if tag:
        f = inter(26, 750)
        tw = d.textlength(tag, font=f) + 34
        rrect(img, (x0 + 16, y0 + 16, x0 + 16 + tw, y0 + 62), 23, VIO)
        d.text((x0 + 16 + tw / 2, y0 + 39), tag, font=f, fill=WHITE, anchor="mm")


def base(kicker, bgcol=BG, pill=FG):
    img = Image.new("RGBA", (W, H), bgcol)
    d = ImageDraw.Draw(img)
    # Konfetti-Akzente (fest verteilt, nicht zufällig -> gleiche Pins bei jedem Build)
    for (x, y, c, r) in [(70, 125, PINK, 14), (930, 110, ORA, 16), (960, 210, MINT, 10), (36, 200, VIO, 8)]:
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    # Kopfzeile: Anzeige + Marke
    f = inter(24, 700)
    rrect(img, (40, 40, 40 + d.textlength("Anzeige", font=f) + 30, 80), 20, "#FFFFFFCC")
    d.text((55, 60), "Anzeige", font=f, fill=FG, anchor="lm")
    f = anton(34)
    d.text((W - 48, 60), "NASCHPASS", font=f, fill=FG, anchor="rm")
    if kicker:
        f = inter(30, 700)
        tw = d.textlength(kicker, font=f) + 44
        rrect(img, ((W - tw) / 2, 120, (W + tw) / 2, 172), 26, pill)
        d.text((W / 2, 146), kicker, font=f, fill=WHITE, anchor="mm")
    return img, d


def headline(img, d, text, y, size=118, color=FG, maxlines=3):
    """Überschrift in Anton, groß; '\n' erzwingt Zeilenumbrüche (z. B. „Gleiche Packung.\n3 Shops.“)."""
    text = text.upper()
    if "\n" in text:
        ls = text.split("\n")
        s = size
        while s > 60 and any(d.textlength(x, font=anton(s)) > W - 120 for x in ls):
            s -= 4
        f = anton(s)
    else:
        f, ls = fit(d, text, W - 120, maxlines, size, 64)
    for ln in ls:
        d.text((W / 2, y), ln, font=f, fill=color, anchor="ma")
        y += int(f.size * 1.05)
    return y


def footer(img, d, cta, sub=None):
    f = inter(36, 750)
    tw = d.textlength(cta, font=f) + 70
    shadow(img, ((W - tw) / 2, 1330, (W + tw) / 2, 1408), r=39, off=6, blur=10, alpha=50)
    rrect(img, ((W - tw) / 2, 1330, (W + tw) / 2, 1408), 39, VIO)
    d.text((W / 2, 1369), cta, font=f, fill=WHITE, anchor="mm")
    d.text((W / 2, 1450), sub or DOMAIN, font=inter(26, 600), fill=FG, anchor="mm")


def clean_name(n, maxlen=34):
    n = re.split(r"\s+[-–|]\s+", n)[0]
    n = re.sub(r",?\s*\d+(?:[.,]\d+)?\s*(g|kg|ml|l|gramm|stück|stk)\b.*$", "", n, flags=re.I).strip(" ,")
    return n if len(n) <= maxlen else n[:maxlen - 1].rsplit(" ", 1)[0] + "…"


def make(dist, products, cats, cat_items, facets, euro, today, top_brands, log=print):
    out = dist / "pins"
    out.mkdir(parents=True, exist_ok=True)
    cache = HERE / "img_cache"
    by_cat = {c["id"]: c for c in cats}
    datum = today.strftime("%d.%m.%Y")

    def local(p):
        im = p.get("image", "")
        if im.startswith("/i/") and (cache / im[3:]).exists():
            return cache / im[3:]
        return None

    usable = lambda p: p.get("source") == "awin" and local(p) and (p.get("imgkb") or 99) >= 7

    # Große Bilder nur für die Produkte holen, die wirklich auf Pins landen
    picked = {}

    def want(p):
        picked[id(p)] = p
        return p

    plans = []
    # 1) Entdecken je Welt
    for cid, (board, wo, kw) in WELTEN.items():
        if cid not in by_cat:
            continue
        items = [p for p in cat_items(by_cat[cid]) if usable(p)]
        echt = ECHT.get(cid)

        def neu(p):  # „Hast du das schon probiert?“: echte Herkunft, keine Supermarkt-Riesen, Marke nicht aus DE/AT
            b = (p.get("brand") or "").lower()
            if echt and p.get("land") not in echt:
                return False
            if BRANDS.get(b) in ("deutschland", "oesterreich"):
                return False
            return not (b in top_brands and cid not in ("japan",))
        pool = [p for p in items if neu(p)]
        if len(pool) < 4:
            pool = items
        seen, sel = set(), []
        for p in pool:  # Abwechslung: nicht 4x dieselbe Marke
            b = (p.get("brand") or p["name"].split()[0]).lower()
            if b in seen:
                continue
            seen.add(b)
            sel.append(want(p))
            if len(sel) == 4:
                break
        if len(sel) == 4:
            n = len(items)
            plans.append(dict(kind="entdecken", slug=f"entdecken-{cid}", board=board, items=sel, cid=cid, wo=wo, n=n,
                              link=f"/kategorie/{cid}/",
                              title=f"Süßigkeiten {wo}: {', '.join(clean_name(p['name'], 22) for p in sel[:3])} & mehr",
                              desc=f"Hast du die schon probiert? {n} Sorten {wo} an einem Ort entdecken – mit Preisvergleich zwischen den Shops. {kw}. Anzeige: Links zu Partner-Shops."))
    # 2) Preisvergleich: bekannte Marken, gleiche Packung, deutlicher Unterschied
    cands = []
    for p in products:
        if not (p.get("offers") and p.get("offers_same") and usable(p) and p.get("price")):
            continue
        brand = (p.get("brand") or "").lower()
        if brand not in top_brands and not any(p["name"].lower().startswith(b) for b in top_brands):
            continue
        hi = max([o["p"] for o in p["offers"]] + [p["price"]])
        lo = min([o["p"] for o in p["offers"]] + [p["price"]])
        spread = hi - lo
        if spread >= 0.4 and hi / lo >= 1.15:
            cands.append((len(p["offers"]), spread / hi, p, hi))
    cands.sort(key=lambda x: (-x[0], -x[1]))
    cands = [(r, p, hi) for _, r, p, hi in cands]
    seen = set()
    for rel, p, hi in cands:
        st = clean_name(p["name"], 60).lower()
        if st in seen:
            continue
        seen.add(st)
        want(p)
        name = clean_name(p["name"], 40)
        n = len(p["offers"]) + 1
        plans.append(dict(kind="vergleich", slug="vergleich-" + re.sub(r"[^a-z0-9]+", "-", st).strip("-")[:40], board=SPAR_BOARD, items=[p],
                          link="/shop/?q=" + urllib.request.quote(clean_name(p["name"], 60)),
                          title=f"{name}: {n} Shops im Preisvergleich",
                          desc=f"Gleiche Packung {name}, {n} Online-Shops im Vergleich (Preise Stand {datum}, ggf. zzgl. Versand). "
                               f"Naschpass zeigt bei über 12.000 Süßigkeiten, wo du am wenigsten zahlst. Anzeige: Links zu Partner-Shops."))
        if sum(1 for x in plans if x["kind"] == "vergleich") >= 12:
            break
    # 3) Unter 3 € je Welt
    for cid in ("japan", "usa", "skandinavien", "mexiko"):
        if cid not in by_cat:
            continue
        board, wo, kw = WELTEN[cid]
        items = [p for p in cat_items(by_cat[cid]) if usable(p) and p.get("price") and p["price"] < 3]
        seen, sel = set(), []
        for p in items:
            b = (p.get("brand") or p["name"].split()[0]).lower()
            if b not in seen:
                seen.add(b)
                sel.append(want(p))
            if len(sel) == 6:
                break
        if len(sel) == 6:
            plans.append(dict(kind="guenstig", slug=f"unter-3-euro-{cid}", board=board, items=sel, wo=wo,
                              link=f"/kategorie/{cid}/",
                              title=f"Snacks {wo} unter 3 € – zum Ausprobieren",
                              desc=f"6 Sorten {wo} für unter 3 € (Preise Stand {datum}): klein anfangen, Neues probieren. {kw}. Anzeige: Links zu Partner-Shops."))
    # 4) Anlässe (Saison nur in der Saison)
    for cid, (board, head, sub, kw) in ANLASS.items():
        c = by_cat.get(cid)
        if not c:
            continue
        se = c.get("season")
        if se:
            md = today.strftime("%m-%d")
            if not (se[0] <= md <= se[1]):
                continue
        items = [p for p in cat_items(c) if usable(p)]
        seen, sel = set(), []
        for p in items:
            b = (p.get("brand") or p["name"].split()[0]).lower()
            if b not in seen:
                seen.add(b)
                sel.append(want(p))
            if len(sel) == 5:
                break
        if len(sel) >= 4:
            plans.append(dict(kind="anlass", slug=f"anlass-{cid}", board=board, items=sel, head=head, sub=sub, n=len(items),
                              link=f"/kategorie/{cid}/",
                              title=f"{board}: {len(items)} Ideen aus aller Welt",
                              desc=f"{sub}: {len(items)} Ideen aus aller Welt an einem Ort, mit Preisvergleich zwischen den Shops. {kw}. Anzeige: Links zu Partner-Shops."))
    # 5) Quiz
    quiz_items = []
    for art in ("schokolade", "gummi", "chips", "getraenke"):
        p = next((x for x in products if usable(x) and x not in quiz_items and art in facets(x).get("art", set())
                  and x.get("land") in ("japan", "usa", "korea", "asien", "mexiko")), None)
        if p:
            quiz_items.append(want(p))
    if len(quiz_items) == 4:
        plans.append(dict(kind="quiz", slug="quiz-snack-typ", board="Snack-Ideen & Naschtipps", items=quiz_items, link="/quiz/",
                          title="Welcher Snack-Typ bist du? Das Naschpass-Quiz",
                          desc="5 Fragen, dein Snack-Typ und passende Süßigkeiten aus aller Welt. Süß, sauer, salzig oder scharf? Anzeige: Links zu Partner-Shops."))

    # Große Bilder parallel laden (Fallback: kleines Bild aus dem Cache)
    def big(p):
        src = p.get("isrc")
        if src and src.startswith("http"):
            try:
                req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 (naschpass-pins)"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                im = Image.open(io.BytesIO(data))
                if im.width >= 300 and im.height >= 300:
                    return id(p), im
            except Exception:
                pass
        return id(p), Image.open(local(p))

    with ThreadPoolExecutor(max_workers=8) as ex:
        pics = dict(ex.map(big, picked.values()))

    def rgba(p):
        im = pics[id(p)]
        if im.mode in ("P", "LA", "RGBA"):
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, WHITE)
            bg.alpha_composite(im)
            return bg
        return im.convert("RGBA")

    manifest = []
    for pl in plans:
        k = pl["kind"]
        BOTTOM = 1305  # darunter: Knopf + Adresse
        if k == "entdecken":
            img, d = base(f"{pl['n']} Sorten {pl['wo']}")
            y = headline(img, d, "Hast du das\nschon probiert?", 205, 120) + 25
            ch = (BOTTOM - y - 20) // 2
            boxes = [(60, y, 490, y + ch), (510, y, 940, y + ch), (60, y + ch + 20, 490, BOTTOM), (510, y + ch + 20, 940, BOTTOM)]
            for bx, p in zip(boxes, pl["items"]):
                card(img, bx, rgba(p), clean_name(p["name"], 30))
            footer(img, d, "Alle Sorten entdecken")
        elif k == "vergleich":
            p = pl["items"][0]
            rows = sorted([(p.get("shop", ""), p["price"])] + [(o["s"], o["p"]) for o in p["offers"]], key=lambda x: x[1])[:5]
            img, d = base(f"Preisvergleich · Stand {datum}")
            y = headline(img, d, f"Gleiche Packung.\n{len(rows)} Shops.", 205, 116) + 20
            f, ls = fit(d, clean_name(p["name"], 60), W - 160, 2, 46, 30, lambda s: inter(s, 750))
            rh = 84
            tab_h = len(ls) * int(f.size * 1.2) + 24 + rh * len(rows)
            pic_bottom = BOTTOM - tab_h - 10
            card(img, (190, y, 810, pic_bottom), rgba(p))
            ty = pic_bottom + 22
            for ln in ls:
                d.text((W / 2, ty), ln, font=f, fill=FG, anchor="ma")
                ty += int(f.size * 1.2)
            ty += 6
            for i, (sh, pr) in enumerate(rows):
                best = i == 0
                rrect(img, (110, ty, 890, ty + rh - 12), 24, MINT if best else WHITE)
                d.text((140, ty + (rh - 12) / 2), sh + ("  · günstigster" if best else ""), font=inter(32, 750 if best else 550), fill=FG, anchor="lm")
                d.text((860, ty + (rh - 12) / 2), euro(pr), font=inter(34, 800 if best else 600), fill=FG, anchor="rm")
                ty += rh
            footer(img, d, "Preise vergleichen", f"ggf. zzgl. Versand · {DOMAIN}")
        elif k == "guenstig":
            img, d = base(f"Stand {datum}")
            y = headline(img, d, f"Snacks {pl['wo']}", 205, 104, maxlines=2)
            d.text((W / 2, y - 6), "UNTER 3 €", font=anton(156), fill=VIO, anchor="ma")
            y += 185
            bw, gx, gy = 280, 30, 26
            bh = min(420, (BOTTOM - y - gy) // 2)
            for i, p in enumerate(pl["items"]):
                cx, cy = 60 + (i % 3) * (bw + gx), y + (i // 3) * (bh + gy)
                card(img, (cx, cy, cx + bw, cy + bh), rgba(p), clean_name(p["name"], 18), tag=euro(p["price"]))
            footer(img, d, "Neues ausprobieren")
        elif k == "anlass":
            img, d = base(pl["sub"])
            y = headline(img, d, pl["head"], 205, 150, maxlines=2) + 25
            items = pl["items"]
            top_h = int((BOTTOM - y) * 0.6)
            sh_ = (top_h - 20) // 2
            card(img, (60, y, 600, y + top_h), rgba(items[0]))
            card(img, (620, y, 940, y + sh_), rgba(items[1]))
            card(img, (620, y + sh_ + 20, 940, y + top_h), rgba(items[2]))
            for i, p in enumerate(items[3:5]):
                card(img, (60 + i * 450, y + top_h + 20, 490 + i * 450, BOTTOM), rgba(p))
            footer(img, d, f"{pl['n']} Ideen ansehen")
        else:  # quiz
            img, d = base("5 Fragen · 1 Minute", FG, pill=VIO)
            y = headline(img, d, "Welcher\nSnack-Typ bist du?", 205, 130, color=WHITE) + 25
            ch = (BOTTOM - y - 20) // 2
            labels = ["Schoko", "Fruchtgummi", "Chips", "Limo"]
            for i, (p, lab) in enumerate(zip(pl["items"], labels)):
                cx, cy = 60 + (i % 2) * 450, y + (i // 2) * (ch + 20)
                card(img, (cx, cy, cx + 430, cy + ch), rgba(p), tag=lab)
            footer(img, d, "Quiz starten")
            rrect(img, (0, 1430, W, H), 0, FG)
            d.text((W / 2, 1450), DOMAIN, font=inter(26, 600), fill=WHITE, anchor="mm")
        img.convert("RGB").save(out / f"{pl['slug']}.jpg", "JPEG", quality=88, optimize=True)
        names = ", ".join(clean_name(p["name"], 40) for p in pl["items"])
        manifest.append({"slug": pl["slug"], "kind": k, "board": pl["board"], "image": f"/pins/{pl['slug']}.jpg",
                         "link": f"https://{DOMAIN}{pl['link']}", "title": pl["title"][:100], "description": pl["desc"][:500],
                         "alt": f"Naschpass-Pin: {pl['title']}. Zu sehen: {names}."[:500], "stand": today.isoformat()})
    (out / "pins.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[Pins] {len(manifest)} Pins: " + ", ".join(f"{k} {sum(1 for m in manifest if m['kind'] == k)}" for k in ("entdecken", "vergleich", "guenstig", "anlass", "quiz")))
    return manifest
