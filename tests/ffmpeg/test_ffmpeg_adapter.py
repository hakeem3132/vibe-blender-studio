from __future__ import annotations

import shutil
import threading
from pathlib import Path

import pytest
from blender_addon.vibe_studio.ffmpeg_adapter import FFmpegAdapter, FFmpegError
from blender_addon.vibe_studio.media_contracts import RenderSafetyError
from PIL import Image


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="real FFmpeg is unavailable")
def test_real_ffmpeg_encode_and_ffprobe_validation(tmp_path: Path) -> None:
    frames = tmp_path / "outputs" / "frames" / "demo"
    frames.mkdir(parents=True)
    for frame in range(1, 7):
        Image.new("RGB", (64, 32), (frame * 20, 40, 100)).save(frames / f"frame_{frame:06d}.png")
    adapter = FFmpegAdapter()
    command = adapter.build_encode_command(
        project_root=tmp_path,
        frames_directory=Path("frames/demo"),
        output_path=Path("videos/demo.mp4"),
        fps=6,
        overwrite=True,
    )
    assert command[0] == shutil.which("ffmpeg")
    assert all(";" not in argument for argument in command)
    adapter.encode(command, timeout_seconds=30)
    probe = adapter.probe(project_root=tmp_path, video_path=Path("videos/demo.mp4"))
    assert probe["validated"] is True
    assert probe["streams"][0]["codec_name"] == "h264"
    assert (probe["streams"][0]["width"], probe["streams"][0]["height"]) == (64, 32)


def test_ffmpeg_arguments_reject_paths_and_invalid_fps(tmp_path: Path) -> None:
    adapter = FFmpegAdapter(ffmpeg=shutil.which("ffmpeg") or "/missing", ffprobe=shutil.which("ffprobe"))
    (tmp_path / "outputs" / "frames").mkdir(parents=True)
    with pytest.raises(RenderSafetyError):
        adapter.build_encode_command(
            project_root=tmp_path,
            frames_directory=Path("frames"),
            output_path=Path("../escape.mp4"),
            fps=24,
            overwrite=True,
        )
    with pytest.raises(RenderSafetyError, match="FPS"):
        adapter.build_encode_command(
            project_root=tmp_path,
            frames_directory=Path("frames"),
            output_path=Path("videos/test.mp4"),
            fps=1000,
            overwrite=True,
        )


def test_missing_tools_are_actionable() -> None:
    adapter = FFmpegAdapter(ffmpeg="", ffprobe="")
    adapter.ffmpeg = None
    adapter.ffprobe = None
    with pytest.raises(FFmpegError, match="required"):
        adapter.version()


def test_ffmpeg_cancellation_terminates_child(monkeypatch: pytest.MonkeyPatch) -> None:
    class Process:
        returncode = -15

        def __init__(self):
            self.terminated = False

        def poll(self):
            return None if not self.terminated else self.returncode

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            del timeout
            return self.returncode

        def kill(self):
            self.terminated = True

        def communicate(self, timeout=None):
            del timeout
            return "", ""

    process = Process()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: process)
    adapter = FFmpegAdapter(ffmpeg="/approved/ffmpeg", ffprobe="/approved/ffprobe")
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(FFmpegError, match="cancelled"):
        adapter.encode(["/approved/ffmpeg", "-version"], cancellation=cancelled)
    assert process.terminated
