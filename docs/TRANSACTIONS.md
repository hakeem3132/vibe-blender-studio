# Transactions

Vibe Studio maintains an application transaction record independent of
Blender's global undo stack. Each record stores the ChangeSet, target UUIDs,
exact tracked before/proposed/applied states, deterministic checks, status,
timestamp, error and rollback result.

Preview uses **snapshot, apply, inspect, restore**. It immediately restores the
approved scene even when execution or verification fails. Apply refuses stale
previews, applies only after validation and a snapshot, and rolls back on failed
verification. Reject never mutates the scene. Undo restores the tracked before
state; redo restores the accepted after state.

Tracked state covers stable identity, transform, visibility, materials,
animation presence and revision for preservation comparison. Milestone 1 object
reconstruction is deliberately bounded to its supported primitive types.
