"""Rendert die Profilbilder (1080x1080) aus SVG. Start: python make_logo.py"""
import math, random, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
import base64
FONT = "data:font/ttf;base64," + base64.b64encode((HERE.parent / "generator" / "fonts" / "Anton-Regular.ttf").read_bytes()).decode()
BG, PINK, YEL, MINT, CREAM = "#1B1036", "#FF4D8D", "#FFD23F", "#3DDC97", "#FFF7EC"

def sprinkles(seed, rmin, rmax, n=26):
    rnd = random.Random(seed); out = []
    for _ in range(n):
        a = rnd.uniform(0, 2*math.pi); r = rnd.uniform(rmin, rmax)
        x, y = 540 + r*math.cos(a), 540 + r*math.sin(a)
        c = rnd.choice([PINK, YEL, MINT, CREAM]); rot = rnd.randint(0, 179)
        out.append(f'<rect x="{x-22:.0f}" y="{y-7:.0f}" width="44" height="14" rx="7" fill="{c}" transform="rotate({rot} {x:.0f} {y:.0f})"/>')
    return "\n".join(out)

def candy(cx=540, cy=540, r=165, rot=-28):
    # Bonbon: Körper mit Streifen + zwei gezackte Wickel-Enden
    def wrap(sign):
        x0 = cx + sign*(r-20)
        pts = [(x0, cy-55)]
        for i, dy in enumerate([-150, -75, 0, 75, 150]):
            pts.append((cx + sign*(r + (215 if i % 2 == 0 else 165)), cy+dy))
        pts.append((x0, cy+55))
        return "M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in pts) + " Z"
    L, R = wrap(-1), wrap(1)
    stripes = "".join(f'<rect x="{cx-r-40+i*70}" y="{cy-r-40}" width="30" height="{2*r+80}" fill="{CREAM}" opacity="0.9" transform="rotate(35 {cx} {cy})"/>' for i in range(6))
    def folds(sign):
        x0 = cx + sign*(r-10)
        return "".join(f'<path d="M{x0:.0f},{cy+dy0} L{cx+sign*(r+150):.0f},{cy+dy1}" stroke="#E0A800" stroke-width="9" stroke-linecap="round"/>'
                       for dy0, dy1 in [(-30, -95), (0, 0), (30, 95)])
    outline = f'stroke="{CREAM}" stroke-width="26" stroke-linejoin="round"'
    return f'''<g transform="rotate({rot} {cx} {cy})">
      <path d="{L}" fill="{CREAM}" {outline}/><path d="{R}" fill="{CREAM}" {outline}/>
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="{CREAM}" {outline}/>
      <path d="{L}" fill="{YEL}"/><path d="{R}" fill="{YEL}"/>
      {folds(-1)}{folds(1)}
      <clipPath id="body"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="{PINK}"/>
      <g clip-path="url(#body)">{stripes}</g>
      <ellipse cx="{cx-60}" cy="{cy-75}" rx="48" ry="26" fill="#fff" opacity="0.45" transform="rotate(-30 {cx-60} {cy-75})"/>
    </g>'''

def ring_text(text, r=438, size=62, color=YEL):
    return f'''<defs><path id="ring" d="M540,540 m-{r},0 a{r},{r} 0 1,1 {2*r},0 a{r},{r} 0 1,1 -{2*r},0"/></defs>
      <text font-family="Anton" font-size="{size}" fill="{color}">
      <textPath href="#ring" startOffset="0" textLength="2735" lengthAdjust="spacing">{text}</textPath></text>'''

def svg(body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080">
    <style>@font-face{{font-family:Anton;src:url("{FONT}")}}</style>
    <rect width="1080" height="1080" fill="{BG}"/>{body}</svg>'''

variants = {
  # A: nur Bonbon + Streusel, liest sich auch winzig
  "profilbild_A_bonbon": svg(sprinkles(3, 360, 470) + candy()),
  # B: Pass-Stempel-Ring mit Schriftzug + Bonbon
  "profilbild_B_stempel": svg(
      f'<circle cx="540" cy="540" r="505" fill="none" stroke="{YEL}" stroke-width="10" stroke-dasharray="4 18" stroke-linecap="round"/>'
      f'<circle cx="540" cy="540" r="380" fill="none" stroke="{YEL}" stroke-width="8"/>'
      + ring_text("NASCHPASS • SÜSSES AUS ALLER WELT • NASCHPASS • SÜSSES AUS ALLER WELT •")
      + candy(r=140)),
}
out = HERE
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1080,"height":1080})
    for name, s in variants.items():
        (out / f"{name}.svg").write_text(s, encoding="utf-8")
        pg.set_content(f'<html><body style="margin:0">{s}</body></html>')
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(out / f"{name}.png"))
    b.close()
print("ok")
