# Shop-Konzept: Sortiment, Herkunft, Reihenfolge

Stand: 08.10.2026. Erst lesen, dann bauen. Ergänzt `WEBSITE_VISION.md` und `PARTNER.md`.

## 1. Diagnose (Vorschau 4, 548 Produkte)
- **Auswahl = die ersten 120 pro Shop** aus riesigen Feeds, gefiltert nur über eine Schwarzliste. Ergebnis: Katzenfutter (Felix Knabbermix), **Jägermeister** (Alkohol-Filter hat ihn nicht erkannt → Rechtsrisiko), Pudding, Suppe, Chutney, Gewürze, Wassersprudler, CO₂-Zylinder.
- **Herkunft fehlt bei 529 von 548** Produkten. Die Feeds haben kein Herkunftsland, unsere Stichwörter finden fast nichts → Länder-Filter leer.
- **Keine Reihenfolge:** Angezeigt wird, was zufällig vorne im Feed steht.
- **Der Kern der Marke fehlt:** REWE, GOURVITA, Piccantino sind Supermarkt/Feinkost. Die Exoten (Pepero, Reese's, …) kommen von **SugarGang** (Google-Feed, 111 vorrätig) – der fehlt noch.

## 2. Was die Top-Shops machen (Runde 2)
- **World of Sweets** – Hauptmenü mit 6 Säulen: Produkte (nach Art) · Weihnachten · Halloween · **Länder** (GB, Italien, Japan, Mexiko, Niederlande, Österreich, Schweden, Südkorea, Thailand, Türkei) · **Marken** (Top-Marken, Klassiker) · **Anlässe** (Geburtstag, Hochzeit, Party, Ostern, Valentinstag). Saison mit Unterkategorien (Adventskalender, Figuren, Gebäck, Präsente).
- **SugarGang** – wenige, stark kuratierte Produkte, Neuheiten zuerst, Bundles/Boxen prominent.
- **Universal Yums / Bokksu** – verkaufen über **Land + Geschichte** („Discover Japan through snacks“). Genau das ist unser Vorteil: Post erzählt die Geschichte, Shop liefert die Süßigkeit.
- Gemeinsam: **Vielfalt im ersten Blick**, nie 10× dasselbe hintereinander; Länder und Marken sind eigene Einstiege, nicht nur Filter.

## 3. Zielbild
### A. Sortiment: Positivliste statt Schwarzliste
Ein Produkt kommt nur rein, wenn es **eindeutig Süßes/Snack/Getränk** ist (Feed-Kategorie oder Name trifft Positivliste) **und** keine harte Ausschlussregel greift (Alkohol inkl. Markennamen wie Jägermeister, Tierfutter, Non-Food, Zubehör/Geräte, Grundnahrung wie Suppe/Sauce/Gewürz).
Jeder Shop hat eine **Rolle**:

| Shop | Rolle | Was rein darf |
| --- | --- | --- |
| SugarGang | Exoten, Kern | fast alles |
| REWE | Supermarkt-Klassiker | Markensüßes, Chips, Limo; keine Eigenmarken-Grundnahrung |
| GOURVITA | Pralinen & Geschenke | Pralinen, Schokolade, Präsente |
| Piccantino | Manufaktur & scharf | Schokolade (z. B. Zotter), scharfe Snacks |
| Burghardt | Nüsse & Snacks | Nüsse, Mixe, Chips |
| Sodapop | Getränke | nur Sirupe, keine Geräte |

Menge: kein festes 120er-Limit mehr, sondern **alles, was passt** (Ziel 1.500–2.500). Die Shop-Seite lädt dann nachträglich (Seitenweise), damit sie am Handy schnell bleibt.

### B. Herkunft automatisch
- **Marken→Land-Tabelle** (`website/brands.json`): z. B. Pepero/Lotte → Südkorea, Reese's/Hershey's → USA, Pocky/Meiji → Japan, Haribo/Ritter Sport → Deutschland, Lindt/Toblerone → Schweiz, Ferrero/Baci → Italien, Fazer/Marabou → Skandinavien, Cadbury → Großbritannien.
- Dazu Wörter im Namen („japanisch“, „aus Korea“) und Shop-Standard (REWE-Eigenmarke → Deutschland).
- Ziel: **≥ 70 % mit Land**. Länder ohne Produkte werden ausgeblendet statt leer gezeigt.

### C. Reihenfolge („Entdecken“)
Punkte pro Produkt: Exot (Land ≠ Deutschland) +, Saison-Treffer +, bekannte Marke +, Post-Bezug +. Dann **mischen**: nie 2 vom selben Shop oder derselben Art hintereinander.
Startseite „Gerade im Shop“: je 1 Produkt pro Hauptart (Schoko, Fruchtgummi, Chips, Getränk, Exot, Geschenk), wechselt bei jedem Build. → Jeder sieht sofort Verschiedenes.

### D. Navigation wie die Großen
Vier Einstiege: **Art · Länder · Anlass/Saison · Marken** (Marken neu). Saison im Oktober: Halloween + Adventskalender, ab November Weihnachten mit Unterpunkten.

### E. Qualitätskontrolle
- Build-Bericht im Log: Anzahl je Shop / Art / Land, aussortiert mit Grund.
- **Prüfseite nur in der Vorschau** (`/pruefen/`): alle Produkte als Liste mit Shop, Art, Land, warum drin. Kev markiert Ausreißer, Claude ergänzt die Regeln.

## 4. Reihenfolge der Umsetzung
1. SugarGang-Import (Google-Format, Bilder `cdn.shopify.com` in `remote_images`).
2. Positivliste + Shop-Rollen + harte Ausschlüsse (zuerst Alkohol/Tierfutter).
3. Marken→Land + Länder-Navigation.
4. Ranking + gemischte Startseite.
5. Prüfseite, dann Kev schaut drüber.
6. Shop-Seite seitenweise laden, Marken-Einstieg.
