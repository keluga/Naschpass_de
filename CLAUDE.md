# Naschpass – Regeln für Claude

Content-Repo für den Kanal **@naschpass_de** (TikTok, Instagram, Pinterest): Karussell-Posts über Süßigkeiten aus aller Welt (Fakten, Verbote, Kuriositäten). Betreiber: Kev. Er hat keine Ware zuhause.

## Harte Regeln
- **Kein Geld und keine Credits ausgeben** (vidIQ, Higgsfield, bezahlte APIs, Metricool-Upgrade), ohne vorher Kevs OK.
- **Nie selbst nach `main` mergen oder pushen** (jeder Produktions-Deploy kostet 15 Netlify-Credits). Nur wenn Kev ausdrücklich „live“ schreibt. „Mach“, „do it“, „passt“ o. Ä. reichen nicht. Änderungen immer über Branch + Pull Request (kostenlose Vorschau).
- **Git in Cloud-Sessions:** Nach dem Klonen `git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*' && git fetch origin`. Nie lokal auf `main` committen. Jeden Arbeits-Branch nach dem Commit sofort mit `git push -u origin <branch>` pushen (kostenlose Vorschau). Sonst meldet der Stop-Hook bei jeder Antwort „unpushed commits“ und frisst Tokens.
- **Partner:** `PARTNER.md` ist die Liste aller AWIN-Partner (Format, Feed-ID, Variable). Bei jeder Zusage aktualisieren.
- **Fakten nur mit Beleg:** Jede Zahl und jedes Datum auf einer geöffneten Webseite prüfen, Quelle in `sources`. Unsicheres weglassen.
- **Recht:** keine Gesundheitsversprechen (HCVO), nichts Abwertendes über Marken (§ 4 UWG), keine Kaufappelle und keine Ansprache von Kindern (UWG Anh. Nr. 28). Enthält ein Post Affiliate-Links oder Produkte eines Partner-Shops: „Anzeige“ auf Folie 1 und in der Caption.
- **Keine fremden Bilder** außer CC0/CC BY mit Quellenangabe. Keine Emojis auf Folien, nur in Captions.

## Aufbau
- `generator/posts.json`: alle Posts (Schema siehe unten). `generator/make_slides.py <id>` rendert nach `fertige_posts/<id>_<name>/` (`01.jpg…`, `pinterest.jpg`, `caption.txt`).
- `THEMEN.md`: Themenliste mit Status. Immer die nächsten offenen Themen von oben nehmen und den Status aktualisieren.
- Öffentliche Bild-URL: `https://raw.githubusercontent.com/keluga/naschpass_de/main/fertige_posts/<ordner>/<datei>.jpg`

## Wochenlauf (geplante Aufgabe, sonntags)
1. `THEMEN.md` lesen und die nächsten 3 offenen Themen nehmen (saisonale Themen rechtzeitig vorziehen).
2. Recherchieren und 3 Posts als JSON an `generator/posts.json` anhängen (`id` fortlaufend, `theme` 0–3 abwechseln). Textregeln: Hook max. 10 Wörter mit 1–2 `*Akzentwörtern*`, 3–4 Fakten-Folien (Titel max. 5 Wörter, Text max. 40 Wörter), 1 Folie `"senf": true` mit Kevs Meinung und einer Frage, CTA max. 8 Wörter, Caption 1–2 Sätze plus Frage, 6 Hashtags inklusive `naschpass`.
3. Rendern, eine Kontaktübersicht der Folien ansehen (Text nicht abgeschnitten, keine Überlappung), dann committen und pushen.
4. Metricool (blogId `7170990`): mit `getScheduledPosts` die Posts des laufenden Monats zählen. **Gratis-Limit: 20 pro Monat, jede Plattform zählt einzeln.** Nur so viele Entwürfe anlegen, dass das Limit nicht überschritten wird. Entwürfe (`draft: true`) für TikTok + Instagram (Karussell, alle Folien in Reihenfolge) auf Mo/Mi/Fr 18:00 Europe/Berlin. Pinterest nur, wenn ein Board verbunden ist und Limit übrig ist.
5. `THEMEN.md` aktualisieren (Status „Entwurf in Metricool“ oder „Dateien – selbst posten“) und pushen.
6. Kev eine kurze Nachricht schicken: welche 3 Posts, welche in Metricool liegen, welche er selbst posten muss (mit Links zu den Ordnern auf GitHub).

## JSON-Schema eines Posts
```json
{"id":"09","short":"Kurzname","series":"#09","tag":"USA","theme":1,
 "hook":"…","sub":"…",
 "slides":[{"label":"…","title":"…","body":"…"},{"label":"Mein Senf","senf":true,"title":"…","body":"…"}],
 "cta":"…","caption":"…","hashtags":["…"],"sources":[{"title":"…","url":"https://…"}]}
```

## Website
- Quelle: `website/` (`site.json` = Texte, Socials, Impressum; `products.json` = Produkte mit Affiliate-Links; `build.py` baut nach `website/dist/`).
- Netlify-Projekt `naschpass` (Site-ID `8c5b425f-4aa1-493b-929e-d394728481dc`) baut automatisch bei jedem Push auf `main` (`netlify.toml`). Ziel-Domain: `naschpass.oneflowsolution.de`.
- Jeder Post bekommt automatisch eine Seite `/p/<id>/`. Produkte zu einem Post: in `products.json` mit `"post": "<id>"` und `"category"` eintragen – nur echte Affiliate-Links aus freigeschalteten Programmen, Bilder nur aus dem Partner-Feed.
- Keine Cookies, kein Tracking, keine externen Einbettungen (sonst Datenschutzerklärung anpassen). Produktbilder: mit Feed bzw. Erlaubnis des Shops über das Netlify Image CDN (`remote_images` in `netlify.toml`, ohne Einwilligung). Shops ohne Feed: Foto-URL von der Produktseite, Bild-Server mit Betreiber + Anschrift in `site.json → partner_shops` eintragen. Diese Fotos lädt die Seite erst nach Klick auf „Fotos anzeigen“ (Einwilligungsleiste unten), die Datenschutzerklärung listet die Shops automatisch.
- **Netlify Free = 300 Credits/Monat, jeder Produktions-Deploy (Push auf `main`) kostet 15.** Änderungen bündeln, nicht für jede Kleinigkeit pushen. Zum Testen einen Branch + Pull Request nutzen: Deploy-Previews sind kostenlos.
- Filter Woher/Geschmack/Art: `site.json → filter`. Produkte werden über `keywords` automatisch zugeordnet (Name, Beschreibung, `feed_category`, `brand`, `tags`); per Hand überschreiben mit `land`/`geschmack`/`art` im Produkt. Shop-Seite filtert kombiniert, Adresse ist teilbar (z. B. `/shop/?geschmack=salzig&art=chips&land=asien`). Die Suche erkennt Wünsche wie „salzige Chips aus Asien“.
- **AWIN-Feeds:** `website/import_feeds.py` läuft im Build vor `build.py` und schreibt `website/feed_products.json` (gitignored). Quelle: Netlify-Umgebungsvariable `AWIN_FEED_URL` (enthält den API-Schlüssel: **nie ins Repo, in Chats oder Logs**). Welche Shops: `website/feeds.json` (`active`, `only`, `themen`, `max`). Alkohol, Non-Food, nicht Vorrätiges und Produkte ohne AWIN-Bild fliegen raus; Handeinträge in `products.json` haben Vorrang. Lokal testen: `AWIN_FEED_FILE=<csv> python3 website/import_feeds.py`.
- Themenwelten (`site.json → categories`): Zuordnung über `category`, `themen`, `facets` oder `keywords`; `season` sortiert saisonal (Weihnachten 01.11.–26.12. vorn). Nichts anzeigen, was es nicht gibt: keine Preise, keine Bestseller-/Bewertungs-Labels, keine Frequenz-Versprechen.
- Extras: Kurzlinks `/9` → `/p/09/` (`dist/_redirects`, automatisch), Zufalls-Rad auf der Startseite (Farbe = Art, keine erfundene Seltenheit), Naschpass-Stempel (nur nach „Pass starten“, localStorage), Adventskalender `/advent/` (Türchen öffnen sich ab 1.12. nach Datum, Teaser auf der Startseite 15.11.–24.12.), Partner-Platzhalter füllen Raster auf, solange es wenige Produkte gibt. Außerdem: Themenwelt Halloween (01.–31.10. vorn), Weltkarte (`static/worldmap.svg`, Natural Earth), Geschenk-Finder `/geschenk/`, Snack-Typ-Quiz `/quiz/`, Pass-Abzeichen; Teilen-Bilder werden im Browser gemalt (nichts hochgeladen).
- Suche: `website/dist/search.json` + selbst gehostetes Fuse.js (`website/static/vendor/`). Vorschau mit Beispielprodukten: `PRODUCTS_FILE=<datei> python3 website/build.py`.
