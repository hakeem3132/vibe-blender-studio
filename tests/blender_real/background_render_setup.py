"""Create the small licensed procedural fixture used by background acceptance."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy


def main() -> None:
    destination = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 3
    scene.render.fps = 24
    scene.render.resolution_x = 160
    scene.render.resolution_y = 90
    scene.render.resolution_percentage = 100
    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
    cube = bpy.context.object
    cube.name = "Background Acceptance Cube"
    cube.rotation_euler.z = 0.0
    cube.keyframe_insert(data_path="rotation_euler", frame=1)
    cube.rotation_euler.z = 2.0 * math.pi
    cube.keyframe_insert(data_path="rotation_euler", frame=3)
    bpy.ops.object.camera_add(location=(4.5, -5.5, 3.5))
    camera = bpy.context.object
    camera.rotation_euler = (math.radians(67.0), 0.0, math.radians(38.0))
    scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(2.0, -2.0, 4.0))
    bpy.context.object.data.energy = 900.0
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 4.0
    scene.world = bpy.data.worlds.new("Background Acceptance World")
    scene.world.color = (0.03, 0.03, 0.03)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))
    print(f"VIBE_BACKGROUND_SETUP={destination}")


if __name__ == "__main__":
    main()
