# Dependency Security

Baseline audit reported `transformers 4.57.6` findings PYSEC-2025-217,
CVE-2026-1839 and CVE-2026-4372. `transformers` entered through vision and
sentence-transformer routing features; it is not required for the deterministic
Milestone 1 workflow.

Remediation: semantic routing (`sentence-transformers`, `lancedb`, `pyarrow`)
and vision (`transformers`, Torch and related packages) are optional Poetry
groups and are excluded from the default core installation. The unused MLX
group was removed because its NumPy 2 transitive requirement conflicts with the
tested NumPy 1.x upstream core. This removes the affected paths from Milestone 1
runtime rather than suppressing audit output.
Users who explicitly install model extras must run the repository dependency
audit and select a remediated compatible release before production use.

FastMCP's optional update lookup is disabled by default so backend startup does
not accidentally require SOCKS proxy support. Proxy support is optional; no
proxy dependency is added to core. Malformed or unsupported proxy configuration
emits an actionable warning while the local backend remains available.

`poetry.lock` is generated with Poetry 2.4.1. A clean `--only main` installation
contained 85 distributions, excluded all model packages and passed pip-audit
2.10.1 with zero known vulnerabilities after bootstrapping pip 26.1.2. The clean
development installation contained 100 audited distributions and also reported
zero known vulnerabilities. Optional AI groups were not installed or audited as
production dependencies in this milestone.

Milestone 2 adds no Python runtime dependency for rendering or encoding. Blender,
FFmpeg and FFprobe are discovered external tools and are not vendored. The Poetry
2.4.1 lock remains valid for product version 0.2.0-dev; `poetry check --strict
--lock` is a required gate. Output path and subprocess argument safety are covered
by the Milestone 2 security suite.
