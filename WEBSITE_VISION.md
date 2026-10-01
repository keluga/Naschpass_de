# Website: Vision und nächste Schritte

Stand: 01.10.2026. Ergänzt `UEBERGABE_WEBSITE.md`, dessen Regeln weiter gelten (Recht, Datenschutz, Datenquellen). Geschrieben nach Durchsicht von Branch `design-c` / Deploy-Preview 1. Was dort schon gebaut ist (Shop mit Filtern Woher/Geschmack/Art, Suche, Netlify Image CDN, Einwilligungs-Leiste für Shop-Fotos, Demo-Produkte nur in Previews), bleibt die Grundlage. Dieses Dokument sagt, wohin es geht.

## 0. Sofort: Seite muss für AWIN-Prüfer überzeugen
Am 01.10. haben Zotter und Mexhaus Kevs Bewerbung abgelehnt, beide mit dem Grund „URL ist für die Advertiser-Marke nicht relevant“. Weitere 26 Bewerbungen sind offen. Die Prüfer schauen sich die Live-Seite an, und dort läuft noch das alte Design: 2 Produkte, überall „Bald hier“. Deshalb hat das Vorrang vor allem anderen:

1. **`design-c` nach `main` mergen** und live nehmen. Vorher prüfen:
   - keine Demo-Produkte oder Beispiel-Shops auf `main`
   - Frequenz-Texte aus Abschnitt 2 korrigiert
   - HTTPS funktioniert (Stand 01.10. ok)
2. **Themenwelten für die offenen Bewerbungen sichtbar machen** (Abschnitt 4): Schokolade & Pralinen, Weihnachten & Geschenke, Mexiko, Italien, Schweiz, Getränke, Snacks. Jede bekommt 2–3 Sätze echten redaktionellen Text, worum es geht: Herkunft, Besonderheiten, verlinkte Posts, falls vorhanden. Keine erfundenen Produkte, keine erfundenen Zahlen. Solange keine Produkte da sind: Text plus „Produkte folgen, sobald Partner-Shops freigeschaltet sind“.
3. **Seite „Über Naschpass“ / „Für Partner“** (verlinkt in Footer und Startseite):
   - **Konzept:** Karussell-Posts über Süßigkeiten aus aller Welt mit Quellen, für Erwachsene.
   - **Kanäle:** Instagram, TikTok, Pinterest, Website.
   - **Was Partner bekommen:** Produkte in passenden Themenwelten und auf Post-Seiten, als Werbung gekennzeichnet, keine Gutscheinseite, keine bezahlten Anzeigen.
   - **Kontakt:** E-Mail aus dem Impressum.
   - Ehrlich: Kanal ist neu, keine Reichweitenzahlen erfinden.
4. **Startseite:** Ein Prüfer muss in 5 Sekunden sehen, worum es geht. Die Posts zeigen, dazu die Themenwelten Schokolade, Länder und Weihnachten weit oben.
5. **Danach** meldet Kev sich im anderen Chat. Dort wird die Seite aus Prüfer-Sicht gecheckt, und Kev bewirbt sich bei Zotter und Mexhaus neu.

## 1. Vision
Auf naschpass.oneflowsolution.de findet jeder eine passende Süßigkeit. Das kann die exotische aus dem Post sein oder der Supermarkt-Klassiker, sortiert nach Herkunft, Geschmack, Art und Anlass. Jede Süßigkeit hat einen Link zu einem Shop, der nach Deutschland liefert. Die Produkte kommen automatisch aus den AWIN-Feeds, Kev pflegt nur Ausnahmen per Hand.

- **Besucher:** fast alle vom Handy, aus TikTok, Instagram oder Pinterest („Link in Bio → #09“). Weg: Post-Nummer → Post-Seite → Produkte aus dem Post, in 1–2 Taps.
- **Stöbern:** „Was gibt es aus Japan?“, „Was Saures?“, „Geschenk zu Weihnachten?“ → Themenwelten, Filter, Suche.
- **Breite:** Exoten und Standardmarken. Wer Haribo sucht, soll es auch finden.
- **Zielgruppe:** Erwachsene. Keine Ansprache von Kindern, keine Kauf-Appelle, Button bleibt „Zum Shop*“.

## 2. Grundregel: nichts versprechen, was es nicht gibt
- Keine Preise anzeigen. Feed-Preise veralten zwischen zwei Builds.
- Keine erfundenen Bewertungen, Bestseller-Labels oder Lagerstände.
- Keine Beispiel- oder Platzhalter-Shops live. Demo nur mit `DEMO=1` in Previews, so wie jetzt. Vor jedem Merge prüfen, dass auf `main` nur echte Produkte mit echten Affiliate-Links landen.
- Texte, die eine Frequenz versprechen, erst wenn sie stimmt:
  - `site.json → intro`: „Jede Woche zeigen wir dir …“
  - Footer: „Jede Woche neue Süßigkeiten aus aller Welt.“

  Die Posts laufen noch nicht wöchentlich. Vorschlag: „Wir zeigen dir die verrücktesten Süßigkeiten der Welt – und wo du sie in Deutschland bekommst.“

## 3. Was in den AWIN-Bewerbungen versprochen wurde (muss existieren)
Kev hat sich am 01.10. bei 28 Programmen beworben. In den Texten steht:

| Versprochen | an | Umsetzung |
| --- | --- | --- |
| eigene Italien-Rubrik, Italien-Content | Gustini, italienisch-einkaufen, Venchi | Woher-Option `italien` und Themenwelt Italien |
| Schweiz / Toblerone-Post | Swiss Finest | Woher-Option `schweiz`; Post #12 steht in `THEMEN.md` |
| „Japan und Asien“ als Rubrik | Asiafoodland, EasyCookAsia | Themenwelt Japan als „Japan & Asien“ anzeigen (id `japan` bleibt) |
| Getränke | Sodapop | Art `getraenke` gibt es; als Themenwelt sichtbar machen |
| Weihnachts-Geschenktipps, Adventszeit | Lauenstein, Dallmayr, GOURVITA, Venchi, Sultan's Palace, Pati-Versand | Themenwelt „Weihnachten“ (siehe 4) |
| Snacks, Gefriergetrocknetes | Kultsnack, Burghardt, MaxGenuss, Barebells | Art `snacks` (Nüsse, Trockenfrüchte, gefriergetrocknet, Riegel); Post-Thema #21 steht in `THEMEN.md` |
| „Alle Links als Werbung gekennzeichnet“ | alle | so lassen |

## 4. Taxonomie-Ergänzungen (`site.json → filter` / `categories`)
Bestehende ids nicht umbenennen, sonst brechen Links.
- **Woher:** neu `italien` (keywords z. B. italien, italia, panettone, pandoro, torrone, cantucci, baci, venchi) und `schweiz` (schweiz, swiss, suisse, toblerone, ricola, lindt, cailler). Beide in `europa` per `includes`.
- **Art:** neu `snacks` (nuss, nüsse, trockenfrucht, gefriergetrocknet, freeze, riegel, snack) und `pralinen` (praline, trüffel, konfekt).
- **Themenwelten (`categories`)** ergänzen:
  - `weihnachten` „Weihnachten“: keywords weihnacht, advent, adventskalender, lebkuchen, stollen, spekulatius, christmas, panettone. Saisonal: 01.11.–26.12. oben auf Start- und Shop-Seite, sonst ans Ende oder aus.
  - `klassiker` „Supermarkt-Klassiker“: Standardmarken aus REWE/Netto-Feeds.
  - `italien`, `schweiz`, `getraenke`, `snacks`, wenn Produkte da sind.
- **Leere Themenwelten:** ausblenden oder „Bald hier“. Nie als gefüllt darstellen.

## 5. Hauptaufgabe: Feed-Import
Ziel: Sobald ein Partner zusagt, erscheinen seine Produkte automatisch.

**Quelle und Schlüssel**
- Quelle: AWIN Create-a-Feed (CSV, ggf. gzip). Der Download-Link enthält Kevs **API-Schlüssel**.
- Der Schlüssel kommt **nie** ins Repo, in einen Chat oder in Logs.
- Kev trägt ihn selbst in Netlify ein: Site configuration → Environment variables, z. B. `AWIN_FEED_URL`.

**Skript `website/import_feeds.py`** (nur Standardbibliothek), läuft im Build vor `build.py`. Schritte:
1. Ohne Umgebungsvariable überspringen. Der Build darf nie daran scheitern, dann gelten nur `products.json` (bzw. Demo in Previews).
2. Feed laden. Nur Advertiser übernehmen, die in `website/feeds.json` mit `"active": true` stehen.
3. Filtern: nicht vorrätig raus. **Alkohol raus** (Wein, Sekt, Spirituosen, Likör, Bier; betrifft Dallmayr, Mexhaus, italienisch-einkaufen). Non-Food raus.
4. Felder auf das bestehende Schema abbilden:
   - `name`
   - `url` = `aw_deep_link` (enthält Publisher-ID 3111189, unverändert lassen)
   - `image` = `aw_image_url` (läuft über `images2.productserve.com`, schon in `netlify.toml` erlaubt; `merchant_image_url` nicht nutzen)
   - `shop`, `brand`, `feed_category`
   - Zuordnung zu Woher/Geschmack/Art macht die vorhandene Keyword-Logik.
5. Begrenzen: pro Themenwelt und Shop eine sinnvolle Menge (z. B. max. 48 je Themenwelt, Shops mischen, Dubletten über Name+Marke entfernen). Große Feeds (Netto 137.000, BOS FOOD 9.800) **nur über Kategorie-Filter** übernehmen.
6. Manuelle Einträge aus `products.json` haben Vorrang (Post-Picks, Shops ohne Feed).

**Weitere Hinweise**
- Spaltennamen beim ersten echten Feed prüfen (erwartet: aw_deep_link, product_name, merchant_id, merchant_name, aw_image_url, merchant_category, category_name, brand_name, in_stock).
- **Zum Entwickeln:** Kev lädt einen Feed einmal selbst als CSV herunter und gibt ihn dem Chat. Die Datei enthält keinen Schlüssel.
- **Aktualisierung:** Jeder Push baut neu (sonntags durch den Wochenlauf). Häufiger erst später, z. B. Netlify Build Hook + zeitgesteuerter GitHub-Action. Die Free-Build-Minuten im Blick behalten, nichts Kostenpflichtiges ohne Kevs OK.

**`website/feeds.json` (Vorschlag)**
```json
{"advertisers": [
  {"id": 112586, "shop": "World of Sweets", "active": false},
  {"id": 11652, "shop": "REWE", "active": false, "only": "Süßwaren|Schokolade|Fruchtgummi|Kekse|Chips|Getränke", "themen": ["klassiker"]},
  {"id": 13812, "shop": "Netto", "active": false, "only": "Süßwaren|Schokolade|Snacks", "themen": ["klassiker"]}
]}
```

## 6. Partner-Stand (AWIN, Publisher-ID 3111189)
Zugelassen: **my-schoko-world 16944** (kein Feed, 2 Produkte per Hand, Fotos nach Einwilligung).

Bewerbung offen (28):

| ID | Shop | Feed (Produkte) | passt zu |
| --- | --- | --- | --- |
| 112586 | World of Sweets | 8.103 | alles: Länder, Sorten, Getränke, Boxen |
| 11652 | REWE | 7.814 | Supermarkt-Klassiker, Getränke |
| 13812 | Netto Marken-Discount | 137.354 | Klassiker (stark filtern) |
| 14396 | Zotter (DACH) | 2.094 | Schokolade, Weihnachten, Geschenke |
| 14610 | Confiserie Lauenstein | 1.040 | Pralinen, Weihnachten, Geschenke |
| 11832 | Dallmayr | 5.101 | Pralinen, Präsente, Weihnachten (kein Wein) |
| 14403 | GOURVITA | 2.980 | Süßwaren, Geschenke |
| 100069 | Venchi | 224 | Italien, Schokolade, Weihnachten |
| 117407 | Swiss Finest | 2.032 | Schweiz, Schokolade |
| 11419 | Gustini | 621 | Italien |
| 128981 | italienisch-einkaufen | 1.403 | Italien (kein Alkohol) |
| 104845 | Mexhaus | 879 | Mexiko, scharf (kein Alkohol) |
| 129605 | Nordland.Shop | 1.584 | Skandinavien (nur Food) |
| 127807 | SugarGang | 122 | Fruchtgummi, sauer |
| 129755 | Kultsnack | 126 | Snacks, gefriergetrocknet |
| 129753 | Sultan's Palace | 187 | Schokofrüchte, Geschenke |
| 19712 | BOS FOOD | 9.835 | Länder (filtern) |
| 79456 | Piccantino | 9.247 | scharf (filtern) |
| 15953 | Velivery | 163 | vegane Süßwaren |
| 42806 | Sodapop | 156 | Getränke (Sirupe) |
| 11746 | Pati-Versand | 6.470 | Pralinen-/Backzutaten, Weihnachten |
| 115505 | Burghardt Delicious | 441 | Snacks, Nüsse |
| 13493 | brandnooz | kein Feed | Boxen (per Hand) |
| 25874 | unverträglich.de | kein Feed | per Hand |
| 14082 | chili-shop24 | kein Feed | scharf (per Hand) |
| 15939 | Asiafoodland | kein Feed | Japan & Asien (per Hand) |
| 116073 | Barebells | kein Feed | Snacks (per Hand) |
| 128775 | MaxGenuss | kein Feed | Snacks (per Hand) |

- **Bei einer Zusage:** in `feeds.json` `active: true` setzen. Status sieht Kev im AWIN-Konto.
- **Keine Produkte von:** Ahead, KoRo, myTime, Paul Schrader (Zahlungsprobleme bei AWIN).
- **Keine Gesundheitsaussagen**, auch nicht bei Barebells, Velivery oder unverträglich.de. Produktnamen wie „Proteinriegel“ sind ok, eigene Claims („gesund“, „weniger Zucker“) nicht.

## 7. Reihenfolge
1. Frequenz-Texte korrigieren (Abschnitt 2) und `design-c` nach `main` mergen, wenn Kev das Design abnimmt.
2. Taxonomie-Ergänzungen (Abschnitt 4), damit die Bewerbungs-Versprechen stimmen.
3. `feeds.json` + `import_feeds.py`, getestet mit einer echten Feed-CSV von Kev.
4. Themenwelt Weihnachten **vor dem 01.11.** live.
5. Später: Open-Graph-Bild pro Post-Seite (`01.jpg`).
6. Amazon PartnerNet erst, wenn die Posts laufen. Gründe: 24-Stunden-Cookie, soweit bekannt Kontoschließung ohne 3 Verkäufe in 180 Tagen, Bilder und Preise nur über die API. Dann nur Textlinks.
