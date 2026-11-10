"""Sound draft for the Markandeya story test: voice treatment, original drone score, synthetic SFX, mix.

Usage: engine/kk.sh <episode> build_sound [picks.json]   (default: <episode>/voice/picks_en.json)
picks.json: {"takes_dir": "voice/takes_en", "picks": {line: file}, "words9": [onset s, onset s, onset s]}.
Reads <episode>/timing.json; writes <episode>/audio/ and copies mix.wav to the app's public/episodes/<slug>/.
Cue sheet: music() and sfx() below are episode 001's. Any other episode supplies its own in <episode>/sound_cues.py,
defining music(B) and sfx(B), where B is this module (timing in B.L, synths, dsp helpers).
Writes audio/stems/{voice,music,sfx}.wav (48 kHz, 24-bit stereo), audio/mix.wav, audio/mix.m4a, audio/sound_report.md.
Everything is seeded, so the same inputs give bit-identical output.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage, signal

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import kk  # noqa: E402

EP = kk.ep()
OUT = EP / "audio"
from dsp import (SR, TAU, ns, tt, dbg, rng, lp, hp, bp, peq, shelf, colored, smooth_noise, fades, pan, st,
                 place, widen, make_ir, convolve_st, integrated, momentary, true_peak, write_wav)

TIMING = json.loads((EP / "timing.json").read_text())
_P = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else EP / "voice/picks_en.json").read_text())
PICKS = _P.get("picks", _P)
TAKES_DIR = EP / _P.get("takes_dir", "voice/takes_en")
DUR = TIMING["total"]
N = ns(DUR)
L = {x["line"]: x for x in TIMING["lines"]}
WORDS9 = tuple(_P.get("words9", (28.32, 28.84, 29.44) if kk.meta()["id"] == "E001" else ()))  # "Rivers." "Mountains." "Gods." onsets, measured from the take

TARGET_LUFS = -14.0
CEIL_DBTP = -2.0                  # AAC encoding adds ~0.6 dB of true peak


# ================================================================ voice
def load_take(path):
    """24 kHz mono take -> 48 kHz float, trimmed the same way review_takes.py trims it."""
    sys.path.insert(0, str(kk.ENGINE / "voice"))
    import review_takes as R
    a = R.read(path)
    s, e = R.speech_bounds(a)
    a = a[max(0, s - int(0.05 * R.SR)): min(len(a), e + int(0.12 * R.SR))]
    a = signal.resample_poly(a.astype(np.float64), 2, 1)
    return fades(a, 0.004, 0.03)


def compress(x, thresh_db=-24, ratio=3.0, att=0.008, rel=0.12, makeup_db=0.0):
    env = np.sqrt(ndimage.uniform_filter1d(x ** 2, ns(0.010)) + 1e-12)
    lvl = 20 * np.log10(env)
    gr = np.minimum(0.0, (thresh_db - lvl) * (1 - 1 / ratio))
    # asymmetric one-pole on gain reduction at 1 ms control rate: fast to reduce, slow to recover
    blk = 48
    nb = len(gr) // blk + 1
    grb = np.pad(gr, (0, nb * blk - len(gr)), mode="edge").reshape(nb, blk).min(1)
    ka, kr = 1 - np.exp(-blk / (att * SR)), 1 - np.exp(-blk / (rel * SR))
    out, y = np.empty(nb), 0.0
    for i, tgt in enumerate(grb):
        y += (tgt - y) * (ka if tgt < y else kr)
        out[i] = y
    g = np.interp(np.arange(len(x)), np.arange(nb) * blk + blk / 2, out)
    return x * dbg(g + makeup_db)


def deess(x, lo=5000, hi=9500, thresh_db=-30, max_cut=8.0):
    band = bp(x, lo, hi, 2)
    e_b = 20 * np.log10(np.sqrt(ndimage.uniform_filter1d(band ** 2, ns(0.005)) + 1e-12))
    cut = np.clip(e_b - thresh_db, 0, max_cut)
    cut = ndimage.uniform_filter1d(cut, ns(0.004))
    return x - band * (1 - dbg(-cut))


def voice_track():
    v = np.zeros(N)
    for n in L:
        a = load_take(TAKES_DIR / PICKS[str(n)])
        i = ns(L[n]["start"])
        v[i:i + len(a)] += a[: N - i]
    v = hp(v, 75, 2)
    v = peq(v, 250, -2.0, 1.0)          # less boxiness
    v = peq(v, 3200, 2.0, 0.9)          # presence
    v = shelf(v, 10000, 1.5, "high")    # air
    v = deess(v)
    v = compress(v, -26, 2.8)
    room = make_ir(0.55, seed=7, pre=0.008, hf=1.6)
    wet = convolve_st(v, room)
    out = st(v) + dbg(-19) * wet
    return out * dbg(-18 - integrated(out))   # park at -18 LUFS before the mix


# ================================================================ music (original, D drone)
def m2f(m):
    return 440.0 * 2 ** ((m - 69) / 12)


D1, A1, D2, A2, D3, E3, Fs3, A3, D4, E4, Fs4, A4, D5 = (m2f(m) for m in (26, 33, 38, 45, 50, 52, 54, 57, 62, 64, 66, 69, 74))


def tanpura_pluck(f, dur, r, bright=1.0):
    """additive string with a 'jawari' bloom: mid harmonics swell after the attack and shimmer."""
    t = tt(dur)
    y = np.zeros_like(t)
    for k in range(1, 36):
        fk = f * k * (1 + 0.0004 * k * k * 0.01)
        if fk > 12000:
            break
        a = k ** -0.9
        tau = 2.6 / (1 + 0.06 * k)
        bloom = 1 + bright * 1.6 * np.exp(-((k - 9) / 6) ** 2) * (1 - np.exp(-t / 0.35))
        shimmer = 1 + 0.25 * np.sin(TAU * r.uniform(0.3, 1.4) * t + r.uniform(0, TAU))
        y += a * np.exp(-t / tau) * bloom * shimmer * np.sin(TAU * fk * t + r.uniform(0, TAU))
    y *= 1 - np.exp(-t / 0.006)
    return fades(y / 6.0, 0.002, 0.4)


def tanpura(t0, t1, r, gain=1.0):
    """Pa - Sa - Sa - Sa (low) cycle, 0.55 s apart, until t1."""
    buf = np.zeros((2, N))
    notes, pans = (A2, D3, D3, D2), (-0.3, 0.2, 0.25, -0.1)
    t, k = t0, 0
    while t < t1:
        p = tanpura_pluck(notes[k % 4], 3.2, r)
        place(buf, pan(p, pans[k % 4]), t + r.uniform(-0.01, 0.01), gain * (0.8 if k % 4 == 0 else 1.0))
        t += 0.55 if k % 4 != 3 else 0.85
        k += 1
    return buf


def pad(freqs, t0, dur, r, att=1.2, rel=1.5, warm=900.0, gain=1.0):
    """bowed / choir-like pad: detuned saws, low-passed, slow swell."""
    t = tt(dur)
    y = np.zeros((2, len(t)))
    for f in freqs:
        for c, det in enumerate((-6, 6)):
            ff = f * 2 ** (det / 1200)
            ph = r.uniform(0, 1)
            saw = 2 * ((ff * t + ph) % 1) - 1
            y[c] += saw * (1 + 0.15 * np.sin(TAU * 0.2 * t + r.uniform(0, TAU)))
    y = lp(y, warm, 2)
    env = np.minimum(1, t / att) * np.minimum(1, np.maximum(0, (dur - t) / rel))
    y *= env ** 1.5
    buf = np.zeros((2, N))
    place(buf, y / (len(freqs) * 2), t0, gain)
    return buf


def sub_drone(f, t0, t1, r, gain=1.0):
    t = tt(t1 - t0)
    y = np.sin(TAU * f * t) + 0.35 * np.sin(TAU * 2 * f * t + 1) + 0.12 * np.sin(TAU * 3 * f * t)
    y *= 1 + 0.2 * np.sin(TAU * 0.13 * t)
    y *= np.minimum(1, t / 1.5) * np.minimum(1, (t1 - t0 - t) / 1.0)
    buf = np.zeros((2, N))
    place(buf, y * 0.5, t0, gain)
    return buf


def bell(f, t0, r, gain=1.0, dur=4.0):
    t = tt(dur)
    y = sum(a * np.exp(-t / d) * np.sin(TAU * f * m * t) for m, a, d in
            ((1, 1, 2.5), (2.76, .5, 1.2), (5.4, .25, .6), (8.9, .12, .3)))
    buf = np.zeros((2, N))
    place(buf, pan(fades(y * (1 - np.exp(-t / 0.002)), 0.001, 0.3) * 0.3, r.uniform(-.5, .5)), t0, gain)
    return buf


def music():
    r = rng(11)
    m = np.zeros((2, N))
    # terror -> loneliness: sub drone and a dark low pad, no melody
    m += sub_drone(D1, 0.0, 10.9, r, gain=dbg(-2))
    m += pad([D2, A2], 0.2, 10.6, r, att=2.0, rel=1.5, warm=380, gain=dbg(-4))
    # banyan: tanpura enters, warming
    m += tanpura(10.75, 21.2, r, gain=dbg(-6))
    m += pad([D2, A2, D3], 11.0, 10.3, r, att=2.5, rel=1.0, warm=700, gain=dbg(-8))
    m += bell(D5, 14.15, r, dbg(-6))                    # the child appears
    m += bell(A4, 14.75, r, dbg(-10))
    # the child speaks: one warm sustained chord
    m += pad([D3, A3, Fs4], 17.4, 4.1, r, att=1.0, rel=0.6, warm=1400, gain=dbg(-6))
    # 22.9-23.9 near silence (only SFX)
    # inside: bloom
    m += tanpura(23.9, 30.3, r, gain=dbg(-4))
    m += pad([D2, A2, D3, Fs3, A3, E4], 23.9, 6.7, r, att=1.6, rel=0.5, warm=2200, gain=dbg(-2))
    m += sub_drone(D1, 23.9, 30.5, r, gain=dbg(-8))
    for i, (w, f) in enumerate(zip(WORDS9, (A4, D5, Fs4 * 2))):
        m += bell(f, w - 0.02, r, dbg(-8 + i))
    # 30.5 drop-out; 33.05 final low chord to silence
    m += pad([D1, D2, A2], 33.0, 3.1, r, att=0.6, rel=2.2, warm=500, gain=dbg(-1))
    m += bell(D5, 34.6, r, dbg(-12), dur=2.0)
    m[:, ns(DUR - 0.6):] *= np.linspace(1, 0, N - ns(DUR - 0.6))[None, :] ** 2
    return m


# ================================================================ SFX (synthetic draft)
def noise(dur, r, slope=0.0):
    return colored(ns(dur), r, slope)


def env(n, pts):
    """piecewise-linear envelope from (t, gain) points."""
    t = np.arange(n) / SR
    a = np.array(pts)
    return np.interp(t, a[:, 0], a[:, 1])


def thunder(r, dur=4.0, dist=0.0):
    n = ns(dur)
    crack = hp(noise(0.25, r, -1.0), 400) * np.exp(-tt(0.25) / 0.05) * (1 - dist)
    rumble = lp(noise(dur, r, -2.0), 160 - 80 * dist, 2) * 6
    rumble *= env(n, [(0, 0), (0.05, 1), (0.6, .8), (1.4, .5), (dur, 0)]) * (1 + 0.6 * smooth_noise(n, r, 6))
    y = rumble
    y[: len(crack)] += crack
    return widen(y, r, 13, 0.7)


def wave_roar(r, dur):
    n = ns(dur)
    y = bp(noise(dur, r, -1.0), 60, 2500, 2) * (0.6 + 0.4 * smooth_noise(n, r, 3))
    y += lp(noise(dur, r, -2.0), 120, 2) * 3
    return widen(y * env(n, [(0, 0), (dur * 0.85, 1), (dur, 1)]) ** 1.6, r, 17, 0.8)


def impact(r):
    y = lp(noise(1.6, r, -1.5), 900, 2) * np.exp(-tt(1.6) / 0.35) * 2
    y += np.sin(TAU * 42 * tt(1.6) * (1 - 0.3 * tt(1.6))) * np.exp(-tt(1.6) / 0.4) * 1.5
    y += hp(noise(1.6, r, 0), 2000) * np.exp(-tt(1.6) / 0.12) * 0.5
    return widen(y, r, 9, 0.9)


def splash(r):
    n = ns(1.2)
    y = bp(noise(1.2, r, 0), 300, 6000, 2) * env(n, [(0, 0), (0.02, 1), (0.25, .45), (1.2, 0)])
    y += lp(noise(1.2, r, -1), 300) * env(n, [(0, 0), (0.01, 1), (0.4, 0)]) * 2
    return widen(y, r, 7, 0.6)


def rain(r, dur):
    n = ns(dur)
    y = hp(noise(dur, r, -0.3), 900, 1) * 0.5
    drops = (r.random(n) < 0.0016) * r.standard_normal(n)
    y += hp(lp(drops, 6000), 1500) * 1.5
    return widen(lp(y, 9000), r, 19, 1.0)


def wind(r, dur, lo=150, hi=900):
    n = ns(dur)
    y = bp(noise(dur, r, -0.5), lo, hi, 2) * (0.4 + 0.6 * smooth_noise(n, r, 0.4) ** 2)
    return widen(y, r, 23, 1.0)


def whoosh(r, dur=1.6):
    """rising inhale into the light: band sweeps up, swells, stops."""
    n = ns(dur)
    x = noise(dur, r, -0.5)
    f = np.linspace(200, 4000, 32)
    seg = np.array_split(x, 32)
    y = np.concatenate([bp(s, fc, fc * 2.5, 1) for s, fc in zip(seg, f)])
    y = ndimage.uniform_filter1d(y, 8)
    return widen(y * env(n, [(0, 0), (dur * .8, 1), (dur, 0)]) ** 2, r, 11, 0.8)


def sfx():
    r = rng(23)
    s = np.zeros((2, N))
    # 1: world ends
    place(s, wind(r, 3.4, 80, 500), 0.0, dbg(-14))
    place(s, thunder(r, 3.0), 0.35, dbg(-4))
    place(s, wave_roar(r, 2.45), 0.4, dbg(-6))
    place(s, impact(r), 2.75, dbg(-2))
    # 2: bursts up
    place(s, splash(r), 3.45, dbg(-8))   # synced to the burst through the surface (animatic frame 105)
    place(s, impact(r), 4.18, dbg(-12))  # the swell hits him (frame 126)
    place(s, splash(r), 4.22, dbg(-12))
    tail = wave_roar(r, 2.0)[:, ::-1] * np.linspace(1, 0, ns(2.0))[None, :] ** 2
    place(s, tail, 3.25, dbg(-12))
    # 3: alone in the rain
    rr = rain(r, 8.2) * env(ns(8.2), [(0, 0), (0.6, 1), (6.9, 1), (8.2, 0)])
    place(s, rr, 4.0, dbg(-16))
    place(s, wind(r, 7.0, 120, 700), 4.4, dbg(-17))
    place(s, thunder(r, 3.0, dist=0.8), 7.6, dbg(-14))
    # 4-6: stillness; low water lap
    place(s, lp(noise(10, r, -1.5), 300) * 0.7, 11.0, dbg(-26))
    # 7: drawn into the light
    place(s, whoosh(r, 1.5), 21.45, dbg(-8))
    # 8: inside, airy world wind
    place(s, wind(r, 6.0, 400, 3000) * env(ns(6.0), [(0, 0), (1, 1), (5, 1), (6, 0)]), 24.0, dbg(-24))
    # 9: soft low thumps on each cut
    for w in WORDS9:
        th = np.sin(TAU * 55 * tt(0.6)) * np.exp(-tt(0.6) / 0.15)
        place(s, th, w - 0.02, dbg(-14))
    # 10: back outside: low flood rumble
    place(s, lp(noise(5.5, r, -2), 140, 2) * 3 * env(ns(5.5), [(0, 0), (0.3, 1), (4.2, .6), (5.5, 0)]), 30.45, dbg(-16))
    return s


# ================================================================ per-episode cue sheet
_CUES = EP / "sound_cues.py"
if _CUES.exists():
    import importlib.util
    _spec = importlib.util.spec_from_file_location("sound_cues", _CUES)
    _cues = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_cues)
    _B = sys.modules[__name__]
    music = lambda: _cues.music(_B)   # noqa: E731
    sfx = lambda: _cues.sfx(_B)       # noqa: E731


# ================================================================ mix
def limiter(x, ceil_db=CEIL_DBTP, look=0.003, rel=0.08):
    """Adapted from claude-animated-shorts mix.py (MIT): 4x oversampled peaks, look-ahead, release, smoothing."""
    c = dbg(ceil_db)
    n = x.shape[1]
    up = np.abs(signal.resample_poly(x, 4, 1, axis=-1)).max(0)
    pk = np.pad(up, (0, max(0, 4 * n - len(up))))[: 4 * n].reshape(n, 4).max(1)
    gr = np.minimum(1.0, c / np.maximum(pk, 1e-12))
    La = max(1, ns(look))
    g1 = ndimage.minimum_filter1d(gr, 2 * La + 1, mode="nearest")
    kr = 1 - np.exp(-1 / (rel * SR))
    g2 = g1.copy()
    # release: one-pole recovery computed at 1 ms resolution
    blk = 48
    gb = g1[: n // blk * blk].reshape(-1, blk).min(1)
    out = np.empty_like(gb)
    g = 1.0
    kb = 1 - (1 - kr) ** blk
    for k, v in enumerate(gb):
        g = min(v, g + (1 - g) * kb)
        out[k] = g
    g2[: len(out) * blk] = np.repeat(out, blk)
    g3 = np.minimum(ndimage.uniform_filter1d(np.minimum(g1, g2), 2 * La + 1, mode="nearest"), 1.0)
    return x * g3[None, :], g3


def duck_curve(depth_db, pre=0.12, post=0.25, att=0.08, rel=0.5):
    ctrl = 1000
    nc = int(DUR * ctrl) + 2
    va = np.zeros(nc)
    for x in TIMING["lines"]:
        va[int((x["start"] - pre) * ctrl): int((x["end"] + post) * ctrl)] = 1.0
    ka, kr = 1 - np.exp(-1 / (att * ctrl)), 1 - np.exp(-1 / (rel * ctrl))
    e, envv = 0.0, np.zeros(nc)
    for i in range(nc):
        e += (va[i] - e) * (ka if va[i] > e else kr)
        envv[i] = e
    return dbg(np.interp(np.arange(N) / SR, np.arange(nc) / ctrl, depth_db * envv))


MIN_CLEAR_LU = 9.0


def clarity_ride(v, bed):
    """Extra bed reduction over each spoken line so voice sits >= MIN_CLEAR_LU above music+SFX."""
    d = np.zeros(N)
    for x in TIMING["lines"]:
        a, b = ns(x["start"]), ns(x["end"])
        short = MIN_CLEAR_LU - (integrated(v[:, a:b]) - integrated(bed[:, a:b]))
        if short > 0:
            d[max(0, a - ns(0.1)): b + ns(0.15)] = np.minimum(d[max(0, a - ns(0.1)): b + ns(0.15)], -short - 0.5)
    return dbg(ndimage.uniform_filter1d(d, ns(0.12), mode="nearest"))


def ebur(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    tail = r[r.rfind("Summary:"):]
    get = lambda k: float(tail.split(k)[1].split()[0])
    return dict(I=get("I:"), LRA=get("LRA:"), TP=get("Peak:"))


def main():
    v = voice_track()
    m = music()
    s = sfx()
    m *= dbg(-21 - integrated(m))
    s *= dbg(-22 - integrated(s))
    m_d = m * duck_curve(-6)[None, :]
    s_d = s * duck_curve(-4)[None, :]
    ride = clarity_ride(v, m_d + s_d)[None, :]
    m_d, s_d = m_d * ride, s_d * ride
    mix = v + m_d + s_d
    mix *= dbg(TARGET_LUFS + 0.4 - integrated(mix))
    mix, g = limiter(mix)
    mix *= dbg(TARGET_LUFS - integrated(mix))
    mix, g = limiter(mix)
    gain = dbg(TARGET_LUFS - integrated(v + m_d + s_d))  # stems at the mix's pre-limiter gain, for reuse
    (OUT / "stems").mkdir(parents=True, exist_ok=True)
    write_wav(str(OUT / "stems/voice.wav"), v * gain)
    write_wav(str(OUT / "stems/music_ducked.wav"), m_d * gain)
    write_wav(str(OUT / "stems/sfx_ducked.wav"), s_d * gain)
    write_wav(str(OUT / "stems/music_raw.wav"), m * gain)
    write_wav(str(OUT / "mix.wav"), mix)
    subprocess.run(["cp", str(OUT / "mix.wav"), str(kk.public_dir() / "mix.wav")], check=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(OUT / "mix.wav"),
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", str(OUT / "mix.m4a")], check=True)

    e_wav, e_aac = ebur(OUT / "mix.wav"), ebur(OUT / "mix.m4a")
    # voice-over-bed margin per spoken line (LU), using short windows on the pre-limiter stems
    rows = []
    for x in TIMING["lines"]:
        a, b = ns(x["start"]), ns(x["end"])
        lv, lb = integrated(v[:, a:b]), integrated((m_d + s_d)[:, a:b])
        rows.append(f"| {x['line']} | {x['start']:.2f} | {lv - lb:.1f} |")
    rep = ["# Sound draft report", "",
           f"Length {DUR:.2f} s, 48 kHz stereo.", "",
           "| File | Integrated LUFS | LRA | True peak dBTP |", "|---|---|---|---|",
           f"| mix.wav | {e_wav['I']} | {e_wav['LRA']} | {e_wav['TP']} |",
           f"| mix.m4a (AAC 256k) | {e_aac['I']} | {e_aac['LRA']} | {e_aac['TP']} |", "",
           f"Max limiter gain reduction: {-20 * np.log10(g.min()):.1f} dB", "",
           "Voice above music+SFX per line (LU, higher = clearer; aim ≥ 8):", "",
           "| Line | Start s | Voice − bed LU |", "|---|---|---|"] + rows
    (OUT / "sound_report.md").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
