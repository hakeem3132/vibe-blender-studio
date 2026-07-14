# Camera System

The camera layer creates managed cameras, makes one active, and configures
location, rotation, focal length, clipping, depth of field and focus object. A
targeted camera is aimed geometrically with Blender's `-Z` track direction; names
are display labels and UUIDs are authoritative.

The release-visible Hero Product preset uses a 55 mm lens, a bounded transform and
the selected object as its focus direction. Atomic camera configuration, push-in
and orbit macros are available through validated ChangeSets. Push-in preserves
the lens and target unless explicitly changed. Orbit uses target UUID, radius,
angles, height and bounded start/end frames.

Inspection reports the camera UUID, active state, lens, sensor, clipping, DOF,
focus UUID, transform and animation state. The real acceptance created and
activated the hero camera, animated a six-second push, reopened the `.blend`, and
verified camera/action UUID persistence. Other named composition presets remain
planned and are not enabled in the current UI.
