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
if DEMO and not os.environ.get("PRODUCTS_FILE"):  # Vorschau: echte Produkte zuerst, dann Beispiele
    products = json.loads((HERE / "products.json").read_text(encoding="utf-8"))["products"] + products
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
@font-face{font-family:Anton;src:url(/static/Anton-Regular.ttf) format("truetype");font-display:swap}
@font-face{font-family:Inter;src:url(/static/Inter.ttf) format("truetype");font-weight:100 900;font-display:swap}
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

/* Werbehinweis + Kopf */
.ad{background:var(--fg);color:#EAF6F1;font-size:12.5px;line-height:1.35;text-align:center;padding:6px 12px}
header{position:sticky;top:0;z-index:30;background:rgba(234,246,241,.9);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
header .wrap{display:flex;align-items:center;gap:10px;height:60px}
.logo{display:flex;align-items:center;gap:9px;text-decoration:none;color:var(--fg);font:23px Anton,sans-serif;letter-spacing:.5px;margin-right:auto}
.logo img{width:38px;height:38px;border-radius:50%}
header nav{display:flex;gap:2px}
header nav a{color:var(--fg);text-decoration:none;font-weight:700;font-size:15px;padding:8px 11px;border-radius:999px}
header nav a:hover{background:#fff}
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
.imgbar{position:fixed;left:12px;right:12px;bottom:12px;z-index:40;max-width:560px;margin:0 auto;background:var(--fg);color:#fff;border-radius:18px;
padding:14px 14px 12px;box-shadow:0 12px 40px rgba(43,35,80,.35);font-size:14.5px;line-height:1.4}
.imgbar p{margin:0 0 10px}.imgbar a{color:var(--mint)}
.imgbar .row{display:flex;gap:8px;flex-wrap:wrap}
.imgbar button{border:0;border-radius:12px;font-weight:800;font-size:15px;padding:10px 16px;cursor:pointer}
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
<input type="search" id="q" placeholder="KitKat, Japan, sauer, #08 …" autocomplete="off" enterkeyhint="search" aria-label="Suchbegriff"></label>
<button class="x" type="button" data-close>Schließen</button></div><div class="sres" id="sres" aria-live="polite"></div></dialog>"""


def socials_btns():
    return "".join(f'<a class="btn" href="{e(s["url"])}" rel="noopener" target="_blank">{e(s["name"])}</a>' for s in site["socials"])


def follow_box():
    return (f'<div class="follow"><p>Jede Woche neue Süßigkeiten aus aller Welt.</p>'
            f'<div class="btns">{socials_btns()}</div></div>')


def page(title, body, desc=None, path="/", og_img=None, script=""):
    desc = desc or site["intro"]
    og = og_img or f"{BASE}/static/logo.png"
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<meta name="theme-color" content="#EAF6F1"><link rel="canonical" href="{BASE}{path}">
<link rel="icon" href="/static/favicon.png"><link rel="apple-touch-icon" href="/static/logo.png">
<link rel="preload" href="/static/Anton-Regular.ttf" as="font" type="font/ttf" crossorigin>
<meta property="og:type" content="website"><meta property="og:url" content="{BASE}{path}"><meta property="og:locale" content="de_DE">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{og}"><meta name="twitter:card" content="summary_large_image">
<style>{CSS}</style></head><body>
<div class="ad">{AD}</div>{'<div class="ad" style="background:#FFB547;color:#2B2350;font-weight:700">VORSCHAU mit Beispielprodukten – nicht live</div>' if DEMO else ''}
<header><div class="wrap"><a class="logo" href="/"><img src="/static/logo.png" alt="" width="38" height="38">NASCHPASS</a>
<nav aria-label="Hauptmenü"><a href="/shop/">Shop</a><a href="/posts/">Posts</a></nav>
<button class="sbtn" type="button" data-open-search aria-label="Suche öffnen">{ICON_SEARCH}</button></div></header>
<main class="wrap">
{body}
{follow_box()}
</main>
<footer><div class="wrap"><a href="/impressum/">Impressum</a><a href="/datenschutz/">Datenschutz</a>
<button class="linkbtn" type="button" data-imgpref hidden>Foto-Einstellung</button>
<span>Keine Cookies, kein Tracking.</span></div></footer>
<div class="imgbar" id="imgbar" role="region" aria-label="Produktfotos" hidden><p>Einige Produktfotos kommen direkt vom Shop. Dabei bekommt der Shop deine IP-Adresse. <a href="/datenschutz/#fotos">Mehr</a></p>
<div class="row"><button class="yes" type="button" data-img="1">Fotos anzeigen</button><button class="no" type="button" data-img="0">Nein danke</button></div></div>
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


def cat_tile(c):
    items = [p for p in products if p.get("category") == c["id"]]
    n = f'<span class="n">{len(items)} {"Sorte" if len(items) == 1 else "Sorten"}</span>' if items else '<span class="n soon">Bald hier</span>'
    return (f'<a class="cat" href="/kategorie/{c["id"]}/" style="--c:{cat_color[c["id"]]}">{sticker(c["id"])}'
            f'<h3>{e(c["name"])}</h3><p>{e(c["teaser"])}</p>{n}</a>')


def band(live, title_prod="Unsere Empfehlungen", title_post="Neu auf Naschpass"):
    """Laufband: empfohlene Produkte (featured), sonst die neuesten Produkte, sonst die neuesten Posts."""
    feat = [p for p in products if p.get("featured")] or products[:12]
    if feat:
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
    sugg = ["salzige Chips aus Asien", "sauer", "Japan", "Schokolade", "scharf", "Lakritz"]
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
        items = [p for p in products if p.get("category") == c["id"]]
        inner = (f'<div class="tools"><span></span>{view_toggle("g-cat", ["big", "small", "list"], "small")}</div>'
                 + prod_grid(items, "g-cat")) if items else (
            '<div class="empty"><strong>Hier kommen bald die ersten Sorten rein.</strong><br>'
            'Bis dahin findest du in den Posts, was es in dieser Ecke der Welt zu naschen gibt.</div>')
        rel = [p for p in live if any(x.get("post") == p["id"] and x.get("category") == c["id"] for x in products)]
        rel_html = (f'<section><h2>Passende Posts</h2><div class="grid posts v-small">{"".join(post_card(p) for p in rel)}</div></section>'
                    if rel else "")
        others = "".join(f'<a class="sc" href="/kategorie/{o["id"]}/">{sticker(o["id"], 34)}{e(o["name"])}</a>'
                         for o in cats if o["id"] != c["id"])
        write(f"kategorie/{c['id']}/index.html", page(
            f"{c['name']} – Naschpass",
            f'<a class="back" href="/shop/">← Zum Shop</a>'
            f'<section style="padding-top:14px"><div style="display:flex;align-items:center;gap:14px;margin-bottom:6px">{sticker(c["id"], 64)}'
            f'<h1 style="margin:0">{e(c["name"])}</h1></div><p class="sub">{e(c["teaser"])}</p>{inner}</section>{rel_html}'
            f'<section><h2>Mehr entdecken</h2><div class="stickers">{others}</div></section>',
            c["teaser"], f"/kategorie/{c['id']}/"))

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
        prods = (f'<section id="produkte"><div class="head"><h2>Die Süßigkeiten aus dem Post</h2>'
                 f'{view_toggle("g-post", ["big", "small", "list"], "small")}</div>{prod_grid(items, "g-post")}</section>') if items else (
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
                                              f"/p/{p['id']}/", f"{BASE}/p/{p['id']}/01.jpg"))

    # --- Gemeinsame Bausteine
    newest = list(reversed(live))
    stick = "".join(f'<a class="sc" href="/kategorie/{c["id"]}/">{sticker(c["id"], 34)}{e(c["name"])}</a>' for c in cats)
    tiles = f'<div class="cats">{"".join(cat_tile(c) for c in cats)}</div>'

    def chips_for(gid, key, opts):
        return ('<div class="chips" role="group" aria-label="Filtern">'
                f'<button class="chip" data-filter="alle" data-grid="{gid}" data-key="{key}" aria-pressed="true">Alle</button>'
                + "".join(f'<button class="chip" data-filter="{v}" data-grid="{gid}" data-key="{key}" aria-pressed="false" '
                          f'style="--c:{col}"><i></i>{e(n)}</button>' for v, n, col in opts) + '</div>')

    used = [c for c in cats if any(p.get("category") == c["id"] for p in products)]
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
        return sum(1 for p in products if p.get("category") == c["id"])
    theme_row = "".join(
        f'<a class="bc" href="/kategorie/{c["id"]}/">{sticker(c["id"], 40)}{e(c["name"])}'
        f'<small>{_n(c) or "bald"}{(" Sorte" if _n(c) == 1 else " Sorten") if _n(c) else ""}</small></a>'
        for c in sorted(cats, key=lambda c: -_n(c)))
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
                f'<div class="grid prods v-small" id="g-all">{"".join(prod_card(p) for p in reversed(products))}</div>'
                f'<div class="empty" id="fempty" hidden><strong>Keine Treffer mit dieser Kombination.</strong> Nimm einen Filter raus oder probier die Suche.</div>'
                f'<div class="morebar"><button class="morebtn" type="button" id="fmore" hidden>Mehr zeigen</button></div>'
                f'<p class="wl">* Werbelink</p>') if products else empty_shop
    write("shop/index.html", page(
        "Shop – Naschpass",
        f'<section class="hero" style="padding-bottom:0">{SPRINKLES}<h1>Shop</h1>'
        f'<p class="sub">Such dir aus, worauf du Lust hast: nach Herkunft, Geschmack und Art, frei kombinierbar.</p>'
        f'<button class="fake" type="button" data-open-search>{ICON_SEARCH}<span>z. B. „salzige Chips aus Asien“ …</span></button></section>'
        f'<nav class="themes" aria-label="Themenwelten"><h2>Themenwelten</h2><div class="trow">{theme_row}</div></nav>'
        f'<section id="alle" style="padding-top:18px">{shop_all}</section>',
        "Süßigkeiten aus aller Welt nach Herkunft, Geschmack und Art.", "/shop/"))

    # --- Posts-Seite: alle Posts mit Filter, Nummernsuche unten
    write("posts/index.html", page(
        "Alle Posts – Naschpass",
        f'<section class="hero" style="padding-bottom:0"><h1>Alle Posts</h1>'
        f'<p class="sub">Jede Woche neue Fakten über Süßigkeiten aus aller Welt.</p></section>'
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
                  f'{clip_grid([prod_card(p) for p in new_prods], "g-new", "prods")}<p class="wl">* Werbelink</p>'
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
    if tabs:
        browse_html = (f'<nav class="browse" aria-label="Stöbern"><h2>Stöbern nach</h2><div class="tabs" role="tablist">{tabs}</div>{panels}'
                       f'<p style="margin:10px 0 0"><a class="more" href="/shop/#alle">Alles frei filtern</a></p></nav>')
    else:
        ordered = sorted(cats, key=lambda c: -sum(1 for p in products if p.get("category") == c["id"]))
        browse_html = ('<nav class="browse" aria-label="Stöbern"><h2>Stöbern nach Land & Thema</h2><div class="bgrid">' + "".join(
            f'<a class="bc" href="/kategorie/{c["id"]}/">{sticker(c["id"], 40)}{e(c["name"])}<small>bald</small></a>' for c in ordered) + '</div></nav>')
    fan = "".join(f'<a href="/p/{p["id"]}/" tabindex="-1" aria-hidden="true">{slide_img(cover_url(p), "", 230, "230px")}</a>'
                  for p in newest[:3][::-1])
    home = (f'<section class="hero has-fan">{SPRINKLES}<div class="fan">{fan}</div><h1>Süßes aus <span class="acc">aller Welt</span></h1>'
            f'<p class="sub">{e(site["tagline"])} Und wo du es in Deutschland bekommst.</p>'
            f'<button class="fake" type="button" data-open-search>{ICON_SEARCH}<span>Snacks, Länder, Marken suchen …</span></button>'
            f'{browse_html}</section>'
            f'{band(live)}'
            f'{home_prods}'
            f'<section id="posts"><div class="head"><h2>Aus unseren Posts</h2>{view_toggle("g-home-posts", ["big", "small"], "small")}</div>'
            f'{clip_grid([post_card(p) for p in home_posts], "g-home-posts", "posts")}'
            f'{more_bar("g-home-posts", len(home_posts), len(live), "/posts/", f"Alle {len(live)} Posts")}</section>'
            f'{jump}')
    write("index.html", page("Naschpass – Süßigkeiten aus aller Welt", home))

    write("search.json", json.dumps(search_index(live), ensure_ascii=False, separators=(",", ":")))
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
<h2>4a. Suche</h2><p>Die Suche läuft komplett in deinem Browser. Deine Suchbegriffe werden nicht übertragen und nicht gespeichert.</p>
<h2>5. Social-Media-Links</h2><p>Links zu Instagram, TikTok und Pinterest sind einfache Verlinkungen, keine eingebetteten Inhalte. Daten werden erst übertragen, wenn du den Link anklickst und die jeweilige Plattform besuchst; dort gelten deren Datenschutzbestimmungen.</p>
<h2>6. Kontakt per E-Mail</h2><p>Schreibst du uns eine E-Mail, verarbeiten wir deine Angaben nur, um deine Anfrage zu beantworten (Art. 6 Abs. 1 lit. b bzw. f DSGVO), und löschen sie, wenn sie nicht mehr benötigt werden.</p>
<h2>7. Deine Rechte</h2><p>Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch (Art. 15–21 DSGVO). Außerdem kannst du dich bei einer Datenschutz-Aufsichtsbehörde beschweren, z. B. bei der Landesbeauftragten für Datenschutz und Informationsfreiheit Nordrhein-Westfalen.</p>
<p style="color:var(--mut);font-size:14px">Stand: Oktober 2026</p></section>""", "Datenschutz"))


    (DIST / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    for w in WARN:
        print("WARNUNG:", w)
    print("fertig:", DIST, "| Impressum-Adresse fehlt!" if missing else "")


if __name__ == "__main__":
    build()
