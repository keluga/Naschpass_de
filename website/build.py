"""Baut die Naschpass-Website nach website/dist/ (statisch, keine Cookies, kein Tracking).
Start: python website/build.py
Quellen: website/site.json, website/products.json, generator/posts.json, fertige_posts/
"""
import html
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / "dist"

site = json.loads((HERE / "site.json").read_text(encoding="utf-8"))
products = json.loads((HERE / "products.json").read_text(encoding="utf-8"))["products"]
posts = json.loads((ROOT / "generator" / "posts.json").read_text(encoding="utf-8"))["posts"]

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


CSS = """
@font-face{font-family:Anton;src:url(/static/Anton-Regular.ttf) format("truetype");font-display:swap}
@font-face{font-family:Inter;src:url(/static/Inter.ttf) format("truetype");font-weight:100 900;font-display:swap}
:root{--bg:#1B1036;--bg2:#241547;--card:#2C1A57;--fg:#FFF7EC;--mut:#CFC3E6;--pink:#FF4D8D;--yel:#FFD23F;--mint:#3DDC97}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.55 Inter,system-ui,sans-serif}
a{color:var(--yel)}img{max-width:100%;display:block}
.wrap{max-width:1040px;margin:0 auto;padding:0 18px}
.ad{background:var(--yel);color:var(--bg);font-size:13px;font-weight:600;text-align:center;padding:7px 12px}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 0}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--fg);font:26px Anton,sans-serif;letter-spacing:.5px}
.logo img{width:44px;height:44px;border-radius:50%}
nav a{color:var(--mut);text-decoration:none;font-weight:600;margin-left:14px;font-size:15px}
h1,h2,h3{font-family:Anton,sans-serif;font-weight:400;text-transform:uppercase;line-height:1.05;margin:0 0 .4em}
h1{font-size:clamp(44px,9vw,92px)}h2{font-size:clamp(30px,5vw,46px)}h3{font-size:24px}
.acc{color:var(--pink)}
.hero{padding:34px 0 26px;position:relative}
.hero p{font-size:19px;color:var(--mut);max-width:620px}
.socials{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0 6px}
.btn{display:inline-block;padding:13px 20px;border-radius:999px;font-weight:800;text-decoration:none;font-size:16px}
.btn.p{background:var(--pink);color:#fff}.btn.y{background:var(--yel);color:var(--bg)}.btn.o{border:2px solid var(--fg);color:var(--fg)}
section{padding:34px 0}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}
.card{background:var(--card);border-radius:18px;padding:18px;text-decoration:none;color:var(--fg);display:block;position:relative;overflow:hidden}
.card:hover{outline:2px solid var(--pink)}
.card p{color:var(--mut);margin:.2em 0 0;font-size:15px}
.soon{display:inline-block;margin-top:12px;font-size:12px;font-weight:800;letter-spacing:1px;color:var(--bg);background:var(--mint);border-radius:999px;padding:4px 10px}
.post img{border-radius:12px;margin-bottom:12px;aspect-ratio:4/5;object-fit:cover}
.post .num{font:14px Inter;font-weight:800;color:var(--yel)}
.prod img{border-radius:12px;background:#fff;aspect-ratio:1;object-fit:contain;margin-bottom:10px}
.slides{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:10px}
.slides img{width:min(78vw,380px);border-radius:14px;scroll-snap-align:start;flex:none}
.cap{background:var(--card);border-radius:16px;padding:18px;white-space:pre-line;color:var(--mut)}
.sprinkle{position:absolute;width:40px;height:12px;border-radius:6px;opacity:.9}
footer{border-top:1px solid #3a2a66;margin-top:30px;padding:24px 0 40px;color:var(--mut);font-size:14px}
footer a{color:var(--mut);margin-right:14px}
.legal h2{font-size:28px;margin-top:1.2em}.legal{max-width:760px}
@media(max-width:700px){.sprinkle{display:none}}
.warn{background:#5a1030;border:2px solid var(--pink);padding:14px;border-radius:12px}
"""

SPRINKLES = "".join(
    f'<i class="sprinkle" style="background:{c};top:{t}%;left:{l}%;transform:rotate({r}deg)"></i>'
    for c, t, l, r in [("#FF4D8D", 8, 88, 30), ("#FFD23F", 30, 95, 120), ("#3DDC97", 70, 90, 60),
                       ("#FFF7EC", 88, 80, 150), ("#FFD23F", 4, 60, 20)])


def page(title, body, desc=None, path="/"):
    desc = desc or site["intro"]
    socials = " ".join(f'<a href="{s["url"]}" rel="noopener" target="_blank">{s["name"]}</a>' for s in site["socials"])
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<link rel="icon" href="/static/favicon.png"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}"><meta property="og:image" content="/static/logo.png">
<style>{CSS}</style></head><body>
<div class="ad">Enthält Werbelinks: Kaufst du über einen Shop-Link, bekomme ich eine kleine Provision. Dein Preis bleibt gleich.</div>
<div class="wrap"><header><a class="logo" href="/"><img src="/static/logo.png" alt="">NASCHPASS</a>
<nav><a href="/#kategorien">Shop</a><a href="/#posts">Posts</a></nav></header>
{body}
<footer>{socials}<br><br><a href="/impressum/">Impressum</a><a href="/datenschutz/">Datenschutz</a>
<span>© Naschpass · Keine Cookies, kein Tracking.</span></footer></div></body></html>"""


def prod_cards(items):
    out = []
    for p in items:
        img = f'<img src="{e(p["image"])}" alt="{e(p["name"])}" loading="lazy">' if p.get("image") else ""
        out.append(f'<a class="card prod" href="{e(p["url"])}" rel="sponsored noopener" target="_blank">{img}'
                   f'<h3>{e(p["name"])}</h3><p>{e(p.get("note", ""))}</p>'
                   f'<span class="btn p" style="margin-top:12px">Hier kaufen*</span></a>')
    return "".join(out)


def write(rel, content):
    f = DIST / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(HERE / "static", DIST / "static")

    socials_btns = "".join(
        f'<a class="btn {"p" if i == 0 else "o"}" href="{s["url"]}" rel="noopener" target="_blank">{s["name"]}</a>'
        for i, s in enumerate(site["socials"]))

    cats = []
    for c in site["categories"]:
        n = sum(1 for p in products if p.get("category") == c["id"])
        badge = f'<span class="soon">{n} PRODUKTE</span>' if n else '<span class="soon">BALD HIER</span>'
        cats.append(f'<a class="card" href="/kategorie/{c["id"]}/"><h3>{e(c["name"])}</h3><p>{e(c["teaser"])}</p>{badge}</a>')
        items = [p for p in products if p.get("category") == c["id"]]
        inner = (f'<div class="grid">{prod_cards(items)}</div><p style="color:var(--mut);font-size:13px">* Werbelink</p>'
                 if items else '<p class="cap">Hier kommen bald die besten Produkte rein. Folg uns, dann verpasst du nichts.</p>')
        write(f"kategorie/{c['id']}/index.html", page(
            f"{c['name']} – Naschpass", f'<section><h1>{e(c["name"])}</h1><p>{e(c["teaser"])}</p>{inner}'
            f'<div class="socials">{socials_btns}</div></section>', c["teaser"]))

    post_cards = []
    for p in reversed(posts):
        folder = ROOT / "fertige_posts" / post_folder(p)
        if not folder.exists():
            continue
        dest = DIST / "p" / p["id"]
        dest.mkdir(parents=True, exist_ok=True)
        imgs = sorted(x for x in folder.glob("[0-9][0-9].jpg"))
        for x in imgs:
            shutil.copy(x, dest / x.name)
        post_cards.append(f'<a class="card post" href="/p/{p["id"]}/"><img src="/p/{p["id"]}/01.jpg" alt="" loading="lazy">'
                          f'<span class="num">#{p["id"]}</span><h3>{plain(p["hook"])}</h3></a>')
        items = [x for x in products if str(x.get("post", "")) == p["id"]]
        prods = (f'<h2>Die Süßigkeiten aus dem Post</h2><div class="grid">{prod_cards(items)}</div>'
                 f'<p style="color:var(--mut);font-size:13px">* Werbelink</p>') if items else \
                '<h2>Die Süßigkeiten aus dem Post</h2><p class="cap">Die passenden Produkte kommen hier bald rein.</p>'
        srcs = "".join(f'<li><a href="{e(s["url"])}" rel="noopener" target="_blank">{e(s["title"])}</a></li>'
                       for s in p.get("sources", []))
        slides = "".join(f'<img src="/p/{p["id"]}/{x.name}" alt="Folie {i + 1}" loading="lazy">' for i, x in enumerate(imgs))
        body = (f'<section><span class="num" style="color:var(--yel);font-weight:800">NASCHPASS #{p["id"]}</span>'
                f'<h1>{accent(p["hook"])}</h1><div class="slides">{slides}</div></section>'
                f'<section>{prods}</section>'
                + (f'<section><h2>Quellen</h2><ul>{srcs}</ul></section>' if srcs else "")
                + f'<section><div class="socials">{socials_btns}</div></section>')
        write(f"p/{p['id']}/index.html", page(f"#{p['id']} {plain(p['hook'])} – Naschpass", body, plain(p["sub"])))

    home = (f'<section class="hero">{SPRINKLES}<h1>Süßes aus<br><span class="acc">aller Welt</span></h1>'
            f'<p>{e(site["intro"])}</p><div class="socials">{socials_btns}</div></section>'
            f'<section id="posts"><h2>Aus den <span class="acc">Posts</span></h2>'
            f'<p style="color:var(--mut)">Du kommst von Instagram oder TikTok? Such hier die Nummer aus dem Post.</p>'
            f'<div class="grid">{"".join(post_cards)}</div></section>'
            f'<section id="kategorien"><h2>Entdecken</h2><div class="grid">{"".join(cats)}</div></section>')
    write("index.html", page("Naschpass – Süßigkeiten aus aller Welt", home))

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
<h2>2. Kurz gesagt</h2><p>Diese Website setzt keine Cookies, nutzt keine Analyse- oder Tracking-Tools und lädt keine Inhalte von Drittanbietern. Schriften und Bilder liegen auf unserem eigenen Server.</p>
<h2>3. Hosting</h2><p>Die Website wird bei Netlify, Inc., 101 2nd Street, San Francisco, CA 94105, USA gehostet. Beim Aufruf verarbeitet Netlify technisch notwendige Daten (z. B. IP-Adresse, Datum und Uhrzeit, aufgerufene Seite, Browser) in Server-Logfiles, um die Seite auszuliefern und die Sicherheit zu gewährleisten. Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an einem sicheren und stabilen Betrieb). Dabei können Daten in die USA übermittelt werden; die Übermittlung erfolgt auf Grundlage der EU-Standardvertragsklauseln bzw. des EU-US Data Privacy Framework, soweit der Anbieter dort zertifiziert ist. Mit Netlify besteht ein Vertrag zur Auftragsverarbeitung. Details: <a href="https://www.netlify.com/privacy/" rel="noopener" target="_blank">netlify.com/privacy</a></p>
<h2>4. Werbelinks (Affiliate)</h2><p>Einige Links führen zu Online-Shops und sind mit einer Partnerkennung versehen (z. B. über das Netzwerk Awin). Erst wenn du einen solchen Link anklickst, verlässt du diese Website; der Shop bzw. das Partnernetzwerk kann dann auf seiner eigenen Seite Cookies setzen, um den Kauf zuzuordnen. Dafür ist der jeweilige Anbieter verantwortlich. Auf dieser Website selbst wird dabei nichts gespeichert.</p>
<h2>5. Social-Media-Links</h2><p>Links zu Instagram, TikTok und Pinterest sind einfache Verlinkungen, keine eingebetteten Inhalte. Daten werden erst übertragen, wenn du den Link anklickst und die jeweilige Plattform besuchst; dort gelten deren Datenschutzbestimmungen.</p>
<h2>6. Kontakt per E-Mail</h2><p>Schreibst du uns eine E-Mail, verarbeiten wir deine Angaben nur, um deine Anfrage zu beantworten (Art. 6 Abs. 1 lit. b bzw. f DSGVO), und löschen sie, wenn sie nicht mehr benötigt werden.</p>
<h2>7. Deine Rechte</h2><p>Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch (Art. 15–21 DSGVO). Außerdem kannst du dich bei einer Datenschutz-Aufsichtsbehörde beschweren, z. B. bei der Landesbeauftragten für Datenschutz und Informationsfreiheit Nordrhein-Westfalen.</p>
<p style="color:var(--mut);font-size:14px">Stand: Oktober 2026</p></section>""", "Datenschutz"))

    (DIST / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    print("fertig:", DIST, "| Impressum-Adresse fehlt!" if missing else "")


if __name__ == "__main__":
    build()
