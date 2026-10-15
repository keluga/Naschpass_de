"""Schreibt SORTIMENT.md aus dem Sortiments-Bericht der Live-Seite (/sortiment.json, erzeugt von build.py).
Läuft nachts in der GitHub-Action (ohne Claude). Lokal: SORTIMENT_URL=<url> oder SORTIMENT_FILE=website/dist/sortiment.json."""
import json, os, urllib.request
from pathlib import Path

SRC = os.environ.get("SORTIMENT_URL", "https://naschpass.oneflowsolution.de/sortiment.json")
OUT = Path(__file__).resolve().parent.parent / "SORTIMENT.md"


def lade():
    f = os.environ.get("SORTIMENT_FILE")
    if f:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    req = urllib.request.Request(SRC, headers={"User-Agent": "naschpass-sortiment"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def tabelle(kopf, zeilen):
    return "| " + " | ".join(kopf) + " |\n|" + "|".join(" --- " for _ in kopf) + "|\n" + "".join("| " + " | ".join(str(c) for c in z) + " |\n" for z in zeilen)


def main():
    r = lade()
    shops = sorted(r["shops"].items(), key=lambda x: -x[1]["n"])
    md = [f"# Sortiment – Stand {r['stand']}", "",
          "Automatisch aus `/sortiment.json` (nächtliche Action, `tools/sortiment_md.py`). Volle Tabellen: `/pruefen/sortiment/` auf der Seite.", "",
          f"**{r['gesamt']} Produkte** · ohne Herkunft {r['ohne_land']} · ohne Art {r['ohne_art']} · Sorten bei mehreren Shops {r['dubletten']}", "",
          "## Je Shop", tabelle(["Shop", "Produkte", "ohne Herkunft", "ohne Art", "ohne Preis", "Bild schwach", "Preis median"],
                                [[s, v["n"], v["ohne_land"], v["ohne_art"], v["ohne_preis"], v["bild_klein"], f"{v['preis'][1]:.2f} €" if v.get("preis") else "–"] for s, v in shops]),
          "## Herkunft", tabelle(["Herkunft", "Produkte"], list(r["land"].items())),
          "## Art", tabelle(["Art", "Produkte"], list(r["art"].items())),
          "## Themenwelten", tabelle(["Welt", "Produkte", "Saison"], [[t["titel"], t["n"], "aktiv" if t["saison"] else ""] for t in r["themen"]]),
          "## Lücken", "Häufigste Marken ohne Herkunft (Kandidaten für `brands.json`):", "",
          tabelle(["Marke", "Produkte"], r["ohne_land_marken"][:25]),
          "Häufigste Namen ohne Art (Kandidaten für Stichwörter in `site.json → filter`):", "",
          tabelle(["Name", "Produkte"], r["ohne_art_namen"][:25]),
          "## Dubletten (gleiche Sorte, mehrere Shops)", tabelle(["Sorte", "Shops", "Preis"], [[d["name"], ", ".join(d["shops"]), f"{d['preis'][0]:.2f}–{d['preis'][1]:.2f} €" if d["preis"] else "–"] for d in r["dubletten_top"][:30]])]
    OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"SORTIMENT.md: {r['gesamt']} Produkte, Stand {r['stand']}")


if __name__ == "__main__":
    main()
