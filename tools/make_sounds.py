"""Naschpass-Rad: Casino-Sounds bauen (Kenney Casino Audio, CC0, + Synthese).
Ausgabe: tick, start, riser, stop, win als .mp3 + eine Hörprobe (ganzer Dreh)."""
import subprocess, sys, os
import numpy as np

SR = 44100
K = os.path.join(os.path.dirname(__file__), "kenney", "Audio")
OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)


def load(name):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", os.path.join(K, name), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def pitch(x, f):  # einfache Tonhöhenänderung über Resampling
    idx = np.arange(0, len(x) - 1, f)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


def env(n, a=0.002, d=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)
    return e


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1
    return (x / m * peak).astype(np.float32)


def mix(*parts):
    n = max(len(p) + o for p, o in parts)
    y = np.zeros(n, np.float32)
    for p, o in parts:
        y[o:o + len(p)] += p
    return y


def at(sec):
    return int(sec * SR)


def bell(freq, dur=1.2, bright=1.0):
    """FM-Glocke (klingt nach Spielautomat / Gewinn)."""
    t = np.arange(int(dur * SR)) / SR
    mod = np.sin(2 * np.pi * freq * 3.5 * t) * (2.2 * bright) * np.exp(-t * 6)
    car = np.sin(2 * np.pi * freq * t + mod)
    car += 0.35 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 4)
    return (car * env(len(t), 0.001, dur / 3.2)).astype(np.float32)


def reverb(x, wet=0.25):
    ir_len = int(0.6 * SR)
    ir = rng.standard_normal(ir_len).astype(np.float32) * np.exp(-np.arange(ir_len) / SR * 7)
    ir[0] = 0
    y = np.convolve(x, ir)[:len(x) + ir_len] * (wet / 12)
    return mix((x, 0), (y.astype(np.float32), 0))


def save(name, x):
    x = norm(x, 0.95)
    p = subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                        "-b:a", "96k", os.path.join(OUT, name + ".mp3")], input=x.tobytes())
    return x


# --- Ticks: kurzer Chip-Klick + harter Synth-Klick (Ratsche) ---
chip = load("chip-lay-1.ogg")
chip = chip[np.argmax(np.abs(chip) > 0.05):][:int(0.07 * SR)] * env(int(0.07 * SR), 0.0005, 0.025)[:len(chip[:int(0.07*SR)])]
n = int(0.03 * SR)
t = np.arange(n) / SR
click = (np.sin(2 * np.pi * 2600 * t) * 0.6 + rng.standard_normal(n) * 0.4) * np.exp(-t * 260)
tick = mix((chip * 0.8, 0), (click.astype(np.float32) * 0.7, 0))
tick = save("tick", tick)

# --- Start: Hebel/„Ka-Tschunk“ + Chips ---
thud_n = int(0.25 * SR); tt = np.arange(thud_n) / SR
thud = np.sin(2 * np.pi * (90 - 40 * tt / 0.25) * tt) * np.exp(-tt * 18)
start = mix((load("chips-handle-3.ogg") * 0.7, 0), (thud.astype(np.float32) * 0.9, at(0.02)),
            (pitch(load("card-shove-2.ogg"), 0.8) * 0.5, at(0.05)))
save("start", reverb(start, 0.2))

# --- Riser: ansteigende Spannung (Sägezahn-Sweep + Rauschen + Tremolo), 1,6 s ---
rd = 1.6; rn = int(rd * SR); rt = np.arange(rn) / SR
f = 180 * (2 ** (2.2 * rt / rd))
ph = 2 * np.pi * np.cumsum(f) / SR
saw = 2 * ((ph / (2 * np.pi)) % 1) - 1
sq = np.sign(np.sin(ph * 2.0)) * 0.25
trem = 0.6 + 0.4 * np.sin(2 * np.pi * (6 + 18 * rt / rd) * rt)
noise = rng.standard_normal(rn) * (rt / rd) ** 2 * 0.35
riser = (saw * 0.35 + sq + noise) * trem * (0.15 + 0.85 * (rt / rd) ** 1.5)
riser = np.convolve(riser, np.ones(6) / 6, mode="same")  # etwas weicher
save("riser", reverb(riser.astype(np.float32), 0.15))

# --- Stopp: satter Einraster ---
sn = int(0.45 * SR); st = np.arange(sn) / SR
boom = np.sin(2 * np.pi * (70 - 30 * st) * st) * np.exp(-st * 9)
stop = mix((boom.astype(np.float32) * 1.0, 0), (load("die-throw-1.ogg")[:int(0.3 * SR)] * 0.8, 0), (tick * 0.9, 0))
save("stop", reverb(stop, 0.25))

# --- Gewinn: Dur-Arpeggio (C-E-G-C-E) + Akkord + Münzregen ---
notes = [523.25, 659.25, 783.99, 1046.5, 1318.5]
parts = [(bell(fq, 0.9) * 0.55, at(i * 0.085)) for i, fq in enumerate(notes)]
parts += [(bell(fq, 1.8, 0.7) * 0.35, at(0.5)) for fq in (523.25, 659.25, 783.99, 1046.5)]
coins = [load(f"chips-collide-{i}.ogg") for i in (1, 2, 3, 4)] + [load(f"chips-stack-{i}.ogg") for i in (1, 2, 3)]
for k in range(26):  # Münzregen: viele kleine, leicht höher gestimmte Chip-Treffer
    c = pitch(coins[k % len(coins)], 1.25 + rng.random() * 0.5)
    parts.append((c * (0.35 + rng.random() * 0.25), at(0.35 + k * 0.045 + rng.random() * 0.03)))
win = mix(*parts)
save("win", reverb(win, 0.35))

# --- Hörprobe: ein ganzer Dreh wie auf der Seite (Ticks werden langsamer + höher) ---
demo = [(start, 0)]
tpos, gap = 0.35, 0.045
ticks = 0
while gap < 0.42:
    demo.append((pitch(tick, 1.0 - min(0.25, ticks * 0.004)) * 2.2, at(tpos)))
    tpos += gap
    gap *= 1.045
    ticks += 1
demo.append((reverb(riser.astype(np.float32), 0.15) * 0.45, at(tpos - 1.6)))
demo.append((stop, at(tpos)))
demo.append((win * 0.6, at(tpos + 0.25)))
save("hoerprobe_ganzer_dreh", mix(*demo))
print("ok", ticks, "ticks", round(tpos, 2), "s")
