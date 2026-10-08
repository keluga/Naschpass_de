# Partner-Liste (AWIN, Publisher-ID 3111189)

Eine Zeile pro Partner. Stand: 08.10.2026. Wer was ändert, trägt es hier ein.
Technik dazu: `website/feeds.json` (welche Shops aktiv sind) und Netlify-Variablen `AWIN_FEED_URL`, `AWIN_FEED_URL_2` … (Feed-Links, **nie** ins Repo oder in den Chat).

## Zugelassen

| Shop | AWIN-ID | Feed-Format | Feed-ID | Produkte | Steckt in | Notiz |
| --- | --- | --- | --- | --- | --- | --- |
| Burghardt Delicious | 115505 | Awin | 103286 | ~450 | `AWIN_FEED_URL` | Nüsse, Snacks. Höhere Provision für feste Platzierung auf Anfrage |
| GOURVITA | 14403 | Awin | 54723 | ~3.000 | `AWIN_FEED_URL` | nur Süßes/Geschenke (Filter in feeds.json) |
| Piccantino | 79456 | Awin | 93446 | ~9.200 | `AWIN_FEED_URL` | Feed zuletzt 15.05.26 aktualisiert, evtl. veraltet; nur Süßes/Snacks |
| REWE | 11652 | Awin | 41437 (Lieferservice Overall) | ~7.500 | `AWIN_FEED_URL` | 8 % Neukunden, 4 % Bestand, 30 Tage Cookie. Feed 26025 (Angebote) weglassen, wechselt wöchentlich |
| SugarGang | 127807 | **Google** | F4010 | ~120 | `AWIN_FEED_URL_2` | anderes Format, eigener Link. Adventskalender! |
| Sodapop | 42806 | ? | ? | ~160 | ? | nur Sirupe/Getränke |
| my-choco-world | 16944 | kein Feed | – | 2 per Hand | `products.json` | Fotos nur nach Einwilligung |

## Abgelehnt
Zotter, Mexhaus (01.10., „URL nicht relevant“, alte Seite). Neu bewerben, wenn die neue Seite live ist.

## Offen
Siehe `WEBSITE_VISION.md`, Abschnitt 6.

## Ablauf bei einer neuen Zusage (Kev)
1. AWIN → Toolbox → **Create-a-Feed** → Advertiser suchen → Spalte **Format** ansehen.
2. **Format „Awin“:** im bestehenden Feed mit anhaken, neuen Link in Netlify bei `AWIN_FEED_URL` ersetzen.
   **Format „Google“:** eigenen Feed nur für diesen Shop bauen, Link als nächste freie Variable `AWIN_FEED_URL_2`, `_3` … eintragen.
   **Kein Feed:** Claude 3–5 Produktseiten-Links schicken, die kommen per Hand rein.
3. Netlify-Variablen: https://app.netlify.com/projects/naschpass/configuration/env (Bereich „All deploy contexts“, damit auch die Vorschau sie hat).
4. Claude Bescheid geben: „Zusage XY, Format Z“. Claude trägt ihn hier und in `feeds.json` ein und prüft die Vorschau.
