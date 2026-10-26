"""Synthesised kid-friendly audio: bouncy background music and party sound effects (numpy only)."""
import math, wave
import numpy as np

SR = 44100
_rng = np.random.default_rng(3)


def _t(dur):
    return np.arange(int(SR * dur)) / SR


def _midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _lp(x, n):  # crude low-pass (moving average)
    return np.convolve(x, np.ones(n) / n, mode="same")


def _hp(x, n):
    return x - _lp(x, n)


def put(buf, at, x, gain=1.0):
    s = int(at * SR)
    if s >= len(buf) or s < 0:
        return
    e = min(len(buf), s + len(x))
    buf[s:e] += x[: e - s] * gain


# ---- instruments -----------------------------------------------------------------------
def marimba(f, dur=0.35):
    t = _t(dur)
    return (np.sin(math.tau * f * t) + 0.45 * np.sin(math.tau * 3 * f * t) * np.exp(-30 * t)
            + 0.2 * np.sin(math.tau * 4.2 * f * t) * np.exp(-40 * t)) * np.exp(-9 * t)


def bass(f, dur=0.22):
    t = _t(dur)
    return (np.sin(math.tau * f * t) + 0.35 * np.sin(math.tau * 2 * f * t)) * np.exp(-8 * t)


def kick():
    t = _t(0.18)
    return np.sin(math.tau * np.cumsum(50 + 120 * np.exp(-30 * t)) / SR) * np.exp(-14 * t)


def clap():
    t = _t(0.14)
    return _hp(_rng.standard_normal(len(t)), 12) * np.exp(-30 * t)


def hat():
    t = _t(0.05)
    return _hp(_rng.standard_normal(len(t)), 4) * np.exp(-70 * t)


def bell(f, dur=0.5):
    t = _t(dur)
    return (np.sin(math.tau * f * t) + 0.4 * np.sin(math.tau * 2.76 * f * t)) * np.exp(-7 * t)


def toot(f, dur):
    t = _t(dur)
    wave_ = sum(np.sin(math.tau * k * f * t) / k for k in range(1, 7))
    return wave_ * np.minimum(1, t * 80) * np.minimum(1, (dur - t) * 40) * 0.5


# ---- music -----------------------------------------------------------------------------
def music(total, bpm=132):
    """Upbeat 'oom-pah' marimba tune in C major (C-G-Am-F), 8-bar loop, with drums."""
    beat = 60 / bpm
    chords = [(60, 64, 67, 36), (59, 62, 67, 43), (57, 60, 64, 45), (60, 65, 69, 41)]
    pent = [72, 74, 76, 79, 81, 84]
    rnd = np.random.default_rng(11)
    bar_len = 4 * beat
    loop_bars = 8
    loop = np.zeros(int(SR * bar_len * loop_bars) + SR)
    phrase = []
    for b in range(4):
        notes = []
        for e in range(8):
            ct = [n + 12 for n in chords[b][:3]]
            pool = ct if e % 2 == 0 else pent
            notes.append(None if rnd.random() < 0.15 and e % 2 else int(rnd.choice(pool)))
        phrase.append(notes)
    for bar in range(loop_bars):
        c = chords[bar % 4]
        notes = phrase[bar % 4]
        if bar == 7:  # little turnaround
            notes = [72, 76, 79, 84, 79, 76, 72, None]
        t0 = bar * bar_len
        for e, n in enumerate(notes):
            if n is not None:
                put(loop, t0 + e * beat / 2, marimba(_midi(n)), 0.30 if e % 2 == 0 else 0.22)
        for q in range(4):  # oom-pah bass + chord stabs
            root = c[3] + (12 if q % 2 else 0)
            put(loop, t0 + q * beat, bass(_midi(root)), 0.5)
            if q % 2:
                for n in c[:3]:
                    put(loop, t0 + q * beat, marimba(_midi(n - 12), 0.18), 0.12)
            put(loop, t0 + q * beat, kick(), 0.45) if q % 2 == 0 else put(loop, t0 + q * beat, clap(), 0.25)
        for e in range(8):
            put(loop, t0 + e * beat / 2 + beat / 4 * (e % 2 == 1) * 0, hat(), 0.12 if e % 2 else 0.07)
    loop_len = int(SR * bar_len * loop_bars)
    reps = int(total * SR // loop_len) + 1
    out = np.tile(loop[:loop_len], reps)[: int(total * SR)]
    fade = int(SR * 1.5)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


# ---- sound effects ----------------------------------------------------------------------
def tick(high=False):
    t = _t(0.09)
    return np.sin(math.tau * (1500 if high else 1100) * t) * np.exp(-45 * t) * 0.5


def boing():
    t = _t(0.18)
    f = 300 + 500 * (t / 0.18)
    return np.sin(math.tau * np.cumsum(f) / SR) * np.exp(-10 * t) * 0.5


def whoosh(dur=0.35):
    t = _t(dur)
    n = _rng.standard_normal(len(t))
    return _lp(n, 6) * np.sin(math.pi * t / dur) ** 2 * 0.6


def celebrate():
    """Pop + toot-toot party horn + sparkly bell run + crowd cheer and claps (~2 s)."""
    out = np.zeros(int(SR * 2.2))
    pop = _hp(_rng.standard_normal(int(SR * 0.08)), 8) * np.exp(-_t(0.08) * 60)
    put(out, 0, pop, 0.8)
    put(out, 0, kick(), 0.5)
    put(out, 0.05, toot(_midi(72), 0.14), 0.30)
    put(out, 0.22, toot(_midi(76), 0.14), 0.30)
    put(out, 0.39, toot(_midi(79), 0.5), 0.30)
    for i, n in enumerate([84, 88, 91, 96, 100, 103, 108]):  # rising sparkle
        put(out, 0.12 + i * 0.07, bell(_midi(n)), 0.30)
    t = _t(1.6)
    cheer = _hp(_lp(_rng.standard_normal(len(t)), 5), 60) * np.minimum(1, t * 8) * np.exp(-1.6 * t) * 2.2
    put(out, 0.1, cheer, 0.45)
    rnd = np.random.default_rng(5)
    for tt in rnd.uniform(0.3, 1.5, 9):
        put(out, float(tt), clap(), 0.25)
    return out


def write_wav(path, x):
    x = np.tanh(x * 1.3)
    x = x / max(1e-9, np.abs(x).max()) * 0.8
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((x * 32767).astype(np.int16).tobytes())


def mix(total, voice, sfx, music_track):
    """voice/sfx/music_track are float arrays of len total*SR; music ducks under the voice."""
    env = _lp(np.abs(voice), int(SR * 0.08))
    duck = 1 - 0.6 * np.clip(env / 0.04, 0, 1)
    duck = _lp(duck, int(SR * 0.15))
    return music_track * 0.55 * duck + sfx * 0.9 + voice * 1.25
