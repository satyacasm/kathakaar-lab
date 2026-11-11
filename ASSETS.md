
## Social profile assets (8 Nov 2026), `brand/social/`
| File | Source | Licence / note |
|---|---|---|
| `ai/emblem_a.png`, `ai/emblem_b.png`, `ai/panorama_a.png`, `ai/panorama_b.png` | AI-generated on Higgsfield (model Z Image, Satyam's Pro plan), prompts in the 8 Nov session: Pattachitra-style diya emblems and a temple-river scroll, no people, no text | Generated for Kathakaar under Higgsfield's terms for paid plans; check the current terms before any trademark use |
| `profile_1080.png`, `profile_youtube_800.png`, `youtube_watermark_150.png`, `profile_named_1080.png`, `youtube_banner_2560x1440.png`, `facebook_cover_1640x624.png`, `ig_highlight_*.png` | Own work: layouts, name plates and Devanagari text drawn in `engine/app/src/brand/BrandAssets.tsx` over the AI art above | Own work |

## Reel motion engine tools and weights (11 Nov 2026), `tools/`, `models/`
| File | Source | Licence / note |
|---|---|---|
| `models/depth-anything-v2-small/model.onnx` | huggingface.co/onnx-community/depth-anything-v2-small (ONNX export of Depth-Anything-V2-Small) | Apache-2.0 (model card). Do not swap in Base/Large: CC-BY-NC-4.0 |
| `tools/rife/rife-ncnn-vulkan-20221029-macos/` (model `rife-v4.6` used) | github.com/nihui/rife-ncnn-vulkan release 20221029 | MIT (binary); RIFE weights from hzwer/Practical-RIFE, MIT |
| `tools/esrgan/` (model `realesr-animevideov3`) | github.com/xinntao/Real-ESRGAN release v0.2.5.0, `realesrgan-ncnn-vulkan-20220424-macos.zip` | Real-ESRGAN BSD-3-Clause; ncnn-vulkan wrapper MIT |
| pip `onnxruntime` 1.31.1 in `pipeline/.venv` | PyPI | MIT |
