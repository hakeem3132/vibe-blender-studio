# ADR: Offline Dependency Distribution

## Decision

Vibe Blender Studio publishes platform-specific, wheel-only dependency
artifacts generated from the committed Poetry lock. Wheelhouses are not stored
in Git or inside the Blender add-on. CI caches or publishes them as short-lived
workflow/release artifacts. Supported preparation targets are CPython 3.11 and
3.12 on Linux x86-64 and Windows x86-64; each target needs its own manifest.

`scripts/build_wheelhouse.py` selects only the `main` group for `core`, and
`main` plus `dev` for `development`. Semantic and vision/model groups are never
included. It requests binary wheels with `--only-binary=:all:` and `--no-deps`,
then rejects any filename/version/hash not recorded by `poetry.lock`. Source
archives are not executed. The manifest records platform, Python, lock hash,
wheel filenames, SHA-256 values, groups and distribution license metadata.

Offline installation first re-verifies the manifest and every wheel, then uses:

```bash
python scripts/install_offline.py .runtime/wheelhouse/core /tmp/vibe-core --profile core
```

The installer invokes pip with `--no-index --find-links --require-hashes`.
Missing, extra, tampered or wrong-Python wheels fail with an actionable error.

## Preparation and update

```bash
python scripts/build_wheelhouse.py --profile core --refresh
python scripts/build_wheelhouse.py --profile development --refresh
python scripts/verify_wheelhouse.py .runtime/wheelhouse/core --profile core
python scripts/test_clean_install.py .runtime/wheelhouse/core --profile core
```

Regenerate after every accepted `poetry.lock` change and for every supported
Python/OS target. CI artifacts are retained for 14 days; release wheelhouses may
be retained with their matching product release and manifest. Vulnerability
scanning uses the locked default profile before publication. License metadata is
part of the manifest; release engineering must review packages whose metadata is
unknown or whose redistribution terms require accompanying text.

This decision avoids hundreds of megabytes of binaries in Git while making the
validation install independent of live PyPI.
