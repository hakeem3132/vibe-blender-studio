# Blender Compatibility

- Primary and only real-tested runtime: Blender 4.2.15 LTS.
- Distribution: official Blender Linux x64 archive, provisioned by the repository
  installer with its pinned SHA-256.
- Embedded Python: 3.11.7.
- Product render identifier: `BLENDER_EEVEE_NEXT`.
- CPU Cycles is an allowlisted fallback.
- Minimum supported Blender: 4.2.15 until another version passes the real suite.
- Other Blender 4.x releases and operating systems are currently untested.

The portable runtime lives in an ignored cache/tool directory, needs no
administrator rights and is never packaged or committed. On managed scratch
workspaces the installer uses `/tmp/vibe-blender-4.2.15`; normal CI can use its
repository cache. The current Linux host has no `libEGL`, so Eevee background
rendering is unavailable and real render acceptance uses CPU Cycles.
