# Render Pipeline

Animation output remains image-sequence first: validate a typed `RenderJob`,
render deterministic PNG frames, validate dimensions/numbers, encode with
FFmpeg, and independently validate the MP4 with FFprobe.

Preview frames may use the synchronous main-thread renderer. Full animation
renders use `BackgroundRenderRunner` by default. It saves the current project,
writes a bounded job manifest, and launches the same Blender executable as a
child process using an argument array (never a shell command). A Blender-side
worker revalidates the manifest and output path, renders only approved frames,
and writes a structured result. The parent modal operator polls completed frames,
so the interactive UI remains responsive and displays real progress.

Only one child job can be active. Cancellation first terminates gracefully and
kills only after the grace timeout. Completed PNG frames remain available.
Non-zero exits, stderr, stalls and missing frames produce a failed job. Resume
renders only missing/invalid expected frames. Stale manifests are explicitly
recovered to `FAILED`. Cleanup removes only expected job frames and its own
manifest/result/log files; unrelated artist files are preserved.

Limits remain 240 preview frames, 10,000 final frames, 8192 pixels per dimension,
100 percent scale, 3,600 seconds for FFmpeg and 7,200 seconds for Blender. The
current headless Linux host lacks `libEGL`, so real acceptance used the allowlisted
one-sample CPU Cycles override. This is runtime evidence, not a visual-quality
claim.
