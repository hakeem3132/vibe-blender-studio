# Milestone 1.1 Evidence Report

## Starting revision

- Branch: `codex/vibe-blender-launch`
- Starting commit: `226535f64a927e3a329f398e37f989065f94b330`
- Starting tree: clean; existing history retained

## Real Blender

- Blender: 4.2.15 LTS, Linux x64 archive
- Embedded Python: 3.11.7
- Provisioning: repository installer into ignored `.runtime/blender`; no system
  installation or administrator privileges
- Archive SHA-256:
  `b9dcc1d06861529779e7faf8d82c9dd3563443dfb1eb14212424c8c40b77074e`
- Command: `BLENDER_PATH=.runtime/blender/blender-4.2.15-linux-x64/blender python scripts/run_blender_tests.py`
- Result: 51 passed, 0 failed
- Evidence: `outputs/blender_real/milestone_1_1_results.json`
- Saved scene: `outputs/blender_real/milestone_1_1.blend`
- Redacted diagnostics: `outputs/blender_real/milestone_1_1_diagnostics.json`

The workflow installed the packaged add-on in a clean Blender home, registered
the panel/operators/properties, executed the panel draw path, authenticated a
backend health probe, created and renamed a UUID object, previewed/applied and
rejected changes, verified preserve rules, performed application undo/redo,
saved, closed and reopened the `.blend`, and re-inspected the persistent UUID.

Automated UI registration passed. No interactive visual Blender session was
performed; `docs/MANUAL_BLENDER_UI_ACCEPTANCE.md` remains the visual smoke test.

## Dependency resolution and clean installation

- Policy: committed application lock
- Poetry: 2.4.1
- Gate: `poetry check --strict --lock` passed
- Core: 85 distributions, 277,649,239 bytes after pip 26.1.2 bootstrap
- Development: 100 distributions, 325,427,392 bytes
- Optional AI packages in core: absent
- Core and development pip-audit 2.10.1: zero known vulnerabilities
- Backend startup: inherited, no-proxy, HTTP proxy, missing SOCKS support and
  malformed proxy profiles exited successfully; the last two emitted actionable
  warnings

## Quality evidence

- Ruff lint: passed, 751 files
- Ruff formatting: passed, 751 files
- mypy: passed, 751 files
- Unit/contract/security/mock: 3,243 passed, 1 skipped
- Focused Vibe/add-on/RPC: 49 passed
- Real Blender: 51 passed
- Package integrity: passed
- Two clean add-on builds: byte-identical

## Package

- Path: `outputs/blender_ai_mcp.zip`
- Size: 129,974 bytes
- SHA-256: `25ccbc0ca5a3ccc40561b1902e24b89f332da01e67fe2de5537e0c34821a3201`
- Entries: 46
- ZIP integrity: passed
- LICENSE, NOTICE, THIRD_PARTY_NOTICES, product/upstream version metadata and
  installation instructions: present
- Secrets, caches, tests, binaries, `.blend` files and local paths: absent

## Repository destination

The connected GitHub account is `hakeem3132`, but the GitHub connector returned
404 for `hakeem3132/vibe-blender-studio`. The local checkout still points to the
read-only upstream `PatrykIti/blender-ai-mcp`, and GitHub CLI is unavailable.
No push or pull request is claimed. A verified bundle and patch series preserve
the branch until the product repository is created or exposed.

## Product boundary

This report covers the Foundation only. Materials, animation, video, characters,
Godot, ComfyUI, FreeMoCap and text-to-3D were not started.
