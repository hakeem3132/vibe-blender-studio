# Vibe Studio Milestone 2 Quick Start

1. Run `python scripts/build_addon.py`. In Blender 4.2.15 Preferences, install
   `outputs/blender_ai_mcp.zip` from disk and enable **Vibe Blender Studio**.
2. Run `python -m server.main`. Open 3D View > Sidebar > **Vibe Studio**, select
   **Connect**, then **Health check**. No API key is needed for deterministic
   Milestone 1 or 2 prompts.
3. Save the `.blend`, create project metadata and inspect the scene.
4. For the tested product demo, create a cylinder and plane with the Prompt panel.
   Select the cylinder, choose Product Black under Materials, then create
   Three-point studio lighting and a Hero product camera.
5. Set frames 1-144 and 24 fps, then choose **Create 360° rotation**. Use a
   validated camera-push ChangeSet for the complete demonstrated camera motion.
6. Choose **Preview animation frame**. Preview/range jobs snapshot and restore
   final render settings.
7. Use a micro-prompt such as `Reduce only roughness to 0.2.` or
   `Slow the selected animation by 20%.` Preview it, then Apply or Reject. Undo
   and Redo use application transaction snapshots.
8. Select Draft or Preview and choose **Render verified MP4**. Vibe Studio renders
   PNG frames first, validates them, encodes H.264 with FFmpeg, and validates the
   result with FFprobe. FFmpeg/FFprobe and an active camera are prerequisites.

The complete automated demonstration is:

```bash
export BLENDER_PATH="$(scripts/install_blender_ci.sh | tail -n1)"
python scripts/run_milestone2_tests.py
```

This produces the `.blend`, representative preview, frame manifests, MP4,
FFprobe JSON, diagnostics and machine-readable results under `outputs/`.

Storyboard, audio, subtitles, characters, games, ComfyUI and professional
cinematic rendering are not implemented in Milestone 2.
