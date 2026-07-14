# Milestone 2.1 Start State

Validation began on `codex/vibe-blender-launch` from the preserved Milestone 2
source snapshot. The resumed workspace retained the source, lock, Blender archive
and add-on artifact, but its Git object database had been pruned. Therefore the
requested historical objects `35e878a`, `45d856b` and `cfec314` could not be
proved reachable locally and were not falsely reconstructed. The source snapshot
was re-anchored to upstream `43253155440f78ce208f7c4264bb8be6fb784ec7` as
`15fbffb38b75a0d03c07e18e8f4548cbeaa56e4e`. This is a repository-history
limitation, not a runtime test pass.

The existing add-on was 157,452 bytes with SHA-256
`04f58d9fbf6ffd2e944c106441a7a8d6e3c1414ad4971f56e271658d3e67cd62`.
The retained Blender 4.2.15 archive matched its pinned SHA-256, although the
workspace copy of the extracted executable was truncated; a complete copy was
re-extracted into `/tmp` from the verified archive. FFmpeg and FFprobe 6.1.1 were
available. The prior MP4 was absent after workspace maintenance, so its continued
presence could not be confirmed and Milestone 2 real acceptance was rerun.

After restoring files missing from the pruned snapshot from the pinned upstream
tree, the focused Foundation/animation groups passed 57 tests. Real Foundation
acceptance passed 51 checks, Milestone 2 passed 94 checks, and the rebuilt MP4
was independently probed as H.264, 320x180, 6.0 seconds and 144 frames.
