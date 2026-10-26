#!/usr/bin/env python3
"""Render an emoji guessing-quiz video from puzzles.json.

Usage: python3 make_video.py [puzzles.json] [-o quiz.mp4] [--landscape]
"""
import argparse, random, json, math, struct, subprocess, wave, os, tempfile
from PIL import Image, ImageDraw, ImageFont

FPS = 30
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
TEXT_FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
SR = 44100
BURST = ["✨", "💖", "🎉", "⭐", "🦄", "🎈", "🌈", "🍭", "🌸", "💫"]

PALETTES = [((255, 154, 158), (250, 208, 196)), ((161, 140, 209), (251, 194, 235)),
            ((132, 250, 176), (143, 211, 244)), ((255, 236, 210), (252, 182, 159)),
            ((137, 247, 254), (102, 166, 255)), ((250, 177, 160), (255, 234, 167))]


def text_font(size):
    for p in TEXT_FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


_emoji_cache = {}
def emoji_img(ch, size):
    key = (ch, size)
    if key not in _emoji_cache:
        f = ImageFont.truetype(EMOJI_FONT, 109)  # bitmap font: only size 109
        im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox() or (0, 0, 1, 1))
        _emoji_cache[key] = im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)
    return _emoji_cache[key]


def gradient(w, h, c1, c2):
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        col.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    return col.resize((w, h))


def centered(d, text, font, cx, cy, fill, shadow=True):
    if shadow:
        d.text((cx + 4, cy + 5), text, font=font, fill=(0, 0, 0, 70), anchor="mm")
    d.text((cx, cy), text, font=font, fill=fill, anchor="mm")


def ease_out_back(t):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


class Renderer:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.u = min(w, h) / 1080
        self.bg = {}

    def background(self, i):
        if i not in self.bg:
            self.bg[i] = gradient(self.w, self.h, *PALETTES[i % len(PALETTES)])
        return self.bg[i].copy()

    def paste_emoji(self, im, ch, size, cx, cy, scale=1.0):
        e = emoji_img(ch, size)
        if scale != 1.0:
            e = e.resize((max(1, int(e.width * scale)), max(1, int(e.height * scale))), Image.LANCZOS)
        im.paste(e, (int(cx - e.width / 2), int(cy - e.height / 2)), e)

    def title(self, title, subtitle, t, dur):
        im = self.background(0)
        d = ImageDraw.Draw(im, "RGBA")
        u, w, h = self.u, self.w, self.h
        s = min(1, ease_out_back(min(1, t / 0.6)))
        centered(d, title, text_font(int(100 * u * s) + 1), w / 2, h * 0.38, (255, 255, 255))
        centered(d, subtitle, text_font(int(60 * u)), w / 2, h * 0.38 + 150 * u, (90, 60, 120))
        bounce = math.sin(t * 6) * 15 * u
        for k, ch in enumerate("🧊🍦❓"):
            self.paste_emoji(im, ch, int(190 * u), w / 2 + (k - 1) * 250 * u, h * 0.65 + bounce * (1 if k % 2 else -1))
        return im

    def question(self, n, total, p, t, think):
        im = self.background(n + 1)
        d = ImageDraw.Draw(im, "RGBA")
        u, w, h = self.u, self.w, self.h
        centered(d, f"Question {n + 1} / {total}", text_font(int(56 * u)), w / 2, h * 0.09, (255, 255, 255))
        centered(d, "What word is it?", text_font(int(80 * u)), w / 2, h * 0.17, (90, 60, 120))
        self.draw_pair(im, d, p["emoji"], t, "+")
        # cute round countdown: white bubble, pink ring that drains, number inside
        left = max(0.0, think - t)
        self.timer(im, left, think, w / 2, h * 0.80)
        return im

    def timer(self, im, left, think, cx, cy):
        """A long stick with a cat walking along it; time is up when the cat reaches the fish."""
        k = 3  # supersample so the rounded stick is smooth
        bw, bh = int(self.w * 0.78), int(34 * self.u)
        pad = int(120 * self.u)
        W, H = bw + 2 * pad, bh + 2 * pad
        layer = Image.new("RGBA", (W * k, H * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x0, x1, y0, y1 = pad * k, (pad + bw) * k, pad * k, (pad + bh) * k
        d.rounded_rectangle([x0, y0, x1, y1], radius=bh * k / 2, fill=(255, 255, 255, 220))
        prog = min(1.0, max(0.0, 1 - left / think))
        px = x0 + (x1 - x0) * prog
        if prog > 0:
            d.rounded_rectangle([x0, y0, max(px, x0 + bh * k), y1], radius=bh * k / 2, fill=(255, 107, 150, 255))
        layer = layer.resize((W, H), Image.LANCZOS)
        im.paste(layer, (int(cx - W / 2), int(cy - H / 2)), layer)
        # paw-print dots along the walked part
        d2 = ImageDraw.Draw(im, "RGBA")
        left_x = cx - bw / 2
        catx = left_x + bw * prog
        # goal fish and walking cat (flipped so it faces right), bobbing as it walks
        self.paste_emoji(im, "🐟", int(95 * self.u), left_x + bw + 10 * self.u, cy - 10 * self.u)
        cat = emoji_img("🐈", int(150 * self.u)).transpose(Image.FLIP_LEFT_RIGHT)
        bob = abs(math.sin(prog * think * 5)) * 14 * self.u
        im.paste(cat, (int(catx - cat.width / 2), int(cy - bh / 2 - cat.height + 8 * self.u - bob)), cat)
        d2.text((cx, cy + 95 * self.u), f"{math.ceil(left)}", font=text_font(int(110 * self.u)),
                fill=(255, 255, 255), anchor="mm")

    def reveal(self, n, p, t):
        im = self.background(n + 1)
        d = ImageDraw.Draw(im, "RGBA")
        u, w, h = self.u, self.w, self.h
        centered(d, "The answer is…", text_font(int(70 * u)), w / 2, h * 0.17, (90, 60, 120))
        self.draw_pair(im, d, p["emoji"], 99, "+")
        s = max(0.01, ease_out_back(min(1, t / 0.5)))
        size = int(130 * u * s)
        fnt = text_font(max(8, size))
        # shrink long answers to fit
        while fnt.getlength(p["answer"]) > w * 0.9 and size > 20:
            size -= 6
            fnt = text_font(size)
        centered(d, p["answer"], fnt, w / 2, h * 0.78, (255, 255, 255))
        self.burst(im, t)
        return im

    def burst(self, im, t):
        """Sparkles and cute emojis pop out when the timer hits zero."""
        if t > 2.2:
            return
        u, w, h = self.u, self.w, self.h
        rnd = random.Random(7)
        if t < 0.15:  # quick white flash
            ov = Image.new("RGBA", im.size, (255, 255, 255, int(160 * (1 - t / 0.15))))
            im.paste((255, 255, 255), (0, 0), ov.getchannel("A"))
        for k in range(28):
            ang = rnd.uniform(0, math.tau)
            speed = rnd.uniform(500, 1300) * u
            ch = BURST[k % len(BURST)]
            x = w / 2 + math.cos(ang) * speed * t
            y = h * 0.45 + math.sin(ang) * speed * t + 900 * u * t * t * 0.5  # gravity
            fade = max(0.0, 1 - max(0, t - 1.4) / 0.8)
            size = int(rnd.uniform(60, 130) * u * min(1, t * 6) * fade)
            if size > 4:
                self.paste_emoji(im, ch, size, x, y)

    def draw_pair(self, im, d, emojis, t, op):
        u, w, h = self.u, self.w, self.h
        n = len(emojis)
        size = int(min(330, (w / u - 200) / (n + 0.6)) * u)
        gap = size * 0.55
        total = n * size + (n - 1) * gap
        x = w / 2 - total / 2 + size / 2
        for k, ch in enumerate(emojis):
            wob = math.sin(t * 4 + k * 1.5) * 10 * u if t < 50 else 0
            self.paste_emoji(im, ch, size, x, h * 0.45 + wob)
            if k < n - 1:
                centered(d, op, text_font(int(120 * u)), x + (size + gap) / 2, h * 0.45, (255, 255, 255))
            x += size + gap

    def outro(self, t):
        im = self.background(2)
        d = ImageDraw.Draw(im, "RGBA")
        u, w, h = self.u, self.w, self.h
        centered(d, "How many did you get?", text_font(int(70 * u)), w / 2, h * 0.38, (255, 255, 255))
        centered(d, "Tell us in the comments!", text_font(int(64 * u)), w / 2, h * 0.5, (90, 60, 120))
        self.paste_emoji(im, "👇", int(170 * u), w / 2, h * 0.65 + abs(math.sin(t * 5)) * 30 * u)
        return im


def tone(freq, dur, vol=0.4, decay=6):
    n = int(SR * dur)
    return [vol * math.sin(math.tau * freq * i / SR) * math.exp(-decay * i / SR) for i in range(n)]


def build_audio(path, events, total):
    buf = [0.0] * int(SR * total)
    for at, samples in events:
        s = int(at * SR)
        for i, v in enumerate(samples):
            if s + i < len(buf):
                buf[s + i] += v
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32000)) for v in buf))


def render(cfg, output, landscape=False):
    w, h = (1920, 1080) if landscape else (1080, 1920)
    think, rev = cfg.get("think_seconds", 6), cfg.get("reveal_seconds", 3)
    puzzles = cfg["puzzles"]
    r = Renderer(w, h)

    # timeline: (duration, frame_fn)
    segs, events, clock = [], [], 0.0
    segs.append((3.0, lambda t: r.title(cfg["title"], cfg["subtitle"], t, 3.0)))
    events.append((0.0, tone(660, 0.5)))
    clock += 3.0
    for n, p in enumerate(puzzles):
        segs.append((think, lambda t, n=n, p=p: r.question(n, len(puzzles), p, t, think)))
        for s in range(int(think)):
            events.append((clock + s, tone(880, 0.12, 0.25, 20)))
        clock += think
        segs.append((rev, lambda t, n=n, p=p: r.reveal(n, p, t)))
        events.append((clock, tone(988, 0.15, 0.4, 8) + tone(1319, 0.5, 0.4, 5)))
        clock += rev
    segs.append((3.0, r.outro))
    clock += 3.0

    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "a.wav")
    build_audio(wav, events, clock)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", "-i", wav,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "128k", "-shortest", output]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for dur, fn in segs:
        for f in range(int(dur * FPS)):
            ff.stdin.write(fn(f / FPS).convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    print(f"Wrote {output} ({clock:.0f}s, {w}x{h})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="?", default="puzzles.json")
    ap.add_argument("-o", "--output", default="quiz.mp4")
    ap.add_argument("--landscape", action="store_true", help="1920x1080 instead of vertical 1080x1920")
    a = ap.parse_args()
    render(json.load(open(a.config, encoding="utf-8")), a.output, a.landscape)


if __name__ == "__main__":
    main()
