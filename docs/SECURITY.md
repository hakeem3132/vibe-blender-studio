# Milestone 2 Security Controls

Milestone 2 retains the authenticated loopback RPC boundary documented in the
root `SECURITY.md`. Scene mutations are strict, versioned ChangeSets using a fixed
tool allowlist; raw Python, `exec`, `eval` and shell execution are rejected.

Render ranges, resolution, job count, timeouts and message sizes are bounded.
Output paths resolve inside the approved project `outputs` directory and reject
traversal, repository metadata and unconfirmed overwrite. FFmpeg uses argument
arrays. Diagnostics redact tokens, secrets and personal paths. Imported scene
data is inspected and is not executed as Python by the Vibe workflow.

The optional AI dependency groups are excluded from core. See
`docs/DEPENDENCY_SECURITY.md` for the lock and audit policy.
