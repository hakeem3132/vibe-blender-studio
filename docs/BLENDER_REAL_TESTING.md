# Real Blender Testing

Supported baseline is Blender 4.2 LTS; CI pins `4.2.15`. The add-on declares a
minimum of Blender 4.0. The Linux archive is downloaded from
`https://download.blender.org/release/Blender4.2/` and verified against SHA-256
`b9dcc1d06861529779e7faf8d82c9dd3563443dfb1eb14212424c8c40b77074e`.
The Windows ZIP is pinned to SHA-256
`e17c122edb011159bb825e2fba2118e232ba61e47ba610e116e743d5a7798d42`.

Run explicitly:

```bash
scripts/install_blender_ci.sh
export BLENDER_PATH=/path/printed/by/installer/blender
python scripts/run_blender_tests.py
```

The acceptance installs the packaged ZIP into a clean Blender home, checks the
panel/operator/property registrations and draw path, authenticates a real local
RPC session, creates a cube through a typed ChangeSet, verifies preview,
apply/reject, preserve constraints and application undo/redo, then saves and
reopens the file to verify UUID persistence. It writes machine-readable
evidence under `outputs/blender_real/`.

The local Milestone 1.1 run passed 51 checks on Blender 4.2.15 LTS with embedded
Python 3.11.7. Headless registration is not a visual layout test; execute
`docs/MANUAL_BLENDER_UI_ACCEPTANCE.md` in a normal Blender window before making
a claim about interactive layout quality. If Blender is absent, the runner
exits 2 and prints `BLOCKED`; that is not a passing real Blender result.
