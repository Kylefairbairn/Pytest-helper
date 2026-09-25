"""Run a command on a development board using the system SSH client."""

import argparse
from dataclasses import dataclass
import shlex
import subprocess
import sys


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int


def execute_ssh(
    host: str,
    username: str,
    command: str,
    *,
    port: int = 22,
    key_file: str | None = None,
    timeout: float = 30,
) -> CommandResult:
    """Execute a trusted command remotely; return output and the remote exit code.

    The remote shell interprets `command`, so do not build it from untrusted input.
    SSH uses normal local configuration and known_hosts verification.
    """
    if not host or not username or not command:
        raise ValueError("host, username, and command are required")

    ssh_args = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-p", str(port),
    ]
    if key_file:
        ssh_args.extend(["-i", key_file])
    ssh_args.extend(["--", f"{username}@{host}", command])

    completed = subprocess.run(
        ssh_args, capture_output=True, text=True, timeout=timeout, check=False
    )
    return CommandResult(completed.stdout, completed.stderr, completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a command on a dev board via SSH")
    parser.add_argument("host", help="Board IP address or hostname")
    parser.add_argument("username", help="SSH username")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Remote command")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--key-file")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()

    if not args.command:
        parser.error("a remote command is required")
    command = shlex.join(args.command)
    try:
        result = execute_ssh(
            args.host, args.username, command,
            port=args.port, key_file=args.key_file, timeout=args.timeout,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"SSH execution failed: {exc}\n")

    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
