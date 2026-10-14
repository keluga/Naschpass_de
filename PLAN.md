# Naschpass – Stand und Plan (15.10.2026)

Für den nächsten Chat. Erst `CLAUDE.md` lesen, dann das hier. Technik-Details: `UEBERGABE_WEBSITE.md`, Partner: `PARTNER.md`, Bewerbungen: `BEWERBUNG_RUNDE2.md`.

## Stand
- Seite live auf Cloudflare: https://naschpass.oneflowsolution.de (Worker `naschpass`, baut bei jedem Push auf `main`, Vorschau je Branch unter `<branch>-naschpass.kevin-88e.workers.dev`). Netlify ist abgeschaltet.
- Erledigt im Oktober: Bilder-Fix (AWIN-Platzhalter → Shop-Originale), SEO-Paket (JSON-LD, Sitemap, robots, llms.txt), Suche mit Beispielsätzen, 12 Produkte auf der Startseite. Sitemap ist in der Google Search Console eingereicht.
- **Zugelassene AWIN-Partner (11):** SugarGang, REWE, GOURVITA, Piccantino, Burghardt Delicious, Sodapop, my-choco-world + **neu am 14./15.10.: World of Sweets (112586), Asiafoodland (15939), myfruits (103075), Haushalt-und-Genuss (83939)**. Die vier Neuen sind noch **nicht** eingebaut.
- Abgelehnt (nicht weiter verfolgen): Zotter, italienisch-einkaufen, Mexhaus, Venchi, BOS FOOD, Netto, unverträglich.de. Rest der Runde 2 offen.

## Phase 1: Neue Partner einbauen (nächster Chat, zuerst)
1. In AWIN unter Create-a-Feed (https://ui.awin.com → Tools → Create-a-Feed) Format + Feed-ID der vier Neuen nachsehen. Awin-Format → nur `fid` in `website/feeds.json` eintragen (`active: true`). Google-Format → Kev legt eine neue Variable `AWIN_FEED_URL_3` … in Cloudflare an. Kein Feed (vermutlich Asiafoodland, evtl. myfruits) → Kev schickt 3–5 Produktlinks, Handeintrag in `products.json`, Bild-Server in `site.json → partner_shops`.
2. World of Sweets ist der größte Partner (~8.000 Produkte, alles Süßes). Vorsicht: Nicht alles ungefiltert reinkippen, sonst erschlägt er die Exoten. `include`/`boost` in `feeds.json` so setzen, dass Länder-Exoten vorn bleiben.
3. Haushalt-und-Genuss: nur Food (Manner, Ölz, Meinl), Non-Food raus, Herkunft Österreich.
4. `PARTNER.md` aktualisieren, Vorschau prüfen (`/pruefen/`), `node website/test_ui.js`, dann erst „live“.

## Phase 2: Sortiment verstehen und Seite ausreizen
- Einmal sauber auswerten, was da ist: Produkte je Land / Geschmack / Art / Shop, Preisspannen, Lücken (z. B. Korea, UK, Skandinavien dünn?). Ergebnis als kurze Tabelle in `SORTIMENT.md`.
- Themenwelten nach den Daten schärfen: leere Welten ausblenden, volle teilen. Reihenfolge nach Saison (Weihnachten ab 1.11. vorn).
- Qualität: Dubletten über Shops, falsche Länderzuordnung, schwache Bilder. `overrides.json` und `sperrliste.json` nutzen.
- Preise: Vergleich desselben Produkts bei mehreren Shops anzeigen („günstigster Shop“), das ist ein echter Nutzen für Besucher.
- Danach Bewerbungsrunde 3 bei den noch offenen Programmen (Lauenstein, Dallmayr, Swiss Finest, Gustini …), diesmal mit vollem Sortiment.

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
> Lies `CLAUDE.md` und `PLAN.md` im Repo keluga/Naschpass_de. Wir starten mit Phase 1: die vier neuen AWIN-Partner (World of Sweets, Asiafoodland, myfruits, Haushalt-und-Genuss) einbauen. Ich bin in AWIN eingeloggt, wenn du Feed-IDs brauchst.
