"""Benchmark different search-file algorithms."""

import asyncio
import gc
import json
import multiprocessing
import socket
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
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
        server_process (asyncio.subprocess.Process): The server process.

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

    async def single_client() -> Optional[float]:
        """Simulate a single client.

        Returns:
            Optional[float]: The elapsed time.

        """
        client = Client(socket.gethostbyname(socket.gethostname()), PORT)
        try:
            await client.connect()
            clients.append(client)
            elapsed = await client.send_message("just_a_test_string")
            return elapsed

        except Exception as e:
            print(f"Error in simulating the Clinet: {e}")

            return None

        finally:
            if client in clients:
                clients.remove(client)

            try:
                await client.close()

            except Exception as e:
                print(f"Error closing client: {e}")

    def run_client_process(
        result_queue: "multiprocessing.Queue[Optional[float]]",
    ) -> None:
        """Run a client process.

        Args:
            result_queue (multiprocessing.Queue): The result queue.

        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(single_client())
            result_queue.put(result)
        finally:
            loop.close()

    try:
        # A dummy request to initialize the server
        await single_client()

        # The list of execution times
        y_values: list[float] = []

        # A dictionary to store some metrics for the current algorithm
        return_dict: dict[int, dict[str, float | int]] = {}

        # Iterate through the different number of clients to be tested
        for number_of_clients in NUMBER_OF_CLIENTS_IN_EACH_BENCHMARK:
            print(f"\nTesting with {number_of_clients} parallel clients...")

            # Create a queue for collecting results
            result_queue: multiprocessing.Queue[Optional[float]] = (
                multiprocessing.Queue()
            )

            # Create and start processes
            processes: list[multiprocessing.Process] = []
            for _ in range(number_of_clients):
                p = multiprocessing.Process(
                    target=run_client_process,
                    args=(result_queue,),
                )
                p.start()
                processes.append(p)

            # Wait for all processes to complete
            for p in processes:
                p.join()

            # Collect results from the queue
            results: list[Optional[float]] = []
            while not result_queue.empty():
                result = result_queue.get()
                results.append(result)

            # Calculate statistics
            valid_results: list[float] = [r for r in results if r is not None]
            if valid_results:
                average: float = sum(valid_results) / len(valid_results)
                success_rate: float = (
                    len(valid_results) / number_of_clients
                ) * 100
                return_dict[number_of_clients] = {
                    "average_execution_time": average,
                    "success_count": len(valid_results),
                }
                print(f"Success rate: {success_rate:.1f}%")
                print(f"Average response time: {average:.2f} ms")
            else:
                average = 0.0
                print("No successful responses in this batch")

            y_values.append(average)

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
        plt.title("Execution Time per Client (Parallel Load)")

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
                / "parallel_load_benchmark_results"
                / "buffer"
                / f"{config_path.name}",
            ],
            check=False,
        )

        plt.savefig(
            Path(__file__).parent.parent
            / "static"
            / "benchmarks"
            / "parallel_load_benchmark_results"
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
            server_process: Optional[asyncio.subprocess.Process] = None

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
        / "parallel_load_benchmark_results"
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
