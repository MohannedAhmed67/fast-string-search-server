"""This module provides the entry point for running the server."""

import argparse
import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.server import cache, file_search
from src.server.server import Server
from src.server.ssl_utils import generate_certificate_and_key

WORKDIR = Path("/tmp/")
UMASK = 0o027
CONFIG_PATH = Path("config.txt")
ALGORITHMS = "./algorithms.json"


def get_local_ip() -> Any:
    """Return the local IP address of the server.

    Returns:
        str: The local IP address as a string.

    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def shutdown_handler(sig: int, frame: Any) -> None:
    print("[SERVER] Shutdown signal received.")
    # graceful shutdown logic here
    sys.exit(0)


# --- Main entry point for the server ---
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
        "--mode",
        default="normal",
        choices=["normal", "daemon"],
        help="Run mode: 'normal' or 'daemon' (default: normal)",
    )
    parser.add_argument(
        "--config_path",
        type=str,
        default=str(Path(__file__).parent / "config.txt"),
        help="Optional path to the config file.",
        required=False,  # This makes it optional
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
        help="Buffer type to use for file searching ('fastset', "
        "'set', or 'trie') respectively, default is 4 (buffer for "
        "shared memory for process pool).",
        required=False,
    )
    args = parser.parse_args()

    # Set the default to be the local ip
    ip = get_local_ip()
    if args.ip == "public":
        ip = "0.0.0.0"

    generate_certificate_and_key(WORKDIR)
    # If daemon mode, you can add daemonization logic here
    if args.mode == "daemon":
        # Run the server as a daemon using the current Python executable
        # and environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent / "src")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "server.daemon",
                "--ip",
                str(args.ip),
                "--algorithm",
                str(args.algorithm),
                "--config_path",
                str(args.config_path),
                "--buffer",
                str(args.buffer),
            ],
            check=False,
            env=env,
            cwd=os.getcwd(),
        )

        return

    if args.config_path is not None:
        global CONFIG_PATH
        CONFIG_PATH = Path(args.config_path)

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
    """Handle SIGTERM or SIGINT signals to perform a
    graceful shutdown of the application.

    Args:
        signum (int): The signal number received.
        frame (FrameType): The current stack frame (unused).

    Exits:
        Exits the process with status code 0.

    """
    # Handle SIGTERM/SIGINT for graceful shutdown
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
