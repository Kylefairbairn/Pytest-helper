from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import CaptureAlreadyRunning, CaptureError, CaptureNotRunning
from .profiles import CaptureProfile, build_capture_filter


@dataclass(frozen=True, slots=True)
class CaptureConfig:
    interface: str
    profile: CaptureProfile = CaptureProfile.ALL
    capture_filter: str | None = None
    rtp_port_range: tuple[int, int] | None = None
    snaplen: int | None = None
    promiscuous: bool = True
    tshark_path: str = "tshark"
    startup_timeout: float = 3.0
    stop_timeout: float = 10.0


@dataclass(frozen=True, slots=True)
class CaptureResult:
    working_file: Path
    packet_count: int | None
    size_bytes: int
    started_at: float
    stopped_at: float


class TsharkCapture:
    """Own one tshark process and its temporary pcapng artifact."""

    def __init__(self, config: CaptureConfig, work_dir: Path | None = None):
        self.config = config
        self._work_dir = work_dir
        self._process: subprocess.Popen[bytes] | None = None
        self._working_file: Path | None = None
        self._stderr_file = None
        self._started_at: float | None = None
        self._result: CaptureResult | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def working_file(self) -> Path | None:
        return self._working_file

    def _command(self, output: Path) -> list[str]:
        cfg = self.config
        executable = shutil.which(cfg.tshark_path)
        if executable is None:
            raise CaptureError(f"tshark executable not found: {cfg.tshark_path}")

        command = [executable, "-i", cfg.interface, "-n", "-q", "-w", str(output)]
        if not cfg.promiscuous:
            command.append("-p")
        if cfg.snaplen is not None:
            if cfg.snaplen < 68:
                raise ValueError("snaplen must be at least 68 bytes")
            command.extend(["-s", str(cfg.snaplen)])

        capture_filter = cfg.capture_filter
        if capture_filter is None:
            capture_filter = build_capture_filter(
                cfg.profile, rtp_port_range=cfg.rtp_port_range
            )
        if capture_filter:
            command.extend(["-f", capture_filter])
        return command

    def start(self) -> Path:
        if self.is_running:
            raise CaptureAlreadyRunning("capture is already running")

        directory = self._work_dir
        if directory is None:
            directory = Path(tempfile.mkdtemp(prefix="test-capture-"))
        directory.mkdir(parents=True, exist_ok=True)
        self._working_file = directory / "capture.pcapng"
        stderr_path = directory / "tshark.stderr.log"
        self._stderr_file = stderr_path.open("wb")

        try:
            self._process = subprocess.Popen(
                self._command(self._working_file),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=self._stderr_file,
                start_new_session=True,
            )
        except Exception:
            self._stderr_file.close()
            self._stderr_file = None
            raise

        self._started_at = time.time()
        deadline = time.monotonic() + self.config.startup_timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                self._close_stderr()
                detail = stderr_path.read_text(errors="replace").strip()
                raise CaptureError(f"tshark exited during startup: {detail}")
            if self._working_file.exists():
                return self._working_file
            time.sleep(0.05)
        self.stop()
        raise CaptureError("tshark did not create its capture file before timeout")

    def stop(self) -> CaptureResult:
        if self._process is None or self._started_at is None or self._working_file is None:
            raise CaptureNotRunning("capture has not been started")
        if self._result is not None:
            return self._result

        process = self._process
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=self.config.stop_timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        self._close_stderr()
        stopped_at = time.time()

        if process.returncode not in (0, 130):
            stderr_path = self._working_file.parent / "tshark.stderr.log"
            detail = stderr_path.read_text(errors="replace").strip()
            raise CaptureError(f"tshark exited with {process.returncode}: {detail}")

        self._result = CaptureResult(
            working_file=self._working_file,
            packet_count=None,
            size_bytes=self._working_file.stat().st_size,
            started_at=self._started_at,
            stopped_at=stopped_at,
        )
        return self._result

    def save_pcap(self, destination: str | Path) -> Path:
        """Atomically copy the completed capture to its permanent artifact path."""
        if self.is_running:
            raise CaptureError("stop the capture before saving it")
        if self._result is None:
            raise CaptureNotRunning("no completed capture is available")

        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        shutil.copyfile(self._result.working_file, temporary)
        os.replace(temporary, target)
        return target

    def __enter__(self) -> "TsharkCapture":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.is_running:
            self.stop()

    def _close_stderr(self) -> None:
        if self._stderr_file is not None:
            self._stderr_file.close()
            self._stderr_file = None

