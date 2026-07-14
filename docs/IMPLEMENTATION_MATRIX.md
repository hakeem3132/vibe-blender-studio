# Implementation Matrix

| Capability | Status | Evidence |
|---|---|---|
| Authenticated bounded RPC | REAL BLENDER TESTED | Loopback backend authenticated during Blender 4.2.15 workflow |
| Foundation object ChangeSets/transactions | REAL BLENDER TESTED | Foundation suite plus Milestone 2 create/transform operations |
| Progressive native Blender UI | REAL BLENDER TESTED | Registration, properties, draw paths, action mapping and icons; visual smoke test remains manual |
| Material create/assign/duplicate/update | REAL BLENDER TESTED | Product Black workflow, preserve checks and undo/redo |
| Material scalar animation | REAL BLENDER TESTED | Principled roughness action created and persisted in real Blender |
| Light create/update/roles | REAL BLENDER TESTED | Deterministic key/fill/rim plus key-energy micro-edit |
| Light energy animation | REAL BLENDER TESTED | Light-data action created in real Blender |
| Camera create/activate/configure | REAL BLENDER TESTED | Hero camera and 55 mm lens |
| Camera push/orbit macros | BETA | Push real-tested and persisted; orbit schema/runtime tested but not in demo |
| Object keyframes/interpolation/retime | REAL BLENDER TESTED | 360° rotation and scoped 20% profile edit |
| Preview frame/range | REAL BLENDER TESTED | Non-destructive settings restore and PNG validation |
| Background image sequence/render recovery | REAL BLENDER TESTED | Child-process 3-frame acceptance; progress, cancel/kill, crash, stall, resume, stale recovery and safe cleanup tests |
| H.264 encode/FFprobe validation | REAL BLENDER TESTED | 320x180, 24 fps, 6.0 s, 144 frames |
| Eevee headless render on current Linux host | BLOCKED | Host lacks `libEGL`; CPU Cycles fallback passed |
| Offline clean installation | WORKING | CPython 3.12 Linux core/development wheelhouses installed with `--no-index`, hashes and lock provenance |
| Proxy-isolated loopback integration | WORKING | Streamable HTTP tests pass with inherited broken HTTP/SOCKS proxies without disabling provider proxy support |
| Interactive visual UI acceptance | BLOCKED | Headless automation proves registration/modal path but cannot assess layout or visual quality |
| Lighting/camera preset families beyond exposed presets | PLANNED | Not exposed as active controls |
| Storyboard/audio/subtitles | PLANNED | Milestone 3+ |
| Character/Godot | PLANNED | Later milestones |

`REAL BLENDER TESTED` describes deterministic headless runtime behavior, not
interactive visual quality.
