# Third-Party Notices

Vibe Blender Studio is a modified product built on **blender-ai-mcp v3.3.0**,
upstream commit `43253155440f78ce208f7c4264bb8be6fb784ec7`, authored by Patryk
Ciechański and distributed under the Apache License 2.0.

The packaged Blender add-on contains project-owned Python source and the
Apache-2.0 license and NOTICE files. It does not bundle Python wheels, model
weights, media assets, or provider SDKs. Runtime dependency licenses remain
the responsibility of the backend environment and are recorded by the
repository dependency lock/audit process.

Blender and FFmpeg/FFprobe are optional external runtimes discovered on the
user's machine or provisioned by explicit CI scripts. Their binaries are not
included in the add-on ZIP. Generated demonstration media uses only Blender
primitives and original Vibe Studio presets; no downloaded asset is packaged.

Modified files retain their SPDX notices where present. New Vibe Studio files
are distributed under the repository's Apache-2.0 license.
