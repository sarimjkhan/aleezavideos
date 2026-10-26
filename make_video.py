#!/usr/bin/env python3
"""Render an emoji guessing-quiz video from puzzles.json.

Usage: python3 make_video.py [puzzles.json] [-o quiz.mp4] [--landscape]
"""
import argparse, random, json, math, subprocess, os, tempfile
import numpy as np
import audio
import colorsys
from PIL import Image, ImageChops, ImageDraw, ImageFont

FPS = 30
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
TEXT_FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
FLOATERS = ["⭐", "🎈", "🌸", "🍭", "🌈", "💖", "✨", "🦋"]
CHEERS = ["Woohoo!", "Yay!", "Boom!", "Yes!", "Ta-da!", "Wow!", "Hooray!"]
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


def centered(d, text, font, cx, cy, fill, shadow=True, outline=None):
    if outline:
        d.text((cx, cy), text, font=font, fill=fill, anchor="mm", stroke_width=max(2, font.size // 16), stroke_fill=outline)
        return
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
        self.gt = 0.0  # global time, set by the render loop

    def background(self, i):
        if i not in self.bg:
            self.bg[i] = gradient(self.w, self.h, *PALETTES[i % len(PALETTES)])
        return self.bg[i].copy()

    def paste_emoji(self, im, ch, size, cx, cy, scale=1.0, rot=0.0, alpha=1.0, sx=1.0, sy=1.0):
        e = emoji_img(ch, size)
        if scale != 1.0 or sx != 1.0 or sy != 1.0:
            e = e.resize((max(1, int(e.width * scale * sx)), max(1, int(e.height * scale * sy))), Image.BILINEAR)
        if rot:
            e = e.rotate(rot, resample=Image.BICUBIC, expand=True)
        if alpha < 1.0:
            e = e.copy()
            e.putalpha(e.getchannel("A").point(lambda v: int(v * alpha)))
        im.paste(e, (int(cx - e.width / 2), int(cy - e.height / 2)), e)

    def floaters(self, im):
        """Slowly drifting stars, balloons and flowers in the background."""
        rnd = random.Random(5)
        u, w, h = self.u, self.w, self.h
        for k in range(10):
            x0, sp = rnd.uniform(0.05, 0.95) * w, rnd.uniform(60, 130) * u
            ph, size = rnd.uniform(0, 100), int(rnd.uniform(55, 100) * u)
            y = (h * 1.1 - (sp * self.gt + ph * 40 * u)) % (h * 1.2) - h * 0.1
            x = x0 + math.sin(self.gt * 1.3 + ph) * 40 * u
            self.paste_emoji(im, FLOATERS[k % len(FLOATERS)], size, x, y, rot=math.sin(self.gt * 2 + ph) * 15, alpha=0.5)

    def pop_in(self, t, delay=0.0):
        """0..1.2 elastic pop-in scale."""
        return max(0.001, ease_out_back(min(1, max(0, (t - delay) / 0.45))))

    def title(self, title, subtitle, t, dur):
        im = self.background(0)
        self.floaters(im)
        d = ImageDraw.Draw(im, "RGBA")
        u, w, h = self.u, self.w, self.h
        s = self.pop_in(t) * (1 + 0.04 * math.sin(t * 8))
        centered(d, title, text_font(max(8, int(88 * u * s))), w / 2, h * 0.38, (255, 255, 255))
        centered(d, subtitle, text_font(int(60 * u)), w / 2, h * 0.38 + 150 * u, (90, 60, 120))
        for k, ch in enumerate("🧊🍦❓"):
            bounce = abs(math.sin(t * 5 + k * 0.9)) * 70 * u
            self.paste_emoji(im, ch, int(190 * u), w / 2 + (k - 1) * 250 * u, h * 0.68 - bounce,
                             scale=self.pop_in(t, 0.2 + k * 0.15), rot=math.sin(t * 6 + k) * 10)
        return im

    def question(self, n, total, p, t, think):
        im = self.background(n + 1)
        self.floaters(im)
        d = ImageDraw.Draw(im, "RGBA")
        u, w, h = self.u, self.w, self.h
        slide = (1 - min(1, t / 0.35)) ** 2 * 200 * u  # header slides down from above
        centered(d, f"Question {n + 1} / {total}", text_font(int(56 * u)), w / 2, h * 0.09 - slide, (255, 255, 255))
        pulse = 1 + 0.05 * math.sin(t * 7)
        centered(d, "What word is it?", text_font(int(80 * u * pulse)), w / 2, h * 0.17 - slide, (90, 60, 120))
        self.draw_pair(im, d, p["emoji"], t, "+")
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
        for k in range(1, 7):  # paw-print trail behind the cat
            fx = catx - k * 70 * self.u
            if fx > left_x:
                self.paste_emoji(im, "🐾", int(46 * self.u), fx, cy, alpha=max(0.1, 0.7 - k * 0.11))
        pulse = 1 + 0.25 * max(0, 1 - (left % 1) * 5)  # number thumps every second
        d2.text((cx, cy + 95 * self.u), f"{math.ceil(left)}", font=text_font(int(110 * self.u * pulse)),
                fill=(255, 255, 255), anchor="mm")

    def reveal(self, n, p, t):
        im = self.background(n + 1)
        self.floaters(im)
        d = ImageDraw.Draw(im, "RGBA")
        u, w, h = self.u, self.w, self.h
        centered(d, "The answer is…", text_font(int(70 * u)), w / 2, h * 0.17, (90, 60, 120))
        self.draw_pair(im, d, p["emoji"], t, "+", dance=True)
        s = self.pop_in(t) * (1 + 0.06 * math.sin(t * 12))
        size = int(130 * u * s)
        fnt = text_font(max(8, size))
        while fnt.getlength(p["answer"]) > w * 0.9 and size > 20:  # shrink long answers to fit
            size -= 6
            fnt = text_font(size)
        hue = (t * 1.5) % 1  # rainbow colour cycling
        col = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.6, 1.0))
        centered(d, p["answer"], fnt, w / 2, h * 0.78 + math.sin(t * 10) * 8 * u, col, outline=(90, 40, 120))
        self.burst(im, t)
        if t < 0.35:  # quick screen shake
            sh = int(math.sin(t * 90) * 14 * u * (1 - t / 0.35))
            im = ImageChops.offset(im, sh, sh // 2)
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
        for k in range(44):
            ang = rnd.uniform(0, math.tau)
            speed = rnd.uniform(500, 1500) * u
            ch = BURST[k % len(BURST)]
            x = w / 2 + math.cos(ang) * speed * t
            y = h * 0.45 + math.sin(ang) * speed * t + 900 * u * t * t * 0.5  # gravity
            fade = max(0.0, 1 - max(0, t - 1.4) / 0.8)
            size = int(rnd.uniform(60, 140) * u * min(1, t * 6) * fade)
            if size > 4:
                self.paste_emoji(im, ch, size, x, y, rot=t * rnd.uniform(-400, 400))
        for k in range(14):  # confetti raining from the top
            x = rnd.uniform(0, w)
            y = (-100 + (t * rnd.uniform(500, 900) + k * 80) * u) % (h * 1.1)
            self.paste_emoji(im, BURST[(k + 3) % len(BURST)], int(70 * u), x + math.sin(t * 6 + k) * 40 * u, y,
                             rot=math.sin(t * 5 + k) * 40, alpha=max(0.0, 1 - max(0, t - 1.6) / 0.6))

    def draw_pair(self, im, d, emojis, t, op, dance=False):
        u, w, h = self.u, self.w, self.h
        n = len(emojis)
        size = int(min(330, (w / u - 200) / (n + 0.6)) * u)
        gap = size * 0.55
        total = n * size + (n - 1) * gap
        x = w / 2 - total / 2 + size / 2
        for k, ch in enumerate(emojis):
            if dance:  # hop and spin on the answer
                hop = abs(math.sin(t * 6 + k * 1.2)) * 60 * u
                self.paste_emoji(im, ch, size, x, h * 0.45 - hop, rot=math.sin(t * 6 + k) * 14,
                                 sy=1 + 0.06 * math.sin(t * 12 + k))
            else:
                pop = self.pop_in(t, 0.05 + k * 0.15)
                squash = math.sin(t * 5 + k * 1.5)
                self.paste_emoji(im, ch, size, x, h * 0.45 + squash * 14 * u, scale=pop,
                                 rot=math.sin(t * 3 + k * 2) * 6, sx=1 - 0.04 * squash, sy=1 + 0.04 * squash)
            if k < n - 1:
                sp = 1 + 0.15 * math.sin(t * 6)
                centered(d, op, text_font(int(120 * u * sp)), x + (size + gap) / 2, h * 0.45, (255, 255, 255))
            x += size + gap

    def outro(self, t):
        im = self.background(2)
        self.floaters(im)
        d = ImageDraw.Draw(im, "RGBA")
        u, w, h = self.u, self.w, self.h
        centered(d, "How many did you get?", text_font(int(70 * u)), w / 2, h * 0.38, (255, 255, 255))
        centered(d, "Tell us in the comments!", text_font(int(64 * u)), w / 2, h * 0.5, (90, 60, 120))
        self.paste_emoji(im, "👇", int(170 * u), w / 2, h * 0.65 + abs(math.sin(t * 6)) * 50 * u, rot=math.sin(t * 4) * 10)
        return im


class Voice:
    """Energetic narrator (Kokoro, runs offline): pitched up, quick and punchy."""
    def __init__(self, name="af_nova", speed=1.12, pitch=1.10):
        self.name, self.speed, self.pitch, self.k = name, speed, pitch, None
        d = os.path.expanduser(os.environ.get("KOKORO_DIR", "~/.cache/kokoro"))
        try:
            from kokoro_onnx import Kokoro
            self.k = Kokoro(f"{d}/kokoro-v1.0.onnx", f"{d}/voices-v1.0.bin")
        except Exception as e:
            print("Voice disabled:", e)

    def say(self, text, speed=None):
        if not self.k:
            return np.zeros(0)
        x, sr = self.k.create(text, voice=self.name, speed=speed or self.speed, lang="en-us")
        n = int(len(x) * audio.SR / sr / self.pitch)  # resampling up shifts pitch (and tempo) up
        y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
        y = np.tanh(y / max(1e-6, np.abs(y).max()) * 1.8) * 0.9  # punchy, even loudness
        return y


def render(cfg, output, landscape=False, voice=True):
    vo = Voice() if voice else None
    say = vo.say if vo else (lambda t, **k: np.zeros(0))
    w, h = (1920, 1080) if landscape else (1080, 1920)
    think, rev = cfg.get("think_seconds", 4), cfg.get("reveal_seconds", 2.5)
    puzzles = cfg["puzzles"]
    r = Renderer(w, h)
    rnd = random.Random(1)

    # timeline: (duration, frame_fn); audio events go on separate tracks (voice / sfx)
    segs, vox, sfx, clock = [], [], [], 0.0
    INTRO, OUTRO = 4.5, 4.0
    segs.append((INTRO, lambda t: r.title(cfg["title"], cfg["subtitle"], t, INTRO)))
    sfx.append((0.0, audio.whoosh(0.5)))
    vox.append((0.3, say(f"{cfg['title']} Can you guess the word? Let's go!", speed=1.1)))
    clock += INTRO
    for n, p in enumerate(puzzles):
        segs.append((think, lambda t, n=n, p=p: r.question(n, len(puzzles), p, t, think)))
        sfx.append((clock, audio.boing()))
        sfx.append((clock + 0.15, audio.boing()))
        vox.append((clock + 0.1, say(f"Number {n + 1}!" if n < len(puzzles) - 1 else "Last one!")))
        for s_ in range(int(think)):
            sfx.append((clock + s_ + 0.5, audio.tick(high=s_ == int(think) - 1)))
        clock += think
        segs.append((rev, lambda t, n=n, p=p: r.reveal(n, p, t)))
        sfx.append((clock, audio.celebrate()))
        vox.append((clock + 0.15, say(f"{rnd.choice(CHEERS)} {p['answer'].title()}!", speed=1.12)))
        clock += rev
    segs.append((OUTRO, r.outro))
    vox.append((clock + 0.2, say("How many did you get? Tell us in the comments!")))
    sfx.append((clock, audio.celebrate()))
    clock += OUTRO

    N = int(audio.SR * clock)
    tracks = []
    for ev in (vox, sfx):
        buf = np.zeros(N)
        for at, x in ev:
            audio.put(buf, at, np.asarray(x))
        tracks.append(buf)
    mixed = audio.mix(clock, tracks[0], tracks[1], audio.music(clock)[:N] if True else 0)
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "a.wav")
    audio.write_wav(wav, mixed)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", "-i", wav,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-shortest", output]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    start = 0.0
    for dur, fn in segs:
        for f in range(int(dur * FPS)):
            r.gt = start + f / FPS
            ff.stdin.write(fn(f / FPS).convert("RGB").tobytes())
        start += dur
    ff.stdin.close(); ff.wait()
    print(f"Wrote {output} ({clock:.0f}s, {w}x{h})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="?", default="puzzles.json")
    ap.add_argument("-o", "--output", default="quiz.mp4")
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--landscape", action="store_true", help="1920x1080 instead of vertical 1080x1920")
    a = ap.parse_args()
    render(json.load(open(a.config, encoding="utf-8")), a.output, a.landscape, not a.no_voice)


if __name__ == "__main__":
    main()
