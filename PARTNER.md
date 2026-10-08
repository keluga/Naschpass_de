# Partner-Liste (AWIN, Publisher-ID 3111189)

Eine Zeile pro Partner. Stand: 08.10.2026. Wer was ändert, trägt es hier ein.
Technik dazu: `website/feeds.json` (welche Shops aktiv sind) und Netlify-Variablen `AWIN_FEED_URL`, `AWIN_FEED_URL_2` … (Feed-Links, **nie** ins Repo oder in den Chat).

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

## Abgelehnt
Zotter, Mexhaus (01.10., „URL nicht relevant“, alte Seite). Neu bewerben, wenn die neue Seite live ist.

## Offen
Siehe `WEBSITE_VISION.md`, Abschnitt 6.

## Ablauf bei einer neuen Zusage
1. Kev schreibt Claude: „Zusage XY“.
2. Claude schaut in `datafeeds.csv` (Feed-Übersicht) bzw. fragt nach Feed-ID + Format.
   - **Format „Awin“:** Claude trägt `fid` in `website/feeds.json` ein (`active: true`). **Kein neuer Link nötig** – der vorhandene `AWIN_FEED_URL` dient nur als Vorlage (Schlüssel + Format).
   - **Format „Google“:** Kev baut in AWIN einen eigenen Link nur für diesen Shop und legt ihn in Cloudflare als nächste Variable `AWIN_FEED_URL_3`, `_4` … an (Encrypt).
   - **Kein Feed:** Kev schickt 3–5 Produktseiten, Claude trägt sie per Hand ein.
3. Claude prüft die Vorschau (`/pruefen/`) und aktualisiert diese Liste.

Variablen liegen in Cloudflare: Workers & Pages → naschpass → Settings → Build → Variables (Netlify nur noch bis zur Umstellung).
