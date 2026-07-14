# Manual Blender UI Acceptance

Use Blender 4.2.15 LTS in a normal graphical session. Install the packaged ZIP,
enable the add-on, open the 3D View sidebar with `N`, and record tester, OS,
Blender version, date and failures. Automated headless results are not visual
passes.

- [ ] `Vibe Studio` is visible and Connection, Project, Prompt, Pending Change,
  Create, Materials, Lighting, Camera, Animate, Render, History and Diagnostics
  are readable at normal UI scale.
- [ ] Simple mode is prompt-first; Creator exposes presets/frame/output controls;
  Professional exposes IDs and diagnostics. Switching mode changes no scene data.
- [ ] Connect/Disconnect/Reconnect/Health update without an infinite spinner.
- [ ] Failure messages are actionable; diagnostics export is redacted.
- [ ] Prompt editing, scope, Preview, Apply, Reject, Undo, Redo and Stop work.
- [ ] Pending Change and History update after each transaction state change.
- [ ] Material preset selection and Create and assign work only for a mesh.
- [ ] Three-point studio and Hero camera buttons disable without a selection.
- [ ] Frame start/end, FPS, speed and 360° animation controls are usable.
- [ ] Preview animation disables without camera/saved project and displays its
  output on success.
- [ ] Render quality, frame range, step and paths are understandable in Creator
  mode; progress/running/success/error states are visible.
- [ ] MP4 render disables with an exact explanation when the project is unsaved,
  camera is missing, or FFmpeg/FFprobe is unavailable.
- [ ] Start a 144+ frame render and continue orbiting the viewport, switching
  panels and editing a text field; verify the UI remains responsive while the
  child Blender process renders.
- [ ] Progress increases as frames appear. Cancel once, verify a clear
  cancelling/cancelled state, partial frames remain, and a resume recovers only
  missing frames.
- [ ] At 100%, output navigation resolves to the verified MP4 and errors expose
  stderr details without revealing local secrets.
- [ ] At 100%, 125%, 150% and 200% UI scale, and at 96/144/192 DPI where the OS
  permits, check panel spacing, label clipping, button overlap and scroll access.
- [ ] Environment Doctor identifies Blender, FFmpeg, FFprobe and output state.
- [ ] No missing icon, layout overflow, dead enabled button or false success is
  observed.

Interactive visual validation remains required; it was not performed in the
headless implementation environment.
