# Material System

The bounded material layer creates, duplicates, assigns, inspects and updates
managed Principled BSDF materials. Presets resolve to explicit values:

| Preset | Intended starting point |
|---|---|
| Matte | rough diffuse surface |
| Glossy | low-roughness dark surface |
| Metal | metallic neutral surface |
| Glass | transmission with low alpha |
| Plastic | moderately glossy dielectric |
| Emissive | explicit emission color and strength |
| Product Black | dark product surface |
| Product White | light product surface |

Supported inputs are base color, metallic, roughness, IOR level, transmission,
alpha, emission color and emission strength. Roughness and emission strength can
be keyframed. A material copy receives a new UUID and records its source UUID.

Edits operate on exactly one Principled node. Unsupported graphs fail closed;
they are not rebuilt. Transactions compare preserved color, node/link topology,
unrequested Principled properties and unrelated objects, then roll back on a
mismatch. The real Blender workflow created, assigned, duplicated and edited the
Product Black material and verified preview, undo and redo.
