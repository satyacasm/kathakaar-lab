# Music-reel pipeline (low-cost)

Makes a one-minute, song-timed reel for about 10 Higgsfield credits. Stills and most motion are made on this Mac;
Higgsfield is used only for a few "hero" clips. Target output: two reels a day inside 600 credits a month.

Measured on the M5 Air (16 GB), 11 Nov 2026: a local still takes 2-3 min (FLUX.2 klein 4B, mflux, 4-bit, 4 steps,
1344x768). Local video models (Wan 2.2 5B) took 34 min for a 3 s clip with almost no motion, so they are not used.
Seedance 2.0 Mini on Higgsfield costs 0.5 credits per second at 480p (2 credits for 4 s).

## Stages

```
script/shots.json + script/edit.json
   │
   ├─ check     validate both files, print shot lengths, hero seconds, credit estimate vs budget
   ├─ stills    local stills and pose variants            → out/keyframes/sNN.png, sNN_<pose>.png
   ├─ motion    local animation of "local" shots          → out/clips/cNN.mp4
   ├─ hero      (Claude, via Higgsfield MCP) hero clips    → out/hero_raw/cNN.mp4, logged in the credit ledger
   ├─ finish    upscale + retime hero clips               → out/clips/cNN.mp4
   └─ assemble  cut to bars, transitions, grade, captions → out/final/*.mp4 + cover
```

CLI: `pipeline/.venv/bin/python pipeline/reel.py <episode-slug> <stage> [--only 3,5] [--force]`.
Every stage is resumable: it skips outputs that exist unless `--force`.

## Code layout

| File | Owner stage | What it does |
|---|---|---|
| `pipeline/reel.py` | all | CLI dispatcher; imports stage modules lazily |
| `pipeline/reel/shots.py` | check | load + validate `shots.json` / `edit.json`; fail fast on unknown values |
| `pipeline/reel/budget.py` | check, hero | credit ledger and caps |
| `pipeline/reel/stills.py` | stills | `run(ep_dir, only=None, force=False)` |
| `pipeline/reel/motion.py`, `fx.py`, `depth.py` | motion | `motion.run(ep_dir, only=None, force=False)` |
| `pipeline/reel/finish.py` | finish | `run(ep_dir, only=None, force=False)` |
| `pipeline/reel/assemble.py` | assemble | `run(ep_dir, captions_only=False)`; uses `pipeline/reel_fx.py` |
| `pipeline/reel/masks.py` | assemble | anime cut-in mask reveals (see "Masks and transitions") |
| `pipeline/reel/styles/<name>.txt` | stills | locked style prompt, appended to every still prompt |
| `pipeline/reel/config.json` | all | caps and defaults (below) |
| `pipeline/gpu_lock.sh` | stills, motion | run a heavy command while holding the one-at-a-time GPU lock |
| `pipeline/new_reel.sh` | scaffold | create `episodes/<nnn-slug>/` for a music reel |

`ep_dir` is the absolute path of `episodes/<slug>/`. All paths inside the JSON files are relative to it.

## `script/shots.json` (what each shot is)

```json
{
  "style": "watercolor_ink",
  "characters": {
    "rama": {"ref": "refs/rama.png",
             "desc": "Rama: blue-grey skin, black hair in a topknot, white tilak, rudraksha beads, torn brown bark cloth, long bow, quiver"}
  },
  "shots": [
    {"n": 1,
     "prompt": "An aged vulture king on a cliff edge at dusk watches a golden flying chariot cross a crimson sky, wide shot",
     "characters": [],
     "seed": 101,
     "source": "local",
     "motion": {"type": "drift", "camera": {"move": "push_in", "amount": 0.07, "ease": "in_out"}, "parallax": 0.6},
     "fx": ["embers", "glow"]},
    {"n": 2,
     "prompt": "Close-up of Rama's face in three-quarter view, calm, forest behind him",
     "characters": ["rama"],
     "seed": 102,
     "source": "hero",
     "hero": {"model": "seedance_2_0_mini", "resolution": "480p", "duration": 4,
              "prompt": "He slowly turns his head to the camera and a faint smile forms, hair drifting, painted watercolor style unchanged"}},
    {"n": 3,
     "prompt": "Rama kneels beside a fallen giant bird in a forest clearing, side view",
     "characters": ["rama"],
     "seed": 103,
     "source": "local",
     "poses": [{"id": "b", "edit": "he has bowed his head and closed his eyes, his hand rests on the bird's wing"}],
     "motion": {"type": "morph", "camera": {"move": "static"}, "parallax": 0.3},
     "fx": ["mist"]}
  ]
}
```

Rules:
- `source`: `local` (made by `motion`) or `hero` (made on Higgsfield, then `finish`).
- The base still of shot N is `out/keyframes/sNN.png` (two digits). Pose variant `b` is `out/keyframes/sNN_b.png`.
  A pose is made by editing the base still with the pose's `edit` text, so character and background stay fixed.
- A shot with `characters` passes each character's `ref` image to the model and puts each `desc` in the prompt.
- `motion.type`:
  - `drift`: one still, depth-based camera move.
  - `morph`: base still to each pose in order, smooth in-between frames (frame interpolation), plus camera move.
  - `step`: hold each pose and snap to the next on a beat, with a short flash; for big moves that cannot blend.
- `camera.move`: `static | push_in | pull_out | pan_left | pan_right | tilt_up | tilt_down`. `amount` is a fraction
  of frame width (keep ≤ 0.08). `ease`: `linear | in_out | out`. `parallax`: 0 (flat) to 1.
- `fx` (any of): `embers, sparks, smoke, mist, glow, rays, rain, stars, flash`. Grain and vignette are always on, low.
- `hero.end_pose` (optional): a pose id whose still is sent as the end frame.
- `sky_title` (optional, local shots; code `pipeline/reel/skytitle.py`): a film title that rises into the sky of the
  shot and is part of the scene: composited before the camera move (it drifts with the sky) and hidden by a
  feathered depth matte behind large near shapes (figures, lion, hills; thin things like a trident shaft are ignored).
  ```json
  "sky_title": {"text": "Mahakali", "sub": ["जयन्ती मङ्गला ... ।", "दुर्गा क्षमा ... ॥"],
                "start": 0.2, "rise": 1.4, "x": 0.72, "y": 0.10, "size": 0.085, "max_width": 0.46, "sub_size": 0.04}
  ```
  `text` (Latin, Avenir Next Demi Bold capitals, gold gradient + warm glow) rises `travel` (0.10) over `rise` s from
  `start` s (slow ease-out, fade and blur-to-sharp in, letter-spacing opening), then holds. `sub` (string with
  newlines, or list) lines follow, smaller and quicker, from `sub_at` (default `start + rise - 0.1`), `sub_rise` (0.9) s
  each, `sub_stagger` (0.22) s apart; Latin lines in Avenir Next Medium capitals, Devanagari lines in Devanagari Sangam
  MN Bold, shaped by HarfBuzz/libraqm (`brew install libraqm`; `check` fails rather than draw unshaped Devanagari).
  Fractions are of the 1920x1080 picture: `x`/`y` (0.5/0.26) centre of the block / title, `size` (0.12) title capital
  height, `sub_size` (0.034) sub letter height, `max_width` (0.72) widest line (fonts shrink to fit). Also `glow`
  (1.0), `occlude` (true). Put the block in open sky. Defaults: `skytitle.py`. `check` warns if the title is settled
  for less than 1 s of the shot. The on-screen-text style rule applies. Check legibility at the inset size (1080x608).
- Unknown `source`, `motion.type`, `camera.move`, `fx` or `style` values are errors in `check`.

## `script/edit.json` (when each shot plays)

Same format as episode 006 (see `episodes/006-jatayu-ravana/script/edit.json`), plus optional keys (`layout`, `end_card`,
per-shot `black_tail` and `mask`, and the transition types in "Masks and transitions"):

```json
{
  "song": "audio/song.wav", "song_in": 21.014, "song_out": 81.014, "fade_out": 1.6,
  "size": [1080, 1920], "fps": 30,
  "layout": "inset",
  "end_card": {"text": "Kathakaar", "sub": "animated stories", "hold": 2.5},
  "bars": [0.0, 2.461, 5.225],
  "shots": [{"n": 1, "clip": "out/clips/c01.mp4", "from_bar": 0, "to_bar": 1, "in": 0.0}],
  "captions": [], "transitions": [], "grade": {}
}
```

- `bars` are seconds from the start of the reel. A shot plays from `bars[from_bar]` to `bars[to_bar]`.
- `layout`:
  - `full` (default): the clip fills `size`, as in episode 006.
  - `inset`: `size` is 1080x1920; the 16:9 picture is scaled to 1080x608 and centred (y = 656) on a dark textured
    background; captions go in the band below the picture; the end card fades in over the last shot.
- `end_card` is optional; a reel can instead end on a `sky_title` in its last shot (shots.json). The cover takes its
  title from `cover.title`/`cover.sub`, falling back to `end_card`.
- Per-shot clips in `out/clips/` are always 1920x1080, 30 fps, H.264 yuv420p, no audio, and at least as long as
  the shot's bar span (the assembler trims; it slows a clip down only if it is too short).

## Masks and transitions

Code: `pipeline/reel/masks.py` (masks), `pipeline/reel_fx.py` (`apply_edits`: every transition except `hero`),
validated by `check`. All edges, slices and shakes come from seeds, so every render is identical. No effect changes a
shot's frame count.

**Mask reveal** (per shot in `edit.json` `shots`; the anime "cut-in"): the whole 1080x1920 screen is black (no
textured background, no picture box) and the picture shows only inside a slanted band across the full width,
scaled to cover it. Frame 0 is a white-hot slash line; the band snaps open over `open` frames (ease-out, slight
overshoot), holds while the picture drifts in, and with `black_tail` snaps shut to a hot line just before the black.
A thin gold or white edge line with a soft glow runs along the band edges, brightest while it opens.

```json
{"n": 9, "clip": "out/clips/c09.mp4", "from_bar": 5, "to_bar": 6, "black_tail": 0.36,
 "mask": {"type": "zigzag", "angle": 10, "width": 0.44, "y": 0.5, "open": 5, "close": 4, "edge": "gold",
          "focus": [0.5, 0.45]}}
```

- `type`: `zigzag` (jagged lightning edges that open out of one crack), `slash` (clean parallelogram),
  `shards` (2-3 parallel bands of different widths, like manga panels; they open one frame apart, `bands`: 2 or 3).
- `angle` -40..40 (degrees, + rises to the right), `width` 0.08..0.7 (share of screen height), `y` 0.15..0.85 (band
  centre), `open` 1..15 and `close` 0..15 (frames), `edge` `gold|white|none`, `focus` [x, y] (0-1 point of the
  picture placed at the band centre), `zoom` 1..2, `drift` 0..0.15 (slow push-in), `lines` (faint speed lines in the
  black, default true), `flash` (white slash on frame 0, default true), `seed`. Vary `angle` sign, `y` and `type`
  between consecutive reveals.
- In an inset reel with any masked shot, the edit pass puts every shot on the 1080x1920 canvas itself (same filter as
  before); without masks the final pass is unchanged. Captions are drawn on top as usual (do not put one on a mask).

**Transitions** (`edit.json` `"transitions"`; `bar` is the index into `bars` of the cut, exactly as for `hero`).
All take `strength` (default 1.0, 0.05-3) and `pre`/`post` in seconds (frames before/after the cut; 0-1.5).
Defaults at 30 fps in brackets. At most one cut transition per bar; `shake` can be added on top.

| type | what it does | example |
|---|---|---|
| `hero` | unchanged (wind-up, flash, punch, shake, RGB split) | `{"type": "hero", "bar": 15, "pre": 0.35, "post": 0.45}` |
| `whip` | both shots slide as one strip with directional motion blur; fastest on the cut [3+4] | `{"type": "whip", "bar": 14, "dir": "left"}` (`dir`: left, right, up, down) |
| `slash` | slanted wipe; a bright edge line crosses the centre exactly on the cut [2+3] | `{"type": "slash", "bar": 10, "angle": 24, "dir": "right", "edge": "gold"}` (`angle` -45..45 lean from vertical) |
| `glitch` | RGB split + displaced horizontal slices, peaking on the cut, a few slices from the other shot [3+4] | `{"type": "glitch", "bar": 13}` |
| `zoom` | accelerating push with radial blur into A, B lands zoomed and settles out [4+6] | `{"type": "zoom", "bar": 9, "cx": 0.5, "cy": 0.5}` |
| `flash` | 2-frame flash cut [0+2] | `{"type": "flash", "bar": 18, "color": "red"}` (`white`, `gold`, `red` or `[r, g, b]`) |
| `shake` | no cut: decaying shake + small zoom punch [0+12] | `{"type": "shake", "bar": 17, "post": 0.35, "strength": 0.6}` or `{"type": "shake", "t": 7.606}` |

Rules where effects meet:
- A cut transition into a masked shot, or out of one, is ignored with a warning (the mask has its own open/close);
  only `flash` out of a masked shot plays.
- Out of a shot with `black_tail`, only the incoming half plays (the outgoing frames are already black), so a drop
  after black is best as `flash` (+ `shake`).
- `shake` works anywhere; on a masked shot it shakes the picture inside the band.
- In the inset layout every transition works inside the 1080x608 picture; the background never moves.

## Hero clips and the credit ledger

Higgsfield is reached through Claude's MCP tools, not from Python, so the `hero` stage is done by Claude:

1. `reel.py <ep> hero-plan` prints, for each hero shot with no file in `out/hero_raw/`: still path, end-frame path
   if any, prompt, model, resolution, duration, and the estimated credits; then the reel total and the month total
   against the caps. It refuses (exit 1) if either cap would be exceeded.
2. Claude uploads the still, calls `generate_video` (first with `get_cost: true`, and only proceeds if the quote
   matches the estimate), downloads the result to `out/hero_raw/cNN.mp4`.
3. `reel.py <ep> hero-log --n 2 --credits 2 --job <job id>` appends to the ledger.

Ledger: `episodes/credits.json` (not in git): `{"entries": [{"date": "2026-11-11", "episode": "...", "n": 2,
"model": "...", "seconds": 4, "credits": 2.0, "job": "..."}]}`.

`pipeline/reel/config.json`:

```json
{"credits_per_month": 600, "credits_per_reel": 10,
 "hero_rate": {"seedance_2_0_mini": {"480p": 0.5, "720p": 1.0}},
 "still": {"model": "flux2-klein-4b", "quantize": 4, "steps": 4, "width": 1344, "height": 768},
 "clip": {"width": 1920, "height": 1080, "fps": 30}}
```

## Machine rules (16 GB, fanless)

- One heavy model at a time. Wrap every still generation, depth pass, interpolation and upscale in
  `pipeline/gpu_lock.sh <command...>`: it waits for the lock, runs the command, releases the lock.
- Never hold a whole clip's frames in RAM at full size when it can be streamed: pipe raw frames to ffmpeg.
- Stills: `mflux-generate-flux2` (new image) and `mflux-generate-flux2-edit --image-paths ...` (reference or pose
  edit), both with `--model flux2-klein-4b --quantize 4 --steps 4`. klein 4B is Apache 2.0; do not use klein 9B,
  FLUX.1 dev or Kontext (non-commercial).
- Licences: only tools and weights that allow commercial use. Record each new one in the root `ASSETS.md`.

## Demo episode

`episodes/900-pipeline-demo/` is a 13 s, 5-shot test reel (bars 0-5 of the episode 006 song) that exercises every
stage. Its hero shot uses a stand-in raw clip so no credits are spent.

## Daily use

One reel, start to finish (run from the repo root):

```
pipeline/new_reel.sh 007-hanuman-leap                 # scaffold episodes/007-hanuman-leap/
# put the song in audio/, write script/shots.json and script/edit.json (copy the demo's as a model)
pipeline/.venv/bin/python pipeline/reel.py 007-hanuman-leap check                              # fix every error it lists
pipeline/.venv/bin/python pipeline/reel.py 007-hanuman-leap stills                             # local, 2-3 min per still
pipeline/.venv/bin/python pipeline/reel.py 007-hanuman-leap motion                             # local clips for the "local" shots
pipeline/.venv/bin/python pipeline/reel.py 007-hanuman-leap hero-plan                          # what to buy; exit 1 if over a cap
#   Claude buys each hero clip (quote first), saves out/hero_raw/cNN.mp4, then:
pipeline/.venv/bin/python pipeline/reel.py 007-hanuman-leap hero-log --n 2 --credits 2 --job <job id>
pipeline/.venv/bin/python pipeline/reel.py 007-hanuman-leap finish                             # upscale + retime hero clips
pipeline/.venv/bin/python pipeline/reel.py 007-hanuman-leap assemble                           # -> out/final/reel_SILENT.mp4, reel_with_song.mp4, cover.jpg
```

`reel.py <ep> all` runs check, stills, motion, finish and assemble in one go; if hero clips are missing it stops before
`finish` and lists them. Upload `reel_SILENT.mp4` with `cover.jpg` and add the song in the Instagram app
(start at `song.instagram_start` in `episode.json`). Caption text change only: `reel.py <ep> assemble --captions`.
`check --strict` also fails on missing clip files; `assemble` always does.

