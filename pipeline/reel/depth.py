"""Depth map per still: Depth Anything V2 Small (Apache-2.0, ONNX export from onnx-community) on CPU via onnxruntime.

`depth_for(still)` returns a float32 HxW map in [0, 1], 1 = near, at the still's resolution, cached next to the
still as sNN_depth.png (16-bit). The caller must already hold the GPU lock (gpu_lock.sh wraps the whole stage).

Also: `paper_mask(img)` finds the rough painted-paper border around the illustration (1 = inside the painting).
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .clipkit import DEPTH_ONNX, log

_SESSION = None
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def depth_path(still: Path) -> Path:
    still = Path(still)
    return still.with_name(still.stem + "_depth.png")


def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = 4  # fanless machine: leave headroom
        _SESSION = ort.InferenceSession(str(DEPTH_ONNX), so, providers=["CPUExecutionProvider"])
    return _SESSION


def _infer(rgb: np.ndarray, short: int = 518) -> np.ndarray:
    h, w = rgb.shape[:2]
    s = short / min(h, w)
    th, tw = max(14, round(h * s / 14) * 14), max(14, round(w * s / 14) * 14)
    x = cv2.resize(rgb, (tw, th), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
    x = ((x - _MEAN) / _STD).transpose(2, 0, 1)[None]
    out = _session().run(None, {"pixel_values": x})[0][0]
    return out.astype(np.float32)  # relative inverse depth: larger = nearer


def compute(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    d = _infer(rgb)
    # test-time flip average: steadier edges at no real cost
    d = 0.5 * (d + _infer(rgb[:, ::-1].copy())[:, ::-1])
    d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
    lo, hi = np.percentile(d, 1), np.percentile(d, 99.5)
    d = np.clip((d - lo) / max(1e-6, hi - lo), 0, 1).astype(np.float32)
    # edge-aware smoothing guided by the painting, so depth steps sit on the ink lines
    guide = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    try:
        d = cv2.ximgproc.guidedFilter(guide, d, 8, 1e-3)  # contrib only; absent in headless build
    except AttributeError:
        d = cv2.bilateralFilter(d, 9, 0.08, 6)
    return np.clip(d, 0, 1)


def depth_for(still: Path, force: bool = False) -> np.ndarray:
    still = Path(still)
    p = depth_path(still)
    if p.exists() and not force and p.stat().st_mtime >= still.stat().st_mtime:
        d16 = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        return d16.astype(np.float32) / 65535.0
    rgb = cv2.cvtColor(cv2.imread(str(still), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    log(f"depth: {still.name}")
    d = compute(rgb)
    cv2.imwrite(str(p), (d * 65535).astype(np.uint16))
    return d


def paper_mask(rgb: np.ndarray) -> np.ndarray:
    """Soft mask, 1 inside the painted area, 0 on the bare paper border (flood-connected to the image edge)."""
    h, w = rgb.shape[:2]
    small = cv2.resize(rgb, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.float32)
    sh, sw = lab.shape[:2]
    k = max(3, sh // 40)
    corners = np.concatenate([lab[:k, :k].reshape(-1, 3), lab[:k, -k:].reshape(-1, 3),
                              lab[-k:, :k].reshape(-1, 3), lab[-k:, -k:].reshape(-1, 3)])
    paper = np.median(corners, 0)
    dist = np.linalg.norm(lab - paper, axis=2)
    cand = (dist < 14).astype(np.uint8)
    # a real paper border lines all four outer edges; otherwise the still is full-bleed
    e = max(1, sh // 100)
    sides = [cand[:e].mean(), cand[-e:].mean(), cand[:, :e].mean(), cand[:, -e:].mean()]
    if min(sides) < 0.8:
        return np.ones((h, w), np.float32)
    # the border lives in the outer band only (pale sky or mist inside the painting must not count)
    band = np.zeros_like(cand)
    by, bx = int(sh * 0.12), int(sw * 0.12)
    band[:by] = 1; band[-by:] = 1; band[:, :bx] = 1; band[:, -bx:] = 1
    cand &= band
    # keep only paper-coloured regions connected to the frame edge
    n, lbl = cv2.connectedComponents(cand, connectivity=4)
    edge = np.unique(np.concatenate([lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]]))
    border = np.isin(lbl, edge[edge > 0]).astype(np.uint8)
    border = cv2.morphologyEx(border, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    inside = 1.0 - border.astype(np.float32)
    if inside.mean() < 0.3:  # no real border found (full-bleed still)
        inside[:] = 1.0
    # soft falloff inward from the torn edge
    dt = cv2.distanceTransform((inside > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    soft = np.clip(dt / max(4.0, sh * 0.06), 0, 1)
    soft = soft * soft * (3 - 2 * soft)
    return cv2.resize(soft.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)


def run(ep_dir, only=None, force=False):
    """Compute depth for every keyframe still of the episode (helper; motion calls depth_for itself)."""
    kdir = Path(ep_dir) / "out" / "keyframes"
    for p in sorted(kdir.glob("s*.png")):
        if p.stem.endswith("_depth"):
            continue
        n = int(p.stem[1:3])
        if only is None or n in set(map(int, only)):
            depth_for(p, force=force)
