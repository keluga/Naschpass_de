"""Holt Produkte aus AWIN-Feeds und schreibt sie nach website/feed_products.json (nicht im Repo).

Läuft im Netlify-Build vor build.py. Nur Python-Standardbibliothek.

Quelle:
- AWIN_FEED_URL (und optional AWIN_FEED_URL_2 … _9): Create-a-Feed-Link aus dem AWIN-Konto.
  Der Link enthält Kevs API-Schlüssel. Er steht NUR als Umgebungsvariable in Netlify
  und wird hier nie ausgegeben, gespeichert oder geloggt.
- AWIN_FEED_FILE: lokale CSV (auch .gz/.zip) zum Testen, z. B. ein von Kev geladener Feed.

Regeln (siehe WEBSITE_VISION.md, Abschnitt 5):
- Nur Advertiser aus website/feeds.json mit "active": true.
- Raus: nicht vorrätig, Alkohol, Non-Food, ohne AWIN-Bild, Dubletten.
- Welche Zeilen passen: "include"/"include_name"/"exclude_name" je Shop in feeds.json.
- Keine Mengen-Kappung. Herkunft ("Welt") aus brands.json + Hinweisen, "score" für die Reihenfolge.
Der Build scheitert nie an diesem Skript: Bei Fehlern wird ohne Feed weitergebaut.
"""
import csv
import gzip
import io
import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "feed_products.json"
CONF = Path(os.environ.get("FEEDS_CONFIG") or HERE / "feeds.json")
_toml = (HERE.parent / "netlify.toml").read_text(encoding="utf-8")
_m = re.search(r"remote_images\s*=\s*\[(.*?)\]", _toml, re.S)
REMOTE_OK = [re.compile(x) for x in re.findall(r"'([^']+)'", _m.group(1))] if _m else []
# Nur in Netlify-Vorschauen: Rohdaten (ohne Links) zum Entwickeln der Sortierung ablegen
DUMP = os.environ.get("CONTEXT") == "deploy-preview" or os.environ.get("FEED_DUMP") == "1" \
    or (os.environ.get("WORKERS_CI") == "1" and os.environ.get("WORKERS_CI_BRANCH", "main") != "main")
DUMP_ROWS = []
# Cloudflare Pages (oder IMG_LOCAL=1): Produktbilder beim Build einmal klein herunterladen und selbst ausliefern.
# Kein Bild-CDN nötig, keine Verbindung der Besucher zu den Shops (kein Cookie-Banner), Traffic bei Cloudflare kostenlos.
IMG_LOCAL = os.environ.get("CF_PAGES") == "1" or os.environ.get("WORKERS_CI") == "1" or os.environ.get("IMG_LOCAL") == "1"
IMG_DIR = HERE / "img_cache"


def parse_price(v):
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)", (v or "").replace("\u00a0", " "))
    if not m:
        return None
    try:
        x = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    return x if 0.1 <= x <= 2000 else None


def small_img(url, w=320):
    """Bild-URL in kleiner Größe (AWIN-Bildserver und Shopify können das selbst)."""
    if "productserve.com" in url:
        url = re.sub(r"([?&])w=\d+", rf"\g<1>w={w}", url)
        return re.sub(r"([?&])h=\d+", rf"\g<1>h={w}", url)
    if "cdn.shopify.com" in url:
        return url + ("&" if "?" in url else "?") + f"width={w}"
    return url


def fetch_images(prods):
    import hashlib
    from concurrent.futures import ThreadPoolExecutor
    IMG_DIR.mkdir(exist_ok=True)
    def one(p):
        name = hashlib.sha1(p["image"].encode()).hexdigest()[:16] + ".jpg"
        dest = IMG_DIR / name
        if not dest.exists():
            try:
                req = urllib.request.Request(small_img(p["image"]), headers={"User-Agent": "naschpass-build"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                if len(data) < 300:
                    return None
                dest.write_bytes(data)
            except Exception:
                return None
        p["image"] = "/i/" + name
        p["imgkb"] = round(dest.stat().st_size / 1024, 1)  # für die Reihenfolge: sehr kleine Bilder sind meist schwach
        return p
    with ThreadPoolExecutor(max_workers=24) as ex:
        out = [p for p in ex.map(one, prods) if p]
    log(f"Bilder: {len(out)} von {len(prods)} geladen")
    return out

ALKOHOL = re.compile(
    r"\b(wein|weine|rotwein|weißwein|weisswein|ros[eé]wein|sekt|prosecco|champagner|cava|spirituose\w*|lik[öo]r\w*|likoer\w*|"
    r"bier|biere|gin|rum|wodka|vodka|whisk(e)?y|tequila|mezcal|grappa|limoncello|amaro|brandy|cognac|schnaps|aperitif|"
    r"vermouth|wermut|sake|alkohol\w*|vol\.?\s*%|\d+([.,]\d+)?\s*%\s*vol)\b", re.I)
NONFOOD = re.compile(
    r"\b(tasse|becher|teller|schale|geschirr|porzellan|st[äa]bchen|messer|gabel|l[öo]ffel|topf|pfanne|buch|kochbuch|t-?shirt|"
    r"shirt|hoodie|socken|kerze|deko|dekoration|vase|gutschein|geschenkgutschein|spielzeug|pl[üu]sch|kosmetik|seife|duft|"
    r"backform|ausstecher|dose leer|grill)\b", re.I)
ADV_RAW, ADV_NO = {}, {}
try:  # Sperrliste: von Hand gemeldete Produkte (ausgelistet, falsch, unpassend)
    SPERR = [x.lower() for x in json.loads((Path(__file__).parent / "sperrliste.json").read_text(encoding="utf-8")).get("eintraege", []) if x]
except Exception:
    SPERR = []
NO = {"0", "no", "nein", "false", "n", "out of stock", "outofstock", "out_of_stock", "nicht verfügbar"}

ALIASES = {
    "name": ["product_name", "name", "title"],
    "desc": ["description", "product_short_description"],
    "url": ["aw_deep_link", "deep_link", "link"],
    "image": ["aw_image_url", "aw_thumb_url", "image_link"],
    "price": ["search_price", "display_price", "price", "store_price"],
    "sale": ["sale_price"],
    "merchant_id": ["merchant_id", "advertiser_id"],
    "merchant_name": ["merchant_name", "advertiser_name"],
    "mcat": ["merchant_category", "merchant_product_category_path"],
    "cat": ["category_name", "product_type", "google_product_category"],
    "brand": ["brand_name", "brand"],
    "stock": ["in_stock", "stock_status", "is_for_sale", "availability"],
}


def log(msg):
    print(f"[Feed-Import] {msg}", flush=True)


def col(row, key):
    for a in ALIASES[key]:
        v = row.get(a)
        if v:
            return v.strip()
    return ""


def open_feed(path):
    """Gibt einen Text-Stream für CSV, CSV.gz oder ZIP (erste CSV darin) zurück."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] == b"\x1f\x8b":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8-sig", errors="replace", newline="")
    if head[:2] == b"PK":
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if not n.endswith("/"))
        return io.TextIOWrapper(z.open(name), encoding="utf-8-sig", errors="replace", newline="")
    return open(path, encoding="utf-8-sig", errors="replace", newline="")


def download(url, n):
    """Lädt einen Feed in eine temporäre Datei. Die URL wird nie ausgegeben."""
    tmp = tempfile.NamedTemporaryFile(prefix="awin_", suffix=".feed", delete=False)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "naschpass-build"})
        with urllib.request.urlopen(req, timeout=420) as r, tmp:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                tmp.write(chunk)
        return tmp.name
    except Exception as ex:  # bewusst ohne str(ex): könnte die URL enthalten
        code = getattr(ex, "code", "")
        log(f"Feed {n}: Download fehlgeschlagen ({type(ex).__name__} {code}). Weiter ohne diesen Feed.")
        os.unlink(tmp.name)
        return None


def sources():
    out = []
    if os.environ.get("AWIN_FEED_FILE"):
        out.append(("Datei", os.environ["AWIN_FEED_FILE"], False))
    try:
        conf = json.loads(CONF.read_text(encoding="utf-8"))
        want = [str(x["fid"]) for x in conf.get("advertisers", []) if x.get("active") and str(x.get("fid", "")).isdigit()]
    except Exception:
        want = []
    template_used = False
    for i, k in enumerate(["AWIN_FEED_URL"] + [f"AWIN_FEED_URL_{n}" for n in range(2, 10)], 1):
        for part in (os.environ.get(k) or "").split():
            m = re.search(r"/fid/([^/]+)/", part)
            ids = m.group(1).split(",") if m else []
            if want and not template_used and m and any(x.isdigit() for x in ids):
                # Awin-Format-Link als Vorlage: Feed-IDs kommen aus feeds.json (aktive Partner), nicht aus dem Link
                template_used = True
                part = part[:m.start(1)] + ",".join(want) + part[m.end(1):]
                log(f"Feed #{i}: als Vorlage genutzt für Feeds {', '.join(want)}")
            elif template_used and m and all(x.isdigit() for x in ids):
                continue  # weitere Awin-Links sind durch die Vorlage schon abgedeckt
            out += split_feed(part, f"#{i}")
    return out


def split_feed(url, label):
    """Ein AWIN-Link mit mehreren Feed-IDs wird in einen Abruf pro Feed zerlegt.
    Grund: AWIN baut die Datei beim Abruf zusammen; ein großer Sammel-Link läuft in den Timeout.
    Die Kategorie-Liste (/cid/...) fällt weg, gefiltert wird ohnehin hier im Skript.
    Google-Format-IDs (z. B. F4010) gehen nicht im selben Link und werden übersprungen."""
    url = re.sub(r"/cid/[^/]+", "", url)
    m = re.search(r"/fid/([^/]+)/", url)
    if not m:
        return [(label, url, True)]
    ids = m.group(1).split(",")
    bad = [x for x in ids if not x.isdigit()]
    if bad and any(x.isdigit() for x in ids):
        log(f"Feed {label}: Google-Format-Feed(s) {', '.join(bad)} übersprungen (brauchen eigenen Link).")
    if not any(x.isdigit() for x in ids):  # eigener Link nur mit Google-Feed(s): so lassen
        return [(label, url, True)]
    return [(f"{label}/{x}", url[:m.start(1)] + x + url[m.end(1):], True) for x in ids if x.isdigit()]


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


BRANDS = json.loads((HERE / "brands.json").read_text(encoding="utf-8")).get("brands", {}) if (HERE / "brands.json").exists() else {}
_BAD_BRANDS = sorted((k for k, v in BRANDS.items() if v.get("alkohol") or v.get("tier")), key=len, reverse=True)
TIER = re.compile(r"\b(katze\w*|hund\w*|kitten|welpe\w*|tierfutter|katzenfutter|hundefutter|nassfutter|trockenfutter|leckerli\w*|kauknochen|vogelfutter)\b", re.I)
# Welt-Hinweise aus Kategorie/Name, wenn die Marke nichts verrät (es geht um die Idee, nicht um die Fabrik)
WELT_HINTS = [
    (r"\bjapan|japanisch|matcha|mochi|pocky|ramune|hi-?chew|yuzu", "japan"),
    (r"\bkorea|koreanisch|kimchi|buldak|gochujang|pepero", "korea"),
    (r"asiatisch|thailand|thai\b|thailändisch|china|chinesisch|vietnam|indonesi|indisch|indien|ayurved|masala|chai\b", "asien"),
    (r"mexikan|mexiko|mexico|jalape|tortilla|nacho|chipotle|tajin|takis", "mexiko"),
    (r"\busa\b|amerikan|american|peanut butter|marshmallow fluff|pop-?tarts", "usa"),
    (r"italien|italia|panettone|pandoro|cantucci|amaretti|torrone|grissini|taralli|piemont|sizilian", "italien"),
    (r"griechisch|arabisch|orient|türkisch|tuerkisch|persisch|baklava|halva|helva|lokum|dattel|pistazien-?creme|persisch", "orient"),
    (r"englisch|british|britisch|scottish|schottisch|shortbread|irish", "uk"),
    (r"schwedisch|norwegisch|finnisch|dänisch|skandinav|lakritz|salmiak", "skandinavien"),
    (r"französisch|france|francais|macaron|crêpe|bretagne|provence", "frankreich"),
    (r"spanisch|españa|turrón|turron|churro|iberico", "spanien"),
    (r"österreich|oesterreich|steiri|tirol|wiener|mozart|vulgo|kärnt", "oesterreich"),
    (r"schweiz|swiss|suisse", "schweiz"),
    (r"belgisch|holländ|niederländ|stroopwafel|speculoos|spekulatius", "benelux"),
]
WELT_HINTS = [(re.compile(r, re.I), w) for r, w in WELT_HINTS]
# Passt nicht zum Naschen, auch wenn die Shop-Kategorie es reinlässt (geprüft an 6.200 echten Produkten)
# HART: immer raus. WEICH: raus, wenn im Namen nichts nach Naschen klingt (NASCH rettet z. B. "Karamell-Salz-Mandeln").
HART = re.compile(r"(wurst|würst|salami|schinken|speck\b|fleisch|geschnetzelt|leber|pastete|terrine|rillette|schmalz|verhackert|grammel|"
                  r"fisch|lachs|hering|thunfisch|sardine|sardelle|anchovi|kaviar|garnele|krabbe|\bhipp\b|babybrei|säugling|basmati|\breis\b|"
                  r"naturreis|langkorn|wildreis|couscous|bulgur|quinoa|polenta|risotto|gnocchi|ravioli|tortellini|maultasche|knödel|windel|"
                  r"teekanne|teefilter|kaffeefilter|filtertüte|flammkuchen|fondant|backmischung|backpulver|\bhefe\b|\bmehl\b|"
                  r"(grün|rot|weiß|weiss|rosen|spitz|blumen)kohl|sauerkraut|rotkraut|rote bete|spargel|spinat|chia|flohsamen|hanfsamen|leinsamen|"
                  r"gemüseaufstrich|tortencreme|tortenguss|sahnesteif|pampers|feuchttüch|stövchen|fertiggericht|mikrowellen)", re.I)
WEICH = re.compile(r"(käse|kaese|parmesan|pecorino|joghurt|quark|sahne\b|\bbutter\b|gemüse|tomate|zwiebel|knoblauch|kartoffel|oliven|pilz|"
                   r"kapern|gurke|bohne|linse|erbse|kichererbse|hummus|pesto|sugo|sauce|soße|sosse|dressing|brot\b|brötchen|toast|knäcke|"
                   r"nudel|pasta\b|spaghetti|\bsalz\b|pfeffer(?!minz)|pfefferoni|pfefferschote|gewürz|würz|brühe|bouillon|suppe|pizza|\böl\b|"
                   r"kokosöl|olivenöl|essig|senf|mayo|ketchup|wrap|burrito|curry|chutney|tofu|tempeh|seitan|eintopf)", re.I)
NASCH = re.compile(r"(schoko|choco|karamell|caramel|toffee|praline|marzipan|lebkuchen|kuchen|torte|keks|cookie|waffel|gummi|bonbon|lolli|"
                   r"lakritz|popcorn|\bpop\b|puffs|chips|crisps|cracker|flips|nüss|nuss|\bnuts?\b|mandel|almond|cashew|pistazie|erdnuss|peanut|"
                   r"snack|riegel|\beis\b|eiscreme|sorbet|dessert|pudding|sirup|limonade|\blimo\b|soda|cola|saft|\btee\b|\btea\b|kakao|honig|"
                   r"konfitüre|marmelade|nougat|candy|sweet|dattel|pringles|knabber|kerne|cocopizza|minz)", re.I)
ART_KERN = re.compile(r"schoko|choco|praline|trüffel|fruchtgummi|gummi|bonbon|lolli|kaugummi|lakritz|marshmallow|chips|cracker|popcorn|"
                      r"keks|cookie|waffel|riegel|nüss|nuss|mandel|cashew|snack|sour|sauer|candy|sweets|zuckerl|brause|nougat|marzipan|"
                      r"adventskalender|soda|limo|cola|sirup|ramune|mochi|pocky", re.I)


_BRAND_RX = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(BRANDS, key=len, reverse=True) if len(k) >= 3) + r")(?![\w])", re.I) if BRANDS else None
_BRAND_LC = {k.lower(): k for k in BRANDS}
_STRONG = re.compile(r"\b(japan|japanisch\w*|korea|koreanisch\w*|usa|amerikanisch\w*|mexikanisch\w*|italienisch\w*|thailändisch\w*|chinesisch\w*|"
                     r"türkisch\w*|griechisch\w*|arabisch\w*|indisch\w*|französisch\w*|spanisch\w*|englisch\w*|britisch\w*|schwedisch\w*|matcha|sakura|yuzu|"
                     r"finnisch\w*|norwegisch\w*|dänisch\w*|österreichisch\w*|schweizer|belgisch\w*|holländisch\w*|asiatisch\w*)\b", re.I)


FERN = {"usa", "japan", "korea", "mexiko", "asien", "orient", "uk"}
WELT_BONUS = {**{w: 4 for w in FERN}, **{w: 1 for w in ("oesterreich", "schweiz", "italien", "frankreich", "benelux", "spanien", "skandinavien", "osteuropa")}}
_GENERIC = re.compile(r"^(nahrungsmittel, getränke & tabak|food, beverages & tobacco|lebensmittel|food items|food)$", re.I)


def _cat_tail(c):
    parts = [x.strip() for x in re.split(r"\s*>\s*", c) if x.strip() and not _GENERIC.match(x.strip())]
    return " ".join(parts[-2:])


def brand_of(name, brand, shop=""):
    """Marke bestimmen. Händler schreiben oft ihren eigenen Namen ins Marken-Feld (z. B. "SugarGang" bei Kinder-Produkten),
    dann wird die Marke im Produktnamen gesucht."""
    b = (brand or "").replace("&amp;", "&").strip()
    reseller = not b or b.lower() in (shop or "").lower() or (shop or "").lower() in b.lower()
    if b in BRANDS and not reseller:
        return b
    if _BRAND_RX:
        m = _BRAND_RX.search(name)
        if m:
            return _BRAND_LC.get(m.group(1).lower(), b)
    if reseller and b and b.lower() not in name.lower():
        return ""  # Händlername ist keine Marke dieses Produkts
    return b


def welt_of(name, brand, cats):
    hay = f"{name} {cats}"
    m = _STRONG.search(hay)  # ausdrückliches Land im Namen/Kategorie schlägt die Marke ("KitKat Matcha Japan")
    if m:
        for r, w in WELT_HINTS:
            if r.search(m.group(0)):
                return w
    b = BRANDS.get(brand, {})
    if b.get("welt"):
        return b["welt"]
    for r, w in WELT_HINTS:
        if r.search(hay):
            return w
    return None


def main():
    srcs = sources()
    if not srcs:
        log("Kein AWIN_FEED_URL gesetzt, übersprungen. Es gelten nur die Produkte aus products.json.")
        OUT.unlink(missing_ok=True)
        return
    conf = json.loads(CONF.read_text(encoding="utf-8"))
    adv = {str(a["id"]): a for a in conf.get("advertisers", []) if a.get("active")}
    if not adv:
        log("Kein Advertiser in feeds.json aktiv, übersprungen.")
        OUT.unlink(missing_ok=True)
        return
    rx = lambda v: re.compile(v, re.I) if v else None
    inc = {k: rx(a.get("include")) for k, a in adv.items()}
    inc_name = {k: rx(a.get("include_name")) for k, a in adv.items()}
    exc_name = {k: rx(a.get("exclude_name")) for k, a in adv.items()}
    manual = json.loads((HERE / "products.json").read_text(encoding="utf-8")).get("products", [])
    seen = {norm(p.get("name", "")) for p in manual} | {p.get("url", "") for p in manual}

    result = []
    stats = {"zeilen": 0, "inaktiv": 0, "lager": 0, "alkohol": 0, "tier": 0, "nonfood": 0, "thema": 0, "ohne_bild": 0, "doppelt": 0}
    per_src = {}
    for label, src, is_url in srcs:
        path = download(src, label) if is_url else src
        if not path:
            continue
        n0 = stats["zeilen"]
        try:
            with open_feed(path) as fh:
                first = fh.readline()
                delim = max([",", "|", ";", "\t"], key=first.count)
                fields = [f.strip() for f in next(csv.reader([first], delimiter=delim))]
                for row in csv.DictReader(fh, fieldnames=fields, delimiter=delim):
                    stats["zeilen"] += 1
                    mid = col(row, "merchant_id")
                    a = adv.get(mid)
                    if not a:
                        stats["inaktiv"] += 1
                        continue
                    name, url, img = col(row, "name"), col(row, "url"), col(row, "image")
                    name = name.replace("&amp;", "&")
                    if DUMP:
                        DUMP_ROWS.append([a.get("shop", ""), name[:120], col(row, "mcat")[:80], col(row, "cat")[:80],
                                          col(row, "brand")[:40], col(row, "desc")[:160], col(row, "stock")[:12], 1 if img else 0])
                    if not name or not url:
                        continue
                    if "advent" in name.lower():  # Diagnose: wie viele Adventskalender liefern die Feeds wirklich?
                        sh = a.get("shop", "")
                        ADV_RAW[sh] = ADV_RAW.get(sh, 0) + 1
                        if col(row, "stock").lower() in NO:
                            ADV_NO[sh] = ADV_NO.get(sh, 0) + 1
                    if SPERR and any(x in name.lower() or x in url.lower() for x in SPERR):
                        stats["gesperrt"] = stats.get("gesperrt", 0) + 1
                        continue
                    if col(row, "stock").lower() in NO:
                        stats["lager"] += 1
                        continue
                    mcat, cat = col(row, "mcat"), col(row, "cat")
                    brand = brand_of(name, col(row, "brand"), a.get("shop", ""))
                    binfo = BRANDS.get(brand, {})
                    hay = f"{name} {mcat} {cat}"
                    if binfo.get("alkohol") or ALKOHOL.search(hay) or re.search(r"alkoholische getränke|\bwein\b|spirituos|\bbier\b", f"{mcat} {cat}", re.I):
                        stats["alkohol"] += 1
                        continue
                    if binfo.get("tier") or TIER.search(hay) or re.search(r"tierbedarf|tiernahrung", mcat, re.I):
                        stats["tier"] += 1
                        continue
                    if NONFOOD.search(name) or re.search(r"heim & garten|küche & esszimmer|drogerie|baby & klein|haushalt", f"{mcat} {cat}", re.I):
                        stats["nonfood"] += 1
                        continue
                    if HART.search(name) or (WEICH.search(name) and not NASCH.search(name)):
                        stats["thema"] += 1
                        continue
                    ok = (inc[mid] is None or inc[mid].search(f"{mcat} || {cat}")) or (inc_name[mid] and inc_name[mid].search(name))
                    if not ok or (exc_name[mid] and exc_name[mid].search(name)):
                        stats["thema"] += 1
                        continue
                    if not img or not any(r.match(img) for r in REMOTE_OK):
                        stats["ohne_bild"] += 1
                        continue
                    key = norm(f"{name} {brand}")
                    if key in seen or norm(name) in seen or url in seen:
                        stats["doppelt"] += 1
                        continue
                    seen.update({key, url, norm(name)})
                    # Feed-Kategorie ohne Oberbegriffe wie "Nahrungsmittel, Getränke & Tabak" (sonst wird alles zum Getränk)
                    fc = " ".join(_cat_tail(x) for x in (mcat, cat) if x)
                    p = {"name": name[:120], "url": url, "image": img, "shop": a.get("shop") or col(row, "merchant_name"),
                         "brand": brand, "feed_category": fc[:160], "source": "awin", "advertiser": int(mid)}
                    vm = re.search(r"variant(?:%3D|=)(\d{6,})", url) or re.search(r"variant=(\d{6,})", row.get("link") or "")
                    if vm:
                        p["vid"] = vm.group(1)  # Shopify-Variante: erlaubt einen Sammel-Warenkorb beim Shop
                    pr = parse_price(col(row, "sale")) or parse_price(col(row, "price"))
                    if pr:
                        p["price"] = round(pr, 2)
                    w = welt_of(name, brand, f"{mcat} {cat}")
                    if w:
                        p["land"] = w
                    if a.get("themen"):
                        p["themen"] = a["themen"]
                    # Punkte für die Reihenfolge: Exoten, klassisches Naschen und Partner-Bonus nach vorn
                    p["score"] = (a.get("boost", 0) + WELT_BONUS.get(w, 0)
                                  + (3 if ART_KERN.search(hay) else 0) + (1 if binfo else 0))
                    result.append(p)
        except Exception as ex:
            log(f"Feed {label}: konnte nicht gelesen werden ({type(ex).__name__}). Weiter ohne diesen Feed.")
        finally:
            if is_url and path:
                os.unlink(path)
        per_src[label] = stats["zeilen"] - n0

    if IMG_LOCAL and result:
        result = fetch_images(result)
    if DUMP and DUMP_ROWS:
        d = HERE / "static" / "_dump"
        d.mkdir(exist_ok=True)
        with gzip.open(d / "rows.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(DUMP_ROWS, fh, ensure_ascii=False)
        log(f"Vorschau-Dump: {len(DUMP_ROWS)} Zeilen")
    OUT.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "products": result}, ensure_ascii=False), encoding="utf-8")
    shops, welten = {}, {}
    for p in result:
        shops[p["shop"]] = shops.get(p["shop"], 0) + 1
        welten[p.get("land", "-")] = welten.get(p.get("land", "-"), 0) + 1
    log("Zeilen je Feed: " + ", ".join(f"{k} {v}" for k, v in per_src.items()))
    log(f"{len(result)} Produkte übernommen: " + ", ".join(f"{k} {v}" for k, v in sorted(shops.items())))
    log("Welten: " + ", ".join(f"{k} {v}" for k, v in sorted(welten.items(), key=lambda x: -x[1])))
    leer = [a.get("name", k) for k, a in adv.items() if not any(str(p.get("advertiser")) == k or p.get("shop") == a.get("name") for p in result)]
    if leer:
        log("WARNUNG: keine Produkte von " + ", ".join(leer) + " (Feed down oder Programm pausiert?)")
    # Schutz: Liefert AWIN kaum etwas (Ausfall, Schlüssel ungültig), bricht der Build ab.
    # Cloudflare lässt dann einfach die letzte gute Version online, statt einen leeren Shop zu zeigen.
    mindest = int(os.environ.get("FEED_MIN", "1500"))
    if (os.environ.get("WORKERS_CI") or os.environ.get("CF_PAGES")) and len(result) < mindest:
        log(f"ABBRUCH: nur {len(result)} Produkte (Minimum {mindest}). Alte Seite bleibt online.")
        sys.exit(1)
    adv_ok = {}
    for p in result:
        if "advent" in p["name"].lower():
            adv_ok[p["shop"]] = adv_ok.get(p["shop"], 0) + 1
    log("Advent (roh / nicht vorrätig / übernommen): " + ", ".join(
        f"{k} {v}/{ADV_NO.get(k, 0)}/{adv_ok.get(k, 0)}" for k, v in sorted(ADV_RAW.items())) if ADV_RAW else "Advent: keine Zeilen in den Feeds")
    log("Aussortiert: " + ", ".join(f"{k} {v}" for k, v in stats.items()))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        log(f"Unerwarteter Fehler ({type(ex).__name__}). Build läuft ohne Feed weiter.")
        OUT.unlink(missing_ok=True)
    sys.exit(0)
