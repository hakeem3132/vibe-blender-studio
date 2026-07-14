# FFmpeg Integration

FFmpeg and FFprobe are discovered external executables; they are not bundled.
Commands are argument arrays and never shell strings. Inputs and outputs must stay
under the project's `outputs` directory. FPS, start frame, timeout and overwrite
policy are validated before launch.

The adapter detects encoders and selects `libx264`, with generic `h264` as the
documented fallback. It emits H.264 MP4 with `yuv420p` and fast-start metadata.
Cancellation sends terminate, waits up to five seconds and then kills the child.
Timeout follows the same bounded shutdown path. Stderr and exit status become
structured errors.

FFprobe validates a non-empty video stream, H.264 codec, dimensions, frame rate,
duration and frame count where available, and stores machine-readable JSON. The
tested runtime used FFmpeg/FFprobe 6.1.1 and produced 144 frames at 320x180,
24 fps, 6.0 seconds.
