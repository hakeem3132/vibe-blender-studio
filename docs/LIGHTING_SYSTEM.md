# Lighting System

Milestone 2 allowlists Point, Area, Spot and Sun creation plus energy, color,
size/radius, location and rotation updates. Managed light objects and data blocks
receive stable UUIDs. Semantic roles are stored as `key`, `fill`, `rim` or
`custom`.

The release-visible preset is deterministic three-point studio lighting:

| Role | Type | Energy | Position |
|---|---:|---:|---|
| Key | Area | 900 W | `(4, -4, 5)` |
| Fill | Area | 420 W | `(-4, -2, 2.5)` |
| Rim | Area | 700 W | `(0, 4, 4.5)` |

Light energy can be keyframed. The real Blender acceptance reduced only key-light
energy by 20%, verified the camera, materials and unrelated lights, then exercised
preview, reject, undo and redo. Product studio, dark luxury, bright commercial,
technical neutral and soft daylight presets remain planned and are not exposed as
working controls.
