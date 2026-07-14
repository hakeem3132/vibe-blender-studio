# Milestone 2.1 Report

Milestone 2.1 closes the runtime gates for offline installation, inherited proxy
isolation and non-blocking full-animation rendering. This report does not claim
interactive visual quality.

## Dependency artifact

Core and development CPython 3.12 Linux wheelhouses were generated from the
Poetry 2.4.1 lock using binary wheels only. Every wheel filename and SHA-256 was
matched to the lock before a manifest and hashed requirements file were emitted.
Fresh temporary environments installed using `--no-index`; core and development
imports/startup diagnostics passed, and optional model packages remained absent.
Wheelhouse binaries stay ignored and are published/cached separately.

## Proxy isolation

Only controlled loopback Streamable HTTP test transports use an HTTPX client
factory with `trust_env=False`. Non-loopback URLs are rejected by that helper.
Normal provider/outbound HTTP and optional SOCKS behavior remains unchanged and
has separate no-proxy, HTTP, malformed, missing-SOCKS and installed-SOCKS tests.

## Background render

Full renders launch Blender as a child process, monitor frame progress through a
Blender modal operator, preserve partial output on cancellation, escalate
terminate to kill, record stderr/exit status, fail stalled/crashed/missing-frame
jobs, resume missing frames and recover stale manifests. Real Blender 4.2.15
rendered and validated three 160x90 frames through this child-process path. Unit
tests cover success, progress, cancellation, forced termination, child failure,
missing frames, resume, stale recovery, stall detection, duplicate jobs, unsafe
paths and ownership-safe cleanup.

## Evidence limitations

The workspace maintenance event removed the original Git object database, so the
requested Milestone 2 commit objects are not reachable in the reconstructed
local repository. The retained source was re-anchored truthfully; exact source
and runtime evidence is preserved in a new verified bundle and patch series.
No graphical Blender session was used, so the manual UI checklist remains open.

## Final validation evidence

- Ruff lint and formatting passed for 774 files; mypy passed for 774 source
  files.
- The complete unit suite passed with 3,245 passed and one documented skip.
- Focused results were: contract 25 passed, security 14 passed, Blender mock
  one passed, render/background 10 passed, FFmpeg four passed, and proxy
  regression 12 passed.
- Real Blender 4.2.15 LTS passed all 51 Foundation checks, all 95 Milestone 2
  checks, and all nine background-render acceptance checks. Blender's embedded
  Python version was 3.11.7.
- FFmpeg and FFprobe 6.1.1 encoded and independently validated H.264 video at
  320x180, six seconds, and 144 frames.
- Poetry 2.4.1 passed `poetry check --strict --lock`; the locked core profile
  produced no known vulnerability in pip-audit 2.10.0.
- Pre-commit and pre-push passed without bypassing hooks.
- Two clean add-on builds were byte-identical. The archive is 162,200 bytes,
  SHA-256 `86f2b8969ab3f6cb3187c329f908d5aedc92c0cc50676f4018a76d7fc48f5662`,
  and ZIP integrity passed.
- Fresh no-index installs passed for the 53,297,631-byte core wheelhouse and the
  75,463,408-byte development wheelhouse. Installed environments measured
  307,863,871 and 380,798,924 bytes respectively.

## Publication and status

The connected GitHub application returned `404 Not Found` for
`hakeem3132/vibe-blender-studio` and its installed-repository search returned no
match. Nothing was pushed and no pull request was created. A verified local Git
bundle and patch series are supplied instead.

All Milestone 2.1 runtime release gates pass. The approved repository-level
status remains **FOUNDATION BETA**, because the required original Milestone 2 Git
objects were removed by workspace maintenance and cannot be proved reachable.
Restoring that provenance and completing the documented graphical UI smoke test
are the remaining release checks; no visual-quality claim is made.
