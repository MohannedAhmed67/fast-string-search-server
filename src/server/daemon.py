"""Production-ready daemon for running server as a Linux service."""

import argparse
import asyncio
import atexit
import json
import signal
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import daemon
from daemon.pidfile import PIDLockFile

from . import cache, file_search
from .logger import stop_logging_listener
from .server import Server

# Path to the PID file for the daemon process
PID_FILE = "/tmp/server_daemon.pid"
# Paths to log files for stdout and stderr
STDOUT_LOG = "/tmp/server_stdout.log"
STDERR_LOG = "/tmp/server_stderr.log"
# Working directory for the daemon process
WORKDIR = Path("/tmp/")
# File creation mask for the daemon process
UMASK = 0o027
# The configuration settings file of the server
CONFIG_PATH = Path(__file__).parent.parent.parent / "config.txt"

ALGORITHMS = str(Path(__file__).parent.parent.parent / "algorithms.json")


def cleanup() -> None:
    """Cleanup function to be called on exit."""
    try:
        stop_logging_listener()
    except Exception as e:
        print(f"Error during cleanup: {e}", file=sys.stderr)


def get_local_ip() -> Any:
    """Get the local IP address of the server.

    Returns:
        str: The local IP address of the server as a string.

    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


async def main() -> None:
    """Run the server."""
    with open(ALGORITHMS, encoding="utf-8") as file:
        algorithms = json.load(file)

    algorithms_names = [
        display_name for display_name, func_name_str in algorithms.items()
    ]

    parser = argparse.ArgumentParser(description="Run the server.")
    parser.add_argument(
        "--ip",
        choices=["local", "public"],
        default="public",
        help="Connect to the server locally or over the internet",
    )
    parser.add_argument(
        "--config_path",
        type=str,
        help="Optional path to the config file.",
        required=False,
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        default="Shell Grep",
        choices=algorithms_names,
        required=False,
    )
    parser.add_argument(
        "--buffer",
        type=int,
        default=1,
        choices=[0, 1, 2, 3],
        help="Buffer type to use for file searching ('fastset', 'set', or "
        "'trie') respectively, default is 4 (buffer for shared memory for "
        "process pool).",
        required=False,
    )
    args = parser.parse_args()

    ip = get_local_ip()
    if args.ip == "public":
        ip = "0.0.0.0"

    global CONFIG_PATH
    if args.config_path is not None:
        CONFIG_PATH = Path(args.config_path)

    # Copy the config file to the working directory of the daemon
    subprocess.run(["cp", CONFIG_PATH, WORKDIR], check=True)

    CONFIG_PATH = WORKDIR / CONFIG_PATH.name

    # Read the original config file and update the linuxpath
    with CONFIG_PATH.open("r", encoding="utf-8") as original_file:
        lines = original_file.readlines()

    # Update the linuxpath line to point to the working directory
    updated_lines = []
    for line in lines:
        if line.strip().startswith("linuxpath="):
            # Extract the filename from the original path and prepend WORKDIR
            original_path = line.split("=./", 1)[1].strip()
            filename = Path(__file__).parent.parent.parent / original_path
            updated_lines.append("linuxpath=" + str(filename) + "\n")
        else:
            updated_lines.append(line)

    # Write the updated content back to the file
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        file.writelines(updated_lines)

    # --- Server Initialization ---
    server_instance = Server(ip, CONFIG_PATH, args.buffer)
    if args.buffer == 3:
        cache.setup_cache_manager()

    func = getattr(file_search, algorithms[args.algorithm])

    if not callable(func):
        print(f"The chosen algorithm {args.algorithm} isn't available.")
        return

    # --- Start the Server ---
    await server_instance.start(
        search_file=func,
        generation_path=WORKDIR,
        certfile_path=Path("cert.pem"),
        key_file_path=Path("key.pem"),
        log_details=True,  # Enable detailed logging
    )

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)


def handle_sigterm(signum: int, frame: Any) -> None:
    """Handle SIGTERM or SIGINT signals to perform a graceful shutdown of
    the application.

    Args:
        signum (int): The signal number received.
        frame (FrameType): The current stack frame (unused).

    """
    # Handle SIGTERM/SIGINT for graceful shutdown
    cleanup()
    sys.exit(0)


if __name__ == "__main__":
    # Register cleanup function
    atexit.register(cleanup)

    # Ensure log files exist (create if not)
    open(STDOUT_LOG, "a").close()
    open(STDERR_LOG, "a").close()

    # Start the daemon context
    with daemon.DaemonContext(
        working_directory=str(WORKDIR),
        umask=UMASK,
        pidfile=PIDLockFile(PID_FILE),
        stdout=open(STDOUT_LOG, "a"),
        stderr=open(STDERR_LOG, "a"),
        detach_process=True,
    ):
        asyncio.run(main())
