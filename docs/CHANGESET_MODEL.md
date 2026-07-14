# ChangeSet Model

ChangeSet schema `1.0` is strict: unknown fields fail validation and invalid
ChangeSets never partially execute. A request contains UUID request/change IDs,
prompt, scope, one to 16 allowlisted operations, preserve rules, deterministic
checks and low risk classification.

Milestone 1 tools are limited to:

- `object.create`: cube, sphere, cylinder, plane or empty;
- `object.transform`: absolute/delta location, absolute/delta Euler rotation,
  absolute scale or uniform scale factor;
- `object.visibility`: viewport and render visibility.

There is no Python/code operation. Stable UUIDs, not display names, resolve
targets. The offline deterministic interpreter supports the examples in the
Quick Start; other prompts return a scope limitation message.
