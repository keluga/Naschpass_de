# Übergabe: Naschpass-Website

Stand: 01.10.2026. Für den Chat, der an der Website weiterarbeitet. Erst ganz lesen, dann loslegen.

**Neu:** `WEBSITE_VISION.md` beschreibt Vision, Partner-Stand, Feed-Import und Reihenfolge. Danach richten.

## 1. Worum es geht
**Naschpass** (@naschpass_de) ist Kevs Social-Media-Kanal über Süßigkeiten aus aller Welt (TikTok, Instagram, Pinterest), bestehend aus Karussell-Posts. Die Website ist der **Link in allen Bios**. Sie soll:
1. Besucher aus einem Post direkt zu „ihrem“ Post führen (`/p/<nr>/`, in den Bios steht „Link in Bio → #09“),
2. Produkte nach Kategorien zeigen, mit **Affiliate-Links** (AWIN, später ggf. Amazon). Damit verdient Kev Geld,
3. Impressum und Datenschutz liefern (Pflicht).

Kev ist Programmier-Anfänger: Schritte erklären, URLs immer mitschicken. **Nichts ausgeben, was Geld oder Credits kostet, ohne vorher zu fragen.**

## 2. Wo alles liegt
| Was | Wo |
| --- | --- |
| Repo (öffentlich) | https://github.com/keluga/Naschpass_de (Branch `main`) |
| Live-Seite | https://naschpass.oneflowsolution.de (auch https://naschpass.netlify.app) |
| Hosting | Netlify, Projekt `naschpass`, Site-ID `8c5b425f-4aa1-493b-929e-d394728481dc`, Konto kevin@oneflowsolution.de (Free-Plan) |
| Domain/DNS | IONOS (`oneflowsolution.de`): CNAME `naschpass` → `naschpass.netlify.app`, TXT `subdomain-owner-verification` (Netlify-Nachweis, drin lassen) |

**Zugriff im neuen Chat:** Repo `keluga/Naschpass_de` mit Schreibrechten hinzufügen (GitHub ist mit Kevs Claude-Konto verbunden). Netlify-Connector ist ebenfalls verbunden. Direkt aus der Cloud zu Netlify deployen geht nicht (Proxy blockt api.netlify.com), muss es aber auch nicht: **Jeder Push auf `main` baut die Seite automatisch neu.**

## 3. Wie der Build läuft
- `netlify.toml`: `command = "python3 website/build.py"`, `publish = "website/dist"`.
- `website/build.py` erzeugt statisches HTML (nur Python-Standardbibliothek, kein pip nötig). `website/dist/` ist in `.gitignore`.
- Lokal testen: `python3 website/build.py`, dann `cd website/dist && python3 -m http.server`.
- Ein anderes Framework (z. B. Astro) ist erlaubt, wenn es auf Netlify Free baut. Dann `netlify.toml` anpassen. **Die Datenquellen in Abschnitt 4 müssen aber weiter gelesen werden.**

## 4. Datenquellen – NICHT umbenennen oder umbauen
| Datei | Inhalt | Wer schreibt |
| --- | --- | --- |
| `generator/posts.json` | alle Posts (`id`, `short`, `hook` mit `*Akzent*`, `sub`, `slides`, `caption`, `hashtags`, `sources`) | Kev und die geplante Wochen-Automatik (sonntags, noch einzurichten) |
| `fertige_posts/<id>_<slug>/01.jpg …` | fertige Karussell-Folien (1080×1350) + `pinterest.jpg` + `caption.txt` | Generator `generator/make_slides.py` |
| `website/site.json` | Texte, Socials, **Impressum-Daten**, Kategorien | Website-Chat |
| `website/products.json` | Produkte (anfangs leer) | Website-Chat / Automatik nach AWIN-Freigabe |

Ordnername eines Posts = `id` + `_` + Slug aus `short` (Kleinbuchstaben, ä→ae, ö→oe, ü→ue, ß→ss, Nicht-Alphanumerisches → `-`, max. 40 Zeichen). Siehe `post_folder()` in `website/build.py` und `slug()` in `generator/make_slides.py`.

**Produkt-Schema** (`products.json` → `"products": [...]`):
```json
{"name": "KitKat Matcha", "category": "japan", "post": "02", "url": "<AWIN-Deeplink>", "image": "<Bild-URL aus dem AWIN-Produktfeed>", "note": "kurzer Satz", "shop": "World of Sweets"}
```
`category` = eine `id` aus `site.json → categories`. `post` ist optional und verknüpft das Produkt mit der Post-Seite.

## 5. Muss drinbleiben (Funktion + Recht)
- **Seiten:** Start, `/p/<id>/` für jeden Post (Folien-Galerie, „Die Süßigkeiten aus dem Post“, Quellen), `/kategorie/<id>/`, `/impressum/`, `/datenschutz/`.
- **Werbehinweis** oben auf jeder Seite, dazu jeder Kauf-Button als „Werbelink“ markiert (`*`). Affiliate-Links mit `rel="sponsored noopener"` und `target="_blank"`.
- **Impressum (§ 5 DDG):** Kevin Agaschtschuk, OneFlow Solution, Schulstr. 4, 32699 Extertal, E-Mail kevin@oneflowsolution.de, Kleinunternehmer § 19 UStG (keine USt-ID). Offen: ein zweiter schneller Kontaktweg (Telefon oder Kontaktformular). Mit Kev klären, ein Formular erfordert eine Ergänzung der Datenschutzerklärung.
- **Datenschutz:** Die Seite hat **keine Cookies, kein Tracking und keine externen Inhalte**. Daran hängt, dass es keinen Cookie-Banner braucht. Daraus folgt:
  - Schriften **selbst hosten** (liegen in `website/static/`), **kein** Google-Fonts-CDN.
  - Keine Analytics, keine eingebetteten Instagram/TikTok/YouTube-Posts, keine externen Skripte. Falls doch gewünscht: erst Kev fragen, dann Consent-Banner und Datenschutzerklärung anpassen.
  - Nur Netlify als Hoster ist in der Datenschutzerklärung beschrieben. Neue Dienste dort ergänzen.
- **Bilder:** nur eigene Folien, Logo, Partner-Feed-Bilder (nach AWIN-Freigabe) oder CC0/CC BY mit Quellenangabe. Keine Bilder aus Google oder von Shops ohne Erlaubnis. Bei Amazon keine Bilder und keine Preise ohne deren API.
- **Zielgruppe Erwachsene:** keine Ansprache von Kindern, keine „Jetzt kaufen!!“-Appelle an Kids (UWG Anh. Nr. 28). Keine Gesundheitsversprechen.
- `robots.txt` erlaubt alles. Das darf so bleiben.

## 6. Design (darf frei überarbeitet werden, Marke bleibt erkennbar)
- **Farben:** Hintergrund `#1B1036`, Karten `#2C1A57`, Text `#FFF7EC`, Pink `#FF4D8D`, Gelb `#FFD23F`, Mint `#3DDC97`.
- **Schriften:** Anton (Überschriften, Großbuchstaben), Inter (Text). Beide sind lokal: `website/static/`, `generator/fonts/`.
- **Logo/Profilbild:** `branding/profilbild_A_bonbon.png` (Bonbon im Sticker-Look), Generator `branding/make_logo.py`. Motiv „Streusel“ (bunte abgerundete Striche).
- Die Folien (`fertige_posts/`) nutzen dieselben Farben und Schriften. Die Seite soll dazu passen.
- **Mobile first:** Fast alle Besucher kommen vom Handy aus Instagram oder TikTok.

## 7. Offene Punkte
1. **HTTPS-Zertifikat:** In Netlify unter *Domain management → HTTPS* prüfen, ob das Let's-Encrypt-Zertifikat aktiv ist. Sonst „Verify DNS configuration“ drücken.
2. **Produkte:** erst nach AWIN-Freigabe (Kev bewirbt sich gerade). Bis dahin zeigen die Kategorien „Bald hier“.
3. Die Hauptdomain `oneflowsolution.de` zeigt noch die IONOS-Parkseite. Optional später.
4. Optional: Startseite um eine Rubrik „Neu diese Woche“ oder eine Suche erweitern, Open-Graph-Bilder pro Post-Seite (`01.jpg`).

## 8. Andere Teile des Repos (nicht kaputt machen)
- `CLAUDE.md`: Regeln für alle Claude-Chats in diesem Repo (Fakten-Check, Recht, Wochenlauf, Metricool-Limits).
- `generator/`: Folien-Generator (Python + Pillow). `THEMEN.md`: Themenliste.
- Metricool (Social-Planung, Free: 20 Posts/Monat, jede Plattform zählt einzeln), Marke `naschpass_de`, blogId `7170990`.
