# Connection Security

Milestone 1 uses a local length-prefixed JSON RPC transport with protocol
version `1.0`.

- Default bind: `127.0.0.1:8765`.
- Remote bind: rejected unless `VIBE_RPC_ALLOW_REMOTE=1`.
- Authentication: 256-bit URL-safe ephemeral token, rotated when the add-on
  listener starts. The token file is outside the repository and `.blend` file,
  and is created with user-only permissions.
- Limits: 1 MiB request, 1 MiB response, JSON depth 24, 16 tool calls, one
  request per envelope. Environment variables prefixed `VIBE_RPC_` configure
  these budgets.
- Timeouts: connection/request timeout in the backend client, 60-second idle
  socket timeout, and bounded add-on execution timeout.
- Errors: request ID, protocol version, stable error code and error boundary.
- Logging: authentication and API-key fields are recursively redacted.

Oversized frames are rejected after the four-byte size header and before the
body is read. Malformed JSON, schema violations, protocol mismatch, missing or
invalid tokens, expired sessions and disconnects return or record actionable
errors.
