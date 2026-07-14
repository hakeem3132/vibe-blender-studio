# Render Recovery

Every job writes `render_job.json` and `frame_validation.json` beside its image
sequence. Validation distinguishes valid, missing, corrupt and inconsistent-size
PNG frames. `resume_missing` rerenders only missing or invalid frame numbers and
revalidates the full expected sequence.

Cancellation is cooperative between frames and retains successfully created
files. FFmpeg cancellation terminates its child process safely. Cleanup never
deletes unrecorded user files; an invalid frame is removed only when its path is
listed in that job's `created_files` manifest.

Unit tests cover partial recovery, corrupt/missing frames, one-active-job policy,
Blender-job cancellation and FFmpeg child termination. The real acceptance
validated a complete sequence; forced cancellation was not injected into the real
Blender render.
