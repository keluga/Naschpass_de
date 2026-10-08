"""Baut die Naschpass-Website nach website/dist/ (statisch, keine Cookies, kein Tracking).
Start: python website/build.py
Quellen: website/site.json, website/products.json, generator/posts.json, fertige_posts/

Regeln, an denen der Datenschutz hängt:
- Keine externen Skripte, Schriften oder Bilder. Alles kommt von der eigenen Domain.
- Produktbilder aus dem Partner-Feed laufen auf Netlify über das Netlify Image CDN (/.netlify/images).
  Netlify holt das Bild serverseitig, der Browser der Besucher verbindet sich nie mit dem Shop.
  Der Bild-Server des Shops muss dafür in netlify.toml unter [images] remote_images stehen.
- Keine Cookies, kein localStorage.
Optional: PRODUCTS_FILE=<pfad> nutzt eine andere Produktdatei (z. B. für eine Vorschau mit Beispieldaten).
"""
import html
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / "dist"

site = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
DEMO = os.environ.get("DEMO") == "1"  # nur Netlify-Vorschau: Beispielprodukte aus website/demo/
_pf = Path(os.environ.get("PRODUCTS_FILE") or (HERE / "demo" / "products.json" if DEMO else HERE / "products.json"))
products = json.loads(_pf.read_text(encoding="utf-8"))["products"]
# Produkte aus den AWIN-Feeds (von import_feeds.py im Build erzeugt, nicht im Repo). Handeinträge haben Vorrang.
_ff = HERE / "feed_products.json"
if _ff.exists() and not os.environ.get("PRODUCTS_FILE"):
    _have = {re.sub(r"[^a-z0-9]+", " ", p.get("name", "").lower()).strip() for p in products}
    products = products + [p for p in json.loads(_ff.read_text(encoding="utf-8")).get("products", [])
                           if re.sub(r"[^a-z0-9]+", " ", p.get("name", "").lower()).strip() not in _have]
if DEMO and not os.environ.get("PRODUCTS_FILE"):  # Vorschau: echte Produkte zuerst, dann Beispiele
    products = json.loads((HERE / "products.json").read_text(encoding="utf-8"))["products"] + products

# ---------- Affiliate-Wächter ----------
# Jeder Produkt-Link MUSS über AWIN mit Kevs Publisher-ID laufen, sonst gibt es keine Provision.
# Links ohne die ID fliegen raus (Build-Log zeigt sie). Formate: cread.php?...awinaffid=ID  oder  pclick.php?...a=ID
AWIN_ID = str(site.get("awin_publisher_id", "3111189"))


def affiliate_ok(url):
    from urllib.parse import urlparse, parse_qs
    try:
        u = urlparse(url)
    except ValueError:
        return False
    if u.scheme != "https" or not (u.hostname or "").endswith("awin1.com"):
        return False
    q = parse_qs(u.query)
    return AWIN_ID in q.get("awinaffid", []) + q.get("a", [])


if not DEMO:
    for _p in products:  # AWIN-Feeds liefern manchmal http:// -> sicher auf https umstellen
        if _p.get("url", "").startswith("http://www.awin1.com/"):
            _p["url"] = "https://" + _p["url"][7:]
    _bad = [p for p in products if not affiliate_ok(p.get("url", ""))]
    products = [p for p in products if affiliate_ok(p.get("url", ""))]
    print(f"[Affiliate-Check] {len(products)} Produkte mit Publisher-ID {AWIN_ID}"
          + (f", {len(_bad)} aussortiert: " + "; ".join(p.get("name", "?")[:40] for p in _bad[:10]) if _bad else ", alles ok"))

posts = json.loads((ROOT / "generator" / "posts.json").read_text(encoding="utf-8"))["posts"]

BASE = f"https://{site['domain']}"
ON_NETLIFY = os.environ.get("NETLIFY") == "true"
FUSE = "/static/vendor/fuse-7.5.0.basic.min.mjs"

# Erlaubte Bild-Server für Partner-Bilder (aus netlify.toml gelesen)
_toml = (ROOT / "netlify.toml").read_text(encoding="utf-8")
_m = re.search(r"remote_images\s*=\s*\[(.*?)\]", _toml, re.S)
REMOTE_OK = [re.compile(x) for x in re.findall(r"'([^']+)'", _m.group(1))] if _m else []
WARN = []

e = html.escape


def plain(text):
    return e(text.replace("*", ""))


def accent(text):
    return re.sub(r"\*([^*]+)\*", r'<span class="acc">\1</span>', e(text))


def post_folder(p):
    s = p["short"].lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return f"{p['id']}_{re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:40]}"


def translit(s):
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return s


def cdn(src, w):
    return f"/.netlify/images?url={quote(src, safe='/')}&w={w}&q=78" if src.startswith("/") else \
        f"/.netlify/images?url={quote(src, safe='')}&w={w}&q=80"


def slide_img(src, alt, w, sizes, cls="", eager=False):
    """Eigene Folienbilder. Auf Netlify verkleinert (spart Ladezeit und Netlify-Credits), sonst Original."""
    lazy = "" if eager else ' loading="lazy" decoding="async"'
    c = f' class="{cls}"' if cls else ""
    if not ON_NETLIFY:
        return f'<img src="{src}" alt="{e(alt)}" width="1080" height="1350"{c}{lazy}>'
    srcset = ", ".join(f"{cdn(src, x)} {x}w" for x in (w, w * 2))
    # Fällt das CDN aus, wird das Original geladen (gleiche Domain, also unbedenklich)
    return (f'<img src="{cdn(src, w * 2)}" srcset="{srcset}" sizes="{sizes}" alt="{e(alt)}" width="1080" height="1350"'
            f'{c}{lazy} onerror="this.onerror=null;this.removeAttribute(\'srcset\');this.src=\'{src}\'">')


PARTNERS = site.get("partner_shops", {})  # Bild-Server -> Betreiber (steht in der Datenschutzerklärung)
EXT_USED = set()


def fotos_html():
    if not PARTNERS:
        return ""
    lst = "".join(f"<li>{e(h)}: {e(v)}</li>" for h, v in sorted(PARTNERS.items()))
    return ('<h2 id="fotos">4b. Produktfotos direkt von Shops</h2><p>Für manche Produkte zeigen wir Fotos, die direkt vom Server des '
            'jeweiligen Shops geladen werden. Das passiert nur, wenn du auf „Fotos anzeigen“ tippst. Dabei werden deine IP-Adresse und '
            'technische Angaben deines Browsers (z. B. Browsertyp, angefragte Bilddatei) an den Shop übertragen. Was der Shop damit macht, '
            f'regelt dessen eigene Datenschutzerklärung. Betroffene Shops:</p><ul>{lst}</ul>'
            '<p>Rechtsgrundlage ist deine Einwilligung (Art. 6 Abs. 1 lit. a DSGVO, § 25 Abs. 1 TDDDG). Deine Entscheidung speichern wir '
            'nur im lokalen Speicher deines Browsers (kein Cookie, wird nicht an uns übertragen), damit wir nicht bei jedem Besuch neu fragen '
            'müssen (§ 25 Abs. 2 Nr. 2 TDDDG). Du kannst die Einwilligung jederzeit über „Foto-Einstellung“ unten auf den Seiten mit '
            'Produktfotos widerrufen. Ohne Einwilligung siehst du statt der Fotos Platzhalter.</p>')


# ---------- Filter: Woher / Geschmack / Art ----------
FILTER = site.get("filter", [])
_parents = {}  # (gruppe, kind) -> [eltern]
for _g in FILTER:
    for _o in _g["options"]:
        for _c in _o.get("includes", []):
            _parents.setdefault((_g["id"], _c), []).append(_o["id"])


def _kw_re(k):
    k = re.escape(translit(k))
    # kurze Wörter nur als ganzes Wort (sonst steckt "uk" in "zucker"), längere am Wortanfang
    return re.compile(rf"(?<![a-z0-9]){k}(?![a-z0-9])" if len(k) <= 3 else rf"(?<![a-z0-9]){k}")


_KW = {(g["id"], o["id"]): [_kw_re(k) for k in o.get("keywords", [])] for g in FILTER for o in g["options"]}


def facets(p):
    """Ordnet ein Produkt automatisch zu (oder per Hand über p['land'|'geschmack'|'art'])."""
    text = translit(" ".join([p.get("name", ""), p.get("note", ""), p.get("feed_category", ""), p.get("brand", "")]
                             + p.get("tags", [])))
    out = {}
    for g in FILTER:
        gid = g["id"]
        if p.get(gid):
            ids = set([p[gid]] if isinstance(p[gid], str) else p[gid])
        else:
            ids = {o["id"] for o in g["options"]
                   if p.get("category") in o.get("categories", []) or any(r.search(text) for r in _KW[(gid, o["id"])])}
        for i in list(ids):
            ids.update(_parents.get((gid, i), []))
        out[gid] = ids
    return out


def facet_attrs(p):
    return "".join(f' data-{g}="{" ".join(sorted(v))}"' for g, v in facets(p).items())


def facet_icon(gid, o, size=24):
    return sticker(o["id"], size) if o.get("icon") == "flag" else f'<span class="emo" aria-hidden="true">{o.get("icon", "")}</span>'


def facet_counts():
    c = {}
    for p in products:
        for g, v in facets(p).items():
            for i in v:
                c[(g, i)] = c.get((g, i), 0) + 1
    return c


import datetime as _dt
TODAY = _dt.date.today()


def in_season(c):
    se = c.get("season")
    if not se:
        return False
    md = TODAY.strftime("%m-%d")
    return se[0] <= md <= se[1] if se[0] <= se[1] else (md >= se[0] or md <= se[1])


_CAT_KW = {}


def in_cat(p, c):
    """Gehört ein Produkt zu einer Themenwelt? (Hand-Kategorie, themen, Facetten oder Stichwörter)"""
    if p.get("category") == c["id"] or c["id"] in p.get("themen", []):
        return True
    if c.get("facets"):
        f = facets(p)
        if any(x.split(":")[1] in f.get(x.split(":")[0], set()) for x in c["facets"]):
            return True
    if c.get("keywords"):
        if c["id"] not in _CAT_KW:
            _CAT_KW[c["id"]] = [_kw_re(k) for k in c["keywords"]]
        text = translit(" ".join([p.get("name", ""), p.get("note", ""), p.get("feed_category", "")]))
        return any(r.search(text) for r in _CAT_KW[c["id"]])
    return False


def cat_items(c):
    return [p for p in products if in_cat(p, c)]


def cats_sorted():
    """Reihenfolge aus site.json; saisonale Themenwelt in ihrer Saison ganz vorn."""
    return sorted(cats, key=lambda c: 0 if in_season(c) else 1)


def host_of(url):
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()


def prod_img(p, w):
    """(art, url) für ein Produktbild.
    art = "own": über die eigene Domain (lokal oder Netlify Image CDN, ohne Einwilligung)
    art = "ext": direkt vom Shop-Server, wird erst nach Einwilligung des Besuchers geladen
    None = kein Bild."""
    src = p.get("image") or ""
    if not src:
        return None
    if src.startswith("/"):
        return ("own", cdn(src, w) if ON_NETLIFY else src)
    if ON_NETLIFY and any(r.match(src) for r in REMOTE_OK):
        return ("own", cdn(src, w))
    h = host_of(src)
    if h not in PARTNERS:
        WARN.append(f"Bild-Server {h} fehlt in site.json -> partner_shops (Datenschutz!), Bild ausgelassen")
        return None
    EXT_USED.add(h)
    return ("ext", src)


def prod_src(p, w):
    """Nur Bilder, die ohne Einwilligung geladen werden dürfen (eigene Domain)."""
    i = prod_img(p, w)
    return i[1] if i and i[0] == "own" else None


def pic_html(p, w, alt, cid):
    """Bild-Markup: eigenes Bild direkt, Shop-Bild als Platzhalter bis zur Einwilligung."""
    i = prod_img(p, w)
    if not i:
        return sticker(cid)
    kind, src = i
    if kind == "own":
        raw = p.get("image") or ""
        fb = f"this.src=\'{e(raw)}\'" if raw.startswith("/") else "this.replaceWith(document.createTextNode(\'\'))"
        return (f'<img src="{e(src)}" alt="{e(alt)}" loading="lazy" decoding="async" '
                f'onerror="this.onerror=null;{fb}">')
    return (f'<span class="xi">{sticker(cid)}<img data-ext="{e(src)}" alt="{e(alt)}" decoding="async" hidden></span>')


# ---------- Farben, Sticker ----------
CAT_COLORS = ["#8B6CFF", "#FF8FB1", "#FFB547", "#9EE3C6", "#9FD3FF", "#FFD966"]
POST_COLORS = ["#FF8FB1", "#8B6CFF", "#FFB547", "#5FCFA0", "#7DBEFF"]
cats = site["categories"]
cat_by_id = {c["id"]: c for c in cats}
cat_color = {c["id"]: CAT_COLORS[i % len(CAT_COLORS)] for i, c in enumerate(cats)}

_tags = []
for _p in posts:
    if _p.get("tag") and _p["tag"] not in _tags:
        _tags.append(_p["tag"])


def tag_color(tag):
    return POST_COLORS[_tags.index(tag) % len(POST_COLORS)] if tag in _tags else "#CFE7DD"


def tag_slug(tag):
    return re.sub(r"[^a-z0-9]+", "-", translit(tag)).strip("-")


# Kleine, selbst gezeichnete Sticker pro Kategorie (keine fremden Bilder)
STICKERS = {
    "japan": '<rect x="1" y="1" width="62" height="62" rx="13" fill="#fff" stroke="#D9D4EA" stroke-width="2"/><circle cx="32" cy="32" r="14" fill="#E8384F"/>',
    "usa": '<clipPath id="cu"><rect width="64" height="64" rx="14"/></clipPath><g clip-path="url(#cu)"><rect width="64" height="64" fill="#fff"/>'
           + "".join(f'<rect y="{y}" width="64" height="5" fill="#E8384F"/>' for y in range(0, 64, 10))
           + '<rect width="30" height="30" fill="#2E4FB8"/><circle cx="9" cy="9" r="2.4" fill="#fff"/><circle cx="21" cy="9" r="2.4" fill="#fff"/>'
             '<circle cx="15" cy="16" r="2.4" fill="#fff"/><circle cx="9" cy="23" r="2.4" fill="#fff"/><circle cx="21" cy="23" r="2.4" fill="#fff"/></g>',
    "verboten": '<rect width="64" height="64" rx="14" fill="#2E4FB8"/>' + "".join(
        f'<circle cx="{32 + 17 * __import__("math").cos(i * 0.5236):.1f}" cy="{32 + 17 * __import__("math").sin(i * 0.5236):.1f}" r="3" fill="#FFD23F"/>'
        for i in range(12)),
    "mexiko": '<clipPath id="cm"><rect width="64" height="64" rx="14"/></clipPath><g clip-path="url(#cm)"><rect width="22" height="64" fill="#1F8A4C"/>'
              '<rect x="21" width="22" height="64" fill="#fff"/><rect x="42" width="22" height="64" fill="#D8263A"/><circle cx="32" cy="32" r="6" fill="#B07A2A"/></g>',
    "korea": '<rect x="1" y="1" width="62" height="62" rx="13" fill="#fff" stroke="#D9D4EA" stroke-width="2"/><path d="M20 32a12 12 0 0 1 24 0z" fill="#D8263A"/>'
             '<path d="M20 32a12 12 0 0 0 24 0z" fill="#2E4FB8"/>',
    "asien": '<rect width="64" height="64" rx="14" fill="#E8384F"/><circle cx="32" cy="32" r="13" fill="#FFD23F"/><circle cx="32" cy="32" r="6" fill="#E8384F"/>',
    "uk": '<clipPath id="ck"><rect width="64" height="64" rx="14"/></clipPath><g clip-path="url(#ck)"><rect width="64" height="64" fill="#2E4FB8"/>'
          '<path d="M0 0L64 64M64 0L0 64" stroke="#fff" stroke-width="12"/><path d="M0 0L64 64M64 0L0 64" stroke="#D8263A" stroke-width="4"/>'
          '<rect x="25" width="14" height="64" fill="#fff"/><rect y="25" width="64" height="14" fill="#fff"/><rect x="28" width="8" height="64" fill="#D8263A"/>'
          '<rect y="28" width="64" height="8" fill="#D8263A"/></g>',
    "deutschland": '<clipPath id="cd"><rect width="64" height="64" rx="14"/></clipPath><g clip-path="url(#cd)"><rect width="64" height="22" fill="#222"/>'
                   '<rect y="21" width="64" height="22" fill="#D8263A"/><rect y="42" width="64" height="22" fill="#FFCE00"/></g>',
    "sauer-scharf": '<rect width="64" height="64" rx="14" fill="#FFB547"/><path d="M20 22c6-2 14 2 20 10s8 16 4 18c-6 3-16-4-22-12s-8-14-2-16z" fill="#E8384F"/>'
                    '<path d="M21 23c-3-4-2-8 1-10" stroke="#2FAE7E" stroke-width="4" fill="none" stroke-linecap="round"/>',
    "skandinavien": '<rect width="64" height="64" rx="14" fill="#2D6FD2"/><rect x="18" width="10" height="64" fill="#FFD23F"/><rect y="27" width="64" height="10" fill="#FFD23F"/>',
    "boxen": '<rect width="64" height="64" rx="14" fill="#FF8FB1"/><rect x="14" y="26" width="36" height="26" rx="3" fill="#fff"/><rect x="11" y="19" width="42" height="10" rx="3" fill="#fff"/>'
             '<rect x="29" y="19" width="6" height="33" fill="#8B6CFF"/><path d="M32 19c-4-8-14-8-12-2 1 3 8 3 12 2zm0 0c4-8 14-8 12-2-1 3-8 3-12 2z" fill="#8B6CFF"/>',
}


STICKERS["europa"] = STICKERS["verboten"]
STICKERS["italien"] = ('<clipPath id="ci"><rect width="64" height="64" rx="14"/></clipPath><g clip-path="url(#ci)"><rect width="22" height="64" fill="#1F8A4C"/>'
                       '<rect x="21" width="22" height="64" fill="#fff"/><rect x="42" width="22" height="64" fill="#D8263A"/></g>')
STICKERS["schweiz"] = ('<rect width="64" height="64" rx="14" fill="#D8263A"/><rect x="27" y="14" width="10" height="36" fill="#fff"/>'
                       '<rect x="14" y="27" width="36" height="10" fill="#fff"/>')
for _k, (_bg, _em) in {"halloween": ("#FF8A3D", "🎃"), "weihnachten": ("#2FAE7E", "🎄"), "adventskalender": ("#E8505B", "📅"), "schokolade": ("#B07A55", "🍫"), "getraenke": ("#9FD3FF", "🥤"), "snacks": ("#FFD966", "🥜"),
                       "klassiker": ("#FF8FB1", "🛒")}.items():
    STICKERS[_k] = (f'<rect width="64" height="64" rx="14" fill="{_bg}"/>'
                    f'<text x="32" y="44" font-size="34" text-anchor="middle">{_em}</text>')


def sticker(cid, size=56):
    inner = STICKERS.get(cid) or (f'<rect width="64" height="64" rx="14" fill="{cat_color.get(cid, "#8B6CFF")}"/>'
                                  '<rect x="14" y="20" width="22" height="7" rx="3.5" fill="#fff" transform="rotate(-20 25 23)"/>'
                                  '<rect x="30" y="36" width="22" height="7" rx="3.5" fill="#2B2350" transform="rotate(25 41 39)"/>')
    return f'<svg class="stk" width="{size}" height="{size}" viewBox="0 0 64 64" aria-hidden="true">{inner}</svg>'


ICON_SEARCH = ('<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" '
               'stroke="currentColor" stroke-width="2.4"/><path d="M15.5 15.5 21 21" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>')
ICONS_VIEW = {
    "big": '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="2" width="14" height="14" rx="3" fill="currentColor"/></svg>',
    "small": '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><rect x="1" y="1" width="7" height="7" rx="2" fill="currentColor"/>'
             '<rect x="10" y="1" width="7" height="7" rx="2" fill="currentColor"/><rect x="1" y="10" width="7" height="7" rx="2" fill="currentColor"/>'
             '<rect x="10" y="10" width="7" height="7" rx="2" fill="currentColor"/></svg>',
    "list": '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><rect x="1" y="2" width="5" height="5" rx="1.5" fill="currentColor"/>'
            '<rect x="8" y="3" width="9" height="3" rx="1.5" fill="currentColor"/><rect x="1" y="11" width="5" height="5" rx="1.5" fill="currentColor"/>'
            '<rect x="8" y="12" width="9" height="3" rx="1.5" fill="currentColor"/></svg>',
}
VIEW_LABEL = {"big": "Große Kacheln", "small": "Kleine Kacheln", "list": "Liste"}


def view_toggle(target, views, default):
    btns = "".join(f'<button type="button" data-view="{v}" data-target="{target}" aria-pressed="{str(v == default).lower()}" '
                   f'title="{VIEW_LABEL[v]}" aria-label="{VIEW_LABEL[v]}">{ICONS_VIEW[v]}</button>' for v in views)
    return f'<div class="views" role="group" aria-label="Ansicht">{btns}</div>'


CSS = """
@font-face{font-family:Anton;src:url(/static/fonts/anton-latin.woff2) format("woff2");font-display:swap}
@font-face{font-family:Inter;src:url(/static/fonts/inter-latin.woff2) format("woff2");font-weight:100 900;font-display:swap}
:root{--bg:#EAF6F1;--bg2:#DDF0E8;--card:#fff;--fg:#2B2350;--mut:#5F5A85;--line:#CFE7DD;
--vio:#6248E8;--vio2:#8B6CFF;--pink:#FF8FB1;--ora:#FFB547;--mint:#9EE3C6;--r:20px;--sh:0 1px 0 #CFE7DD,0 6px 18px rgba(43,35,80,.07)}
*{box-sizing:border-box}html{scroll-behavior:smooth;-webkit-text-size-adjust:100%;scroll-padding-top:70px}
body{margin:0;background:var(--bg);color:var(--fg);font:16.5px/1.55 Inter,system-ui,sans-serif;overflow-x:hidden}
a{color:var(--vio)}img{max-width:100%;height:auto;display:block}button{font:inherit;color:inherit}
:focus-visible{outline:3px solid var(--vio);outline-offset:3px;border-radius:8px}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
h1,h2{font-family:Anton,Impact,sans-serif;font-weight:400;text-transform:uppercase;line-height:1.02;margin:0 0 .35em;letter-spacing:.3px}
h1{font-size:clamp(38px,9.5vw,76px)}h2{font-size:clamp(28px,6vw,42px)}
h3{font-size:17px;line-height:1.25;margin:0}
.acc{color:var(--vio)}
.sub{color:var(--mut);max-width:60ch;margin:0 0 1em}
.lead{font-size:18px;line-height:1.6;max-width:62ch;margin:6px 0 18px}
.how{list-style:none;padding:0;margin:-6px 0 16px;display:flex;flex-wrap:wrap;gap:6px 14px;font-size:14px;font-weight:700;color:var(--mut)}
.how a{display:flex;gap:5px;align-items:center;color:var(--mut);text-decoration:none;border-bottom:2px dotted var(--line)}
.how a:hover{color:var(--vio);border-color:var(--vio2)}
.how .advpill{color:#1F8A62;border-bottom-color:#9EE3C6}.how .advpill.hw{color:#D35A00;border-bottom-color:#FFC58F}.how em{font-style:normal}.how span{font-size:16px}
.hgrid .hr{margin-top:22px}
.hero.hgrid{position:relative;z-index:6}
.ddp{max-height:min(62vh,460px);overflow-y:auto;overscroll-behavior:contain}
@media(min-width:980px){.hgrid{display:grid;grid-template-columns:1fr 470px;gap:34px;align-items:start}.hgrid .hr{margin-top:6px}
.hgrid .spin{padding:0}.hgrid .card{width:92px;height:140px}.hgrid .card img{height:70px}.hgrid .card .svgw{height:70px}.hgrid .card .svgw svg{width:54px;height:54px}
.hgrid .card b{font-size:11px}.hgrid .reel{height:164px}}
.hgrid .spin{padding-top:0}
.cats.clip>[data-more],.bgrid.clip>[data-more]{display:none}
.bgrid:not(.clip)>.bmore{display:none}
.chip.off{opacity:.45;cursor:default}
.mrow{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
@media(min-width:980px){.hgrid .mrow{grid-template-columns:repeat(3,1fr)}.hgrid .minis .head{margin-top:0!important}}
.mini{display:flex;flex-direction:column;gap:6px;background:#fff;border-radius:14px;padding:8px;text-decoration:none;color:var(--fg);box-shadow:var(--sh)}
.mini .mp{aspect-ratio:1;border-radius:10px;background:var(--bg2);display:grid;place-items:center;overflow:hidden}
.mini .mp img{width:100%;height:100%;object-fit:cover}.mini .mp .stk{width:60%;height:auto}
.mini b{font-size:12.5px;line-height:1.25;max-height:2.5em;overflow:hidden}
.mini.slot,.prod.pslot{background:transparent;border:2px dashed var(--vio2);box-shadow:none}
.mini.slot .mp,.prod.pslot .pi{background:rgba(139,108,255,.08)}
.mini.slot b{color:var(--vio)}.prod.pslot h3{color:var(--vio)}
.prod.pslot .cta span{background:transparent;color:var(--vio);border:2px solid var(--vio2)}
.mini.slot:hover,.prod.pslot:hover{border-style:solid}
@media(max-width:520px){.mrow{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:4px}.mrow .mini{flex:0 0 86px;scroll-snap-align:start}}.ddp a.chip{text-decoration:none}
.bc.off{opacity:.45;box-shadow:none;background:rgba(255,255,255,.6);cursor:default}.bc.off:hover{outline:0}
.bmore{border:2px dashed var(--line);background:transparent;box-shadow:none;cursor:pointer;font:inherit;color:var(--fg);font-weight:800}
.bmore .emo{background:#fff}
.slots{display:grid;gap:12px;grid-template-columns:1fr}
@media(min-width:760px){.slots{grid-template-columns:2fr 1fr 1fr}}
.slot{border:2px dashed var(--line);border-radius:18px;min-height:150px}
.slot.main{display:flex;gap:14px;align-items:flex-start;padding:18px;background:rgba(255,255,255,.7)}
.slot.main p{margin:4px 0 8px;color:var(--mut)}
.slot.ghost{background:repeating-linear-gradient(135deg,transparent 0 12px,rgba(207,231,221,.5) 12px 24px)}
@media(max-width:759px){.slot.ghost{display:none}}
.aboutbox{background:#fff;border-radius:var(--r);padding:20px;box-shadow:var(--sh);position:relative;overflow:hidden}
.aboutbox:after{content:"";position:absolute;right:-40px;top:-40px;width:140px;height:140px;border-radius:50%;background:var(--mint);opacity:.5}
.aboutbox p{color:var(--mut);max-width:60ch;position:relative;z-index:1}.aboutbox .btn{border:2px solid var(--fg)}
.prose{max-width:68ch}.prose h2{font-size:clamp(24px,5vw,32px);margin-top:1.4em}.prose li{margin:6px 0}

/* Werbehinweis + Kopf */
.ad{background:var(--fg);color:#EAF6F1;font-size:12.5px;line-height:1.35;text-align:center;padding:6px 12px}
header{position:sticky;top:0;z-index:30;background:rgba(234,246,241,.9);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
header .wrap{display:flex;align-items:center;gap:10px;height:60px}
.logo{display:flex;align-items:center;gap:9px;text-decoration:none;color:var(--fg);font:23px Anton,sans-serif;letter-spacing:.5px;margin-right:auto}
.logo img{width:38px;height:38px;border-radius:50%}
header nav{display:flex;gap:2px}
header nav a{color:var(--fg);text-decoration:none;font-weight:700;font-size:15px;padding:8px 11px;border-radius:999px}
header nav a:hover{background:#fff}
@media(max-width:420px){.hide-s{display:none}}
.sbtn{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;border:0;background:var(--fg);color:#fff;cursor:pointer}

/* Hero */
.hero{position:relative;padding:26px 0 6px;isolation:isolate}
.hero h1{max-width:13ch}
.fake{display:flex;align-items:center;gap:12px;width:100%;max-width:620px;background:#fff;border:2px solid var(--line);border-radius:18px;
padding:15px 16px;color:var(--mut);font-size:16.5px;cursor:text;text-align:left;box-shadow:var(--sh)}
.fake span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.fake svg{color:var(--vio);flex:none}.fake:hover{border-color:var(--vio2)}
.stickers{display:flex;gap:10px;overflow-x:auto;padding:16px 16px 6px;margin:0 -16px;scrollbar-width:none}
.stickers::-webkit-scrollbar{display:none}
.sc{flex:none;display:flex;align-items:center;gap:9px;background:#fff;border-radius:999px;padding:5px 15px 5px 5px;text-decoration:none;color:var(--fg);font-weight:700;font-size:15px;box-shadow:var(--sh)}
.sc .stk{width:34px;height:34px}
.sc:hover{outline:2px solid var(--vio2)}
.spr{position:absolute;inset:0;pointer-events:none;z-index:-1;overflow:hidden}
.browse{margin-top:20px;max-width:620px}
.browse h2{font:800 15px Inter,sans-serif;text-transform:none;letter-spacing:0;margin:0 0 10px;color:var(--mut)}
.browse{display:block}.bgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
@media(min-width:900px){.bgrid{grid-template-columns:repeat(6,1fr)}}
.bc{display:flex;flex-direction:column;align-items:center;gap:6px;background:#fff;border-radius:16px;padding:12px 6px 10px;text-decoration:none;color:var(--fg);
font-weight:700;font-size:13.5px;line-height:1.2;text-align:center;box-shadow:var(--sh)}
.bc .stk{width:40px;height:40px}.bc:hover{outline:2px solid var(--vio2)}
.bc small{font-size:11.5px;font-weight:600;color:var(--mut)}
.emo{font-size:30px;line-height:40px;width:40px;height:40px;display:grid;place-items:center;border-radius:12px;background:var(--bg2)}
.chip .emo{font-size:17px;width:24px;height:24px;line-height:24px;background:none}
.chip .stk{width:24px;height:24px}.chip small{color:var(--mut);font-weight:600}
.chip[aria-pressed=true] small{color:#CFC9E8}
.tabs{display:flex;gap:6px;margin:0 0 10px;background:#fff;border-radius:14px;padding:4px;box-shadow:var(--sh);width:max-content;max-width:100%}
.tabs button{border:0;background:none;font-weight:800;font-size:14.5px;padding:8px 14px;border-radius:10px;cursor:pointer;color:var(--mut)}
.tabs button[aria-selected=true]{background:var(--fg);color:#fff}
.themes{margin-top:20px}
.themes h2{font:800 15px Inter,sans-serif;text-transform:none;letter-spacing:0;margin:0 0 10px;color:var(--mut)}
.trow{display:flex;gap:10px;overflow-x:auto;padding:2px 16px 8px;margin:0 -16px;scrollbar-width:none}
.trow::-webkit-scrollbar{display:none}.trow .bc{flex:none;width:118px}
@media(min-width:760px){.trow{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));overflow:visible;margin:0;padding:2px 0 8px}.trow .bc{width:auto}}
.filters{margin-bottom:8px}
.fbtns{position:relative;display:flex;gap:8px;flex-wrap:wrap}
.ddb{display:inline-flex;align-items:center;gap:7px;border:0;background:#fff;box-shadow:var(--sh);border-radius:999px;padding:10px 15px;
font-weight:800;font-size:15px;cursor:pointer;color:var(--fg)}
.ddb .car{font-size:12px;transition:transform .15s}
.dd.open .ddb{background:var(--fg);color:#fff}.dd.open .car{transform:rotate(180deg)}
.badge{background:var(--vio);color:#fff;border-radius:999px;font-size:12px;min-width:20px;height:20px;display:inline-grid;place-items:center;padding:0 6px}
.ddp{display:none;position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:25;background:#fff;border-radius:18px;padding:12px;
box-shadow:0 14px 40px rgba(43,35,80,.2)}
.ddp .chips{flex-wrap:wrap;overflow:visible}.ddp .chip{box-shadow:none;background:var(--bg)}
.ddp .chip[aria-pressed=true]{background:var(--fg)}
.dd.open .ddp{display:block}
@media(hover:hover) and (pointer:fine){.dd{position:relative}.ddp{right:auto;width:440px;top:100%;margin-top:0}
.dd:hover .ddp{display:block}.dd:hover .ddb{background:var(--fg);color:#fff}
.ddp:before{content:"";position:absolute;left:0;right:0;top:-8px;height:8px}}
.active{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.active:empty{display:none}
.active button{border:0;background:var(--vio);color:#fff;font-weight:700;font-size:13.5px;border-radius:999px;padding:6px 12px;cursor:pointer}
.fbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:4px 0 12px}
.fbar b{font-size:15px}
.sres .hint{background:#fff;border-radius:14px;padding:12px;margin:12px 0 4px;font-size:14.5px}
.sres .hint b{display:block;margin-bottom:6px}.sres .hint .chips{flex-wrap:wrap}
.fan{display:none}@media(min-width:900px){.hero.has-fan{padding-right:400px;min-height:470px}.fan{display:block;position:absolute;right:30px;top:30px;width:360px;height:420px}.fan a{position:absolute;top:0;width:230px;border-radius:16px;overflow:hidden;box-shadow:0 14px 34px rgba(43,35,80,.25);transition:transform .2s}.fan a:nth-child(1){left:0;transform:rotate(-9deg) translateY(30px)}.fan a:nth-child(2){left:120px;transform:rotate(7deg) translateY(40px)}.fan a:nth-child(3){left:60px;transform:rotate(-1deg);z-index:2}.fan a:hover{z-index:3}}
.spr i{position:absolute;width:30px;height:9px;border-radius:5px}

section{padding:34px 0 6px}
.head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.head h2{margin:0}
.more{font-weight:700;text-decoration:none;font-size:15px}

/* Empfehlungs-Band */
.recs{padding-top:26px}
.band{display:flex;gap:12px;overflow-x:auto;padding:4px 16px 14px;margin:0 -16px;scrollbar-width:none;cursor:grab}
.band::-webkit-scrollbar{display:none}
.ri{flex:none;width:168px;background:#fff;border-radius:18px;overflow:hidden;text-decoration:none;color:var(--fg);box-shadow:var(--sh)}
.ri .im{aspect-ratio:1;background:var(--bg2);display:grid;place-items:center;padding:10px}
.ri .im img{max-height:100%;object-fit:contain}
.ri.post .im{padding:0;aspect-ratio:4/5}.ri.post .im img{width:100%;height:100%;object-fit:cover}
.ri .tx{padding:9px 11px 11px;font-size:14px;line-height:1.3}
.ri .tx b{display:block;font-size:14.5px}
.ri .tx span{color:var(--mut);font-size:12.5px}

/* Kategorien */
.cats{display:grid;gap:12px;grid-template-columns:repeat(2,1fr)}
@media(min-width:760px){.cats{grid-template-columns:repeat(3,1fr)}}
.cat{position:relative;display:flex;flex-direction:column;gap:6px;background:#fff;border-radius:var(--r);padding:14px;text-decoration:none;color:var(--fg);box-shadow:var(--sh);overflow:hidden}
.cat:before{content:"";position:absolute;right:-30px;top:-30px;width:110px;height:110px;border-radius:50%;background:var(--c);opacity:.28}
.cat .stk{transform:rotate(-6deg);filter:drop-shadow(0 3px 0 rgba(43,35,80,.12))}
.cat h3{font:22px/1.05 Anton,sans-serif;text-transform:uppercase;margin-top:6px}
.cat p{margin:0;color:var(--mut);font-size:13.5px;line-height:1.4}
.cat .n{align-self:flex-start;margin-top:4px;font-size:12px;font-weight:800;border-radius:999px;padding:3px 9px;background:var(--fg);color:#fff}
.cat .n.soon{background:var(--bg2);color:var(--mut)}
.cat:hover{outline:2px solid var(--vio2)}

/* Filter-Chips + Ansicht */
.tools{display:flex;gap:10px;align-items:center;justify-content:space-between;margin:0 0 14px;flex-wrap:wrap}
.chips{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;padding:2px}
.chips::-webkit-scrollbar{display:none}
.chip{flex:none;display:inline-flex;align-items:center;gap:7px;border:0;background:#fff;color:var(--fg);font-weight:700;font-size:14px;padding:8px 13px;border-radius:999px;cursor:pointer;box-shadow:var(--sh)}
.chip i{width:9px;height:9px;border-radius:50%;background:var(--c)}
.chip[aria-pressed=true]{background:var(--fg);color:#fff}
.views{display:flex;background:#fff;border-radius:12px;padding:3px;box-shadow:var(--sh);flex:none}
.views button{border:0;background:none;color:var(--mut);width:36px;height:32px;border-radius:9px;display:grid;place-items:center;cursor:pointer}
.views button[aria-pressed=true]{background:var(--fg);color:#fff}

/* Produktkarten */
.grid{display:grid;gap:12px}
.prods.v-small{grid-template-columns:repeat(2,1fr)}
.prods.v-big{grid-template-columns:1fr}
.prods.v-list{grid-template-columns:1fr;gap:10px}
@media(min-width:620px){.prods.v-big{grid-template-columns:repeat(2,1fr)}.prods.v-small{grid-template-columns:repeat(3,1fr)}.prods.v-list{grid-template-columns:repeat(2,1fr)}}
@media(min-width:960px){.prods.v-big{grid-template-columns:repeat(3,1fr)}.prods.v-small{grid-template-columns:repeat(4,1fr)}}
.prod{display:flex;flex-direction:column;background:#fff;border-radius:18px;overflow:hidden;text-decoration:none;color:var(--fg);box-shadow:var(--sh)}
.prod .pi{position:relative;background:var(--bg2);aspect-ratio:1;display:grid;place-items:center;padding:12px}
.prod .pi img{max-height:100%;object-fit:contain}
.prod .pi .stk{width:44%;height:auto;opacity:.9}
.prod .pc{position:absolute;left:8px;top:8px;background:#fff;border-radius:999px;font-size:11.5px;font-weight:800;padding:3px 8px 3px 6px;display:flex;align-items:center;gap:5px}
.prod .pc i{width:8px;height:8px;border-radius:50%;background:var(--c)}
.prod .pb{padding:11px 12px 12px;display:flex;flex-direction:column;gap:3px;flex:1}
.prod .note{font-size:13.5px;color:var(--mut);margin:0;line-height:1.4}
.prod .shop{font-size:12.5px;color:var(--mut);font-weight:600}
.prod .cta{margin-top:auto;padding-top:9px}
.prod .cta span{display:block;text-align:center;background:var(--vio);color:#fff;font-weight:800;font-size:14.5px;border-radius:12px;padding:10px 8px}
.prod:hover .cta span{background:#4F35D6}
.v-small .prod .note{display:none}.prod .cta em{font-style:normal}.prod .cta .s,.v-small .prod .cta .l,.v-list .prod .cta .l{display:none}.v-small .prod .cta .s,.v-list .prod .cta .s{display:inline}
.v-big .prod h3{font-size:19px}
.v-list .prod{flex-direction:row;align-items:stretch}
.v-list .prod .pi{width:110px;flex:none;aspect-ratio:auto;padding:8px}
.v-list .prod .pc{display:none}
.v-list .prod .note{display:none}
.v-list .prod .cta span{display:inline-block;padding:7px 12px;font-size:13.5px}
.wl{font-size:13px;color:var(--mut);margin:10px 0 0}
.xi{display:contents}.xi.ok .stk{display:none}
.imgbar{position:fixed;left:10px;right:10px;bottom:10px;z-index:40;max-width:560px;margin:0 auto;background:var(--fg);color:#fff;border-radius:14px;
padding:8px 8px 8px 14px;box-shadow:0 10px 30px rgba(43,35,80,.3);font-size:13px;line-height:1.35;display:flex;align-items:center;gap:10px}
.imgbar[hidden]{display:none}
.imgbar p{margin:0;flex:1}.imgbar a{color:var(--mint)}
.imgbar .row{display:flex;gap:6px;flex:none}
.imgbar button{border:0;border-radius:10px;font-weight:800;font-size:14px;padding:8px 12px;cursor:pointer}
.imgbar .yes{background:var(--mint);color:var(--fg)}.imgbar .no{background:transparent;color:#fff;border:2px solid rgba(255,255,255,.4)}
.linkbtn{border:0;background:none;color:var(--mut);text-decoration:underline;cursor:pointer;font-size:14px;padding:0}
.clip>[data-more]{display:none}
.morebar{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.morebtn{border:2px solid var(--fg);background:none;color:var(--fg);font-weight:800;font-size:15px;border-radius:999px;padding:9px 16px;cursor:pointer}
.morebtn:hover{background:#fff}
.btn.dark{background:var(--fg);color:#fff}
.empty{background:#fff;border:2px dashed var(--line);border-radius:18px;padding:18px;color:var(--mut)}
.empty strong{color:var(--fg)}
[hidden]{display:none!important}

/* Post-Karten */
.posts.v-small{grid-template-columns:repeat(2,1fr)}
.posts.v-big{grid-template-columns:1fr}
@media(min-width:620px){.posts.v-small{grid-template-columns:repeat(3,1fr)}.posts.v-big{grid-template-columns:repeat(2,1fr)}}
@media(min-width:960px){.posts.v-small{grid-template-columns:repeat(4,1fr)}.posts.v-big{grid-template-columns:repeat(3,1fr)}}
.post{display:block;text-decoration:none;color:var(--fg)}
.post .cover{position:relative;border-radius:16px;overflow:hidden;background:var(--fg);aspect-ratio:4/5;box-shadow:var(--sh)}
.post .cover img{width:100%;height:100%;object-fit:cover;transition:transform .25s}
.post:hover .cover img{transform:scale(1.03)}
.post .no{position:absolute;left:8px;bottom:8px;background:#fff;color:var(--fg);font:18px/1 Anton,sans-serif;padding:6px 8px 5px;border-radius:9px}
.post .t{display:flex;align-items:center;gap:6px;margin:7px 2px 0;font-size:13px;font-weight:700;color:var(--mut)}
.post .t i{width:8px;height:8px;border-radius:50%;background:var(--c)}

/* Nummer aus dem Post */
.pass{position:relative;background:#fff;border-radius:24px;padding:20px 18px;box-shadow:var(--sh);overflow:hidden;max-width:640px}
.pass:after{content:"";position:absolute;right:-40px;bottom:-40px;width:150px;height:150px;border-radius:50%;background:var(--pink);opacity:.3}
.pass h2{font-size:clamp(24px,5.5vw,32px)}
.pass p{margin:0 0 14px;color:var(--mut);font-size:15px}
.pass .row{display:flex;gap:10px;position:relative;z-index:1}
.num{flex:1;display:flex;align-items:center;background:var(--bg);border:2px solid var(--line);border-radius:14px;padding:0 12px}
.num span{font:36px Anton,sans-serif;color:var(--vio)}
.num input{width:100%;border:0;background:none;font:36px Anton,sans-serif;color:var(--fg);padding:4px 6px;outline:none;min-width:0}
.num input::placeholder{color:#B9B4D3}
.num:focus-within{border-color:var(--vio)}
.pass button{border:0;border-radius:14px;background:var(--vio);color:#fff;font-weight:800;padding:0 18px;cursor:pointer}
.pass .msg{min-height:1.4em;margin:10px 0 0;font-size:14px;font-weight:600;color:var(--mut)}
.stamp{position:absolute;right:18px;top:14px;width:80px;height:80px;border:3px solid var(--vio);border-radius:50%;color:var(--vio);
display:grid;place-items:center;font:22px/1 Anton,sans-serif;transform:rotate(-14deg);opacity:0;pointer-events:none;z-index:2}
.stamp.go{animation:stamp .45s cubic-bezier(.2,1.6,.4,1) forwards}
@keyframes stamp{0%{opacity:0;transform:rotate(-14deg) scale(2.2)}100%{opacity:.95;transform:rotate(-14deg) scale(1)}}

/* Post-Seite */
.back{display:inline-block;margin:16px 0 0;color:var(--mut);font-weight:700;text-decoration:none;font-size:15px}
.meta{display:flex;align-items:center;gap:8px;margin:14px 0 10px;font-weight:800;font-size:14px}
.meta .pill{background:var(--fg);color:#fff;border-radius:8px;padding:5px 8px 3px;font:18px/1 Anton,sans-serif}
.meta .tg{display:inline-flex;align-items:center;gap:6px}.meta .tg i{width:9px;height:9px;border-radius:50%;background:var(--c)}
.gal{position:relative;margin:12px -16px 0}
.slides{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;padding:0 16px 10px;scrollbar-width:none}
.slides::-webkit-scrollbar{display:none}
.slides img{width:min(84vw,400px);border-radius:16px;scroll-snap-align:center;flex:none;aspect-ratio:4/5;object-fit:cover;background:var(--fg)}
.dots{display:flex;justify-content:center;gap:7px;margin-top:4px}
.dots b{width:8px;height:8px;border-radius:50%;background:var(--line);transition:width .2s,background .2s}
.dots b.on{background:var(--vio);width:22px;border-radius:4px}
.arrow{display:none}
@media(min-width:900px){.arrow{display:grid;place-items:center;position:absolute;top:calc(50% - 30px);width:46px;height:46px;border-radius:50%;
border:0;background:#fff;color:var(--fg);font-size:24px;cursor:pointer;z-index:2;box-shadow:var(--sh)}.arrow.l{left:6px}.arrow.r{right:6px}}
.src{padding-left:1.1em;color:var(--mut);font-size:15px}.src li{margin:4px 0}
.next{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.next a{background:#fff;border-radius:16px;padding:14px;text-decoration:none;color:var(--fg);font-weight:700;font-size:15px;line-height:1.35;box-shadow:var(--sh)}
.next a small{display:block;color:var(--mut);font-weight:600;margin-bottom:4px}
.next a.r{text-align:right}

/* Suche */
dialog#suche{border:0;padding:0;margin:0 auto;width:100%;max-width:680px;max-height:100dvh;height:100dvh;background:var(--bg);color:var(--fg)}
@media(min-width:700px){dialog#suche{margin-top:6vh;height:auto;max-height:84vh;border-radius:24px;box-shadow:0 24px 80px rgba(43,35,80,.35)}}
dialog#suche::backdrop{background:rgba(43,35,80,.45)}
.sbar{position:sticky;top:0;display:flex;gap:8px;align-items:center;padding:12px;background:var(--bg);border-bottom:1px solid var(--line);z-index:1}
.sbar label{flex:1;display:flex;align-items:center;gap:10px;background:#fff;border:2px solid var(--vio2);border-radius:14px;padding:0 12px}
.sbar label svg{color:var(--vio);flex:none}
.sbar input{flex:1;border:0;outline:none;background:none;font-size:17px;padding:12px 0;min-width:0;color:var(--fg)}
.sbar .x{border:0;background:none;font-weight:700;color:var(--mut);padding:10px;cursor:pointer}
.sres{padding:6px 14px 30px}
.sres h4{margin:16px 2px 8px;font-size:13px;color:var(--mut);font-weight:800}
.hit{display:flex;align-items:center;gap:12px;background:#fff;border-radius:14px;padding:8px;margin-bottom:8px;text-decoration:none;color:var(--fg)}
.hit .th{width:52px;height:52px;flex:none;border-radius:10px;overflow:hidden;background:var(--bg2);display:grid;place-items:center}
.hit .th img{width:100%;height:100%;object-fit:cover}.hit .th img.ct{object-fit:contain;padding:4px}
.hit .th .stk{width:52px;height:52px}
.hit b{display:block;font-size:15px;line-height:1.3}.hit span{font-size:13px;color:var(--mut)}
.hit:hover,.hit:focus{outline:2px solid var(--vio2)}
.sres .none{color:var(--mut);padding:10px 2px}
.sugg{display:flex;flex-wrap:wrap;gap:8px}

/* Social-Leiste + Footer */
.follow{background:var(--fg);color:#fff;border-radius:var(--r);padding:20px;margin-top:40px;display:flex;flex-wrap:wrap;align-items:center;gap:14px;justify-content:space-between}
.follow p{margin:0;font-weight:700}
.btns{display:flex;flex-wrap:wrap;gap:8px}
.btn{display:inline-block;padding:10px 17px;border-radius:999px;font-weight:800;text-decoration:none;font-size:15px;background:#fff;color:var(--fg)}
.btn:hover{background:var(--mint)}
footer{margin-top:30px;padding:22px 0 44px;color:var(--mut);font-size:14px;border-top:1px solid var(--line)}
footer .wrap{display:flex;flex-wrap:wrap;gap:8px 18px}footer a{color:var(--mut)}
.legal{max-width:760px}.legal h1{font-size:clamp(34px,8vw,56px);margin-top:22px}.legal h2{font-size:24px;margin-top:1.2em}
.warn{background:#FFE3EC;border:2px solid var(--pink);padding:14px;border-radius:12px}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}.stamp.go{opacity:.95}}
"""

SPRINKLES = '<div class="spr" aria-hidden="true">' + "".join(
    f'<i style="background:{c};top:{t}%;left:{l}%;transform:rotate({r}deg)"></i>'
    for c, t, l, r in [("#FF8FB1", 9, 82, 30), ("#FFB547", 22, 94, 120), ("#8B6CFF", 3, 64, 100),
                       ("#9EE3C6", 17, 70, 150), ("#8B6CFF", 27, 84, 60)]) + "</div>"

AD = 'Enthält Werbelinks (*): Kaufst du darüber, bekomme ich eine kleine Provision. Dein Preis bleibt gleich.'

SEARCH_DIALOG = f"""<dialog id="suche" aria-label="Suche"><div class="sbar"><label>{ICON_SEARCH}
<input type="search" id="q" placeholder="Süßigkeit, Land, Geschmack oder #Nummer" autocomplete="off" enterkeyhint="search" aria-label="Suchbegriff"></label>
<button class="x" type="button" data-close>Schließen</button></div><div class="sres" id="sres" aria-live="polite"></div></dialog>"""


def socials_btns():
    return "".join(f'<a class="btn" href="{e(s["url"])}" rel="noopener" target="_blank">{e(s["name"])}</a>' for s in site["socials"])


def follow_box():
    return (f'<div class="follow"><p>Mehr Süßigkeiten-Fakten gibt es auf unseren Kanälen.</p>'
            f'<div class="btns">{socials_btns()}</div></div>')


def page(title, body, desc=None, path="/", og_img=None, script="", stamp=""):
    desc = desc or site["intro"]
    og = og_img or f"{BASE}/static/og.jpg"
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<meta name="theme-color" content="#EAF6F1"><link rel="canonical" href="{BASE}{path}">
<link rel="icon" href="/static/favicon.png"><link rel="apple-touch-icon" href="/static/logo.png">
<link rel="preload" href="/static/fonts/anton-latin.woff2" as="font" type="font/woff2" crossorigin>
<meta property="og:type" content="website"><meta property="og:url" content="{BASE}{path}"><meta property="og:locale" content="de_DE">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{og}"><meta name="twitter:card" content="summary_large_image">
<style>{CSS}{SPIN_CSS}{EXTRA_CSS}{EXTRA_CSS2}</style></head><body{stamp_attr(stamp)}>
<div class="ad">{AD}</div>{'<div class="ad" style="background:#FFB547;color:#2B2350;font-weight:700">VORSCHAU mit Beispielprodukten – nicht live</div>' if DEMO else ''}
<header><div class="wrap"><a class="logo" href="/"><img src="/static/logo-96.png" alt="" width="38" height="38">NASCHPASS</a>
<nav aria-label="Hauptmenü"><a href="/shop/">Shop</a><a href="/posts/">Posts</a><a href="/ueber/" class="hide-s">Über uns</a></nav>
<button class="sbtn" type="button" data-open-search aria-label="Suche öffnen">{ICON_SEARCH}</button></div></header>
<main class="wrap">
{body}
{follow_box()}
</main>
<footer><div class="wrap"><a href="/advent/">Adventskalender</a><a href="/geschenk/">Geschenk-Finder</a><a href="/quiz/">Snack-Typ-Quiz</a><a href="/ueber/">Über Naschpass</a><a href="/ueber/#partner">Für Partner</a><a href="/impressum/">Impressum</a><a href="/datenschutz/">Datenschutz</a>
<button class="linkbtn" type="button" data-imgpref hidden>Foto-Einstellung</button>
<span>Keine Cookies, kein Tracking.</span></div></footer>
<div class="imgbar" id="imgbar" role="region" aria-label="Produktfotos" hidden><p>Shop-Fotos laden? Der Shop sieht dann deine IP-Adresse. <a href="/datenschutz/#fotos">Mehr</a></p>
<div class="row"><button class="yes" type="button" data-img="1">Ja</button><button class="no" type="button" data-img="0">Nein</button></div></div>
{SEARCH_DIALOG}
<script>{COMMON_JS}</script><script type="module">{SEARCH_JS}</script>{script}</body></html>"""


def prod_card(p):
    cid = p.get("category", "")
    cname = cat_by_id.get(cid, {}).get("name", "")
    pic = pic_html(p, 480, p["name"], cid)
    shop = p.get("shop", "")
    btn = f"Bei {e(shop)} ansehen*" if shop else "Zum Shop*"
    return (f'<a class="prod" href="{e(p["url"])}" rel="sponsored noopener" target="_blank" data-cat="{e(cid)}"{facet_attrs(p)} style="--c:{cat_color.get(cid, "#CFE7DD")}">'
            f'<div class="pi">{pic}' + (f'<span class="pc"><i></i>{e(cname)}</span>' if cname else "") + '</div>'
            f'<div class="pb"><h3>{e(p["name"])}</h3>'
            + (f'<p class="note">{e(p["note"])}</p>' if p.get("note") else "")
            + (f'<span class="shop">bei {e(shop)}</span>' if shop else "")
            + f'<div class="cta"><span><em class="l">{btn}</em><em class="s">Zum Shop*</em></span></div></div></a>')


def partner_card():
    """Platzhalter für Partner, solange es wenige Produkte gibt. Kein Werbelink, führt zur Partner-Seite."""
    return ('<a class="prod pslot" href="/ueber/#partner"><div class="pi"><span class="emo">🤝</span></div>'
            '<div class="pb"><h3>Hier könnte dein Produkt stehen</h3><span class="shop">Platz für Partner-Shops</span>'
            '<div class="cta"><span><em class="l">Für Partner</em><em class="s">Für Partner</em></span></div></div></a>')


def fill_slots(cards, target):
    """Füllt bis 'target' Kacheln mit Partner-Plätzen auf (nur solange es wenige Produkte gibt)."""
    return cards + [partner_card() for _ in range(max(0, target - len(cards)))]


def prod_grid(items, gid, default="small"):
    return (f'<div class="grid prods v-{default}" id="{gid}">{"".join(prod_card(p) for p in items)}</div>'
            f'<p class="wl">* Werbelink</p>')


def cover_url(p):
    return "/p/" + p["id"] + "/01.jpg"


def post_card(p):
    c = tag_color(p.get("tag", ""))
    return (f'<a class="post" href="/p/{p["id"]}/" data-tag="{tag_slug(p.get("tag", ""))}" style="--c:{c}">'
            f'<div class="cover">{slide_img(cover_url(p), plain(p["hook"]), 300, "(min-width:960px) 220px, (min-width:620px) 31vw, 46vw")}'
            f'<span class="no">#{p["id"]}</span></div>'
            f'<span class="t"><i></i>{e(p.get("tag", ""))}</span></a>')


def write(rel, content):
    f = DIST / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")


COMMON_JS = r"""
(function(){
/* Naschpass-Stempel: nur nach "Pass starten", nur im Browser */
var PK='np_pass';function pget(){try{return JSON.parse(localStorage.getItem(PK)||'null')}catch(e){return null}}
function pset(v){try{if(v)localStorage.setItem(PK,JSON.stringify(v));else localStorage.removeItem(PK)}catch(e){}}
var b=document.body,pass=pget();
if(b.dataset.stamp&&pass&&pass.s.indexOf(b.dataset.stamp)<0){pass.s.push(b.dataset.stamp);pset(pass);
 var t=document.createElement('div');t.className='toast';t.setAttribute('role','status');
 var slot=document.querySelector('#pass [data-s="'+b.dataset.stamp+'"] svg');
 t.innerHTML='🛂 Stempel: '+b.dataset.stampName+' ('+pass.s.length+'/'+b.dataset.stampTotal+')';document.body.appendChild(t);
 setTimeout(function(){t.classList.add('on')},300);setTimeout(function(){t.classList.remove('on')},3600)}
var pb=document.getElementById('pass');
if(pb){var slots=pb.querySelectorAll('[data-s]'),cnt=pb.querySelector('.pcount'),st=pb.querySelector('[data-pass=start]'),rs=pb.querySelector('[data-pass=reset]');
 function draw(){pass=pget();slots.forEach(function(x){x.classList.toggle('got',!!pass&&pass.s.indexOf(x.dataset.s)>=0)});
  cnt.textContent=pass?(pass.s.length+'/'+slots.length):'';st.hidden=!!pass;rs.hidden=!pass}
 st.addEventListener('click',function(){pset({s:[]});draw()});
 rs.addEventListener('click',function(){pset(null);draw()});draw()}
})();
(function(){
/* Produktfotos von Shop-Servern: erst nach Einwilligung laden. Die Wahl liegt nur im Browser (localStorage). */
var K='np_fotos',bar=document.getElementById('imgbar'),pref=document.querySelector('[data-imgpref]');
function get(){try{return localStorage.getItem(K)}catch(e){return null}}
function set(v){try{localStorage.setItem(K,v)}catch(e){}}
window.npImgOK=function(){return get()==='1'};
var ext=document.querySelectorAll('img[data-ext]');
function show(){ext.forEach(function(i){if(i.src)return;i.onload=function(){i.hidden=false;i.parentNode.classList.add('ok')};
 i.onerror=function(){i.remove()};i.src=i.dataset.ext})}
if(ext.length){if(pref)pref.hidden=false;
 if(get()==='1')show();else if(get()!=='0')bar.hidden=false}
document.querySelectorAll('[data-img]').forEach(function(b){b.addEventListener('click',function(){
 var was=[].some.call(ext,function(i){return i.src});set(b.dataset.img);bar.hidden=true;
 if(b.dataset.img==='1')show();else if(was)location.reload()})});
if(pref)pref.addEventListener('click',function(){bar.hidden=false;bar.querySelector('.yes').focus()});
})();
(function(){
/* Ansicht umschalten (nur für diesen Besuch, es wird nichts gespeichert) */
document.querySelectorAll('[data-view]').forEach(function(b){b.addEventListener('click',function(){
 var g=document.getElementById(b.dataset.target);if(!g)return;
 g.className=g.className.replace(/\bv-\w+/,'v-'+b.dataset.view);
 b.parentNode.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-pressed',x===b)})})});
/* Filter-Chips */
document.querySelectorAll('[data-filter]').forEach(function(c){c.addEventListener('click',function(){
 var g=document.getElementById(c.dataset.grid),v=c.dataset.filter,k=c.dataset.key;
 c.parentNode.querySelectorAll('[data-filter]').forEach(function(x){x.setAttribute('aria-pressed',x===c)});
 g.querySelectorAll(':scope > a').forEach(function(a){a.hidden=!(v==='alle'||a.dataset[k]===v)})})});
/* Empfehlungs-Band: läuft langsam durch, stoppt beim Anfassen/Hovern, wischbar */
var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
document.querySelectorAll('.band[data-shuffle]').forEach(function(b){
 var o=[].slice.call(b.querySelectorAll('.ri:not([aria-hidden])'));if(o.length<2)return;
 for(var i=o.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1)),t=o[i];o[i]=o[j];o[j]=t}
 b.innerHTML='';o.forEach(function(x){b.appendChild(x)});
 o.forEach(function(x){var c=x.cloneNode(true);c.setAttribute('aria-hidden','true');c.tabIndex=-1;b.appendChild(c)})});
document.querySelectorAll('.band').forEach(function(b){
 if(reduce||b.scrollWidth<=b.clientWidth+10)return;
 var half=b.scrollWidth/2,pause=0,x=b.scrollLeft;
 function hold(){pause=Date.now()+2500}
 ['pointerdown','touchstart','wheel','focusin','mouseenter'].forEach(function(ev){b.addEventListener(ev,hold,{passive:true})});
 b.addEventListener('mousemove',hold,{passive:true});
 function tick(){if(Date.now()>pause&&!document.hidden){x=b.scrollLeft+.45;if(x>=half)x-=half;b.scrollLeft=x}requestAnimationFrame(tick)}
 requestAnimationFrame(tick)});
/* Mehr zeigen */
document.querySelectorAll('[data-expand]').forEach(function(b){b.addEventListener('click',function(){
 var g=document.getElementById(b.dataset.expand);g.classList.remove('clip');b.remove();
 var f=g.querySelector('[data-more]');if(f){var a=f.matches('a')?f:f.querySelector('a');if(a)a.focus({preventScroll:true})}})});
/* Saison-Hinweis: im Herbst Halloween, danach Advent (nur Text, nichts gespeichert) */
document.querySelectorAll('[data-season]').forEach(function(a){var n=new Date(),y=n.getFullYear(),m=n.getMonth(),d=n.getDate(),
 days=function(mm,dd){return Math.round((new Date(y,mm,dd)-new Date(y,m,d))/864e5)},em=a.querySelector('em'),ic=a.querySelector('span');
 if(m===8&&d>=15||m===9){a.href='/kategorie/halloween/';a.classList.add('hw');ic.textContent='🎃';
  var t=days(9,31);em.textContent=t>0?'Halloween in '+t+' Tagen':'Heute ist Halloween';return}
 a.href='/advent/';a.classList.remove('hw');ic.textContent='🎄';
 if(m===11&&d<=24){em.textContent='Türchen '+d+' ist offen';return}
 if(m===11){em.textContent='Adventskalender';return}
 em.textContent='Advent in '+days(11,1)+' Tagen'});
/* Weltkarte am Handy mittig (Europa) starten, Rest wischbar */
document.querySelectorAll('.map').forEach(function(m){m.scrollLeft=(m.scrollWidth-m.clientWidth)*.45});
/* Klapp-Menüs auf der Startseite */
document.querySelectorAll('.ddnav').forEach(function(nv){
 function close(x){nv.querySelectorAll('.dd.open').forEach(function(d){if(d!==x){d.classList.remove('open');d.querySelector('.ddb').setAttribute('aria-expanded','false')}})}
 nv.querySelectorAll('.ddb').forEach(function(t){t.addEventListener('click',function(){var d=t.parentNode,o=!d.classList.contains('open');close(d);d.classList.toggle('open',o);t.setAttribute('aria-expanded',o)})});
 document.addEventListener('click',function(ev){if(!nv.contains(ev.target))close()});
 document.addEventListener('keydown',function(ev){if(ev.key==='Escape')close()})});
/* Stöbern-Tabs */
document.querySelectorAll('[role=tab]').forEach(function(t){t.addEventListener('click',function(){
 var n=t.closest('nav');n.querySelectorAll('[role=tab]').forEach(function(x){x.setAttribute('aria-selected',x===t)});
 n.querySelectorAll('[data-panel]').forEach(function(p){p.hidden=p.dataset.panel!==t.dataset.tab})})});
/* Shop-Filter: innerhalb einer Gruppe ODER, zwischen Gruppen UND; Zustand steht in der Adresse (teilbar) */
var fl=document.getElementById('flt');
if(fl){var grid=document.getElementById(fl.dataset.grid),cards=[].slice.call(grid.children),PAGE=24,shown=PAGE,sel={};
 var cnt=document.getElementById('fcount'),rst=document.getElementById('freset'),more=document.getElementById('fmore'),emp=document.getElementById('fempty');
 fl.querySelectorAll('[data-g]').forEach(function(b){sel[b.dataset.g]=[]});
 var u=new URLSearchParams(location.search);Object.keys(sel).forEach(function(k){var v=u.get(k);if(v)sel[k]=v.split(',')});
 function ok(c){return Object.keys(sel).every(function(k){if(!sel[k].length)return true;var h=' '+(c.dataset[k]||'')+' ';
  return sel[k].some(function(v){return h.indexOf(' '+v+' ')>=0})})}
 function apply(){var n=0;cards.forEach(function(c){var m=ok(c);if(m)n++;c.hidden=!m||n>shown});
  fl.querySelectorAll('[data-g]').forEach(function(b){b.setAttribute('aria-pressed',sel[b.dataset.g].indexOf(b.dataset.v)>=0)});
  fl.querySelectorAll('[data-badge]').forEach(function(x){var k=sel[x.dataset.badge].length;x.textContent=k;x.hidden=!k});
  var act=[];fl.querySelectorAll('[data-g][aria-pressed=true]').forEach(function(b){act.push('<button type="button" data-rm="'+b.dataset.g+':'+b.dataset.v+'" aria-label="'+b.dataset.n+' entfernen">'+b.dataset.n+' ×</button>')});
  document.getElementById('factive').innerHTML=act.join('');
  cnt.textContent=n+' Treffer';more.hidden=n<=shown;more.textContent='Mehr zeigen ('+(n-shown)+')';emp.hidden=n>0;
  var any=Object.keys(sel).some(function(k){return sel[k].length});rst.hidden=!any;
  var q=Object.keys(sel).filter(function(k){return sel[k].length}).map(function(k){return k+'='+sel[k].join(',')}).join('&');
  history.replaceState(null,'',location.pathname+(q?'?'+q:'')+location.hash)}
 function closeAll(x){fl.querySelectorAll('.dd.open').forEach(function(d){if(d!==x){d.classList.remove('open');d.querySelector('.ddb').setAttribute('aria-expanded','false')}})}
 fl.querySelectorAll('.ddb').forEach(function(t){t.addEventListener('click',function(){var d=t.parentNode,o=!d.classList.contains('open');
  closeAll(d);d.classList.toggle('open',o);t.setAttribute('aria-expanded',o)})});
 document.addEventListener('click',function(ev){if(!ev.target.closest('.dd'))closeAll()});
 document.addEventListener('keydown',function(ev){if(ev.key==='Escape')closeAll()});
 fl.addEventListener('click',function(ev){var r=ev.target.closest('[data-rm]');if(r){var kv=r.dataset.rm.split(':'),a2=sel[kv[0]];a2.splice(a2.indexOf(kv[1]),1);shown=PAGE;apply();return}
  var b=ev.target.closest('[data-g]');if(!b)return;var a=sel[b.dataset.g],i=a.indexOf(b.dataset.v);
  if(i>=0)a.splice(i,1);else a.push(b.dataset.v);shown=PAGE;apply()});
 rst.addEventListener('click',function(){Object.keys(sel).forEach(function(k){sel[k]=[]});shown=PAGE;apply()});
 more.addEventListener('click',function(){shown+=PAGE;apply()});
 apply()}
/* Folien-Galerie */
var s=document.querySelector('.slides');
if(s){var im=s.querySelectorAll('img'),d=document.querySelectorAll('.dots b');
 function cur(){var c=s.scrollLeft+s.clientWidth/2,b=0,bd=1e9;im.forEach(function(x,i){var m=x.offsetLeft+x.offsetWidth/2,dd=Math.abs(m-c);if(dd<bd){bd=dd;b=i}});return b}
 s.addEventListener('scroll',function(){requestAnimationFrame(function(){var i=cur();d.forEach(function(x,j){x.classList.toggle('on',j===i)})})},{passive:true});
 function go(k){var i=Math.max(0,Math.min(im.length-1,cur()+k));s.scrollTo({left:im[i].offsetLeft-(s.clientWidth-im[i].offsetWidth)/2,behavior:reduce?'auto':'smooth'})}
 document.querySelectorAll('.arrow').forEach(function(a){a.addEventListener('click',function(){go(+a.dataset.k)})});
 s.addEventListener('keydown',function(ev){if(ev.key==='ArrowRight')go(1);if(ev.key==='ArrowLeft')go(-1)})}
/* Nummer aus dem Post */
var f=document.getElementById('jump');
if(f){var inp=f.querySelector('input'),msg=f.querySelector('.msg'),st=f.querySelector('.stamp'),ids=JSON.parse(f.dataset.ids);
 f.addEventListener('submit',function(ev){ev.preventDefault();
  var n=(inp.value||'').replace(/\D/g,'');if(!n){msg.textContent='Gib die Nummer aus dem Post ein, z. B. 2.';inp.focus();return}
  n=n.length<2?('0'+n):n;
  if(ids.indexOf(n)<0){msg.textContent='Post #'+n+' gibt es noch nicht. Schau mal bei allen Posts.';return}
  msg.textContent='';st.textContent='#'+n;st.classList.remove('go');void st.offsetWidth;st.classList.add('go');
  setTimeout(function(){location.href='/p/'+n+'/'},reduce?0:480)})}
})();
"""

SEARCH_JS = r"""
const dlg=document.getElementById('suche'),q=document.getElementById('q'),out=document.getElementById('sres');
let data=null,fuse=null;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function load(){if(data)return;
 const [r,m]=await Promise.all([fetch('/search.json').then(x=>x.json()),import('__FUSE__')]);
 data=r;fuse=new m.default(r.items,{keys:[{name:'title',weight:3},{name:'alt',weight:2},{name:'tags',weight:2},{name:'text',weight:1}],
  threshold:.36,ignoreLocation:true,ignoreDiacritics:true,minMatchCharLength:2});}
function hit(i){
 const im=i.img||(i.ext&&window.npImgOK&&window.npImgOK()?i.ext:'');
 const th=im?`<img src="${esc(im)}" alt="" loading="lazy"${i.type==='product'?' class="ct"':''}>`:(i.svg||'');
 const ext=i.type==='product'?' rel="sponsored noopener" target="_blank"':'';
 return `<a class="hit" href="${esc(i.url)}"${ext}><span class="th">${th}</span><span><b>${esc(i.title)}${i.type==='product'?'*':''}</b><span>${esc(i.sub||'')}</span></span></a>`}
function group(t,arr){return arr.length?`<h4>${t}</h4>`+arr.map(hit).join(''):''}
function render(){
 const v=q.value.trim();
 if(!v){out.innerHTML='<h4>Vorschläge</h4><div class="sugg">'+data.sugg.map(s=>`<button class="chip" type="button" data-s="${esc(s)}">${esc(s)}</button>`).join('')+'</div>'
  +group('Neueste Posts',data.items.filter(i=>i.type==='post').slice(0,4));return}
 let res=fuse.search(v).map(r=>r.item);
 const n=v.replace(/^#/,'');
 if(/^\d{1,3}$/.test(n)){const id=n.padStart(2,'0');const p=data.items.find(i=>i.type==='post'&&i.id===id);
  if(p)res=[p,...res.filter(x=>x!==p)]}
 let P=res.filter(i=>i.type==='product'),hint='';
 const C=res.filter(i=>i.type==='cat'),T=res.filter(i=>i.type==='post');
 /* Ganze Wünsche verstehen: "salzige Chips, eventuell asiatisch" -> Salzig + Chips + Asien */
 const {found,rest}=parse(v);
 if(found.length){
  const groups={};found.forEach(f=>(groups[f.g]=groups[f.g]||[]).push(f.id));
  const gk=Object.keys(groups),prods=data.items.filter(i=>i.type==='product');
  const score=i=>gk.filter(g=>groups[g].some(id=>(' '+i.f+' ').includes(' '+g+':'+id+' '))).length;
  let best=prods.map(i=>[i,score(i)]).filter(x=>x[1]>0).sort((a,b)=>b[1]-a[1]);
  const full=best.filter(x=>x[1]===gk.length).map(x=>x[0]);
  let list=full.length?full:best.map(x=>x[0]);
  if(rest.length){const f2=fuse.search(rest.join(' ')).map(r=>r.item);list=[...f2.filter(x=>list.includes(x)),...list.filter(x=>!f2.includes(x))]}
  P=[...list,...P.filter(x=>!list.includes(x))];
  const qs=gk.map(g=>g+'='+groups[g].join(',')).join('&');
  hint=`<div class="hint"><b>${full.length?'Passt zu':'Nicht alles auf einmal gefunden, das kommt am nächsten'}:</b><div class="chips">`
   +found.map(f=>`<span class="chip" aria-pressed="true">${esc(f.name)}</span>`).join('')
   +`</div><p style="margin:10px 0 0"><a class="btn dark" href="/shop/?${qs}#alle">${full.length} im Shop ansehen</a></p></div>`}
 out.innerHTML=hint+((group('Süßigkeiten',P.slice(0,12))+group('Länder & Themen',C)+group('Posts',T.slice(0,8)))
  +(P.length?'<p class="wl">* Werbelink</p>':'')
  ||`<p class="none">Nichts gefunden zu „${esc(v)}“. Probier ein Land (Japan, USA), einen Geschmack (sauer, salzig) oder eine Marke.</p>`)}
const STOP=new Set('ich mag mich mir und oder eventuell evtl vielleicht was mit ohne gern gerne etwas irgendwas auch die der das den dem ein eine einen liebsten mal bitte lust auf suche such haette habe hab aus von fuer sowas sachen zeug richtig sehr total eher bisschen oder sind ist was'.split(' '));
const norm=s=>s.toLowerCase().replace(/ä/g,'ae').replace(/ö/g,'oe').replace(/ü/g,'ue').replace(/ß/g,'ss');
function parse(v){
 const toks=norm(v).split(/[^a-z0-9]+/).filter(t=>t.length>=3&&!STOP.has(t));const found=[],rest=[];
 toks.forEach(t=>{const st=t.replace(/(en|er|es|em|e|n|s)$/,'');
  let h=data.facets.filter(f=>f.id===t||f.id===st||norm(f.name).split(/[^a-z0-9]+/).some(w=>w===t||w===st));
  let byKw=false;
  if(!h.length){h=data.facets.filter(f=>f.kw.some(k=>t.startsWith(k)||(st.length>=4&&k.startsWith(st))));byKw=true}
  h.forEach(x=>{if(!found.some(y=>y.g===x.g&&y.id===x.id))found.push(x)});
  if(!h.length||byKw)rest.push(t)});
 return {found,rest}}
out.addEventListener('click',ev=>{const b=ev.target.closest('[data-s]');if(b){q.value=b.dataset.s;render();q.focus()}});
q.addEventListener('input',()=>{if(fuse)render()});
async function open(){dlg.showModal();q.focus();out.innerHTML='<p class="none">Lädt …</p>';await load();render()}
document.querySelectorAll('[data-open-search]').forEach(b=>b.addEventListener('click',open));
dlg.querySelector('[data-close]').addEventListener('click',()=>dlg.close());
dlg.addEventListener('click',ev=>{if(ev.target===dlg)dlg.close()});
document.addEventListener('keydown',ev=>{if(ev.key==='/'&&!dlg.open&&!/input|textarea/i.test(document.activeElement.tagName)){ev.preventDefault();open()}});
""".replace("__FUSE__", FUSE)


# ---------- Zufalls-Rad "Was naschst du heute?" ----------
# Farbe = Art der Süßigkeit (bzw. Thema, solange es wenige Produkte gibt). Keine erfundene Seltenheit.
ART_COLORS = {"schokolade": "#8B5A3C", "pralinen": "#C2185B", "gummi": "#FF4D8D", "bonbons": "#FFB547", "chips": "#E8384F",
              "kekse": "#D4A373", "snacks": "#2FAE7E", "getraenke": "#3D8BFF", "boxen": "#8B6CFF"}


def spin_items(live):
    items = []
    art_name = {o["id"]: o["name"] for g in FILTER if g["id"] == "art" for o in g["options"]}
    for p in products:
        arts = [a for a in ART_COLORS if a in facets(p).get("art", set())]
        a = arts[0] if arts else ""
        i = prod_img(p, 240)
        items.append({"t": p["name"], "u": p["url"], "k": "p", "c": ART_COLORS.get(a, "#9C94C7"), "l": art_name.get(a, "Süßigkeit"),
                      "img": i[1] if i and i[0] == "own" else "", "ext": i[1] if i and i[0] == "ext" else "",
                      "svg": "" if i and i[0] == "own" else sticker(p.get("category", ""), 64)})
    if len(products) < 6:  # noch wenige Produkte: Posts und Themenwelten mit ins Rad
        for p in live:
            items.append({"t": f"#{p['id']} {plain(p.get('short', ''))}", "u": f"/p/{p['id']}/", "k": "post", "c": "#FF4D8D",
                          "l": "Post", "img": cdn(cover_url(p), 240) if ON_NETLIFY else cover_url(p)})
        for c in cats:
            items.append({"t": c["name"], "u": f"/kategorie/{c['id']}/", "k": "cat", "c": "#3DDC97", "l": "Themenwelt",
                          "svg": sticker(c["id"], 64)})
    return items


def spin_html(live):
    items = spin_items(live)
    if len(items) < 3:
        return ""
    leg, seen = [], set()
    for i in items:
        if i["l"] not in seen:
            seen.add(i["l"])
            leg.append(f'<span class="chip" style="--c:{i["c"]}"><i></i>{e(i["l"])}</span>')
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    return (f'<section class="spin" id="zufall"><div class="spinbox"><div class="spinhead"><h2>Was naschst du heute?</h2>'
            f'<button class="snd" type="button" aria-pressed="true" aria-label="Ton an/aus">🔊</button></div>'
            f'<p class="sub" style="margin:0 0 12px">Dreh das Rad und lass dich überraschen. Die Farbe verrät, was es ist.</p>'
            f'<div class="reel"><div class="track"></div><div class="marker" aria-hidden="true"></div></div>'
            f'<div class="legend">{"".join(leg)}</div>'
            f'<button class="spinbtn" type="button">Drehen</button>'
            f'<div class="result" aria-live="polite"></div></div>'
            f'<script type="application/json" id="spin-data">{data}</script></section>')


SPIN_CSS = """
.spin .spinbox{position:relative;background:var(--fg);color:#fff;border-radius:26px;padding:20px 16px 18px;overflow:hidden}
.spin .spinbox:before{content:"";position:absolute;inset:-40%;background:conic-gradient(from 0deg,#FF4D8D,#FFB547,#3DDC97,#3D8BFF,#8B6CFF,#FF4D8D);
opacity:.14;filter:blur(30px);pointer-events:none}
.spin.go .spinbox:before{opacity:.32;animation:spinlight 2.4s linear infinite}
@keyframes spinlight{to{transform:rotate(1turn)}}
.spinhead{position:relative;display:flex;align-items:center;justify-content:space-between;gap:10px}
.spinhead h2{margin:0;color:#fff}.spin .sub{color:#CFC9E8;position:relative}
.snd{border:0;background:rgba(255,255,255,.12);color:#fff;border-radius:12px;width:42px;height:42px;font-size:20px;cursor:pointer}
.reel{position:relative;height:170px;border-radius:18px;background:#14092B;overflow:hidden;
box-shadow:inset 0 0 0 2px rgba(255,255,255,.08),inset 0 0 40px rgba(0,0,0,.6)}
.reel:after{content:"";position:absolute;inset:0;pointer-events:none;
background:linear-gradient(90deg,#14092B 0,transparent 18%,transparent 82%,#14092B 100%)}
.track{position:absolute;left:0;top:12px;display:flex;gap:10px;will-change:transform}
.card{flex:none;width:100px;height:146px;border-radius:14px;background:#22144A;border-bottom:6px solid var(--c);
display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;padding:8px;text-align:center;
box-shadow:0 0 0 1px rgba(255,255,255,.06),0 -24px 30px -24px var(--c) inset}
.card img{width:100%;height:76px;object-fit:cover;border-radius:10px;background:#fff}
.card .svgw{height:76px;display:grid;place-items:center}.card .svgw svg{width:58px;height:58px}
.card b{font-size:11.5px;line-height:1.2;max-height:2.4em;overflow:hidden;color:#fff}
.card.win{animation:winpulse 1s ease-in-out 3;box-shadow:0 0 0 3px var(--c),0 0 34px var(--c)}
@keyframes winpulse{50%{transform:scale(1.07)}}
.marker{position:absolute;left:50%;top:0;bottom:0;width:4px;margin-left:-2px;background:#FFD23F;z-index:2;
box-shadow:0 0 10px #FFD23F,0 0 26px #FF4D8D}
.marker:before,.marker:after{content:"";position:absolute;left:50%;margin-left:-9px;border:9px solid transparent}
.marker:before{top:0;border-top-color:#FFD23F}.marker:after{bottom:0;border-bottom-color:#FFD23F}
.marker.tick{box-shadow:0 0 18px #FFD23F,0 0 44px #FF4D8D}
.legend{position:relative;display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}
.legend .chip{background:rgba(255,255,255,.1);color:#fff;box-shadow:none;font-size:13px;padding:6px 11px;cursor:default}
.spinbtn{position:relative;width:100%;border:0;border-radius:16px;padding:16px;font:28px Anton,sans-serif;letter-spacing:1px;text-transform:uppercase;
color:#2B2350;background:linear-gradient(90deg,#FFD23F,#FF8FB1,#8B6CFF,#3DDC97,#FFD23F);background-size:300% 100%;cursor:pointer;
animation:btnflow 6s linear infinite;box-shadow:0 8px 26px rgba(255,77,141,.35)}
@keyframes btnflow{to{background-position:300% 0}}
.spinbtn:disabled{opacity:.6;cursor:wait}
.result{min-height:112px;transition:opacity .25s}.result.dim{opacity:.35}
.result:not(.has){justify-content:center;color:var(--mut);border-left-color:transparent}
.card{transition:transform .12s,filter .12s;filter:saturate(.75) brightness(.85)}
.card.ps{background:transparent;border:2px dashed rgba(139,108,255,.7);border-bottom-width:2px}.card.ps b{color:#CFC9E8}
.card.hot{transform:scale(1.06);filter:none}.card.win{filter:none}
.result{position:relative;margin-top:14px;background:#fff;color:var(--fg);border-radius:18px;padding:14px;display:flex;gap:14px;align-items:center;
border-left:8px solid var(--c)}
.result .ri2{width:76px;height:76px;flex:none;border-radius:12px;overflow:hidden;background:var(--bg2);display:grid;place-items:center}
.result .ri2 img{width:100%;height:100%;object-fit:cover}.result .ri2 svg{width:60px;height:60px}
.result small{color:var(--mut);font-weight:700}.result h3{font-size:18px;margin:2px 0 8px}
.result .acts{display:flex;gap:8px;flex-wrap:wrap}.result .btn{padding:8px 14px;font-size:14px}
.confetti{position:absolute;width:10px;height:4px;border-radius:2px;top:50%;left:50%;pointer-events:none;z-index:3;
animation:conf 1.1s ease-out forwards}
@keyframes conf{to{transform:translate(var(--x),var(--y)) rotate(var(--r));opacity:0}}
@media(prefers-reduced-motion:reduce){.spin.go .spinbox:before,.spinbtn{animation:none}}
"""

SPIN_JS = r"""<script>
(function(){
var root=document.getElementById('zufall');if(!root)return;
var items=JSON.parse(document.getElementById('spin-data').textContent),track=root.querySelector('.track'),reel=root.querySelector('.reel'),
 mk=root.querySelector('.marker'),btn=root.querySelector('.spinbtn'),res=root.querySelector('.result'),snd=root.querySelector('.snd'),
 box=root.querySelector('.spinbox'),reduce=matchMedia('(prefers-reduced-motion: reduce)').matches,sound=true,ac=null,busy=false;
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function pic(i){var ok=window.npImgOK&&window.npImgOK(),src=i.img||(i.ext&&ok?i.ext:'');
 return src?'<img src="'+esc(src)+'" alt="" loading="lazy">':'<span class="svgw">'+(i.svg||'')+'</span>'}
function card(i){return '<div class="card" style="--c:'+i.c+'">'+pic(i)+'<b>'+esc(i.t)+'</b></div>'}
function rnd(n){return Math.floor(Math.random()*n)}
function setX(x){track.style.transform='translateX('+x+'px)'}
(function(){var h='';for(var k=0;k<14;k++)h+=card(items[rnd(items.length)]);track.innerHTML=h;setX(-40)})();
res.innerHTML='<small>Tippe auf „Drehen“ und lass dich überraschen.</small>';
snd.addEventListener('click',function(){sound=!sound;snd.textContent=sound?'🔊':'🔇';snd.setAttribute('aria-pressed',sound)});
/* Klänge werden im Browser erzeugt (keine Audiodateien):
   Tick = kurzes, gefiltertes Rauschen wie ein Plastik-Klick, plus leiser "Körper"-Ton
   Einrasten = weicher, tiefer Plopp; Aufdecken = Glocken-Pling mit Glitzer */
var master=null,noise=null;
function audio(){if(!sound)return null;try{if(!ac){ac=new (window.AudioContext||window.webkitAudioContext)();
  master=ac.createDynamicsCompressor();master.connect(ac.destination);
  noise=ac.createBuffer(1,Math.floor(ac.sampleRate*.05),ac.sampleRate);var d=noise.getChannelData(0);for(var k=0;k<d.length;k++)d[k]=(Math.random()*2-1)*Math.pow(1-k/d.length,3)}
 if(ac.state==='suspended')ac.resume();return ac}catch(e){return null}}
function env(g,t,peak,att,dec){g.gain.setValueAtTime(0.0001,t);g.gain.exponentialRampToValueAtTime(peak,t+att);g.gain.exponentialRampToValueAtTime(0.0001,t+att+dec)}
function tick(speed){var a=audio();if(!a)return;var t=a.currentTime,src=a.createBufferSource(),bp=a.createBiquadFilter(),g=a.createGain();
 src.buffer=noise;bp.type='bandpass';bp.frequency.value=2300+Math.random()*500+speed*600;bp.Q.value=4;env(g,t,.18,.001,.03);
 src.connect(bp);bp.connect(g);g.connect(master);src.start(t);src.stop(t+.05);
 var o=a.createOscillator(),g2=a.createGain();o.type='sine';o.frequency.setValueAtTime(420,t);o.frequency.exponentialRampToValueAtTime(180,t+.03);
 env(g2,t,.05,.001,.035);o.connect(g2);g2.connect(master);o.start(t);o.stop(t+.05)}
function bell(f,t,vol,dur){var a=ac;[1,2.01,3.02].forEach(function(m,k){var o=a.createOscillator(),g=a.createGain();o.type='sine';o.frequency.value=f*m;
 env(g,t,vol/(k*1.8+1),.004,dur/(k+1));o.connect(g);g.connect(master);o.start(t);o.stop(t+dur+.1)})}
function thunk(){var a=audio();if(!a)return;var t=a.currentTime,o=a.createOscillator(),g=a.createGain();o.type='sine';
 o.frequency.setValueAtTime(220,t);o.frequency.exponentialRampToValueAtTime(90,t+.09);env(g,t,.16,.003,.12);o.connect(g);g.connect(master);o.start(t);o.stop(t+.2)}
function fanfare(){var a=audio();if(!a)return;var t=a.currentTime+.02;bell(880,t,.12,1.4);bell(1318.5,t+.11,.08,1.2);
 [1760,2093,2637,3136].forEach(function(f,k){bell(f,t+.22+k*.07,.035,.45)})}
function confetti(color){var r=reel.getBoundingClientRect(),b=box.getBoundingClientRect();
 for(var k=0;k<44;k++){var c=document.createElement('i');c.className='confetti';
  c.style.background=['#FFD23F','#FF4D8D','#3DDC97','#3D8BFF',color][k%5];
  c.style.left=(r.left-b.left+r.width/2)+'px';c.style.top=(r.top-b.top+r.height/2)+'px';
  c.style.setProperty('--x',(Math.random()*420-210)+'px');c.style.setProperty('--y',(Math.random()*-220-20)+'px');
  c.style.setProperty('--r',(Math.random()*720)+'deg');box.appendChild(c);setTimeout(c.remove.bind(c),1300)}}
function show(i){var ext=i.k==='p',lbl=i.k==='p'?'Zum Shop*':(i.k==='post'?'Zum Post':'Zur Themenwelt');
 res.style.setProperty('--c',i.c);res.classList.add('has');
 res.innerHTML='<div class="ri2">'+pic(i)+'</div><div><small>Dein Zufalls-Vorschlag · '+esc(i.l)+'</small><h3>'+esc(i.t)+'</h3><div class="acts">'
  +'<a class="btn dark" href="'+esc(i.u)+'"'+(ext?' rel="sponsored noopener" target="_blank"':'')+'>'+lbl+'</a>'
  +'<button class="btn" type="button" data-share style="border:2px solid var(--fg)">Teilen</button>'
  +(ext?'<small style="align-self:center">* Werbelink</small>':'')+'</div></div>';
 res.querySelector('[data-share]').addEventListener('click',function(ev){var b=ev.currentTarget,
  d={title:'Naschpass',text:'Mein Naschpass-Rad sagt: '+i.t+' 🍬 Was zeigt es dir?',url:location.origin+'/#zufall'};
  if(navigator.share){navigator.share(d).catch(function(){})}
  else{try{navigator.clipboard.writeText(d.text+' '+d.url);b.textContent='Kopiert!'}catch(e){}}})}
/* Ablauf wie beim Case-Opening: kurz ausholen, schnell los, lange sanft auslaufen,
   knapp an der Kante liegen bleiben, kurze Pause, dann in die Mitte rutschen und aufdecken */
function spin(){if(busy)return;busy=true;btn.disabled=true;btn.textContent='…';res.classList.add('dim');
 var N=48,T=41,seq=[];for(var k=0;k<N;k++)seq.push(items[rnd(items.length)]);var win=seq[T];
 var PS='<div class="card ps"><span class="svgw"><span style="font-size:34px">🤝</span></span><b>Hier könnte dein Produkt stehen</b></div>';
 track.innerHTML=seq.map(function(i,k){return (k!==T&&items.length<20&&Math.random()<.18)?PS:card(i)}).join('');setX(0);
 var cw=track.children[0].offsetWidth,W=cw+10,mid=reel.clientWidth/2,center=-(T*W+cw/2-mid),
  edge=(Math.random()<.5?-1:1)*cw*(.28+Math.random()*.17),end=center+edge,
  dur=reduce?0:8200,t0=null,last=-1,hot=null;
 root.classList.add('go');
 function hi(idx){if(hot)hot.classList.remove('hot');hot=track.children[idx];if(hot)hot.classList.add('hot')}
 function reveal(){if(hot)hot.classList.remove('hot');track.children[T].classList.add('win');root.classList.remove('go');
  fanfare();if(!reduce)confetti(win.c);show(win);res.classList.remove('dim');busy=false;btn.disabled=false;btn.textContent='Nochmal drehen'}
 if(!dur){setX(center);reveal();return}
 function settle(){var s0=null,from=end;
  function f(ts){if(!s0)s0=ts;var p=Math.min(1,(ts-s0)/550),e=p<.5?2*p*p:1-Math.pow(-2*p+2,2)/2;setX(from+(center-from)*e);
   if(p<1)requestAnimationFrame(f);else reveal()}
  setTimeout(function(){thunk();requestAnimationFrame(f)},450)}
 function frame(ts){if(!t0)t0=ts;var t=ts-t0,x;
  if(t<260){x=26*Math.sin(t/260*Math.PI/2)}                 /* ausholen */
  else{var p=Math.min(1,(t-260)/dur),e=1-Math.pow(1-p,3.4);x=26+(end-26)*e}
  setX(x);var idx=Math.floor((mid-x)/W);
  if(idx!==last&&idx>=0){last=idx;hi(idx);try{tick(Math.max(0,1-(p||0)*1.4))}catch(e){}mk.classList.add('tick');setTimeout(function(){mk.classList.remove('tick')},70)}
  if(t<260+dur)requestAnimationFrame(frame);else settle()}
 requestAnimationFrame(frame)}
btn.addEventListener('click',function(){btn.blur();spin()});
})();
</script>"""


# ---------- Naschpass mit Stempeln ----------
# Ein Stempel pro Länder-Themenwelt. Gesammelt wird erst nach "Pass starten" und nur im Browser (localStorage).
STAMPS = [c for c in cats if any(f.startswith("land:") for f in c.get("facets", []))]
STAMP_IDS = {c["id"] for c in STAMPS}
TAG_STAMP = {"japan": "japan", "usa": "usa", "usa vs. eu": "usa", "mexiko": "mexiko", "italien": "italien",
             "schweiz": "schweiz", "skandinavien": "skandinavien"}


def stamp_attr(sid):
    if not sid or sid not in STAMP_IDS:
        return ""
    c = cat_by_id[sid]
    return f' data-stamp="{sid}" data-stamp-name="{e(c["name"])}" data-stamp-total="{len(STAMPS)}"'


def pass_html():
    slots = "".join(f'<a class="stamp-slot" href="/kategorie/{c["id"]}/" data-s="{c["id"]}" title="{e(c["name"])}">'
                    f'{sticker(c["id"], 46)}<small>{e(c["name"])}</small></a>' for c in STAMPS)
    return (f'<section id="pass"><div class="passbook"><div class="passhead"><div><h2>Dein Naschpass</h2>'
            f'<p class="sub" style="margin:0">Sammle Länder-Stempel: Jede Länder-Themenwelt, die du besuchst, stempelt deinen Pass.</p></div>'
            f'<b class="pcount" aria-live="polite"></b></div><div class="stamps">{slots}</div>'
            f'<div class="pactions"><button class="btn dark" type="button" data-pass="start">Pass starten</button>'
            f'<button class="linkbtn" type="button" data-pass="reset" hidden>Pass zurücksetzen</button></div>'
            f'<p class="wl">Dein Pass liegt nur in deinem Browser und wird nie an uns gesendet.</p></div></section>')


# ---------- Adventskalender ----------
def advent_page(live):
    pool = []
    for p in reversed(live):
        pool.append({"t": plain(p["hook"]), "s": f"Post #{p['id']}", "u": f"/p/{p['id']}/",
                     "img": cdn(cover_url(p), 240) if ON_NETLIFY else cover_url(p)})
    for c in cats_sorted():
        pool.append({"t": c["name"], "s": c.get("teaser", ""), "u": f"/kategorie/{c['id']}/", "svg": sticker(c["id"], 64)})
    if not pool:
        return ""
    order = [7, 19, 3, 12, 24, 9, 1, 15, 21, 5, 17, 11, 2, 23, 8, 14, 20, 4, 18, 10, 6, 13, 22, 16]
    pal = ["#FF4D8D", "#8B6CFF", "#2FAE7E", "#FFB547", "#3D8BFF", "#E8384F"]
    doors = "".join(f'<button class="door{" big" if d == 24 else ""}" type="button" data-day="{d}" style="--c:{pal[d % len(pal)]}">'
                    f'<span class="num">{d}</span><i class="lock" aria-hidden="true">🔒</i></button>' for d in order)
    content = json.dumps({str(d): pool[(d - 1) % len(pool)] for d in range(1, 25)}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<section class="hero" style="padding-bottom:0">{SPRINKLES}<h1>Naschpass-<span class="acc">Adventskalender</span></h1>
<p class="lead">Vom 1. bis 24. Dezember öffnet sich jeden Tag ein Türchen mit einem Süßigkeiten-Fakt oder einer Themenwelt zum Stöbern.</p>
<div class="countdown" aria-live="polite"><div><b data-cd="d">–</b><small>Tage</small></div><div><b data-cd="h">–</b><small>Std</small></div>
<div><b data-cd="m">–</b><small>Min</small></div><div><b data-cd="s">–</b><small>Sek</small></div></div>
<p class="amsg" aria-live="polite"></p></section><div class="fall" aria-hidden="true"></div>
<section style="padding-top:10px"><div class="doors">{doors}</div><div class="result adv" aria-live="polite" hidden></div></section>
<script type="application/json" id="adv-data">{content}</script>"""


EXTRA_CSS = """
.passbook{background:#FFF7EC;border-radius:var(--r);padding:20px;box-shadow:var(--sh);border:2px solid #E9DCC6;position:relative}
.passbook:before{content:"";position:absolute;left:14px;top:14px;bottom:14px;width:6px;border-radius:3px;background:repeating-linear-gradient(#E9DCC6 0 8px,transparent 8px 14px)}
.passhead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding-left:12px}
.passhead h2{margin:0 0 4px}.pcount{font:28px Anton,sans-serif;color:var(--vio);white-space:nowrap}
.stamps{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0 12px;padding-left:12px}
@media(min-width:700px){.stamps{grid-template-columns:repeat(6,1fr)}}
.stamp-slot{display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px 6px;border:2px dashed #E0D2B8;border-radius:16px;text-decoration:none;
color:var(--mut);font-weight:700;text-align:center}
.stamp-slot .stk{filter:grayscale(1);opacity:.35;transition:all .3s}
.stamp-slot small{font-size:11.5px;line-height:1.2}
.stamp-slot.got{border-style:solid;border-color:var(--vio2);color:var(--fg);background:#fff}
.stamp-slot.got .stk{filter:none;opacity:1;transform:rotate(-8deg)}
.pactions{display:flex;gap:14px;align-items:center;padding-left:12px}
.toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%) translateY(120%);background:var(--fg);color:#fff;border-radius:16px;padding:12px 16px;
font-weight:800;z-index:60;display:flex;gap:10px;align-items:center;box-shadow:0 12px 30px rgba(43,35,80,.35);transition:transform .35s cubic-bezier(.2,1.4,.4,1)}
.toast.on{transform:translateX(-50%) translateY(0)}.toast .stk{width:34px;height:34px;transform:rotate(-8deg)}
.doors{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
@media(min-width:700px){.doors{grid-template-columns:repeat(6,1fr)}}
.doors{perspective:900px}
.door{aspect-ratio:1;border:0;border-radius:16px;background:var(--c);color:#fff;font:34px Anton,sans-serif;cursor:pointer;position:relative;overflow:hidden;
box-shadow:inset 0 0 0 4px rgba(255,255,255,.35),var(--sh);text-shadow:0 2px 0 rgba(43,35,80,.25);transition:transform .5s cubic-bezier(.2,1.2,.4,1)}
.door:before,.door:after{content:"";position:absolute;background:rgba(255,255,255,.55)}
.door:before{left:50%;top:0;bottom:0;width:8px;margin-left:-4px}.door:after{top:50%;left:0;right:0;height:8px;margin-top:-4px}
.door .num{position:relative;z-index:1;background:var(--c);padding:0 6px;border-radius:8px}
.door .lock{position:absolute;right:6px;bottom:4px;font-size:13px;font-style:normal;z-index:1;display:none}
.door.big{grid-column:span 2;aspect-ratio:auto;font-size:44px}
.door[disabled]{filter:saturate(.45);opacity:.6;cursor:default}.door[disabled] .lock{display:block}
.door.today{animation:todayglow 1.6s ease-in-out infinite}
@keyframes todayglow{50%{box-shadow:inset 0 0 0 4px #fff,0 0 0 4px var(--c),0 0 26px var(--c)}}
.door.open{background:#fff;color:var(--c);box-shadow:inset 0 0 0 3px var(--c);transform:rotateY(-18deg)}
.door.open:before,.door.open:after{background:transparent}.door.open .num{background:#fff}
.door:not([disabled]):hover{transform:translateY(-3px) rotate(-2deg)}
.countdown{display:flex;gap:10px;margin:4px 0 6px}
.countdown div{background:#fff;border-radius:14px;padding:8px 12px;text-align:center;min-width:64px;box-shadow:var(--sh)}
.countdown b{display:block;font:30px/1 Anton,sans-serif;color:var(--vio)}.countdown small{font-weight:700;color:var(--mut);font-size:12px}
.fall{position:fixed;inset:0;pointer-events:none;z-index:-1;overflow:hidden;opacity:.6}
.fall i{position:absolute;top:-20px;width:22px;height:7px;border-radius:4px;opacity:.75;animation:fall linear infinite}
@keyframes fall{to{transform:translateY(110vh) rotate(540deg)}}
@media(prefers-reduced-motion:reduce){.fall{display:none}.door.today{animation:none}}
.amsg{font-weight:800;color:var(--vio)}
.result.adv{margin-top:16px;background:#fff;border-left:8px solid var(--c)}
.advteaser{display:flex;gap:14px;align-items:center;background:linear-gradient(135deg,#2FAE7E,#1F8A62);color:#fff;border-radius:var(--r);padding:18px;text-decoration:none}
.advteaser h2{color:#fff;margin:0}.advteaser p{margin:4px 0 0;color:#E6FFF4}.advteaser .stk{flex:none}
"""

ADVENT_JS = r"""<script>
(function(){
var data=JSON.parse(document.getElementById('adv-data').textContent),now=new Date(),dec=now.getMonth()===11,today=now.getDate(),
 msg=document.querySelector('.amsg'),res=document.querySelector('.result.adv');
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
var cdEl=document.querySelector('.countdown');
function tickCd(){var n=new Date(),y=n.getMonth()===11?n.getFullYear()+1:n.getFullYear(),diff=new Date(y,11,1)-n;
 if(dec&&today<=24){cdEl.hidden=true;return}
 var q=function(k,v){cdEl.querySelector('[data-cd='+k+']').textContent=v};
 q('d',Math.floor(diff/864e5));q('h',Math.floor(diff/36e5)%24);q('m',Math.floor(diff/6e4)%60);q('s',Math.floor(diff/1e3)%60)}
tickCd();setInterval(tickCd,1000);
if(!matchMedia('(prefers-reduced-motion: reduce)').matches){var fl=document.querySelector('.fall'),cols=['#FF4D8D','#FFB547','#3DDC97','#8B6CFF','#3D8BFF'];
 for(var k=0;k<18;k++){var f=document.createElement('i');f.style.left=Math.random()*100+'%';f.style.background=cols[k%5];
  f.style.animationDuration=(9+Math.random()*9)+'s';f.style.animationDelay=(-Math.random()*15)+'s';fl.appendChild(f)}}
msg.textContent=dec?(today<=24?'Heute ist Türchen '+today+' dran.':'Alle Türchen sind offen. Frohe Weihnachten!'):'Der Kalender startet am 1. Dezember. Bis dahin sind alle Türchen zu.';
document.querySelectorAll('.door').forEach(function(d){var n=+d.dataset.day,ok=dec&&n<=today;d.disabled=!ok;
 if(dec&&n===today)d.classList.add('today');
 if(!ok)d.setAttribute('aria-label','Türchen '+n+', noch zu');
 d.addEventListener('click',function(){var i=data[n];if(!i)return;d.classList.add('open');
  res.style.setProperty('--c',getComputedStyle(d).getPropertyValue('--c'));res.hidden=false;res.classList.add('has');
  var pic=i.img?'<img src="'+esc(i.img)+'" alt="">':(i.svg||'');
  res.innerHTML='<div class="ri2">'+pic+'</div><div><small>Türchen '+n+' · '+esc(i.s)+'</small><h3>'+esc(i.t)+'</h3><div class="acts"><a class="btn dark" href="'+esc(i.u)+'">Ansehen</a></div></div>';
  res.scrollIntoView({behavior:'smooth',block:'nearest'})})});
})();
</script>"""


# ---------- Weltkarte, Geschenk-Finder, Snack-Typ-Quiz, Teilen-Bilder ----------
# Karte: Punkte-Weltkarte aus Natural-Earth-Daten (gemeinfrei, via world-atlas, ISC), liegt als static/worldmap.svg.
# (Länge, Breite, Seite des Namensschilds: b=unten, t=oben, l=links, r=rechts)
MAP_PINS = {"japan": (138, 37, "r"), "usa": (-100, 41, "t"), "mexiko": (-102, 21, "b"), "italien": (15, 40, "r"),
            "schweiz": (3, 49, "l"), "skandinavien": (16, 63, "t")}


def map_html():
    pins = ""
    for cid, pos in MAP_PINS.items():
        if not pos or cid not in cat_by_id:
            continue
        c = cat_by_id[cid]
        n = len(cat_items(c))
        x, y = (pos[0] + 180) / 360 * 100, (82 - pos[1]) / 138 * 100
        pins += (f'<a class="pin s-{pos[2]}" href="/kategorie/{cid}/" style="left:{x:.1f}%;top:{y:.1f}%;--c:{cat_color[cid]}">{sticker(cid, 34)}'
                 f'<span class="pl">{e(c["name"])}<small>{f"{n} Sorten" if n > 1 else ("1 Sorte" if n else "bald")}</small></span></a>')
    return (f'<section id="karte"><div class="head"><h2>Süßigkeiten-Weltkarte</h2><a class="more" href="/shop/">Alle Themenwelten</a></div>'
            f'<div class="map"><div class="mapin"><img src="/static/worldmap.svg" alt="" width="1000" height="440" loading="lazy">{pins}</div></div>'
            f'<p class="wl">Tippe auf ein Land, um seine Themenwelt zu öffnen. Am Handy kannst du die Karte wischen. Kartendaten: Natural Earth.</p></section>')


def explore_html():
    items = [("🎡", "Zufalls-Rad", "/#zufall"), ("🎁", "Geschenk-Finder", "/geschenk/"), ("🧠", "Snack-Typ-Quiz", "/quiz/"),
             ("🗺️", "Weltkarte", "/#karte"), ("🛂", "Dein Naschpass", "/#pass"), ("🎄", "Adventskalender", "/advent/")]
    return ('<nav class="explore" aria-label="Entdecken">' + "".join(
        f'<a href="{u}"><span aria-hidden="true">{i}</span>{t}</a>' for i, t, u in items) + '</nav>')


def _opt_btn(q, v, label, icon):
    return f'<button class="qopt" type="button" data-q="{q}" data-v="{v}">{icon}<span>{e(label)}</span></button>'


def finder_page():
    land_opts = [("asien", "Japan & Asien", "japan"), ("usa", "USA", "usa"), ("italien", "Italien", "italien"),
                 ("schweiz", "Schweiz", "schweiz"), ("mexiko", "Mexiko", "mexiko"), ("skandinavien", "Skandinavien", "skandinavien")]
    q1 = "".join(_opt_btn("anlass", v, l, f'<span class="emo">{i}</span>') for v, l, i in
                 [("weihnachten", "Zu Weihnachten", "🎄"), ("mitbringsel", "Mitbringsel & Geburtstag", "🎁"), ("ich", "Für mich selbst", "😋")])
    q2 = "".join(_opt_btn("geschmack", v, l, f'<span class="emo">{i}</span>') for v, l, i in
                 [("schoko", "Schokoladig", "🍫"), ("sauer", "Sauer", "🍋"), ("scharf", "Scharf", "🌶️"), ("salzig", "Salzig", "🧂"),
                  ("fruchtig", "Fruchtig", "🍓"), ("", "Egal, Hauptsache lecker", "🤷")])
    q3 = "".join(_opt_btn("land", v, l, sticker(s, 40)) for v, l, s in land_opts) + _opt_btn("land", "", "Egal, überrasch mich", '<span class="emo">🌍</span>')
    return f"""<section class="hero" style="padding-bottom:0">{SPRINKLES}<h1>Geschenk-<span class="acc">Finder</span></h1>
<p class="lead">Drei Fragen, dann zeigen wir dir passende Süßigkeiten und Themenwelten. Es wird nichts gespeichert.</p></section>
<section class="quiz" id="finder" style="padding-top:12px">
<div class="qstep" data-step="1"><h2>1. Wofür suchst du?</h2><div class="qgrid">{q1}</div></div>
<div class="qstep" data-step="2" hidden><h2>2. Welcher Geschmack?</h2><div class="qgrid">{q2}</div></div>
<div class="qstep" data-step="3" hidden><h2>3. Woher darf es sein?</h2><div class="qgrid">{q3}</div></div>
<div class="qres" hidden></div></section>"""


QUIZ_TYPES = {
    "schoko": ("Schoko-Genießer", "🍫", "#8B5A3C", "Du nimmst lieber ein richtig gutes Stück Schokolade als eine ganze Tüte irgendwas. Pralinen, Tafeln aus der Schweiz und Italien sind deine Welt.", "/kategorie/schokolade/"),
    "sauer": ("Sauer-Abenteurer", "🍋", "#E6B800", "Je saurer, desto besser. Extrem saure Bonbons sind für dich kein Risiko, sondern eine Einladung.", "/shop/?geschmack=sauer#alle"),
    "scharf": ("Chili-Held", "🌶️", "#E8384F", "Süß allein ist dir zu langweilig. Chili, Limette und Tamarinde wie in Mexiko machen dich glücklich.", "/kategorie/mexiko/"),
    "exot": ("Weltreisender", "🌏", "#3D8BFF", "Du willst probieren, was es hier nicht gibt: limitierte Sorten aus Japan, Snacks aus Korea und alles, was ungewöhnlich klingt.", "/kategorie/japan/"),
    "frucht": ("Fruchtgummi-Fan", "🐻", "#FF4D8D", "Bunt, fruchtig, zum Teilen (oder auch nicht): Fruchtgummi aus Skandinavien und dem Rest der Welt ist dein Ding.", "/shop/?art=gummi#alle"),
    "salzig": ("Salzig-Snacker", "🥨", "#2FAE7E", "Knuspern muss es: Chips, Brezeln und Salzlakritz schlagen bei dir jede Schokolade.", "/shop/?geschmack=salzig#alle"),
}
QUIZ_QS = [
    ("Filmabend: Wonach greifst du?", [("Schokolade", "🍫", {"schoko": 2}), ("Chips", "🥨", {"salzig": 2}),
                                       ("Fruchtgummi", "🐻", {"frucht": 2}), ("Etwas, das ich noch nie probiert habe", "❓", {"exot": 2})]),
    ("Wie scharf darf es sein?", [("Gar nicht", "🙅", {"schoko": 1, "frucht": 1}), ("Ein bisschen", "🙂", {"salzig": 1, "exot": 1}),
                                  ("So scharf es geht", "🔥", {"scharf": 3})]),
    ("Saure Bonbons?", [("Je saurer, desto besser", "🍋", {"sauer": 3}), ("Geht so", "😐", {"frucht": 1}), ("Nein danke", "🙈", {"schoko": 1, "salzig": 1})]),
    ("Spontanreise: Wohin?", [("Tokio", "🗼", {"exot": 2}), ("Mexiko-Stadt", "🌮", {"scharf": 2}), ("Rom", "🍝", {"schoko": 1, "frucht": 1}),
                              ("Stockholm", "🛶", {"salzig": 1, "sauer": 1, "frucht": 1})]),
    ("Dein Snack-Motto?", [("Genuss statt Masse", "✨", {"schoko": 2}), ("Hauptsache Abenteuer", "🧭", {"exot": 1, "scharf": 1, "sauer": 1}),
                           ("Knuspern muss es", "😋", {"salzig": 2}), ("Bunt und fruchtig", "🌈", {"frucht": 2})]),
]


def quiz_page():
    steps = ""
    for k, (q, opts) in enumerate(QUIZ_QS):
        btns = "".join(f'<button class="qopt" type="button" data-pts=\'{json.dumps(pts)}\'><span class="emo">{ic}</span><span>{e(t)}</span></button>'
                       for t, ic, pts in opts)
        steps += f'<div class="qstep" data-step="{k + 1}"{"" if k == 0 else " hidden"}><h2>{k + 1}. {e(q)}</h2><div class="qgrid">{btns}</div></div>'
    types = json.dumps({k: {"n": v[0], "i": v[1], "c": v[2], "t": v[3], "u": v[4]} for k, v in QUIZ_TYPES.items()}, ensure_ascii=False)
    return f"""<section class="hero" style="padding-bottom:0">{SPRINKLES}<h1>Welcher <span class="acc">Snack-Typ</span> bist du?</h1>
<p class="lead">Fünf Fragen, ein Ergebnis, passende Süßigkeiten dazu. Nur zum Spaß, es wird nichts gespeichert.</p>
<div class="qbar"><i></i></div></section>
<section class="quiz" id="quiz" style="padding-top:12px">{steps}<div class="qres" hidden></div></section>
<script type="application/json" id="quiz-types">{types}</script>"""


EXTRA_CSS2 = """
.explore{display:flex;gap:8px;overflow-x:auto;padding:4px 16px 6px;margin:18px -16px 0;scrollbar-width:none}
.explore::-webkit-scrollbar{display:none}
.explore a{flex:none;display:flex;align-items:center;gap:7px;background:#fff;border-radius:999px;padding:9px 14px;font-weight:800;font-size:14px;
color:var(--fg);text-decoration:none;box-shadow:var(--sh)}.explore a:hover{outline:2px solid var(--vio2)}.explore span{font-size:18px}
.map{background:#fff;border-radius:var(--r);padding:12px;box-shadow:var(--sh);overflow-x:auto;scrollbar-width:thin}
.mapin{position:relative;min-width:680px}.map img{width:100%;height:auto;display:block}
.pin{position:absolute;transform:translate(-50%,-50%);display:block;text-decoration:none;color:var(--fg);z-index:1}
.pin .pl{position:absolute;left:50%;top:100%;transform:translateX(-50%)}
.pin.s-t .pl{top:auto;bottom:100%;margin:0 0 3px}.pin.s-l .pl{left:auto;right:100%;top:50%;transform:translateY(-50%);margin:0 4px 0 0}
.pin.s-r .pl{left:100%;top:50%;transform:translateY(-50%);margin:0 0 0 4px}
.pin .stk{width:30px;height:30px;filter:drop-shadow(0 3px 4px rgba(43,35,80,.3));transition:transform .2s}
.pin:hover .stk,.pin:focus .stk{transform:scale(1.25) rotate(-8deg)}
.pin .pl{margin-top:3px;background:#fff;border-radius:8px;padding:2px 6px;font-size:11px;font-weight:800;white-space:nowrap;box-shadow:var(--sh);text-align:center;line-height:1.2}
.pin .pl small{display:block;font-weight:600;color:var(--mut);font-size:10px}
@media(max-width:600px){.pin .pl small{display:none}.pin .stk{width:26px;height:26px}}
.pin:hover{z-index:2}
.qstep h2{font-size:clamp(24px,5.5vw,34px)}
.qgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
@media(min-width:760px){.qgrid{grid-template-columns:repeat(3,1fr)}}
.qopt{display:flex;flex-direction:column;align-items:center;gap:8px;border:0;background:#fff;border-radius:18px;padding:16px 10px;font:inherit;
font-weight:800;color:var(--fg);cursor:pointer;box-shadow:var(--sh);transition:transform .15s}
.qopt:hover{transform:translateY(-2px);outline:2px solid var(--vio2)}.qopt .stk{width:40px;height:40px}
.qopt.sel{background:var(--fg);color:#fff}
.qbar{height:8px;background:#fff;border-radius:4px;max-width:520px;overflow:hidden}.qbar i{display:block;height:100%;width:0;background:var(--vio);transition:width .3s}
.qres{animation:pop .4s cubic-bezier(.2,1.5,.4,1)}
@keyframes pop{from{transform:scale(.9);opacity:0}}
.qtype{background:var(--c);color:#fff;border-radius:var(--r);padding:22px;text-align:center;margin-bottom:16px}
.qtype .big{font-size:72px;line-height:1}.qtype h2{color:#fff;margin:6px 0}.qtype p{max-width:52ch;margin:0 auto 14px;color:#fff}
.qtype .btns{justify-content:center}.qtype .btn{background:#fff;color:var(--fg)}
.badge-cta{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:linear-gradient(135deg,#8B6CFF,#FF4D8D);color:#fff;border-radius:16px;padding:14px;margin:0 0 12px 12px}
.badge-cta b{font-size:17px}.badge-cta .btn{background:#fff;color:var(--fg)}
"""

SHARE_JS = r"""<script>
/* Teilen-Bild im Browser malen (nichts wird hochgeladen) */
window.npCard=async function(o){
 try{await document.fonts.load('80px Anton')}catch(e){}
 var c=document.createElement('canvas');c.width=1080;c.height=1350;var x=c.getContext('2d');
 var g=x.createLinearGradient(0,0,1080,1350);g.addColorStop(0,'#2B2350');g.addColorStop(1,o.color||'#6248E8');x.fillStyle=g;x.fillRect(0,0,1080,1350);
 var cols=['#FF4D8D','#FFB547','#3DDC97','#8B6CFF','#FFF7EC'];for(var k=0;k<40;k++){x.save();x.translate(Math.random()*1080,Math.random()*1350);
  x.rotate(Math.random()*6);x.fillStyle=cols[k%5];x.globalAlpha=.55;x.beginPath();x.roundRect?x.roundRect(-22,-7,44,14,7):x.rect(-22,-7,44,14);x.fill();x.restore()}
 x.textAlign='center';x.fillStyle='#FFF7EC';x.font='54px Anton, Impact, sans-serif';x.fillText((o.kicker||'').toUpperCase(),540,190);
 if(o.imgs&&o.imgs.length){var n=o.imgs.length,cols2=Math.min(3,n),sz=200,gap=40,rows=Math.ceil(n/cols2);
  for(var i=0;i<n;i++){var r=Math.floor(i/cols2),cc=i%cols2,inRow=Math.min(cols2,n-r*cols2),w=inRow*sz+(inRow-1)*gap;
   var im=await new Promise(function(res){var m=new Image();m.onload=function(){res(m)};m.onerror=function(){res(null)};m.src=o.imgs[i]});
   if(im){x.save();x.translate(540-w/2+cc*(sz+gap)+sz/2,330+r*(sz+gap)+sz/2);x.rotate(-.12+Math.random()*.24);x.drawImage(im,-sz/2,-sz/2,sz,sz);x.restore()}}}
 else{x.font='260px serif';x.fillText(o.emoji||'🍬',540,560)}
 x.fillStyle='#FFD23F';x.font='110px Anton, Impact, sans-serif';
 var words=(o.title||'').toUpperCase().split(' '),line='',y=o.imgs?900:820,lines=[];
 words.forEach(function(w){var t=line?line+' '+w:w;if(x.measureText(t).width>960&&line){lines.push(line);line=w}else line=t});lines.push(line);
 lines.forEach(function(l,k){x.fillText(l,540,y+k*118)});
 x.fillStyle='#FFF7EC';x.font='bold 40px Inter, sans-serif';x.fillText(o.sub||'',540,y+lines.length*118+30);
 x.font='bold 36px Inter, sans-serif';x.fillStyle='#CFC9E8';x.fillText('naschpass.oneflowsolution.de',540,1270);
 var blob=await new Promise(function(r){c.toBlob(r,'image/png')}),file=new File([blob],'naschpass.png',{type:'image/png'});
 if(navigator.canShare&&navigator.canShare({files:[file]})){try{await navigator.share({files:[file],text:o.text||''});return}catch(e){return}}
 var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='naschpass.png';document.body.appendChild(a);a.click();a.remove()};
window.npSvgUrl=function(svg){var s=svg.cloneNode(true);s.setAttribute('xmlns','http://www.w3.org/2000/svg');s.setAttribute('width','200');s.setAttribute('height','200');
 return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(s.outerHTML)};
</script>"""

PASS_SHARE_JS = r"""<script>
(function(){var pb=document.getElementById('pass');if(!pb)return;var slots=pb.querySelectorAll('[data-s]'),cta=document.createElement('div');
 cta.className='badge-cta';cta.hidden=true;pb.querySelector('.stamps').before(cta);
 function upd(){var got=pb.querySelectorAll('.stamp-slot.got'),all=got.length===slots.length&&slots.length>0;cta.hidden=!got.length;
  cta.innerHTML=all?'<b>🌍 Geschafft: Naschpass-Weltreisender!</b><button class="btn" type="button">Abzeichen teilen</button>'
   :'<b>'+got.length+' von '+slots.length+' Stempeln</b><button class="btn" type="button">Pass teilen</button>';
  cta.querySelector('button').onclick=function(){var imgs=[].map.call(got,function(g){return npSvgUrl(g.querySelector('svg'))});
   npCard({kicker:all?'Abzeichen freigeschaltet':'Mein Naschpass',title:all?'Weltreisender':got.length+' von '+slots.length+' Ländern',
    sub:all?'Alle Länder-Stempel gesammelt':'Süßigkeiten aus aller Welt entdeckt',imgs:imgs,color:'#8B6CFF',
    text:all?'Ich bin Naschpass-Weltreisender 🌍🍬':'Mein Naschpass: '+got.length+'/'+slots.length+' Länder 🍬'})}}
 upd();new MutationObserver(upd).observe(pb,{subtree:true,attributes:true,attributeFilter:['class']})})();
</script>"""

FINDER_JS = r"""<script>
(function(){var root=document.getElementById('finder'),ans={},data=null;
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
root.addEventListener('click',async function(ev){var b=ev.target.closest('.qopt');if(!b)return;
 var st=b.closest('.qstep'),n=+st.dataset.step;ans[b.dataset.q]=b.dataset.v;st.querySelectorAll('.qopt').forEach(function(x){x.classList.toggle('sel',x===b)});
 var next=root.querySelector('[data-step="'+(n+1)+'"]');if(next){next.hidden=false;next.scrollIntoView({behavior:'smooth',block:'center'});return}
 data=data||await fetch('/search.json').then(function(r){return r.json()});
 var prods=data.items.filter(function(i){return i.type==='product'}),has=function(i,k){return (' '+i.f+' ').indexOf(' '+k+' ')>=0};
 var want=[];if(ans.geschmack)want.push('geschmack:'+ans.geschmack);if(ans.land)want.push('land:'+ans.land);
 if(ans.anlass!=='ich')want.push('art:boxen');
 var scored=prods.map(function(i){return [i,want.filter(function(w){return has(i,w)}).length]}).filter(function(x){return x[1]>0||!want.length})
  .sort(function(a,b){return b[1]-a[1]}).slice(0,6).map(function(x){return x[0]});
 var ok=window.npImgOK&&window.npImgOK(),themes=[];
 if(ans.anlass==='weihnachten')themes.push(['/kategorie/weihnachten/','Weihnachten & Geschenke']);
 if(ans.anlass==='mitbringsel')themes.push(['/kategorie/boxen/','Boxen & Geschenke']);
 var lt={asien:['/kategorie/japan/','Japan & Asien'],usa:['/kategorie/usa/','USA'],italien:['/kategorie/italien/','Italien'],schweiz:['/kategorie/schweiz/','Schweiz'],
  mexiko:['/kategorie/mexiko/','Mexiko'],skandinavien:['/kategorie/skandinavien/','Skandinavien']};if(lt[ans.land])themes.push(lt[ans.land]);
 if(ans.geschmack==='sauer'||ans.geschmack==='scharf')themes.push(['/kategorie/sauer-scharf/','Sauer & scharf']);
 if(ans.geschmack==='schoko')themes.push(['/kategorie/schokolade/','Schokolade & Pralinen']);
 var q=[];if(ans.geschmack)q.push('geschmack='+ans.geschmack);if(ans.land)q.push('land='+ans.land);
 var cards=scored.map(function(i){var im=i.img||(i.ext&&ok?i.ext:'');return '<a class="hit" href="'+esc(i.url)+'" rel="sponsored noopener" target="_blank"><span class="th">'
  +(im?'<img class="ct" src="'+esc(im)+'" alt="">':(i.svg||''))+'</span><span><b>'+esc(i.title)+'*</b><span>'+esc(i.sub||'')+'</span></span></a>'}).join('');
 var res=root.querySelector('.qres');res.hidden=false;
 res.innerHTML='<h2>Unsere Vorschläge</h2>'+(cards?cards+'<p class="wl">* Werbelink</p>':
  '<div class="slot main"><span class="emo">🤝</span><div><strong>Noch keine passenden Produkte</strong><p>Wir nehmen gerade neue Partner-Shops auf. Bis dahin findest du hier die passenden Themenwelten.</p></div></div>')
  +'<div class="btns" style="margin-top:14px">'+themes.map(function(t){return '<a class="btn dark" href="'+t[0]+'">'+esc(t[1])+'</a>'}).join('')
  +'<a class="btn" style="border:2px solid var(--fg)" href="/shop/'+(q.length?'?'+q.join('&'):'')+'#alle">Im Shop filtern</a>'
  +'<button class="btn" type="button" style="border:2px solid var(--fg)" onclick="location.reload()">Nochmal</button></div>';
 res.scrollIntoView({behavior:'smooth',block:'start'})});
})();
</script>"""

QUIZ_JS = r"""<script>
(function(){var root=document.getElementById('quiz'),T=JSON.parse(document.getElementById('quiz-types').textContent),pts={},steps=root.querySelectorAll('.qstep'),
 bar=document.querySelector('.qbar i');
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
root.addEventListener('click',function(ev){var b=ev.target.closest('.qopt');if(!b)return;var st=b.closest('.qstep'),n=+st.dataset.step;
 var p=JSON.parse(b.dataset.pts);Object.keys(p).forEach(function(k){pts[k]=(pts[k]||0)+p[k]});bar.style.width=(n/steps.length*100)+'%';
 st.hidden=true;var next=root.querySelector('[data-step="'+(n+1)+'"]');if(next){next.hidden=false;return}
 var best=Object.keys(T).sort(function(a,b){return (pts[b]||0)-(pts[a]||0)})[0],t=T[best],res=root.querySelector('.qres');res.hidden=false;
 res.innerHTML='<div class="qtype" style="--c:'+t.c+'"><div class="big">'+t.i+'</div><small>Dein Snack-Typ</small><h2>'+esc(t.n)+'</h2><p>'+esc(t.t)+'</p>'
  +'<div class="btns"><a class="btn" href="'+t.u+'">Passende Süßigkeiten</a><button class="btn" type="button" data-share>Ergebnis teilen</button>'
  +'<button class="btn" type="button" onclick="location.reload()">Nochmal</button></div></div>';
 res.querySelector('[data-share]').onclick=function(){npCard({kicker:'Mein Snack-Typ',title:t.n,emoji:t.i,sub:'Welcher bist du?',color:t.c,
  text:'Mein Snack-Typ: '+t.n+' '+t.i+' Welcher bist du? '+location.origin+'/quiz/'})}});
})();
</script>"""


def cat_tile(c):
    items = cat_items(c)
    n = f'<span class="n">{len(items)} {"Sorte" if len(items) == 1 else "Sorten"}</span>' if items else '<span class="n soon">Produkte folgen</span>'
    return (f'<a class="cat" href="/kategorie/{c["id"]}/" style="--c:{cat_color[c["id"]]}">{sticker(c["id"])}'
            f'<h3>{e(c["name"])}</h3><p>{e(c["teaser"])}</p>{n}</a>')


def band(live, title_prod="Unsere Empfehlungen", title_post="Neu auf Naschpass"):
    """Laufband: empfohlene Produkte (featured), sonst die neuesten Produkte, sonst die neuesten Posts."""
    feat = [p for p in products if p.get("featured")] or products[:12]
    if len(feat) >= 6:
        cells = []
        for p in feat:
            pic = pic_html(p, 340, "", p.get("category", ""))
            cells.append(f'<a class="ri" href="{e(p["url"])}" rel="sponsored noopener" target="_blank"><div class="im">{pic}</div>'
                         f'<div class="tx"><b>{e(p["name"])}*</b><span>{e(p.get("shop", ""))}</span></div></a>')
        title, foot = title_prod, '<p class="wl" style="margin-top:0">* Werbelink</p>'
    else:
        cells = [f'<a class="ri post" href="/p/{p["id"]}/"><div class="im">'
                 f'{slide_img(cover_url(p), "", 170, "168px")}</div>'
                 f'<div class="tx"><b>#{p["id"]} {e(p.get("short", ""))}</b><span>{e(p.get("tag", ""))}</span></div></a>'
                 for p in list(reversed(live))[:10]]
        title, foot = title_post, ""
    if not cells:
        return ""
    # Inhalt doppelt, damit das Band endlos weiterlaufen kann (die Kopie ist für Screenreader versteckt)
    dup = "".join(cells).replace('<a class="ri', '<a tabindex="-1" aria-hidden="true" class="ri')
    return (f'<section class="recs"><div class="head"><h2>{title}</h2></div>'
            f'<div class="band" data-shuffle>{"".join(cells)}{dup}</div>{foot}</section>')


def search_index(live):
    items = []
    for p in products:
        cid = p.get("category", "")
        cname = cat_by_id.get(cid, {}).get("name", "")
        ii = prod_img(p, 120)
        items.append({"type": "product", "title": p["name"], "url": p["url"],
                      "img": ii[1] if ii and ii[0] == "own" else "", "ext": ii[1] if ii and ii[0] == "ext" else "",
                      "svg": "" if ii and ii[0] == "own" else sticker(cid, 52),
                      "sub": " · ".join(x for x in (p.get("shop", ""), cname) if x),
                      "alt": translit(p["name"]), "tags": " ".join([cname, cid] + p.get("tags", [])),
                      "text": p.get("note", ""),
                      "f": " ".join(f"{g}:{i}" for g, v in facets(p).items() for i in sorted(v))})
    for c in cats:
        items.append({"type": "cat", "title": c["name"], "url": f"/kategorie/{c['id']}/", "svg": sticker(c["id"], 52),
                      "sub": c["teaser"], "alt": translit(c["name"]), "tags": c["id"].replace("-", " "), "text": c["teaser"]})
    for p in reversed(live):
        txt = " ".join([p.get("sub", "")] + [plain(s.get("title", "")) + " " + s.get("body", "") for s in p.get("slides", [])])
        items.append({"type": "post", "id": p["id"], "title": f"#{p['id']} {p['hook'].replace('*', '')}", "url": f"/p/{p['id']}/",
                      "img": cdn(f"/p/{p['id']}/01.jpg", 120) if ON_NETLIFY else f"/p/{p['id']}/01.jpg",
                      "sub": p.get("tag", ""), "alt": translit(p.get("short", "")),
                      "tags": " ".join([p.get("tag", ""), p.get("short", "")] + p.get("hashtags", [])), "text": txt})
    sugg = [c["name"] for c in cats[:4]] + ["KitKat", "Farbstoffe"]  # feste Vorschläge, keine Auswertung
    fac = [{"g": g["id"], "gn": g["name"], "id": o["id"], "name": o["name"],
            "kw": sorted({translit(k) for k in o.get("keywords", []) + [o["name"], o["id"]] if len(k) >= 3})}
           for g in FILTER for o in g["options"]]
    cnt = facet_counts()
    sugg = [o["name"] for g in FILTER for o in sorted(g["options"], key=lambda o: -cnt.get((g["id"], o["id"]), 0))[:3]
            if cnt.get((g["id"], o["id"]))]
    return {"items": items, "sugg": sugg, "facets": fac}


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(HERE / "static", DIST / "static")
    if DEMO:
        shutil.copytree(HERE / "demo", DIST / "static" / "demo")
    live = [p for p in posts if (ROOT / "fertige_posts" / post_folder(p)).exists()]

    # --- Kategorie-Seiten
    for c in cats:
        items = cat_items(c)
        inner = (f'<div class="tools"><span></span>{view_toggle("g-cat", ["big", "small", "list"], "small")}</div>'
                 + prod_grid(items, "g-cat")) if items else (
            f'<div class="slots"><div class="slot main"><span class="emo">🤝</span><div><strong>Partner-Platz frei</strong>'
            f'<p>Hier erscheinen Produkte zum Thema {e(c["name"])}, sobald ein passender Partner-Shop freigeschaltet ist.'
            + (' Bis dahin findest du unten die passenden Posts.' if c.get("posts") else '')
            + '</p><a class="more" href="/ueber/#partner">Du hast einen Shop oder eine Marke? Für Partner</a></div></div>'
            '<div class="slot ghost" aria-hidden="true"></div><div class="slot ghost" aria-hidden="true"></div></div>')
        rel = [p for p in live if p["id"] in c.get("posts", [])
               or any(x.get("post") == p["id"] and in_cat(x, c) for x in products)]
        rel_html = (f'<section><h2>Passende Posts</h2><div class="grid posts v-small">{"".join(post_card(p) for p in rel)}</div></section>'
                    if rel else "")
        others = "".join(f'<a class="sc" href="/kategorie/{o["id"]}/">{sticker(o["id"], 34)}{e(o["name"])}</a>'
                         for o in cats if o["id"] != c["id"])
        write(f"kategorie/{c['id']}/index.html", page(
            f"{c['name']} – Naschpass",
            f'<a class="back" href="/shop/">← Zum Shop</a>'
            f'<section style="padding-top:14px"><div style="display:flex;align-items:center;gap:14px;margin-bottom:6px">{sticker(c["id"], 64)}'
            f'<h1 style="margin:0">{e(c["name"])}</h1></div><p class="lead">{e(c.get("text") or c["teaser"])}</p>{inner}</section>{rel_html}'
            f'<section><h2>Mehr entdecken</h2><div class="stickers">{others}</div></section>'
            + ('<section><a class="advteaser" href="/advent/">' + sticker("weihnachten", 56) + '<div><h2>Adventskalender</h2>'
               '<p>Vom 1. bis 24. Dezember jeden Tag ein Türchen.</p></div></a>'
               '<p style="margin-top:12px"><a class="btn dark" href="/geschenk/">🎁 Geschenk-Finder: passende Süßigkeiten in 3 Fragen</a></p></section>'
               if c["id"] in ("weihnachten", "boxen") else ""),
            c["teaser"], f"/kategorie/{c['id']}/", stamp=c["id"]))

    # --- Post-Seiten
    for k, p in enumerate(live):
        folder = ROOT / "fertige_posts" / post_folder(p)
        dest = DIST / "p" / p["id"]
        dest.mkdir(parents=True, exist_ok=True)
        imgs = sorted(folder.glob("[0-9][0-9].jpg"))
        for x in imgs:
            shutil.copy(x, dest / x.name)
        c = tag_color(p.get("tag", ""))
        items = [x for x in products if str(x.get("post", "")) == p["id"]]
        # Passt zum Thema: Produkte, die Herkunft/Art/Geschmack mit dem Post teilen (automatisch, wird mit den Feeds voller)
        pf = facets({"name": p.get("short", ""), "note": " ".join([p.get("hook", ""), p.get("sub", "")] +
                     [x.get("title", "") + " " + x.get("body", "") for x in p.get("slides", [])]), "tags": [p.get("tag", "")]})
        def _score(x):
            xf = facets(x)
            return sum((2 if g == "land" else 1) * len((pf.get(g, set()) - {"europa", "asien"}) & xf.get(g, set())) for g in pf)
        auto = sorted([x for x in products if x not in items and _score(x) >= 2], key=lambda x: -_score(x))[:8]
        auto_html = (f'<section><div class="head"><h2>Passt zum Thema</h2></div>{prod_grid(auto, "g-auto")}</section>') if auto else ""
        prods = (f'<section id="produkte"><div class="head"><h2>Die Süßigkeiten aus dem Post</h2>'
                 f'{view_toggle("g-post", ["big", "small", "list"], "small")}</div>{prod_grid(items, "g-post")}</section>{auto_html}') if items else auto_html.replace(
                 '<section>', '<section id="produkte">', 1) if auto else (
            '<section id="produkte"><h2>Die Süßigkeiten aus dem Post</h2><div class="empty"><strong>Kommt bald.</strong> '
            'Sobald es die Sachen aus dem Post bei einem Partner-Shop gibt, findest du sie hier.</div></section>')
        srcs = "".join(f'<li><a href="{e(s["url"])}" rel="noopener" target="_blank">{e(s["title"])}</a></li>' for s in p.get("sources", []))
        slides = "".join(slide_img(f"/p/{p['id']}/{x.name}", f"Folie {i + 1} von {len(imgs)}", 400, "(min-width:500px) 400px, 84vw",
                                   eager=(i == 0)) for i, x in enumerate(imgs))
        dots = "".join(f'<b{" class=on" if i == 0 else ""}></b>' for i in range(len(imgs)))
        prev_p = live[k - 1] if k > 0 else None
        next_p = live[k + 1] if k + 1 < len(live) else None
        nav = ('<section><div class="next">'
               + (f'<a href="/p/{prev_p["id"]}/"><small>← #{prev_p["id"]}</small>{plain(prev_p["hook"])}</a>' if prev_p else "<span></span>")
               + (f'<a class="r" href="/p/{next_p["id"]}/"><small>#{next_p["id"]} →</small>{plain(next_p["hook"])}</a>' if next_p else "")
               + "</div></section>") if (prev_p or next_p) else ""
        stick = "".join(f'<a class="sc" href="/kategorie/{o["id"]}/">{sticker(o["id"], 34)}{e(o["name"])}</a>' for o in cats)
        body = (f'<a class="back" href="/posts/">← Alle Posts</a>'
                f'<div class="meta" style="--c:{c}"><span class="pill">#{p["id"]}</span><span class="tg"><i></i>{e(p.get("tag", ""))}</span></div>'
                f'<h1 style="font-size:clamp(32px,7.5vw,60px);max-width:18ch">{accent(p["hook"])}</h1>'
                f'<p class="sub">{e(p.get("sub", ""))}</p>'
                f'<div class="gal"><button class="arrow l" data-k="-1" aria-label="Vorherige Folie">‹</button>'
                f'<div class="slides" tabindex="0" aria-label="Folien zum Wischen">{slides}</div>'
                f'<button class="arrow r" data-k="1" aria-label="Nächste Folie">›</button><div class="dots" aria-hidden="true">{dots}</div></div>'
                f'{prods}{band(live, "Das könnte dir auch schmecken", "Mehr Posts")}'
                f'<section><h2>Länder & Themen</h2><div class="stickers">{stick}</div></section>'
                + (f'<section><h2>Quellen</h2><ul class="src">{srcs}</ul></section>' if srcs else "") + nav)
        write(f"p/{p['id']}/index.html", page(f"#{p['id']} {plain(p['hook'])} – Naschpass", body, plain(p.get("sub", "")),
                                              f"/p/{p['id']}/", f"{BASE}/p/{p['id']}/01.jpg",
                                              stamp=TAG_STAMP.get(p.get("tag", "").lower(), "")))

    # --- Gemeinsame Bausteine
    newest = list(reversed(live))
    stick = "".join(f'<a class="sc" href="/kategorie/{c["id"]}/">{sticker(c["id"], 34)}{e(c["name"])}</a>' for c in cats)
    tiles = f'<div class="cats">{"".join(cat_tile(c) for c in cats)}</div>'

    def chips_for(gid, key, opts):
        return ('<div class="chips" role="group" aria-label="Filtern">'
                f'<button class="chip" data-filter="alle" data-grid="{gid}" data-key="{key}" aria-pressed="true">Alle</button>'
                + "".join(f'<button class="chip" data-filter="{v}" data-grid="{gid}" data-key="{key}" aria-pressed="false" '
                          f'style="--c:{col}"><i></i>{e(n)}</button>' for v, n, col in opts) + '</div>')

    used = [c for c in cats if cat_items(c)]
    prod_chips = chips_for("g-all", "cat", [(c["id"], c["name"], cat_color[c["id"]]) for c in used])
    tags_live = [t for t in _tags if any(p.get("tag") == t for p in live)]
    post_chips = chips_for("g-posts", "tag", [(tag_slug(t), t, tag_color(t)) for t in tags_live])
    ex = newest[0]["id"] if newest else "01"
    jump = (f'<section id="nummer"><form class="pass" id="jump" action="/" novalidate data-ids=\'{json.dumps([p["id"] for p in live])}\'>'
            f'<h2>Du kommst aus einem Post?</h2><p>Gib die Nummer aus dem Post ein, dann bringen wir dich direkt hin.</p>'
            f'<div class="row"><label class="num" for="nr"><span>#</span><input id="nr" name="nr" inputmode="numeric" pattern="[0-9]*" '
            f'maxlength="3" placeholder="{ex}" autocomplete="off" aria-label="Post-Nummer" aria-describedby="nrmsg"></label>'
            f'<button type="submit">Zum Post</button></div><p class="msg" id="nrmsg" role="status"></p>'
            f'<div class="stamp" aria-hidden="true"></div></form></section>')
    empty_shop = ('<div class="empty"><strong>Die ersten Sorten kommen bald.</strong><br>'
                  'Wir suchen gerade Shops aus, bei denen du die Sachen aus den Posts in Deutschland bekommst.</div>')

    # --- Shop-Seite: alle Länder/Themen + alle Produkte
    def _n(c):
        return len(cat_items(c))
    theme_row = "".join(
        f'<a class="bc" href="/kategorie/{c["id"]}/">{sticker(c["id"], 40)}{e(c["name"])}'
        f'<small>{_n(c) or "bald"}{(" Sorte" if _n(c) == 1 else " Sorten") if _n(c) else ""}</small></a>'
        for c in cats_sorted())
    counts = facet_counts()
    fgroups = ""
    for g in FILTER:
        opts = [o for o in g["options"] if counts.get((g["id"], o["id"]))]
        if not opts:
            continue
        fgroups += (f'<div class="dd"><button class="ddb" type="button" aria-expanded="false" aria-controls="dd-{g["id"]}">'
                    f'{e(g["name"])} <span class="badge" data-badge="{g["id"]}" hidden></span><span class="car" aria-hidden="true">▾</span></button>'
                    f'<div class="ddp" id="dd-{g["id"]}"><div class="chips">'
                    + "".join(f'<button class="chip" type="button" data-g="{g["id"]}" data-v="{o["id"]}" data-n="{e(o["name"])}" aria-pressed="false">'
                              f'{facet_icon(g["id"], o)}{e(o["name"])} <small>{counts[(g["id"], o["id"])]}</small></button>' for o in opts)
                    + '</div></div></div>')
    shop_all = (f'<div class="filters" id="flt" data-grid="g-all"><div class="fbtns">{fgroups}</div><div class="active" id="factive"></div></div>'
                f'<div class="fbar"><b id="fcount" aria-live="polite"></b><button class="linkbtn" type="button" id="freset" hidden>Filter zurücksetzen</button>'
                f'<span style="margin-left:auto">{view_toggle("g-all", ["big", "small", "list"], "small")}</span></div>'
                f'<div class="grid prods v-small" id="g-all">{"".join(fill_slots([prod_card(p) for p in reversed(products)], 8 if len(products) < 8 else 0))}</div>'
                f'<div class="empty" id="fempty" hidden><strong>Keine Treffer mit dieser Kombination.</strong> Nimm einen Filter raus oder probier die Suche.</div>'
                f'<div class="morebar"><button class="morebtn" type="button" id="fmore" hidden>Mehr zeigen</button></div>'
                f'<p class="wl">* Werbelink</p>') if products else empty_shop
    write("shop/index.html", page(
        "Shop – Naschpass",
        f'<section class="hero" style="padding-bottom:0">{SPRINKLES}<h1>Shop</h1>'
        f'<p class="sub">Such dir aus, worauf du Lust hast: nach Herkunft, Geschmack und Art, frei kombinierbar.</p>'
        f'<button class="fake" type="button" data-open-search>{ICON_SEARCH}<span>Snacks, Länder, Marken suchen …</span></button></section>'
        f'<nav class="themes" aria-label="Themenwelten"><h2>Themenwelten</h2><div class="trow">{theme_row}</div></nav>'
        f'<section id="alle" style="padding-top:18px">{shop_all}</section>',
        "Süßigkeiten aus aller Welt nach Herkunft, Geschmack und Art.", "/shop/"))

    # --- Posts-Seite: alle Posts mit Filter, Nummernsuche unten
    write("posts/index.html", page(
        "Alle Posts – Naschpass",
        f'<section class="hero" style="padding-bottom:0"><h1>Alle Posts</h1>'
        f'<p class="sub">Fakten, Verbote und Kuriositäten rund um Süßigkeiten aus aller Welt.</p></section>'
        f'<section style="padding-top:10px"><div class="tools">{post_chips}{view_toggle("g-posts", ["big", "small"], "small")}</div>'
        f'<div class="grid posts v-small" id="g-posts">{"".join(post_card(p) for p in newest)}</div></section>{jump}',
        "Alle Naschpass-Posts auf einen Blick.", "/posts/"))

    # --- Startseite: Shop zuerst, Posts danach, Nummernsuche ganz unten
    SHOW, LIMIT = 4, 12  # erst 4 zeigen, per Knopf bis 12 aufklappen, Rest im Shop
    def clip_grid(cards, gid, cls):
        cells = [c if i < SHOW else c.replace("<a ", "<a data-more ", 1) for i, c in enumerate(cards)]
        return f'<div class="grid {cls} v-small clip" id="{gid}">{"".join(cells)}</div>'

    def more_bar(gid, n_shown, total, href, label):
        btn = (f'<button class="morebtn" type="button" data-expand="{gid}" aria-controls="{gid}">{n_shown - SHOW} weitere zeigen</button>'
               if n_shown > SHOW else "")
        link = f'<a class="btn dark" href="{href}">{label}</a>' if total > SHOW else ""
        return f'<div class="morebar">{btn}{link}</div>' if (btn or link) else ""

    new_prods = list(reversed(products))[:LIMIT]
    home_prods = (f'<section id="neu"><div class="head"><h2>Neu im Shop</h2>{view_toggle("g-new", ["big", "small", "list"], "small")}</div>'
                  f'{clip_grid(fill_slots([prod_card(p) for p in new_prods], 4), "g-new", "prods")}<p class="wl">* Werbelink</p>'
                  f'{more_bar("g-new", len(new_prods), len(products), "/shop/", f"Alle {len(products)} im Shop")}</section>'
                  ) if products else ""
    home_posts = newest[:LIMIT]
    # Stöbern: Tabs Woher / Geschmack / Art (nur Optionen mit Produkten), sonst alte Kategorien
    counts = facet_counts()
    tabs, panels = "", ""
    for g in FILTER:
        opts = sorted([o for o in g["options"] if counts.get((g["id"], o["id"]))], key=lambda o: -counts[(g["id"], o["id"])])[:6]
        if not opts:
            continue
        first = not tabs
        tabs += (f'<button type="button" role="tab" data-tab="{g["id"]}" aria-selected="{str(first).lower()}">{e(g["name"])}</button>')
        panels += (f'<div class="bgrid" data-panel="{g["id"]}"{"" if first else " hidden"}>' + "".join(
            f'<a class="bc" href="/shop/?{g["id"]}={o["id"]}#alle">{facet_icon(g["id"], o, 40)}{e(o["name"])}'
            f'<small>{counts[(g["id"], o["id"])]} {"Sorte" if counts[(g["id"], o["id"])] == 1 else "Sorten"}</small></a>' for o in opts) + '</div>')
    # Stöbern als Klapp-Menüs direkt unter der Suche (Hover am PC, Tippen am Handy)
    def sorte(n):
        return f'{n} {"Sorte" if n == 1 else "Sorten"}'
    gorder = sorted(FILTER, key=lambda g: {"art": 0, "geschmack": 1, "land": 2}.get(g["id"], 9))
    dds = ""
    for g in gorder:
        chips = ""
        for o in sorted(g["options"], key=lambda o: -counts.get((g["id"], o["id"]), 0)):
            n = counts.get((g["id"], o["id"]), 0)
            icon = facet_icon(g["id"], o)
            chips += (f'<a class="chip" href="/shop/?{g["id"]}={o["id"]}#alle">{icon}{e(o["name"])} <small>{n}</small></a>' if n else
                      f'<span class="chip off">{icon}{e(o["name"])} <small>bald</small></span>')
        dds += (f'<div class="dd"><button class="ddb" type="button" aria-expanded="false">{e(g["name"])} <span class="car" aria-hidden="true">▾</span></button>'
                f'<div class="ddp"><div class="chips">{chips}</div><a class="more" style="display:block;margin-top:10px" href="/shop/#alle">Im Shop frei kombinieren</a></div></div>')
    tchips = "".join(f'<a class="chip" href="/kategorie/{c["id"]}/">{sticker(c["id"], 24)}{e(c["name"])}'
                     f' <small>{len(cat_items(c)) or "bald"}</small></a>' for c in cats_sorted())
    dds += (f'<div class="dd"><button class="ddb" type="button" aria-expanded="false">Themenwelten <span class="car" aria-hidden="true">▾</span></button>'
            f'<div class="ddp"><div class="chips">{tchips}</div></div></div>')
    browse_html = f'<nav class="fbtns ddnav" aria-label="Stöbern" style="margin-top:14px">{dds}</nav>'
    minis = []
    for p in list(reversed(products))[:6]:
        minis.append(f'<a class="mini" href="{e(p["url"])}" rel="sponsored noopener" target="_blank" style="--c:{cat_color.get(p.get("category", ""), "#CFE7DD")}">'
                     f'<span class="mp">{pic_html(p, 200, p["name"], p.get("category", ""))}</span><b>{e(p["name"])}*</b></a>')
    while len(minis) < 4:
        minis.append('<a class="mini slot" href="/ueber/#partner"><span class="mp"><span class="emo">🤝</span></span><b>Hier könnte dein Produkt stehen</b></a>')
    minis_html = (f'<div class="minis"><div class="head" style="margin:18px 0 8px"><h2 style="font:800 15px Inter,sans-serif;text-transform:none;'
                    f'letter-spacing:0;color:var(--mut);margin:0">Gerade im Shop</h2><a class="more" href="/shop/#alle">Alle ansehen</a></div>'
                    f'<div class="mrow">{"".join(minis)}</div>' + ('<p class="wl" style="margin-top:6px">* Werbelink</p>' if products else '') + '</div>')
    season_html = '<section class="seasons" style="padding-top:22px"><div class="cats">' + "".join(
        f'<a class="cat" style="--c:{cat_color[c["id"]]}" href="/kategorie/{c["id"]}/">{sticker(c["id"])}'
        f'<h3>{e(c["name"])}</h3><p>{e(c["teaser"])}</p>'
        + (f'<span class="n">{len(cat_items(c))} {"Sorte" if len(cat_items(c)) == 1 else "Sorten"}</span>' if cat_items(c) else '<span class="n soon">Jetzt Saison</span>')
        + '</a>' for c in cats if in_season(c)) + '</div></section>'
    if 'class="cat"' not in season_html:
        season_html = ""
    # Themenwelten: erst 8, Rest aufklappbar
    ordered = cats_sorted()
    tcells = [cat_tile(c) if i < 8 else cat_tile(c).replace("<a ", "<a data-more ", 1) for i, c in enumerate(ordered)]
    themes_html = (f'<section id="themen"><div class="head"><h2>Themenwelten</h2><a class="more" href="/shop/">Zum Shop</a></div>'
                   f'<div class="cats clip" id="g-themen">{"".join(tcells)}</div>'
                   + (f'<div class="morebar"><button class="morebtn" type="button" data-expand="g-themen">{len(ordered) - 8} weitere Themenwelten</button></div>'
                      if len(ordered) > 8 else "") + '</section>')
    band_html = band(live)
    band_is_posts = 'class="ri post"' in band_html
    if band_is_posts:
        band_html = band_html.replace('<h2>Neu auf Naschpass</h2></div>',
                                      f'<h2>Neu auf Naschpass</h2><a class="more" href="/posts/">Alle {len(live)} Posts</a></div>', 1)
    posts_html = "" if band_is_posts else (
        f'<section id="posts"><div class="head"><h2>Aus unseren Posts</h2>{view_toggle("g-home-posts", ["big", "small"], "small")}</div>'
        f'{clip_grid([post_card(p) for p in home_posts], "g-home-posts", "posts")}'
        f'{more_bar("g-home-posts", len(home_posts), len(live), "/posts/", f"Alle {len(live)} Posts")}</section>')
    how = ('<ul class="how">'
           '<li><a href="/posts/"><span aria-hidden="true">📲</span>Fakten-Posts mit Quellen</a></li>'
           '<li><a href="/shop/"><span aria-hidden="true">🗺️</span>Nach Land & Thema</a></li>'
           '<li><a href="/shop/#alle"><span aria-hidden="true">🛒</span>Direkt zum Shop</a></li>'
           + ('<li><a href="/kategorie/halloween/" class="advpill hw" data-season><span aria-hidden="true">🎃</span><em>Halloween</em></a></li></ul>'
              if TODAY.month in (9, 10) else
              '<li><a href="/advent/" class="advpill" data-season><span aria-hidden="true">🎄</span><em>Adventskalender</em></a></li></ul>'))
    about_box = (f'<section><div class="aboutbox"><h2>Neu hier?</h2><p>Naschpass ist ein junges Projekt rund um Süßigkeiten aus aller Welt. '
                 f'Wie wir arbeiten und was Shops und Marken bei uns bekommen, steht auf einer Seite.</p>'
                 f'<div class="btns"><a class="btn dark" href="/ueber/">Über Naschpass</a><a class="btn" href="/ueber/#partner">Für Partner</a></div></div></section>')
    fan = "".join(f'<a href="/p/{p["id"]}/" tabindex="-1" aria-hidden="true">{slide_img(cover_url(p), "", 230, "230px")}</a>'
                  for p in newest[:3][::-1])
    md = TODAY.strftime("%m-%d")
    advent_teaser = ('<section style="padding-top:22px"><a class="advteaser" href="/advent/">' + sticker("weihnachten", 56)
                     + '<div><h2>Naschpass-Adventskalender</h2><p>' + ("Heute wartet ein neues Türchen." if md >= "12-01" else "Ab 1. Dezember jeden Tag ein Türchen.")
                     + '</p></div></a></section>') if "11-15" <= md <= "12-24" else ""
    home = (f'<section class="hero hgrid">{SPRINKLES}<div class="hl"><h1>Süßes aus <span class="acc">aller Welt</span></h1>'
            f'<p class="lead" style="max-width:36ch">{e(site["intro"])}</p>{how}'
            f'<button class="fake" type="button" data-open-search>{ICON_SEARCH}<span>Snacks, Länder, Marken suchen …</span></button>{browse_html}</div>'
            f'<div class="hr">{minis_html}</div></section>'
            f'{season_html}{advent_teaser}{home_prods}{explore_html()}{spin_html(live)}{map_html()}{pass_html()}{band_html}{posts_html}{about_box}{jump}')
    write("index.html", page("Naschpass – Süßigkeiten aus aller Welt", home, script=SPIN_JS + SHARE_JS + PASS_SHARE_JS))

    # --- Über Naschpass / Für Partner (ehrlich: neuer Kanal, keine Reichweitenzahlen)
    im = site["impressum"]
    chans = "".join(f'<li><a href="{e(x["url"])}" rel="noopener" target="_blank">{e(x["name"])}</a></li>' for x in site["socials"])
    worlds = ", ".join(e(c["name"]) for c in cats_sorted()[:6])
    about = f"""<section class="prose"><h1 style="margin-top:22px">Über Naschpass</h1>
<p class="lead">Naschpass zeigt Süßigkeiten aus aller Welt: was sie besonders macht, wo sie verboten sind und wo du sie in Deutschland bekommst.</p>
<h2>Das Konzept</h2>
<ul><li>Wir veröffentlichen kurze Karussell-Posts über Süßigkeiten aus aller Welt: Kuriositäten, Verbote und Unterschiede zwischen Ländern.</li>
<li>Jede Zahl und jedes Datum prüfen wir an einer Quelle. Die Quellen stehen bei jedem Post.</li>
<li>Auf dieser Website hat jeder Post eine eigene Seite. Dazu sortieren wir Süßigkeiten nach Herkunft, Geschmack, Art und Anlass und verlinken Shops, die nach Deutschland liefern.</li>
<li>Naschpass richtet sich an Erwachsene.</li></ul>
<h2>Kanäle</h2>
<ul>{chans}<li><a href="/">naschpass.oneflowsolution.de</a> (diese Website)</li></ul>
<p>Ehrlich gesagt: Naschpass ist neu und die Kanäle sind im Aufbau. Bisher gibt es {len(live)} Posts, alle findest du unter <a href="/posts/">Posts</a>.</p>
<h2 id="partner">Für Partner</h2>
<p>Du betreibst einen Shop oder eine Marke mit Süßigkeiten, Snacks oder alkoholfreien Getränken? So arbeiten wir:</p>
<ul><li>Deine Produkte erscheinen in passenden Themenwelten (zum Beispiel {worlds}) und auf den Seiten der Posts, in denen sie vorkommen.</li>
<li>Jeder Partner-Link ist als Werbung gekennzeichnet, dazu steht ein Hinweis oben auf jeder Seite.</li>
<li>Keine Gutscheinseite, keine bezahlten Suchanzeigen, kein Bieten auf Markennamen.</li>
<li>Keine Gesundheitsversprechen und keine Werbung, die sich an Kinder richtet.</li>
<li>Keine Cookies und kein Tracking auf dieser Website. Die Zuordnung von Bestellungen läuft über das Partnernetzwerk Awin (Publisher-ID 3111189).</li>
<li>Produktnamen und Bilder übernehmen wir aus deinem Awin-Produktfeed, damit die Angaben aktuell bleiben.</li></ul>
<h2>Kontakt</h2>
<p>{e(im["name"])}, {e(im["firma"])}<br>E-Mail: <a href="mailto:{e(im["email"])}">{e(im["email"])}</a><br>
Vollständige Angaben im <a href="/impressum/">Impressum</a>.</p></section>"""
    write("ueber/index.html", page("Über Naschpass & für Partner", about,
                                   "Was Naschpass ist, wie wir arbeiten und was Partner-Shops bei uns bekommen.", "/ueber/"))

    write("search.json", json.dumps(search_index(live), ensure_ascii=False, separators=(",", ":")))
    write("geschenk/index.html", page("Geschenk-Finder – Naschpass", finder_page(),
                                      "Drei Fragen, passende Süßigkeiten zum Verschenken.", "/geschenk/", script=FINDER_JS))
    write("quiz/index.html", page("Welcher Snack-Typ bist du? – Naschpass", quiz_page(),
                                  "Fünf Fragen, dein Snack-Typ und passende Süßigkeiten.", "/quiz/", script=SHARE_JS + QUIZ_JS))
    adv = advent_page(live)
    if adv:
        write("advent/index.html", page("Adventskalender – Naschpass", adv, "Vom 1. bis 24. Dezember jeden Tag ein Türchen.", "/advent/",
                                        script=ADVENT_JS))
    # Kurzlinks: /9 und /09 führen zu Post #09 (Netlify-Weiterleitungen, kostenlos)
    red = []
    for p in live:
        n = str(int(p["id"]))
        red += [f"/{n} /p/{p['id']}/ 301", f"/{p['id']} /p/{p['id']}/ 301"] if n != p["id"] else [f"/{n} /p/{p['id']}/ 301"]
    (DIST / "_redirects").write_text("\n".join(dict.fromkeys(red)) + "\n", encoding="utf-8")
    write("404.html", page("Seite nicht gefunden – Naschpass",
                           '<section class="hero"><h1>Diese Seite gibt es <span class="acc">nicht</span></h1>'
                           '<p class="sub">Vielleicht hat sich ein Tippfehler eingeschlichen. Probier die Suche oder geh zur Startseite.</p>'
                           '<a class="btn" style="background:var(--fg);color:#fff" href="/">Zur Startseite</a></section>', path="/404"))

    im = site["impressum"]
    missing = not (im["strasse"] and im["ort"])
    addr = f'{e(im["strasse"])}<br>{e(im["ort"])}' if not missing else '<span class="warn">ADRESSE FEHLT NOCH</span>'
    tel = f'<br>Telefon: {e(im["telefon"])}' if im["telefon"] else ""
    write("impressum/index.html", page("Impressum – Naschpass", f"""<section class="legal"><h1>Impressum</h1>
<p>Angaben gemäß § 5 DDG</p><p>{e(im["name"])}<br>{e(im["firma"])}<br>{addr}</p>
<h2>Kontakt</h2><p>E-Mail: <a href="mailto:{e(im["email"])}">{e(im["email"])}</a>{tel}</p>
<h2>Umsatzsteuer</h2><p>Kleinunternehmer gemäß § 19 UStG, daher keine Umsatzsteuer-Identifikationsnummer ausgewiesen.</p>
<h2>Verantwortlich für den Inhalt</h2><p>{e(im["name"])}, Anschrift wie oben.</p>
<h2>Werbelinks</h2><p>Links zu Online-Shops sind Affiliate-Links. Kaufst du darüber ein, erhalte ich eine Provision. Der Preis ändert sich für dich nicht.</p>
<h2>Verbraucherstreitbeilegung</h2><p>Ich bin nicht bereit und nicht verpflichtet, an Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen.</p>
</section>""", "Impressum"))

    write("datenschutz/index.html", page("Datenschutz – Naschpass", f"""<section class="legal"><h1>Datenschutz&shy;erklärung</h1>
<h2>1. Verantwortlicher</h2><p>{e(im["name"])}, {e(im["firma"])}, Anschrift siehe <a href="/impressum/">Impressum</a>, E-Mail: {e(im["email"])}</p>
<h2>2. Kurz gesagt</h2><p>Diese Website setzt keine Cookies, nutzt keine Analyse- oder Tracking-Tools und lädt Inhalte von Drittanbietern nur, wenn du es ausdrücklich erlaubst (Produktfotos, siehe Abschnitt 4b). Schriften und unsere eigenen Bilder liegen auf unserem eigenen Server.</p>
<h2>3. Hosting</h2><p>Die Website wird bei Netlify, Inc., 101 2nd Street, San Francisco, CA 94105, USA gehostet. Beim Aufruf verarbeitet Netlify technisch notwendige Daten (z. B. IP-Adresse, Datum und Uhrzeit, aufgerufene Seite, Browser) in Server-Logfiles, um die Seite auszuliefern und die Sicherheit zu gewährleisten. Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an einem sicheren und stabilen Betrieb). Dabei können Daten in die USA übermittelt werden; die Übermittlung erfolgt auf Grundlage der EU-Standardvertragsklauseln bzw. des EU-US Data Privacy Framework, soweit der Anbieter dort zertifiziert ist. Mit Netlify besteht ein Vertrag zur Auftragsverarbeitung. Details: <a href="https://www.netlify.com/privacy/" rel="noopener" target="_blank">netlify.com/privacy</a></p>
<h2>4. Werbelinks (Affiliate)</h2><p>Einige Links führen zu Online-Shops und sind mit einer Partnerkennung versehen (z. B. über das Netzwerk Awin). Erst wenn du einen solchen Link anklickst, verlässt du diese Website; der Shop bzw. das Partnernetzwerk kann dann auf seiner eigenen Seite Cookies setzen, um den Kauf zuzuordnen. Dafür ist der jeweilige Anbieter verantwortlich. Auf dieser Website selbst wird dabei nichts gespeichert. Produktbilder aus den Datenfeeds der Partner-Shops werden über unseren Hoster Netlify ausgeliefert; dein Browser baut dabei keine Verbindung zu den Shops auf. Ausnahme: Abschnitt 4b.</p>
{fotos_html()}
<h2>4c. Dein Naschpass (Stempel)</h2><p>Wenn du auf der Startseite „Pass starten“ drückst, speichern wir im lokalen Speicher deines Browsers, welche Länder-Themenwelten du besucht hast. Das passiert nur auf deinen Wunsch (§ 25 Abs. 2 Nr. 2 TDDDG), wird nie an uns übertragen und lässt sich mit „Pass zurücksetzen“ jederzeit löschen.</p>
<h2>4a. Suche</h2><p>Die Suche läuft komplett in deinem Browser. Deine Suchbegriffe werden nicht übertragen und nicht gespeichert.</p>
<h2>5. Social-Media-Links</h2><p>Links zu Instagram, TikTok und Pinterest sind einfache Verlinkungen, keine eingebetteten Inhalte. Daten werden erst übertragen, wenn du den Link anklickst und die jeweilige Plattform besuchst; dort gelten deren Datenschutzbestimmungen.</p>
<h2>6. Kontakt per E-Mail</h2><p>Schreibst du uns eine E-Mail, verarbeiten wir deine Angaben nur, um deine Anfrage zu beantworten (Art. 6 Abs. 1 lit. b bzw. f DSGVO), und löschen sie, wenn sie nicht mehr benötigt werden.</p>
<h2>7. Deine Rechte</h2><p>Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch (Art. 15–21 DSGVO). Außerdem kannst du dich bei einer Datenschutz-Aufsichtsbehörde beschweren, z. B. bei der Landesbeauftragten für Datenschutz und Informationsfreiheit Nordrhein-Westfalen.</p>
<p style="color:var(--mut);font-size:14px">Stand: Oktober 2026</p></section>""", "Datenschutz"))


    urls = sorted({"/" + str(f.relative_to(DIST)).replace("index.html", "") for f in DIST.rglob("index.html")})
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "".join(f"<url><loc>{BASE}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    # Sicherheits-Header: Seite darf nur Dinge von der eigenen Domain laden (plus freigegebene Partner-Bildserver nach Einwilligung)
    img_hosts = " ".join(f"https://{h}" for h in sorted(PARTNERS))
    csp = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
           f"img-src 'self' data: blob: {img_hosts}; font-src 'self'; connect-src 'self'; media-src 'none'; object-src 'none'; "
           "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests")
    (DIST / "_headers").write_text(
        "/*\n"
        f"  Content-Security-Policy: {csp}\n"
        "  X-Content-Type-Options: nosniff\n"
        "  X-Frame-Options: DENY\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()\n"
        "  Strict-Transport-Security: max-age=31536000\n"
        "  Cross-Origin-Opener-Policy: same-origin\n", encoding="utf-8")
    for w in WARN:
        print("WARNUNG:", w)
    print("fertig:", DIST, "| Impressum-Adresse fehlt!" if missing else "")


if __name__ == "__main__":
    build()
