// UI-Check für Naschpass: läuft vor jedem "live" (Claude-Sessions). Prüft am PC UND am Handy.
// Start: python3 website/build.py && (cd website/dist && python3 -m http.server 8799 &) && node website/test_ui.js [basis-url]
// Braucht Playwright (npm i playwright) und Chromium.
const { chromium } = require('playwright');
const BASE = process.argv[2] || 'http://localhost:8799';
const PAGES = ['/', '/shop/', '/kategorie/schokolade/', '/kategorie/halloween/', '/p/01/', '/merkliste/', '/geschenk/', '/quiz/', '/advent/', '/posts/', '/ueber/'];
const EXE = process.env.CHROME || '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';
const ID = /awinaffid=3111189|[?&]a=3111189/;

(async () => {
  const b = await chromium.launch({ executablePath: EXE, args: ['--no-sandbox'] });
  const fails = [];
  for (const [dev, vp, mobile] of [['PC', { width: 1366, height: 860 }, false], ['Handy', { width: 390, height: 844 }, true]]) {
    const ctx = await b.newContext({ viewport: vp, hasTouch: mobile, isMobile: mobile });
    for (const path of PAGES) {
      const p = await ctx.newPage();
      const errs = [];
      p.on('pageerror', e => errs.push(e.message));
      p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text()); });
      const r = await p.goto(BASE + path, { waitUntil: 'networkidle' }).catch(e => null);
      if (!r || r.status() >= 400) { fails.push(`${dev} ${path}: Seite lädt nicht (${r && r.status()})`); await p.close(); continue; }
      await p.waitForTimeout(400);
      // 1) Seite wackelt nicht seitlich
      const over = await p.evaluate(() => document.scrollingElement.scrollWidth - innerWidth);
      if (over > 2) fails.push(`${dev} ${path}: Seite ${over}px zu breit (wackelt seitlich)`);
      // 2) Jede Wisch-Reihe, die mehr Inhalt hat, lässt sich weiterbewegen
      const naked = await p.evaluate(() => [...document.querySelectorAll('body *')].filter(e => {
        const cs = getComputedStyle(e); if (cs.overflowX !== 'auto' && cs.overflowX !== 'scroll') return false;
        if (e.scrollWidth <= e.clientWidth + 4 || e.clientHeight < 40) return false;
        if (e.closest('.hsw,.ddp,.slides,.map,.legal,.prose,table,.reel,dialog')) return false;  // eigene Bedienung oder Text
        return !!e.offsetParent;
      }).map(e => e.tagName.toLowerCase() + '.' + [...e.classList].join('.')));
      naked.forEach(n => fails.push(`${dev} ${path}: Reihe ${n} ist abgeschnitten (keine Pfeile/Verlauf)`));
      const rows = await p.$$('.hsw.scrolls');
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const sc = await row.$(':scope > :first-child');
        const cls = await sc.getAttribute('class');
        const before = await sc.evaluate(e => e.scrollLeft);
        if (!mobile) {
          const btn = await row.$(':scope > .hsb.r');
          if (!btn || !(await btn.isVisible())) { fails.push(`${dev} ${path}: Reihe .${cls} hat keinen Weiter-Pfeil`); continue; }
          await btn.click();
        } else {
          await sc.evaluate(e => e.scrollBy({ left: 200 }));
        }
        await p.waitForTimeout(700);
        const after = await sc.evaluate(e => e.scrollLeft);
        if (!(after > before)) fails.push(`${dev} ${path}: Reihe .${cls} bewegt sich nicht weiter`);
      }
      // 3) Laufband läuft von selbst
      const band = await p.$('.band');
      if (band && !(await p.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches))) {
        await p.mouse.move(0, 0);
        const a = await band.evaluate(e => e.scrollLeft);
        await p.waitForTimeout(3500);
        const c = await band.evaluate(e => e.scrollLeft);
        if (await band.evaluate(e => e.scrollWidth > e.clientWidth + 10) && !(c !== a)) fails.push(`${dev} ${path}: Laufband steht still`);
      }
      // 4) Jeder Werbelink trägt die Publisher-ID
      const bad = await p.$$eval('a[rel~=sponsored]', (as, src) => as.map(a => a.href).filter(h => !new RegExp(src).test(h)), ID.source);
      if (bad.length) fails.push(`${dev} ${path}: ${bad.length} Werbelinks ohne Publisher-ID`);
      if (errs.length) fails.push(`${dev} ${path}: Skript-Fehler: ${errs.slice(0, 2).join(' | ')}`);
      await p.close();
    }
    await ctx.close();
  }
  await b.close();
  console.log(fails.length ? 'FEHLER:\n- ' + fails.join('\n- ') : 'Alles ok: ' + PAGES.length + ' Seiten x PC/Handy');
  process.exit(fails.length ? 1 : 0);
})();
