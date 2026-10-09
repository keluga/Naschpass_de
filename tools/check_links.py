"""Nächtlicher Verfügbarkeits-Check (läuft als GitHub-Action, ohne Claude).
Liest https://naschpass.oneflowsolution.de/check.json, ruft die DIREKTE Shop-Seite auf (nie den AWIN-Link,
sonst zählen falsche Klicks) und trägt eindeutig ausgelistete Produkte in website/sperrliste_auto.json ein.
Eindeutig = HTTP 404/410, Umleitung auf die Startseite oder Text wie "nicht mehr verfügbar".
Gesperrt (403/429), Zeitüberschreitung, Serverfehler = unklar -> nichts passiert.
Pro Nacht 1/7 der Produkte (alle mit ALLE=1). Bereits gesperrte werden mit geprüft und bei Rückkehr wieder frei."""
import json, os, re, sys, time, hashlib, datetime, threading, urllib.request, urllib.error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

SRC = os.environ.get("CHECK_URL", "https://naschpass.oneflowsolution.de/check.json")
OUT = os.path.join(os.path.dirname(__file__), "..", "website", "sperrliste_auto.json")
WEG = re.compile(r"nicht mehr (verfügbar|erhältlich|lieferbar|im sortiment)|dauerhaft ausverkauft|no longer available|"
                 r"artikel (wurde )?nicht gefunden|produkt nicht gefunden", re.I)
UA = "Mozilla/5.0 (compatible; NaschpassLinkCheck/1.0; +https://naschpass.oneflowsolution.de/impressum/)"


def check(m):
    try:
        req = urllib.request.Request(m, headers={"User-Agent": UA, "Accept-Language": "de-DE,de"})
        with urllib.request.urlopen(req, timeout=20) as r:
            final = r.geturl()
            body = r.read(400_000).decode("utf-8", "ignore")
        if urlparse(final).path in ("", "/") and urlparse(m).path not in ("", "/"):
            return "weg"
        return "weg" if WEG.search(body[:400_000]) else "ok"
    except urllib.error.HTTPError as e:
        return "weg" if e.code in (404, 410) else "unklar"
    except Exception:
        return "unklar"


def main():
    items = json.load(urllib.request.urlopen(urllib.request.Request(SRC, headers={"User-Agent": UA}), timeout=60))
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        old = {"eintraege": {}}
    sperr = old.get("eintraege", {})
    tag = datetime.date.today().toordinal() % 7
    alle = os.environ.get("ALLE") == "1"
    todo = [i for i in items if alle or int(hashlib.md5(i["u"].encode()).hexdigest(), 16) % 7 == tag]
    known = {i["u"] for i in items}
    # gesperrte Produkte, die gar nicht mehr im Feed sind, braucht die Liste nicht mehr
    sperr = {u: v for u, v in sperr.items() if u in known}
    todo += [i for i in items if i["u"] in sperr and i not in todo]
    # pro Shop nacheinander und mit Pause (höflich), Shops parallel
    by = {}
    for i in todo:
        by.setdefault(urlparse(i["m"]).netloc, []).append(i)
    res, lock = {}, threading.Lock()

    def run(host):
        for i in by[host]:
            r = check(i["m"])
            with lock:
                res[i["u"]] = (r, i)
            time.sleep(1.0)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(run, by))
    # Schutz pro Shop: meldet ein Shop über 30 % als weg, ist eher der Check kaputt (z. B. Text im Seiten-Template)
    kaputt = set()
    for host, lst in by.items():
        w = sum(1 for i in lst if res.get(i["u"], ("",))[0] == "weg")
        if len(lst) >= 10 and w > 0.3 * len(lst):
            kaputt.add(host)
            print(f"{host}: {w}/{len(lst)} als weg gemeldet – vermutlich Fehlalarm, ignoriert.")
    neu = frei = 0
    for u, (r, i) in res.items():
        if urlparse(i["m"]).netloc in kaputt:
            continue
        if r == "weg" and u not in sperr:
            sperr[u] = {"shop": i.get("s", ""), "seit": datetime.date.today().isoformat(), "shop_url": i["m"]}
            neu += 1
        elif r == "ok" and u in sperr:
            del sperr[u]
            frei += 1
    cnt = {k: sum(1 for r, _ in res.values() if r == k) for k in ("ok", "weg", "unklar")}
    print(f"Geprüft {len(res)} ({cnt}), neu gesperrt {neu}, wieder frei {frei}, gesperrt gesamt {len(sperr)}")
    json.dump({"_info": "Automatisch (tools/check_links.py). Nicht von Hand bearbeiten, dafür gibt es sperrliste.json.",
               "eintraege": sperr}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
