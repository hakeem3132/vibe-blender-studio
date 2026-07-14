# Animation System

Milestone 2 provides allowlisted, transaction-aware Blender 4.2 animation tools.
Supported object and camera properties are location, Euler rotation and scale.
Supported scalar properties are Principled roughness/emission strength and light
energy. Atomic insert, update and delete operations are bounded to frames
1-10000. Rotation, movement, camera push and camera orbit are deterministic
macros.

Interpolation supports Constant, Linear and Bezier. Bezier keys use deterministic
auto-clamped handles for the beginner easing presets. Animation inspection records
the action UUID, data path, array index, key values, interpolation, handles,
extrapolation, group and frame range. F-curve comparisons tolerate Blender float
representation while still checking structure and unaffected values.

Preview applies the ChangeSet to a captured state, inspects and verifies it, then
restores the captured state. Apply repeats from that same state. Application undo
and redo restore recorded action snapshots and do not rely exclusively on global
Blender undo.

For the six-second demonstration, "20% slower" is interpreted as a slower motion
profile inside the original frame range: an auto-clamped midpoint is shifted while
the first pose, final pose and scene duration remain fixed. Camera curves,
materials, lights and other objects are verified unchanged.

NLA editing, drivers, constraints, modifiers, skeletal animation and arbitrary
data paths are outside Milestone 2.
