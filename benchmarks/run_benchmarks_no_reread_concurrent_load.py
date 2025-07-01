"""Benchmark different search-file algorithms."""

import asyncio
import gc
import json
import socket
import subprocess
import sys
import time
import tracemalloc
from collections.abc import Awaitable
from pathlib import Path
from types import TracebackType
from typing import Optional

import matplotlib.pyplot as plt
import psutil

from src.client.client import Client

ALGORITHMS_CONFIG_FILE = str(Path(__file__).parent.parent / "algorithms.json")
WORKDIR = Path("/tmp/")
ALGORITHMS_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "server" / "file_search"
)
HOST = "0.0.0.0"
PORT = 5050
NUMBER_OF_CLIENTS_IN_EACH_BENCHMARK = [1, 10, 100, 1000]
DATA_SIZES = [10, 100, 200, 250, 500, 1000]
CONFIG_PATHS = [
    Path(__file__).parent / "configs" / "no_reread_on_query" / "config10.txt",
    Path(__file__).parent / "configs" / "no_reread_on_query" / "config100.txt",
    Path(__file__).parent / "configs" / "no_reread_on_query" / "config200.txt",
    Path(__file__).parent / "configs" / "no_reread_on_query" / "config250.txt",
    Path(__file__).parent / "configs" / "no_reread_on_query" / "config500.txt",
    Path(__file__).parent
    / "configs"
    / "no_reread_on_query"
    / "config1000.txt",
]
BUFFER_OPTIONS_AND_NAMES = [
    (0, "FastSet"),
    (1, "Set"),
    (2, "Trie"),
    (3, "MultiProcesses_Cache"),
]


async def initialize_server(
    func_name: str,
    config_path: Path,
    buffer_option: int,
) -> Optional[asyncio.subprocess.Process]:
    """Initialize the server process.

    Args:
        func_name (str): The name of the algorithm to be benchmarked.
        config_path (Path): The path to the configuration file.
        buffer_option (int): The buffer option.

    Returns:
        Optional[asyncio.subprocess.Process]: The server process.

    """
    try:
        server_process = await asyncio.create_subprocess_exec(
            "python",
            "run_server.py",
            "--config_path",
            str(config_path),
            "--algorithm",
            func_name,
            "--buffer",
            str(buffer_option),
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=str(Path(__file__).parent.parent),
        )

        if server_process is None:
            raise ValueError("Server process is None")

        return server_process

    except Exception as e:
        print(f"[Server Error] {e}")
        return None


async def cleanup_server(server_process: asyncio.subprocess.Process) -> None:
    """Clean up the server process.

    Args:
        server_process (subprocess.Popen): The server process.

    """
    if server_process:
        try:
            # Get the process and all its children
            parent = psutil.Process(server_process.pid)
            children = parent.children(recursive=True)

            # Terminate all child processes
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            # Terminate the parent process
            server_process.terminate()

            # Wait for processes to terminate
            gone, alive = psutil.wait_procs([parent] + children, timeout=3)

            # Force kill if still alive
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass

        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            print(f"Error during cleanup: {e}")


async def simulate_client_async(
    config_path: Path,
    buffer_name: str,
) -> dict[int, dict[str, float | int]]:
    """Simulate a client.

    Args:
        function_name (str): The name of the algorithm to be benchmarked.
        config_path (Path): The path to the configuration file.
        buffer_name (str): The name of the buffer.

    Returns:
        dict[int, dict[str, float | int]]: The results of the simulation.

    """
    clients = []

    class SemaphoreManager:
        """A semaphore manager."""

        def __init__(self, value: int) -> None:
            """Initialize the semaphore manager.

            Args:
                value (int): The value of the semaphore.

            """
            self.semaphore: Optional[asyncio.Semaphore] = asyncio.Semaphore(
                value,
            )
            self.value: int = value

        async def __aenter__(self) -> asyncio.Semaphore:
            """Enter the semaphore manager.

            Returns:
                The semaphore.

            """
            if self.semaphore is None:
                raise ValueError("Semaphore is None")

            return self.semaphore

        async def __aexit__(
            self,
            exc_type: Optional[type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType],
        ) -> None:
            """Exit the semaphore manager."""
            if self.semaphore is not None:
                for _ in range(self.value):
                    try:
                        self.semaphore.release()
                    except ValueError:
                        pass  # Already released
            self.semaphore = None

    async def single_client() -> Optional[float]:
        """Simulate a single client.

        Returns:
            Optional[float]: The elapsed time.

        """
        async with SemaphoreManager(1000):
            client = Client(socket.gethostbyname(socket.gethostname()), PORT)
            try:
                await client.connect()
                clients.append(client)
                elapsed = await client.send_message("just_a_test_string")
                return elapsed

            except Exception as e:
                print(f"Error in client: {e}")
                return None

            finally:
                if client in clients:
                    clients.remove(client)

                try:
                    await client.close()

                except Exception as e:
                    print(f"Error closing client: {e}")

    try:
        # A dummy request to initialize the server
        await single_client()

        # The list of execution times
        y_values: list[float] = []

        # A dictionary to store some metrics for the current algorithm
        return_dict: dict[int, dict[str, float | int]] = {}

        # Iterate through the different number of clients to be tested
        for number_of_clients in NUMBER_OF_CLIENTS_IN_EACH_BENCHMARK:
            tasks: list[Awaitable[float | None]] = [
                single_client() for _ in range(number_of_clients)
            ]

            results: list[float | None] = await asyncio.gather(*tasks)

            success_count: int = 0
            sum_of_elapsed_times: float = 0
            length: int = 0
            for elapsed_time in results:
                if elapsed_time is not None:
                    sum_of_elapsed_times += elapsed_time
                    length += 1
                    success_count += 1

            average: float = sum_of_elapsed_times / length if length > 0 else 0
            y_values.append(average)
            return_dict[number_of_clients] = {
                "average_execution_time": average,
                "success_count": success_count,
            }
            print(f"{number_of_clients} clients => {average:.2f} ms")

        # Create and save the plot
        plt.figure(figsize=(8, 5))
        x = range(len(NUMBER_OF_CLIENTS_IN_EACH_BENCHMARK))
        plt.bar(x, y_values, color="steelblue")
        plt.xticks(
            x,
            [str(item) for item in NUMBER_OF_CLIENTS_IN_EACH_BENCHMARK],
        )
        plt.xlabel("Clients")
        plt.ylabel("Execution Time (ms)")
        plt.title("Execution Time per Client")

        for i, v in enumerate(y_values):
            plt.text(i, v + 0.01, f"{v:.2f}", ha="center", va="bottom")

        plt.tight_layout()

        subprocess.run(
            [
                "mkdir",
                "-p",
                Path(__file__).parent.parent
                / "static"
                / "benchmarks"
                / "concurrent_load_benchmark_results"
                / "buffer"
                / f"{config_path.name}",
            ],
            check=False,
        )

        plt.savefig(
            Path(__file__).parent.parent
            / "static"
            / "benchmarks"
            / "concurrent_load_benchmark_results"
            / "buffer"
            / f"{config_path.name}"
            / f"benchmark_buffer_{buffer_name}.png",
        )

        print(f"Benchmarking results for the {buffer_name} buffer:")
        for i, y in enumerate(y_values):
            print(
                f"Number of clients: {NUMBER_OF_CLIENTS_IN_EACH_BENCHMARK[i]} "
                f"and execution time: {y} ms",
            )

        return return_dict

    finally:
        # Cleanup matplotlib resources
        plt.close("all")

        # Cleanup clients
        for client in clients[:]:
            try:
                await client.close()
            except Exception as e:
                print(f"Error closing client in cleanup: {e}")
        clients.clear()

        # Force garbage collection
        gc.collect()


async def main() -> None:
    """Main function."""
    results_json: dict[
        str,
        dict[
            str,
            dict[int | str, dict[str, float | int] | tuple[int, int]],
        ],
    ] = {}
    for config_path in CONFIG_PATHS:
        results: dict[
            str,
            dict[int | str, dict[str, float | int] | tuple[int, int]],
        ] = {}
        for buffer_option, buffer_name in BUFFER_OPTIONS_AND_NAMES:
            server_process = None

            try:
                print("\n--- Benchmark Running ---")
                function_name = "Shell Grep"
                server_process = await initialize_server(
                    function_name,
                    config_path,
                    buffer_option,
                )
                if server_process:
                    time.sleep(2)
                    tracemalloc.start()

                    wrapped_results: dict[
                        int | str,
                        dict[str, float | int] | tuple[int, int],
                    ] = {
                        k: v
                        for k, v in (
                            await simulate_client_async(
                                config_path,
                                buffer_name,
                            )
                        ).items()
                    }

                    results[buffer_name] = wrapped_results

                    results[buffer_name][
                        "memory_usage"
                    ] = tracemalloc.get_traced_memory()

                    tracemalloc.stop()

            except Exception as e:
                print(f"An error occurred during benchmarking: {e}")

            finally:
                if server_process is not None:
                    # Cleanup server process
                    await cleanup_server(server_process)

                server_process = None

                # Force garbage collection
                gc.collect()
                print("--- Benchmarking Finished ---\n")

        key = config_path.name.replace(".txt", "").replace("config", "")
        results_json[key] = results

    results_json_path = (
        Path(__file__).parent.parent
        / "static"
        / "benchmarks"
        / "concurrent_load_benchmark_results"
        / "buffer"
        / "results.json"
    )

    if results_json_path.exists():
        results_json_path.unlink()

    with open(results_json_path, "w") as f:
        json.dump(results_json, f, indent=4)


if __name__ == "__main__":
    try:
        # Create and run the event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())

    finally:

        try:
            # Cancel all running tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Run the loop until all tasks are cancelled
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True),
            )

            # Close the loop
            loop.close()

        except Exception as e:
            print(f"Error during cleanup: {e}")

        finally:
            # Final garbage collection
            gc.collect()
