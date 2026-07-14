# Milestone 2 Report

## Starting state

- Branch: `codex/vibe-blender-launch`
- Starting head: `96d056ffe3974079017845ada9cc941380bcd6f0`
- Foundation commits: all required revisions reachable
- Baseline: 3,243 passed, 1 skipped; Foundation real Blender 51 passed
- Runtime: Blender 4.2.15 LTS / Python 3.11.7; FFmpeg/FFprobe 6.1.1

## Implemented and real-tested

Strict Milestone 2 ChangeSets cover managed materials, lights, cameras, atomic
keyframes, object/camera animation macros, scoped interpolation/retiming, preview
and render jobs, and video encode/validation. The native sidebar has Create,
Materials, Lighting, Camera, Animate, Render, History and Diagnostics groups with
Simple/Creator/Professional disclosure.

The real product workflow created a cylinder and floor, assigned and duplicated
materials, created key/fill/rim lights, created a hero camera, animated product
rotation, camera push, material roughness and light energy, and executed
transactional material/light/animation edits. Preview/reject/undo/redo and
preservation checks passed. Save/reopen preserved managed and action UUIDs.

## Real render and video evidence

`scripts/run_milestone2_tests.py` passed 94 of 94 checks. It rendered 144 PNG
frames at 320x180, encoded H.264 at 24 fps and validated 6.0 seconds / 144 frames
with FFprobe. Measured on the final runner pass: 3.312 seconds for the image
sequence, 0.201 seconds for encode, and 4.142 seconds for stage one. These are environment-specific
draft-profile measurements, not performance guarantees.

The host lacks `libEGL`; Eevee cannot initialize in headless mode. Product presets
still target Blender 4.2 Eevee Next, while the reproducible acceptance runner used
an allowlisted one-sample CPU Cycles fallback. No interactive graphical layout or
visual-quality acceptance was performed.

## Tests and gates

- Ruff lint/format and mypy: passed across 763 files.
- Unit: 3,231 passed, 1 skipped.
- Contract: 25 passed.
- Security: 12 passed.
- Blender mock: 1 passed.
- Render: 5 passed.
- FFmpeg: 4 passed, including a real encode/probe.
- Foundation real Blender: 51 passed.
- Milestone 2 real Blender/end-to-end: 94 passed.
- Poetry 2.4.1 `check --strict --lock`: passed.
- Default locked dependency audit: zero known vulnerabilities.
- Pre-commit and pre-push: passed.
- Add-on: two byte-identical 157,452-byte builds, SHA-256
  `04f58d9fbf6ffd2e944c106441a7a8d6e3c1414ad4971f56e271658d3e67cd62`.

The clean-install rerun was attempted from the committed lock but could not
download packages because this runtime denies `pypi.org`. Foundation Beta's prior
clean core/development installation evidence remains unchanged and no dependency
was added in Milestone 2, but the current clean-install gate is recorded as
blocked rather than passed. A broad upstream `pytest` invocation also inherited
an unavailable SOCKS proxy in streamable client tests; canonical unit groups pass
with loopback proxy variables cleared, and the product's malformed/missing proxy
profiles remain covered separately.

## Deliberate limits

The visible release controls expose tested Material presets, Three-point studio,
Hero camera, 360° rotation, preview and verified MP4. Additional named lighting
and camera presets are planned. Interactive rendering is synchronous in this beta;
the background runner is recommended for longer jobs. Forced Blender-process
cancellation was unit-tested rather than injected into the real demo.

Storyboard, audio, subtitles, character, Godot, ComfyUI, FreeMoCap, text-to-3D,
render-farm and collaboration workflows are not implemented.

## Status

FOUNDATION BETA
