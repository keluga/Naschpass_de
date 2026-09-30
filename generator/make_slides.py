"""Naschpass Slide-Generator
Macht aus posts.json fertige Karussell-Bilder (Instagram/TikTok 1080x1350)
plus ein Pinterest-Cover (1000x1500) und die Caption pro Post.

Start:  python make_slides.py          -> alle Posts
        python make_slides.py 03       -> nur Post 03
Markup: *Wort* in hook/title = Akzentfarbe
"""
import json
import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
FONTS = BASE / "fonts"
OUT = BASE.parent / "fertige_posts"

W, H = 1080, 1350          # Instagram/TikTok Karussell (4:5)
PW, PH = 1000, 1500        # Pinterest (2:3)
M = 90                     # Seitenrand

THEMES = [
    # bg, text, akzent, akzent2
    ("#1B1036", "#FFF7EC", "#FF4D8D", "#FFD23F"),
    ("#0F2A3F", "#F2FBFF", "#3DDC97", "#FFD23F"),
    ("#3A0F1F", "#FFF4EE", "#FFB23F", "#FF7AA8"),
    ("#10302A", "#F4FFF9", "#FFD23F", "#FF6B6B"),
]


# ---------- Schriften ----------
def anton(size):
    return ImageFont.truetype(str(FONTS / "Anton-Regular.ttf"), size)


def inter(size, weight=400):
    f = ImageFont.truetype(str(FONTS / "Inter.ttf"), size)
    try:
        f.set_variation_by_axes([min(max(size, 14), 32), weight])
    except Exception:
        pass  # aeltere Pillow-Version: dann eben Standardgewicht
    return f


# ---------- Text-Helfer ----------
def tokens(text, upper=False):
    """'Das *Ei*-Rezept' -> Woerter aus Segmenten [(text, akzent)], * schaltet Akzent um."""
    words, acc = [], False
    for raw in text.split():
        segs, buf = [], ""
        for ch in raw:
            if ch == "*":
                if buf:
                    segs.append((buf, acc))
                    buf = ""
                acc = not acc
            else:
                buf += ch
        if buf:
            segs.append((buf, acc))
        if segs:
            words.append([(t.upper() if upper else t, a) for t, a in segs])
    return words


def word_w(draw, word, font):
    return sum(draw.textlength(t, font=font) for t, _ in word)


def wrap(toks, font, max_w, draw):
    lines, cur = [], []
    space = draw.textlength(" ", font=font)
    for tok in toks:
        test = cur + [tok]
        width = sum(word_w(draw, t, font) for t in test) + space * (len(test) - 1)
        if cur and width > max_w:
            lines.append(cur)
            cur = [tok]
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def draw_lines(draw, lines, font, x, y, fg, acc, line_h, align="left", box_w=None):
    space = draw.textlength(" ", font=font)
    for line in lines:
        lw = sum(word_w(draw, t, font) for t in line) + space * (len(line) - 1)
        cx = x + (box_w - lw) / 2 if align == "center" and box_w else x
        for word in line:
            for text, is_acc in word:
                draw.text((cx, y), text, font=font, fill=acc if is_acc else fg)
                cx += draw.textlength(text, font=font)
            cx += space
        y += line_h
    return y


def fit(draw, toks, font_fn, max_w, max_h, start, minimum, lh=1.08, max_lines=6):
    size = start
    while size > minimum:
        f = font_fn(size)
        lines = wrap(toks, f, max_w, draw)
        widest = max((word_w(draw, t, f) for t in toks), default=0)
        if widest <= max_w and len(lines) <= max_lines and len(lines) * size * lh <= max_h:
            return f, lines, int(size * lh)
        size -= 4
    f = font_fn(minimum)
    return f, wrap(toks, f, max_w, draw), int(minimum * lh)


# ---------- Deko ----------
def sprinkles(img, seed, colors, w, h, safe=None):
    """Bunte Streusel nur in den Seitenraendern - nie ueber Text, Kopf- oder Fusszeile."""
    rnd = random.Random(seed)
    for i in range(18):
        left = i % 2 == 0
        x = rnd.randint(8, M - 58) if left else rnd.randint(w - M + 4, w - 58)
        y = rnd.randint(160, h - 190)
        L, T = rnd.randint(34, 52), rnd.randint(11, 13)
        s = Image.new("RGBA", (L, T), (0, 0, 0, 0))
        ImageDraw.Draw(s).rounded_rectangle((0, 0, L - 1, T - 1), radius=T // 2,
                                            fill=rnd.choice(colors))
        s = s.rotate(rnd.randint(0, 179), expand=True, resample=Image.BICUBIC)
        img.alpha_composite(s, (x, y))


def pill(draw, x, y, text, font, bg=None, fg="#000", outline=None, right=False):
    tw = draw.textlength(text, font=font)
    pw, ph = tw + 44, font.size + 26
    if right:
        x = x - pw
    draw.rounded_rectangle((x, y, x + pw, y + ph), radius=ph // 2, fill=bg,
                           outline=outline, width=3 if outline else 0)
    draw.text((x + 22, y + 11), text, font=font, fill=fg)
    return pw


def header(draw, cfg, post, t, w):
    f = inter(28, 800)
    pill(draw, M, 64, f"{cfg['brand']} {post['series']}", f, bg=t[2], fg=t[0])
    pill(draw, w - M, 64, post["tag"].upper(), f, fg=t[1], outline=t[1], right=True)


def footer(draw, cfg, t, w, h, page=None):
    f = inter(30, 600)
    draw.text((M, h - 92), cfg["handle"], font=f, fill=t[1])
    if page:
        pw = draw.textlength(page, font=f)
        draw.text((w - M - pw, h - 92), page, font=f, fill=t[1])


def canvas(t, w, h):
    return Image.new("RGBA", (w, h), t[0])


# ---------- Slide-Typen ----------
def hook_slide(cfg, post, t, w, h, seed, pin=False):
    img = canvas(t, w, h)
    sprinkles(img, seed, [t[2], t[3], t[1]], w, h, (M, 170, w - M, h - 170))
    d = ImageDraw.Draw(img)
    header(d, cfg, post, t, w)
    box_w = w - 2 * M
    f, lines, lh = fit(d, tokens(post["hook"], upper=True), anton, box_w,
                       h * 0.48, 170 if not pin else 160, 80)
    sub_f = inter(46, 500)
    sub_lines = wrap(tokens(post["sub"]), sub_f, box_w, d)
    total = len(lines) * lh + 40 + len(sub_lines) * 60
    y = (h - total) / 2 - 20
    y = draw_lines(d, lines, f, M, y, t[1], t[2], lh)
    draw_lines(d, sub_lines, sub_f, M, y + 40, t[3], t[3], 60)
    if pin:
        f2 = inter(32, 700)
        draw_lines(d, wrap(tokens(cfg["pin_footer"]), f2, box_w, d), f2, M, h - 150,
                   t[1], t[1], 44)
    else:
        f2 = inter(34, 800)
        txt = "WISCHEN  →"
        d.text((w - M - d.textlength(txt, font=f2), h - 96), txt, font=f2, fill=t[2])
        d.text((M, h - 92), cfg["handle"], font=inter(30, 600), fill=t[1])
    return img


def content_slide(cfg, post, t, s, page, seed):
    senf = s.get("senf", False)
    bg, fg, acc, acc2 = (t[2], t[0], t[0], t[0]) if senf else t
    tt = (bg, fg, acc, acc2)
    img = canvas(tt, W, H)
    if not senf:
        sprinkles(img, seed, [t[2], t[3]], W, H, (M, 150, W - M, H - 140))
    d = ImageDraw.Draw(img)
    header(d, cfg, post, tt if senf else t, W)
    box_w = W - 2 * M
    f, lines, lh = fit(d, tokens(s["title"], upper=True), anton, box_w, 330, 104, 64,
                       max_lines=3)
    bf, bl = inter(46, 400), 64
    blines = wrap(tokens(s["body"]), bf, box_w, d)
    if len(blines) > 8:  # langer Text -> etwas kleiner
        bf, bl = inter(40, 400), 56
        blines = wrap(tokens(s["body"]), bf, box_w, d)
    quote_h = 230 if senf else 0
    total = quote_h + 70 + len(lines) * lh + 34 + len(blines) * bl
    y = max(200, (H - total) / 2 - 20)
    if senf:
        d.text((M - 6, y - 40), "\u201c", font=anton(240), fill=fg)
        y += quote_h
    d.text((M, y), " ".join(s["label"].upper()), font=inter(32, 800),
           fill=acc2 if not senf else fg)
    y = draw_lines(d, lines, f, M, y + 70, fg, acc if not senf else fg, lh) + 34
    draw_lines(d, blines, bf, M, y, fg, fg, bl)
    footer(d, cfg, tt if senf else t, W, H, page)
    return img


def cta_slide(cfg, post, t, page, seed):
    img = canvas(t, W, H)
    sprinkles(img, seed, [t[2], t[3], t[1]], W, H, (M, 170, W - M, H - 170))
    d = ImageDraw.Draw(img)
    header(d, cfg, post, t, W)
    box_w = W - 2 * M
    f, lines, lh = fit(d, tokens(post["cta"], upper=True), anton, box_w, 560, 130, 70)
    total = len(lines) * lh + 60 + 62 * len(cfg["cta_lines"])
    y = draw_lines(d, lines, f, M, (H - total) / 2 - 20, t[1], t[2], lh) + 60
    f2 = inter(40, 700)
    for line in cfg["cta_lines"]:
        d.text((M, y), line, font=f2, fill=t[3])
        y += 62
    footer(d, cfg, t, W, H, page)
    return img


# ---------- Ablauf ----------
def caption_text(cfg, post):
    parts = [post["caption"].strip(), ""]
    if post.get("sources"):
        parts.append("Quellen:")
        parts += [f"- {s['title']}: {s['url']}" for s in post["sources"]]
        parts.append("")
    parts.append(" ".join("#" + h.lstrip("#") for h in post["hashtags"]))
    return "\n".join(parts)


def slug(s):
    s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40]


def render(cfg, post):
    t = THEMES[post.get("theme", 0) % len(THEMES)]
    folder = OUT / f"{post['id']}_{slug(post['short'])}"
    folder.mkdir(parents=True, exist_ok=True)
    for old in list(folder.glob("*.png")) + list(folder.glob("*.jpg")):
        try:
            old.unlink()
        except OSError:
            pass
    total = 1 + len(post["slides"]) + 1
    seed = int(post["id"]) * 97
    hook_slide(cfg, post, t, W, H, seed).convert("RGB").save(folder / "01.jpg", quality=92)
    for i, s in enumerate(post["slides"], start=2):
        content_slide(cfg, post, t, s, f"{i}/{total}", seed + i).convert("RGB").save(folder / f"{i:02d}.jpg", quality=92)
    cta_slide(cfg, post, t, f"{total}/{total}", seed + 50).convert("RGB").save(folder / f"{total:02d}.jpg", quality=92)
    hook_slide(cfg, post, t, PW, PH, seed + 7, pin=True).convert("RGB").save(folder / "pinterest.jpg", quality=92)
    cap = caption_text(cfg, post)
    (folder / "caption.txt").write_text(cap, encoding="utf-8")
    return folder, cap


def main():
    cfg = json.loads((BASE / "posts.json").read_text(encoding="utf-8"))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    all_caps = ["# Captions – zum Kopieren\n"]
    for post in cfg["posts"]:
        if only and post["id"] != only:
            continue
        folder, cap = render(cfg, post)
        all_caps.append(f"## {post['id']} – {post['short']}\n\n```\n{cap}\n```\n")
        print("fertig:", folder.name)
    if not only:
        (OUT / "ALLE_CAPTIONS.md").write_text("\n".join(all_caps), encoding="utf-8")
    print("\nAlles in:", OUT)


if __name__ == "__main__":
    main()
