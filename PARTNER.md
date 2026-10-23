# Partner-Liste (AWIN, Publisher-ID 3111189)

Eine Zeile pro Partner. Stand: 23.10.2026. Wer was ändert, trägt es hier ein.
Technik dazu: `website/feeds.json` (welche Shops aktiv sind) und Cloudflare-Variablen `AWIN_FEED_URL`, `AWIN_FEED_URL_2` … (Feed-Links, **nie** ins Repo oder in den Chat).

## Zugelassen

| Shop | AWIN-ID | Feed-Format | Feed-ID | Produkte | Steckt in | Notiz |
| --- | --- | --- | --- | --- | --- | --- |
| Burghardt Delicious | 115505 | Awin | 103286 | ~450 | `AWIN_FEED_URL` | Nüsse, Snacks. Höhere Provision für feste Platzierung auf Anfrage |
| GOURVITA | 14403 | Awin | 54723 | ~3.000 | `AWIN_FEED_URL` | nur Süßes/Geschenke (Filter in feeds.json) |
| Piccantino | 79456 | Awin | 93446 | ~9.200 | `AWIN_FEED_URL` | Feed zuletzt 15.05.26 aktualisiert, evtl. veraltet; nur Süßes/Snacks |
| REWE | 11652 | Awin | 41437 (Lieferservice Overall) | ~7.500 | Vorlage `AWIN_FEED_URL` | 8 % Neukunden, 4 % Bestand, 30 Tage Cookie. Feed 26025 (Angebote) weglassen, wechselt wöchentlich |
| SugarGang | 127807 | **Google** | F4010 | ~120 | `AWIN_FEED_URL_2` ✅ | anderes Format, eigener Link, läuft. Exoten-Kern (Boost +4) |
| Sodapop | 42806 | Awin | 95717 (Default CSV) | ~80 | `AWIN_FEED_URL` | nur Sirupe/Getränke. Feed 82227 (XML) ist derselbe Inhalt, weglassen |
| my-choco-world | 16944 | kein Feed | – | 2 per Hand | `products.json` | Fotos nur nach Einwilligung |
| World of Sweets | 112586 | Awin | 101641 (Default) | ~8.400 | `AWIN_FEED_URL` | Zusage 14.10. Größter Partner, alles Süßes; Länder-Kategorien (GB, Italien, Japan, Mexiko, NL, AT, SE, KR, TH, TR). Brand Bidding verboten |
| Haushalt-und-Genuss | 83939 | Awin | 117069 (Dynamic/Live) | ~2.200 | `AWIN_FEED_URL` | Zusage 15.10. Nur Food (Manner, Ölz, Meinl), Herkunft Österreich per `land` in feeds.json. Feed 98990 ist eine alte Kopie (Juli), weglassen |
| myfruits | 103075 | kein Feed | – | – | – | Zusage 15.10. myfruits.de leitet am 15.10. auf Google um (Shop offline?) → noch nichts eingebaut, später erneut prüfen |
| Asiafoodland | 15939 | kein Feed | – | 12 per Hand | `products.json` | Zusage 14.10. Claude hat Mochi, Koikeya-Chips, Ramune, Buldak-Chips u. a. ausgewählt (Deeplinks `cread.php?awinmid=15939&awinaffid=3111189&ued=…`). Bild-Server asiafoodland.de (ShaNoo GmbH) in `partner_shops`, Fotos nur nach Einwilligung |
| Der Feinschmecker Shop | 42164 | Awin | 82129 | ~330 | `AWIN_FEED_URL` | Zusage 23.10. Nur Schokolade, Pralinen, Gebäck, Honig, Aufstriche (kein Wein, keine Bücher) |
| decocino | 74168 | **Google** | F102 | ~80 | `AWIN_FEED_URL_3` ⏳ | Zusage 23.10. Nur essbare Deko (Streusel, Oblaten, Zuckerschrift). Kev muss den Link noch in Cloudflare anlegen |
| glytter | 77590 | Awin | 92280 | ~30 | `AWIN_FEED_URL` | Zusage 23.10. Nur Glitzerpulver (kein Barzubehör) |

## Ausfall-Schutz (seit 23.10.)
World of Sweets fehlte am 23.10. komplett im Build (Programm laut AWIN aktiv). Seitdem: jeder Feed-Download hat einen zweiten Versuch, und liefert ein Shop unter 80 % vom letzten Lauf, ergänzt `import_feeds.py → auffuellen()` die fehlenden Produkte aus `feed_backup.json.gz` (Release `bilder-cache`, max. 7 Tage alt). Im Cloudflare-Build-Log steht dann „WARNUNG: … aus dem Vorrat ergänzt“.

## Abgelehnt
Zotter, italienisch-einkaufen, Mexhaus, Venchi, BOS FOOD, Netto, unverträglich.de (nicht weiter verfolgen). Rest der Runde 2 offen, siehe `BEWERBUNG_RUNDE2.md`.

## Offen
Siehe `WEBSITE_VISION.md`, Abschnitt 6.

## Ablauf bei einer neuen Zusage
1. Kev schreibt Claude: „Zusage XY“.
2. Claude schaut in die Feed-Liste (AWIN → Create-a-Feed → „feedList“-Download, Kev schickt die CSV) bzw. fragt nach Feed-ID + Format.
   - **Format „Awin“:** Claude trägt `fid` in `website/feeds.json` ein (`active: true`). **Kein neuer Link nötig** – der vorhandene `AWIN_FEED_URL` dient nur als Vorlage (Schlüssel + Format).
   - **Format „Google“:** Kev baut in AWIN einen eigenen Link nur für diesen Shop und legt ihn in Cloudflare als nächste Variable `AWIN_FEED_URL_3`, `_4` … an (Encrypt).
   - **Kein Feed:** Kev schickt 3–5 Produktseiten, Claude trägt sie per Hand ein.
3. Claude prüft die Vorschau (`/pruefen/`) und aktualisiert diese Liste.

Variablen liegen in Cloudflare: Workers & Pages → naschpass → Settings → Build → Variables.
