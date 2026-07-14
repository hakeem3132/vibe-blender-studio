# Antigravity Setup

This archive is a transfer snapshot for continuing Vibe Blender Studio
development from branch `codex/vibe-blender-launch` at revision
`89d4e387bc8a2100ce1dd6fdf499bc790567c0ce`.

## Open

1. Extract the archive into a development workspace.
2. Open the extracted project folder in Antigravity.
3. Confirm the repository state:

```bash
git status --short --branch
git rev-parse HEAD
```

Expected branch: `codex/vibe-blender-launch`

Expected revision: `89d4e387bc8a2100ce1dd6fdf499bc790567c0ce`

## Install

Use the committed lock file for normal development setup:

```bash
poetry install --with dev
poetry check --lock
```

For offline installation work, use the repository scripts:

```bash
python scripts/build_wheelhouse.py --profile core
python scripts/verify_wheelhouse.py --profile core
python scripts/install_offline.py --profile core
```

## Test

Run focused checks first:

```bash
ruff check .
ruff format --check .
mypy .
pytest tests/unit/vibe_studio
```

Real Blender validation requires Blender 4.2.15:

```bash
python scripts/find_blender.py
python scripts/run_blender_tests.py
```

FFmpeg validation requires both `ffmpeg` and `ffprobe` on `PATH`.

## Notes

- Do not commit Blender binaries, virtual environments, wheelhouses, renders,
  videos, caches, secrets, session tokens or runtime directories.
- Repository provenance is recorded in `docs/REPOSITORY_PROVENANCE.md`.
- The included publication bundle can be used to recover the verified local
  Git state if remote publication is unavailable.
