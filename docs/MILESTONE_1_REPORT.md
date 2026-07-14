# Milestone 1 Report

## Implemented

- loopback-first authenticated and bounded RPC protocol;
- coherent `0.1.0-dev` product identity plus upstream provenance;
- native beginner Vibe Studio sidebar with real enabled handlers;
- stable UUID assignment, validation and duplicate repair;
- compact deterministic scene inspection;
- strict allowlisted object ChangeSets and offline prompts;
- snapshot/apply/restore preview and application undo/redo;
- diagnostics redaction and licensing-complete add-on packaging;
- reproducible real Blender scripts and CI acceptance lane.

## Validation status after Milestone 1.1

- Ruff lint and format: passed for 751 files.
- mypy: passed for 751 files.
- Unit/contract/security/mock suite: 3,243 passed, 1 skipped in 87.43 seconds.
- Focused Vibe/add-on/RPC suite: 49 passed.
- Backend startup: normal inherited environment, no proxy, SOCKS proxy and
  malformed proxy all reached FastMCP startup and exited cleanly on stdio EOF;
  unsupported/malformed proxy profiles emitted actionable warnings.
- Add-on: 129,974 bytes; SHA-256
  `25ccbc0ca5a3ccc40561b1902e24b89f332da01e67fe2de5537e0c34821a3201`.
  Two consecutive builds produced the same checksum.
- Real Blender 4.2.15 LTS: 51 acceptance checks passed; packaged add-on,
  authenticated backend probe, transaction workflow and UUID save/reopen passed.
- Poetry 2.4.1: `poetry check --strict --lock` passed and clean core/development
  installations completed from the committed lock.

Interactive visual layout remains manually unverified. Animation, materials,
video, character and Godot features are outside this milestone.
