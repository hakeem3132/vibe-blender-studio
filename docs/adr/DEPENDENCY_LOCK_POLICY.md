# Dependency Lock Policy

## Decision

Vibe Blender Studio is an application, so `poetry.lock` is committed and is
the canonical dependency-resolution artifact. The lock is generated and
validated with Poetry 2.4.1. CI and clean-install checks install from the lock;
they do not resolve unconstrained dependencies during normal validation.

## Groups

- `main`: the deterministic Milestone 1 backend runtime.
- `dev`: lint, type-check, hook and test tooling.
- `semantic`: optional local semantic-routing dependencies.
- `vision`: optional local model dependencies.

The optional groups are excluded from core installation. The unused MLX group
was removed because its transitive OpenCV dependency requires NumPy 2 while the
tested upstream core remains pinned to NumPy 1.x. It may return in a later
model-provider milestone with its own compatible environment; it is not part of
Foundation Beta.

## Reproduction

```bash
python -m pip install pip==26.1.2 poetry==2.4.1
poetry lock
poetry check --strict --lock
poetry install --only main --no-root
poetry install --with dev --no-root
```

`transformers`, Torch, `sentence-transformers`, LanceDB and PyArrow are not
installed by `poetry install --only main`. Model groups require an explicit
opt-in and a separate vulnerability review before production use.

## Vulnerability policy

The core lock is audited separately from optional model groups. A vulnerability
in an explicitly excluded optional group does not silently enter the foundation
runtime, but it remains documented and blocks claiming that optional group as
production-ready.
