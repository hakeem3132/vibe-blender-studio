# Stable Identities

AI-managed objects, scenes and controlled collections use the `vibe_uuid`
custom property. `vibe_revision` tracks accepted supported mutations. UUIDs are
generated once, survive rename and `.blend` save/reopen, and names remain display
labels only.

Inspection is read-only by default. Assignment occurs through explicit project,
selected-ID, migration or prompt actions. Validation reports missing, malformed
and duplicate IDs. Duplicate repair preserves the first valid occurrence and
assigns new UUIDs to later occurrences. Lookup must resolve exactly one object.
