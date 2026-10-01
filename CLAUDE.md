# Naschpass – Regeln für Claude

Content-Repo für den Kanal **@naschpass_de** (TikTok, Instagram, Pinterest): Karussell-Posts über Süßigkeiten aus aller Welt (Fakten, Verbote, Kuriositäten). Betreiber: Kev. Er hat keine Ware zuhause.

## Harte Regeln
- **Kein Geld und keine Credits ausgeben** (vidIQ, Higgsfield, bezahlte APIs, Metricool-Upgrade), ohne vorher Kevs OK.
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
- Suche: `website/dist/search.json` + selbst gehostetes Fuse.js (`website/static/vendor/`). Vorschau mit Beispielprodukten: `PRODUCTS_FILE=<datei> python3 website/build.py`.
