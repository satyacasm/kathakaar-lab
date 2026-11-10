"""Hindi cut: retime the story to the Hindi narration, then mix it.

The English timeline (timing.json) stays the master. Each Hindi line gets a slot at least as long as the
English one, and the line-9 word cuts follow the Hindi words. That gives a piecewise-linear time map
English -> Hindi, which is used twice:
  * picture: app/src/story/warp_hi.ts (Story plays the English frame W^-1(t) at Hindi time t, so shots slow down)
  * sound:   the English music and SFX (unducked) are time-stretched per segment with ffmpeg atempo (pitch kept),
             then ducked under the Hindi voice with the same voice chain, ducking and limiter as build_sound.py.

Usage: engine/kk.sh <episode> build_sound_hi [picks_hi.json]   (default: <episode>/voice/picks_hi.json)
Writes <episode>/timing_hi.json, <app episode dir>/warp_hi.ts, <episode>/audio/mix_hi.wav (+ copy in the app's
public/episodes/<slug>/), <episode>/audio/sound_report_hi.md.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import kk  # noqa: E402

EP = kk.ep()
OUT = EP / "audio"
EN_PICKS = EP / "voice/picks_en.json"
HI_PICKS = Path(sys.argv[1]) if len(sys.argv) > 1 else EP / "voice/picks_hi.json"
sys.argv = [sys.argv[0], str(HI_PICKS)]          # build_sound reads the voice picks from argv at import
import build_sound as B                          # noqa: E402

sys.path.insert(0, str(kk.ENGINE / "voice"))
import review_takes as R                         # noqa: E402

EN_WORDS9 = json.loads(EN_PICKS.read_text()).get("words9", [])   # episode 001 only: three word cuts in line 9
FPS = 30
OWN_PACE = kk.meta().get("hi_pacing") == "own"   # episode.json: Hindi lines keep their own pauses
XF = 0.03   # crossfade between stretched segments, s


def take_len(path):
    """Length as build_sound places it (speech + 0.05 s before + 0.12 s after) and the speech-start offset."""
    x = R.read(path)
    s, e = R.speech_bounds(x)
    return (e - s) / R.SR + 0.17, x, s


def word_onsets(x, s):
    """Word onsets (s, relative to the placed audio) from 10 ms energy frames, for 'Rivers. Mountains. Gods.'"""
    w = 240
    db = np.array([20 * np.log10(np.sqrt(np.mean(x[i:i + w] ** 2)) + 1e-9) for i in range(0, len(x) - w, w)])
    db -= db.max()
    # candidate onsets: level rises above -30 dB after >= 50 ms below -45 dB (breaths stay under -50).
    # Pauses inside a word (Hindi stops like पर्-वत) can be as long as a short word gap, so keep the first
    # onset plus the two that follow the longest silences: the line is exactly three words.
    cand, quiet = [], 10 ** 6
    for i, d in enumerate(db):
        if d < -45:
            quiet += 1
        elif d > -30:
            if quiet >= 5:
                cand.append((quiet, i))
            quiet = 0
    idx = sorted([cand[0][1]] + [i for _, i in sorted(cand[1:], reverse=True)[:2]])
    t = [i * w / R.SR - (s / R.SR - 0.05) for i in idx]
    return [x for x in t if x >= 0][:3]


def hindi_timing():
    en = B.TIMING
    lines, t = [], en["lead_in"]
    picks = B.PICKS
    for i, ln in enumerate(en["lines"]):
        n = ln["line"]
        nxt = en["lines"][i + 1]["start"] if i + 1 < len(en["lines"]) else en["total"]
        en_slot = nxt - ln["start"]
        length, x, s = take_len(B.TAKES_DIR / picks[str(n)])
        # picture-first episodes (001) keep at least the English slot; voice-first ones keep the Hindi pacing
        slot = length + ln["pause_after"] if OWN_PACE else max(en_slot, length + ln["pause_after"])
        if OWN_PACE and i + 1 == len(en["lines"]):   # keep the English closing tail after the last line
            slot += max(0.0, en["total"] - (ln["end"] + 0.12 + ln["pause_after"]))
        rec = dict(line=n, start=round(t, 3), end=round(t + length - 0.12, 3), pause_after=ln["pause_after"])
        if n == 9 and EN_WORDS9:
            rec["words"] = [round(t + w, 3) for w in word_onsets(x, s)]
        lines.append(rec)
        t += slot
    return dict(lead_in=en["lead_in"], total=round(t, 3), lines=lines)


def anchors(hi):
    en = B.TIMING
    a = [(0.0, 0.0)]
    for le, lh in zip(en["lines"], hi["lines"]):
        a.append((le["start"], lh["start"]))
        if le["line"] == 9 and len(lh.get("words", [])) == 3:
            a += list(zip(EN_WORDS9[1:], lh["words"][1:]))   # first word is ~the line start already
    a.append((en["total"], hi["total"]))
    a = sorted(set(a))
    assert all(b[0] > p[0] and b[1] > p[1] for p, b in zip(a, a[1:])), "time map must be increasing"
    return a


def _stages(ratio):
    """atempo accepts 0.5..2 per instance; chain instances for anything outside that."""
    out = []
    while ratio < 0.5 or ratio > 2:
        out.append(0.5 if ratio < 0.5 else 2.0)
        ratio /= out[-1]
    return out + [ratio]


def atempo(x, ratio):
    """Stretch a stereo float block by 1/ratio in time, pitch kept (ffmpeg atempo, 0.5..2 per stage)."""
    if abs(ratio - 1) < 1e-4:
        return x
    raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(B.SR), "-ac", "2", "-i", "-",
                          "-af", ",".join(f"atempo={r:.6f}" for r in _stages(ratio)), "-f", "f32le", "-"],
                         input=x.T.astype("<f4").tobytes(), capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<f4").reshape(-1, 2).T.astype(np.float64)


def warp(x, amap, n_out):
    """Piecewise atempo along the anchor map, overlap-added with short crossfades."""
    out = np.zeros((2, n_out + B.ns(1)))
    xf = B.ns(XF)
    for (e0, h0), (e1, h1) in zip(amap, amap[1:]):
        a, b = B.ns(e0), min(B.ns(e1) + xf, x.shape[1])
        seg = atempo(x[:, a:b], (e1 - e0) / (h1 - h0))
        want = B.ns(h1) - B.ns(h0) + xf
        seg = np.pad(seg, ((0, 0), (0, max(0, want - seg.shape[1]))))[:, :want]
        ramp = np.ones(want)
        ramp[:xf] = np.linspace(0, 1, xf) if h0 > 0 else 1
        ramp[-xf:] = np.linspace(1, 0, xf)
        i = B.ns(h0)
        out[:, i:i + want] += seg * ramp
    return out[:, :n_out]


def write_warp_ts(amap, hi):
    frames = int(round(hi["total"] * FPS)) + 1
    en = [round(e * FPS, 3) for e, _ in amap]
    hn = [round(h * FPS, 3) for _, h in amap]
    (kk.app_dir() / "warp_hi.ts").write_text(
        "// Generated by audio/build_sound_hi.py: Hindi frame -> English story frame (piecewise linear).\n"
        f"export const HI_FRAMES = {frames};\n"
        f"export const HI_WARP = {{hi: {json.dumps(hn)}, en: {json.dumps(en)}}};\n")
    return frames


def main():
    B.WORDS9 = tuple(EN_WORDS9)                         # bells/thumps on the English narrator's words, then warped
    en_total = B.TIMING["total"]
    m, s = B.music(), B.sfx()                          # English timeline, unducked
    m *= B.dbg(-21 - B.integrated(m))
    s *= B.dbg(-22 - B.integrated(s))

    hi = hindi_timing()
    amap = anchors(hi)
    (EP / "timing_hi.json").write_text(json.dumps(hi, indent=1) + "\n")
    frames = write_warp_ts(amap, hi)

    # switch build_sound's globals to the Hindi timeline
    B.TIMING, B.DUR = hi, hi["total"]
    B.N = B.ns(B.DUR)
    B.L = {x["line"]: x for x in hi["lines"]}
    m, s = warp(m, amap, B.N), warp(s, amap, B.N)
    v = B.voice_track()
    m_d = m * B.duck_curve(-6)[None, :]
    s_d = s * B.duck_curve(-4)[None, :]
    ride = B.clarity_ride(v, m_d + s_d)[None, :]
    m_d, s_d = m_d * ride, s_d * ride
    mix = v + m_d + s_d
    mix *= B.dbg(B.TARGET_LUFS + 0.4 - B.integrated(mix))
    mix, g = B.limiter(mix)
    mix *= B.dbg(B.TARGET_LUFS - B.integrated(mix))
    mix, g = B.limiter(mix)
    B.write_wav(str(OUT / "mix_hi.wav"), mix)
    subprocess.run(["cp", str(OUT / "mix_hi.wav"), str(kk.public_dir() / "mix_hi.wav")], check=True)

    e = B.ebur(OUT / "mix_hi.wav")
    rows = [f"| {x['line']} | {x['start']:.2f} | "
            f"{B.integrated(v[:, B.ns(x['start']):B.ns(x['end'])]) - B.integrated((m_d + s_d)[:, B.ns(x['start']):B.ns(x['end'])]):.1f} |"
            for x in hi["lines"]]
    rep = ["# Hindi sound report", "", f"Length {hi['total']:.2f} s ({frames} frames), English {en_total:.2f} s.", "",
           f"mix_hi.wav: {e['I']} LUFS, LRA {e['LRA']}, true peak {e['TP']} dBTP; max limiter GR "
           f"{-20 * np.log10(g.min()):.1f} dB", "", "Time map English s -> Hindi s: " +
           ", ".join(f"{a:.2f}->{b:.2f}" for a, b in amap), "",
           "| Line | Start s | Voice − bed LU |", "|---|---|---|"] + rows
    (OUT / "sound_report_hi.md").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
