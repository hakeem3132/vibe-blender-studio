# Security Policy

Vibe Blender Studio accepts only versioned, authenticated RPC envelopes and
allowlisted Blender operations. Report vulnerabilities privately to the
repository maintainers; do not include credentials or proprietary `.blend`
files in a public issue.

Do not open a public vulnerability issue. Contact the upstream maintainer at
`patryk.ciechanski@patrykiti.pl` and include affected commit/version,
reproduction steps, environment details and redacted logs. Security fixes are
best-effort for the latest development line.

The default listener is `127.0.0.1`. Remote binding is denied unless
`VIBE_RPC_ALLOW_REMOTE=1` is explicitly set, and must be protected by a trusted
network boundary. Session tokens are ephemeral, stored only in a user-specific
temporary file with mode `0600`, and never stored in a `.blend` file.

Raw model-generated Python, `exec`, and `eval` are outside the supported Vibe
Studio workflow. See `docs/CONNECTION_SECURITY.md` for limits and configuration.
