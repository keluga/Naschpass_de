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
- Große Feeds nur über "only" (Regex auf Kategorie/Name).
- Pro Shop höchstens "max" (Standard 120), insgesamt "max_total"; Shops und Kategorien werden gemischt.
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
DUMP = os.environ.get("CONTEXT") == "deploy-preview" or os.environ.get("FEED_DUMP") == "1"
DUMP_ROWS = []

ALKOHOL = re.compile(
    r"\b(wein|weine|rotwein|weißwein|weisswein|ros[eé]wein|sekt|prosecco|champagner|cava|spirituose\w*|lik[öo]r\w*|likoer\w*|"
    r"bier|biere|gin|rum|wodka|vodka|whisk(e)?y|tequila|mezcal|grappa|limoncello|amaro|brandy|cognac|schnaps|aperitif|"
    r"vermouth|wermut|sake|alkohol\w*|vol\.?\s*%|\d+([.,]\d+)?\s*%\s*vol)\b", re.I)
NONFOOD = re.compile(
    r"\b(tasse|becher|teller|schale|geschirr|porzellan|st[äa]bchen|messer|gabel|l[öo]ffel|topf|pfanne|buch|kochbuch|t-?shirt|"
    r"shirt|hoodie|socken|kerze|deko|dekoration|vase|gutschein|geschenkgutschein|spielzeug|pl[üu]sch|kosmetik|seife|duft|"
    r"backform|ausstecher|dose leer|grill)\b", re.I)
NO = {"0", "no", "nein", "false", "n", "out of stock", "outofstock", "out_of_stock", "nicht verfügbar"}

ALIASES = {
    "name": ["product_name", "name", "title"],
    "desc": ["description", "product_short_description"],
    "url": ["aw_deep_link", "deep_link", "link"],
    "image": ["aw_image_url", "aw_thumb_url", "image_link"],
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
    for i, k in enumerate(["AWIN_FEED_URL"] + [f"AWIN_FEED_URL_{n}" for n in range(2, 10)], 1):
        for part in (os.environ.get(k) or "").split():
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
    only = {k: re.compile(a["only"], re.I) for k, a in adv.items() if a.get("only")}
    manual = json.loads((HERE / "products.json").read_text(encoding="utf-8")).get("products", [])
    seen = {norm(p.get("name", "")) for p in manual} | {p.get("url", "") for p in manual}

    buckets = {}  # shop -> kategorie -> [produkte]
    stats = {"zeilen": 0, "inaktiv": 0, "lager": 0, "alkohol": 0, "nonfood": 0, "kategorie": 0, "ohne_bild": 0, "doppelt": 0}
    for label, src, is_url in srcs:
        path = download(src, label) if is_url else src
        if not path:
            continue
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
                    if DUMP:
                        DUMP_ROWS.append([a.get("shop", ""), name[:120], col(row, "mcat")[:80], col(row, "cat")[:80],
                                          col(row, "brand")[:40], col(row, "desc")[:160], col(row, "stock")[:12], 1 if img else 0])
                    if not name or not url:
                        continue
                    if col(row, "stock").lower() in NO:
                        stats["lager"] += 1
                        continue
                    mcat, cat, brand = col(row, "mcat"), col(row, "cat"), col(row, "brand")
                    hay = f"{name} {mcat} {cat}"
                    if ALKOHOL.search(hay):
                        stats["alkohol"] += 1
                        continue
                    if NONFOOD.search(hay):
                        stats["nonfood"] += 1
                        continue
                    if mid in only and not only[mid].search(hay):
                        stats["kategorie"] += 1
                        continue
                    if not img or not any(r.match(img) for r in REMOTE_OK):
                        stats["ohne_bild"] += 1
                        continue
                    key = norm(f"{name} {brand}")
                    if key in seen or norm(name) in seen or url in seen:
                        stats["doppelt"] += 1
                        continue
                    seen.update({key, url})
                    shop = a.get("shop") or col(row, "merchant_name")
                    p = {"name": name[:120], "url": url, "image": img, "shop": shop, "brand": brand,
                         "feed_category": " ".join(x for x in (mcat, cat) if x)[:160], "source": "awin", "advertiser": int(mid)}
                    if a.get("themen"):
                        p["themen"] = a["themen"]
                    buckets.setdefault(shop, {}).setdefault(mcat or cat or "-", []).append(p)
        except Exception as ex:
            log(f"Feed {label}: konnte nicht gelesen werden ({type(ex).__name__}). Weiter ohne diesen Feed.")
        finally:
            if is_url and path:
                os.unlink(path)

    # Pro Shop über die Kategorien mischen, dann Shops reihum mischen
    per_shop = {}
    for shop, cats in buckets.items():
        lim = next((a.get("max", 40000) for a in adv.values() if a.get("shop") == shop), 40000)
        lists, picked = list(cats.values()), []
        while len(picked) < lim and any(lists):
            for l in lists:
                if l and len(picked) < lim:
                    picked.append(l.pop(0))
        per_shop[shop] = picked
    total, result = conf.get("max_total", 1200), []
    while len(result) < total and any(per_shop.values()):
        for l in per_shop.values():
            if l and len(result) < total:
                result.append(l.pop(0))

    if DUMP and DUMP_ROWS:
        d = HERE / "static" / "_dump"
        d.mkdir(exist_ok=True)
        with gzip.open(d / "rows.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(DUMP_ROWS, fh, ensure_ascii=False)
        log(f"Vorschau-Dump: {len(DUMP_ROWS)} Zeilen")
    OUT.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "products": result}, ensure_ascii=False), encoding="utf-8")
    shops = {}
    for p in result:
        shops[p["shop"]] = shops.get(p["shop"], 0) + 1
    log(f"{len(result)} Produkte übernommen: " + ", ".join(f"{k} {v}" for k, v in sorted(shops.items())))
    log("Aussortiert: " + ", ".join(f"{k} {v}" for k, v in stats.items()))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        log(f"Unerwarteter Fehler ({type(ex).__name__}). Build läuft ohne Feed weiter.")
        OUT.unlink(missing_ok=True)
    sys.exit(0)
