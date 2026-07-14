"""Safe external FFmpeg and FFprobe integration for image sequences."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .media_contracts import MAX_FFMPEG_TIMEOUT_SECONDS, RenderSafetyError, safe_output_path


class FFmpegError(RuntimeError):
    """FFmpeg or FFprobe returned a structured failure."""


@dataclass(frozen=True)
class ProcessResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class FFmpegAdapter:
    def __init__(self, ffmpeg: str | None = None, ffprobe: str | None = None):
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg")
        self.ffprobe = ffprobe or shutil.which("ffprobe")

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg and self.ffprobe)

    def version(self) -> dict[str, str]:
        if not self.available:
            raise FFmpegError("FFmpeg and FFprobe are required for MP4 export")
        return {
            "ffmpeg": self._version_line(str(self.ffmpeg)),
            "ffprobe": self._version_line(str(self.ffprobe)),
        }

    @staticmethod
    def _version_line(executable: str) -> str:
        completed = subprocess.run([executable, "-version"], capture_output=True, text=True, check=False, timeout=10)
        if completed.returncode != 0:
            raise FFmpegError(f"Unable to query {Path(executable).name}: {completed.stderr.strip()}")
        return completed.stdout.splitlines()[0]

    def encoders(self) -> set[str]:
        if not self.ffmpeg:
            return set()
        completed = subprocess.run(
            [self.ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, check=False, timeout=20
        )
        if completed.returncode != 0:
            raise FFmpegError(f"Unable to query FFmpeg encoders: {completed.stderr.strip()}")
        return {
            line.split()[1] for line in completed.stdout.splitlines() if line.startswith(" ") and len(line.split()) > 1
        }

    def select_h264_encoder(self) -> str:
        encoders = self.encoders()
        for candidate in ("libx264", "h264"):
            if candidate in encoders:
                return candidate
        raise FFmpegError("This FFmpeg build has no compatible H.264 encoder (libx264 or h264)")

    def build_encode_command(
        self,
        *,
        project_root: Path,
        frames_directory: Path,
        output_path: Path,
        fps: float,
        overwrite: bool,
        start_number: int = 1,
    ) -> list[str]:
        if not self.ffmpeg:
            raise FFmpegError("FFmpeg is unavailable; install it or configure its executable path")
        frames = safe_output_path(project_root, frames_directory)
        output = safe_output_path(project_root, output_path, allow_existing=overwrite)
        if not frames.is_dir():
            raise FFmpegError("Frame directory does not exist")
        if not 1 <= fps <= 240:
            raise RenderSafetyError("FPS must be between 1 and 240")
        if not 1 <= start_number <= 10000:
            raise RenderSafetyError("Start frame must be between 1 and 10000")
        output.parent.mkdir(parents=True, exist_ok=True)
        return [
            self.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if overwrite else "-n",
            "-framerate",
            f"{fps:g}",
            "-start_number",
            str(start_number),
            "-i",
            str(frames / "frame_%06d.png"),
            "-c:v",
            self.select_h264_encoder(),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]

    def encode(
        self,
        command: list[str],
        *,
        cancellation: threading.Event | None = None,
        timeout_seconds: float = MAX_FFMPEG_TIMEOUT_SECONDS,
    ) -> ProcessResult:
        if not command or command[0] != self.ffmpeg:
            raise FFmpegError("FFmpeg command must use the discovered executable")
        if timeout_seconds <= 0 or timeout_seconds > MAX_FFMPEG_TIMEOUT_SECONDS:
            raise RenderSafetyError("FFmpeg timeout exceeds the configured limit")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            while process.poll() is None:
                if cancellation is not None and cancellation.wait(0.05):
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise FFmpegError("FFmpeg encoding was cancelled")
                try:
                    stdout, stderr = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    timeout_seconds -= 0.1
                    if timeout_seconds <= 0:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        raise FFmpegError("FFmpeg encoding exceeded its timeout")
            else:
                stdout, stderr = process.communicate()
        finally:
            if process.poll() is None:
                process.kill()
        result = ProcessResult(tuple(command), int(process.returncode or 0), stdout, stderr)
        if result.returncode != 0:
            raise FFmpegError(f"FFmpeg failed with exit {result.returncode}: {result.stderr.strip()}")
        return result

    def probe(self, *, project_root: Path, video_path: Path) -> dict[str, Any]:
        if not self.ffprobe:
            raise FFmpegError("FFprobe is unavailable; install it or configure its executable path")
        video = safe_output_path(project_root, video_path)
        if not video.is_file() or video.stat().st_size == 0:
            raise FFmpegError("Encoded video is missing or empty")
        command = [
            self.ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(video),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
        if completed.returncode != 0:
            raise FFmpegError(f"FFprobe failed: {completed.stderr.strip()}")
        try:
            payload = json.loads(completed.stdout)
            stream = payload["streams"][0]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise FFmpegError("FFprobe did not return a valid video stream") from exc
        if stream.get("codec_name") != "h264" or int(stream.get("width", 0)) <= 0 or int(stream.get("height", 0)) <= 0:
            raise FFmpegError("FFprobe validation rejected the encoded stream")
        payload["command"] = command
        payload["validated"] = True
        return payload
