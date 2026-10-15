# Naschpass – Stand und Plan (15.10.2026, nachts aktualisiert)

Für den nächsten Chat. Erst `CLAUDE.md` lesen, dann das hier. Technik-Details: `UEBERGABE_WEBSITE.md`, Partner: `PARTNER.md`, Bewerbungen: `BEWERBUNG_RUNDE2.md`.

## Stand
- Seite live auf Cloudflare: https://naschpass.oneflowsolution.de (Worker `naschpass`, baut bei jedem Push auf `main`, Vorschau je Branch unter `<branch>-naschpass.kevin-88e.workers.dev`). Netlify ist abgeschaltet.
- Erledigt im Oktober: Bilder-Fix (AWIN-Platzhalter → Shop-Originale), SEO-Paket (JSON-LD, Sitemap, robots, llms.txt), Suche mit Beispielsätzen, 12 Produkte auf der Startseite. Sitemap ist in der Google Search Console eingereicht.
- **Zugelassene AWIN-Partner (11):** SugarGang, REWE, GOURVITA, Piccantino, Burghardt Delicious, Sodapop, my-choco-world + **neu am 14./15.10.: World of Sweets (112586), Asiafoodland (15939), myfruits (103075), Haushalt-und-Genuss (83939)**. World of Sweets (Feed 101641) und Haushalt-und-Genuss (Feed 117069) sind live (PR #12); myfruits und Asiafoodland haben keinen Feed → Handeinträge, sobald Kev Produktlinks schickt.
- Abgelehnt (nicht weiter verfolgen): Zotter, italienisch-einkaufen, Mexhaus, Venchi, BOS FOOD, Netto, unverträglich.de. Rest der Runde 2 offen.

## Phase 1: Neue Partner einbauen – erledigt 15.10.
- feeds.json: beide Awin-Format-Feeds aktiv, Haushalt-und-Genuss nur Food (`include`), Herkunft Österreich per neuem Feld `land`.
- Bilder-Import drosselt jetzt je Shop (max. 2 gleichzeitig, Abkühlpause), weil gourvita.com sonst ~300 Produkte verliert (PR #13).
- Offen: Handeinträge myfruits + Asiafoodland (3–5 Produktlinks von Kev, Bild-Server in `site.json → partner_shops`).

## Phase 2: Sortiment verstehen und Seite ausreizen (läuft)
Kernidee: Der Build liefert bei jedem Lauf selbst den Sortiments-Bericht, Inventar-Check = ein Blick statt Handarbeit.
1. ✅ **Sortiments-Bericht im Build** (PR #14): `/sortiment.json` + Seite `/pruefen/sortiment/` (Shop × Herkunft × Art × Geschmack, Preise, ohne Herkunft/Art, unbekannte Marken, Dubletten über Shops, Themenwelt-Größen). Die nächtliche Action schreibt die Kurzfassung nach `SORTIMENT.md` (Verlauf im Git).
2. ✅ (PR #15: 20 Marken, Sammelkategorie raus, Art-Stichwörter; ohne Herkunft 3.380 → 2.509) **Lücken schließen nach Bericht:** Top-Marken ohne Herkunft in `brands.json`, `WELT_HINTS` erweitern; Piccantino-Bilder mit „410 Gone“ direkt als ausgelistet sperren.
3. ✅ (PR #16: 265 Karten mit mehreren Shops, 273 Doppel-Karten weniger) **„Günstigster Shop“:** gleiche Sorte bei mehreren Shops → eine Karte, mehrere Preise.
4. ✅ (PR #18: Welten genauer statt kleiner – Schokolade ohne Tee, Getränke ohne Süßes/Tee, Nusssnacks 3.538 → 500 echte; `not_facets`/`not_keywords`; Alkoholfilter mit Wortteilen, Root/Ginger Beer bleiben) **Themenwelten nach den Zahlen:** leere ausblenden, Riesen teilen (Schokolade 7.000+), Saison vorn.
5. **Build stabil:** Bild-Cache zwischen Builds behalten (z. B. GitHub-Release-Datei, kostenlos, braucht Token in Cloudflare).
- Danach Bewerbungsrunde 3 (Lauenstein, Dallmayr, Swiss Finest, Gustini …) mit vollem Sortiment.

## Phase 3: Marketing (Besucher, die kaufen)
Ziel: Leute erreichen, die gerade Süßigkeiten kaufen wollen. Reihenfolge nach Aufwand/Nutzen:
1. **Google (kostenlos, läuft schon an):** Seiten für Suchanfragen mit Kaufabsicht bauen, z. B. „japanische Süßigkeiten kaufen“, „amerikanische Süßigkeiten online“, „Adventskalender Süßigkeiten aus aller Welt“, „Lakritz aus Skandinavien“. Pro Suchbegriff eine Themenwelt mit 2–3 Absätzen echtem Text. Erfolg in der Search Console ablesen.
2. **Pinterest:** passt zum vorhandenen Karussell-Format, lange Lebensdauer der Pins, Kaufabsicht hoch. Pins direkt auf Themenwelten/Produktsuchen verlinken.
3. **Saison-Hooks:** Halloween (jetzt), Adventskalender (Oktober–November ist Kaufzeit!), Weihnachtsgeschenke, Valentinstag, Ostern. Jede Saison eine Landingpage + Posts.
4. **Reddit/Foren/Discord:** ehrlich als Betreiber auftreten, nur wo es passt (r/de, Snack-Communities, Mark's Discord).
5. Kein Geld für Ads, solange nicht klar ist, was konvertiert.

## Phase 4: Social-Media-Pipeline (nach Phase 3 messbar)
- Kevs Einschätzung: Karussells funktionieren eher auf Pinterest; TikTok/Instagram brauchen echte Videos (KI-generierte Personen, da kein eigenes Drehen). Das wird in einem separaten Chat geplant (Projekt `ki-video-pipeline` / Naschpass-Studio).
- Erst Formate testen, dann automatisieren. Messgröße ist nicht Follower, sondern Klicks auf Werbelinks → AWIN-Berichte (Klicks, Sales je Shop).

## Regeln, die bleiben
Kein Geld/Credits ohne OK. Nie selbst auf `main` mergen ohne „live“. Keine erfundenen Zahlen in Texten. Datenschutz: keine Cookies, kein Tracking, keine externen Skripte.

## Starter für den neuen Chat
> Lies `CLAUDE.md`, `PLAN.md` und `SORTIMENT.md` im Repo keluga/Naschpass_de. Wir machen mit Phase 2 weiter: Lücken aus dem Sortiments-Bericht schließen (Schritt 2), dann „günstigster Shop“.
