"""Shared paths for the Kathakaar engine.

The engine is shared; each episode lives in its own folder under episodes/. Scripts find the episode
through the KK_EP environment variable (engine/render.sh and engine/kk.sh set it), so nothing hard-codes a story.
Episode files used here: episode.json (id, slug, app_dir), script/lines.json ({"en": [...], "hi": [...],
"pause_after": {"1": 0.5, ...}}), timing.json, voice/, audio/, out/.
"""

import json
import os
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
LAB = ENGINE.parent
BRAND = LAB / "brand"
MODELS = LAB / "models"
APP = ENGINE / "app"

# Final narrators (decided 7 Nov 2026): designed synthetic voices, no real person.
NARRATOR_EN = BRAND / "voices/narrator_en_A2.wav"
NARRATOR_EN_TEXT = BRAND / "voices/narrator_en_A2.txt"
NARRATOR_HI = BRAND / "voices/narrator_hi_D_ref.wav"


def ep() -> Path:
    v = os.environ.get("KK_EP")
    if not v:
        raise SystemExit("Set KK_EP to the episode folder, e.g. KK_EP=~/kathakaar-lab/episodes/001-markandeya-pralaya")
    p = Path(v).expanduser().resolve()
    if not p.is_dir():
        raise SystemExit(f"KK_EP is not a folder: {p}")
    return p


def meta() -> dict:
    return json.loads((ep() / "episode.json").read_text())


def lines(lang: str) -> list:
    return json.loads((ep() / "script/lines.json").read_text())[lang]


def pause_after() -> dict:
    d = json.loads((ep() / "script/lines.json").read_text()).get("pause_after", {})
    return {int(k): float(v) for k, v in d.items()}


def app_dir() -> Path:
    """The episode's scene code inside the Remotion app."""
    return APP / "src/episodes" / meta()["app_dir"]


def public_dir() -> Path:
    """Where the app reads the episode's audio from."""
    d = APP / "public/episodes" / meta()["slug"]
    d.mkdir(parents=True, exist_ok=True)
    return d
