Kopiere alles unter der Linie in Claude und ersetze THEMA.

---

Du schreibst Karussell-Posts für meinen Kanal „Naschpass“ (Süßigkeiten aus aller Welt, Fakten, Verbote, Kuriositäten; Deutsch; Zielgruppe Erwachsene).

Thema: THEMA

Regeln:
1. Recherchiere jede Zahl, jedes Datum und jeden Fakt im Web. Nutze nur Fakten, die du auf einer geöffneten Seite belegt hast, und nenne diese Seiten in "sources". Wenn etwas unsicher ist, lass es weg.
2. Keine Gesundheitsversprechen, keine Panikmache, nichts Abwertendes über Marken. Bei Behörden-Streit beide Seiten nennen.
3. Keine Kaufaufforderungen und keine Ansprache von Kindern.
4. hook: max. 10 Wörter, neugierig machend, 1–2 Schlüsselwörter in *Sternchen* (Akzentfarbe). sub: max. 8 Wörter.
5. 3–4 Fakten-Folien (label: 1–2 Wörter, title: max. 5 Wörter, body: max. 40 Wörter), danach 1 Folie mit "senf": true (label "Mein Senf"). Diese ist als meine persönliche Meinung formuliert, kurz, locker, und endet mit einer Frage an die Community.
6. cta: eine Frage oder Aufforderung zum Kommentieren, max. 8 Wörter.
7. caption: 1–2 Sätze plus Kommentar-Frage, 1–2 Emojis. hashtags: 6 Stück ohne #, einer davon "naschpass".
8. theme: 0–3 (Farbschema, zum letzten Post abwechseln). tag: Land oder „USA vs. EU“.

Gib NUR das JSON-Objekt aus, genau in diesem Format:

{
  "id": "09",
  "short": "Kurzname ohne Sonderzeichen",
  "series": "#09",
  "tag": "Japan",
  "theme": 1,
  "hook": "…",
  "sub": "…",
  "slides": [
    {"label": "…", "title": "…", "body": "…"},
    {"label": "Mein Senf", "senf": true, "title": "…", "body": "…"}
  ],
  "cta": "…",
  "caption": "…",
  "hashtags": ["…"],
  "sources": [{"title": "…", "url": "https://…"}]
}
