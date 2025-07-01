import asyncio
import concurrent.futures
import gc
import multiprocessing
import os
import socket
import ssl
import sys
import time
import weakref
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Union, cast

from src.custom_data_structures.custom_chash.fastset import FastSet
from src.custom_data_structures.Trie.Trie import StringTrie

from . import cache
from .client_handler import (
    check_buffer_sync,
    initialize_worker_process,
    perform_file_search_sync,
)
from .config import load_config_file
from .logger import (
    log,
    setup_logging_queue,
    setup_worker_process_logging,
    start_logging_listener,
    stop_logging_listener,
)
from .ssl_utils import generate_certificate_and_key

BufferType = Union[FastSet, set[Any], StringTrie]

MAX_CHUNK_SIZE = 1024  # Maximum payload


class Server:
    """Hybrid Asyncio + ProcessPoolExecutor TCP server."""

    def __init__(self, ip: str, config_file_path: Path, buffer_option: int):
        self.ip = ip
        self.configuration_settings = load_config_file(config_file_path)
        self.process_executor: Union[
            concurrent.futures.ProcessPoolExecutor,
            None,
        ] = None
        self.is_running = True
        self.ssl_context: Union[ssl.SSLContext, None] = None
        self.server_instance: Union[asyncio.Server, None] = None
        self.log_details: bool = False
        self._active_connections: weakref.WeakSet[asyncio.StreamWriter] = (
            weakref.WeakSet()
        )
        self._buffer_option: int = buffer_option
        self._buffer: Union[BufferType, None] = None
        self._map_buffer_option()

    def _map_buffer_option(self) -> None:
        """Initialize the server's buffer based on the selected buffer option.

        Buffer options:
            0: FastSet (custom C-backed set)
            1: Python built-in set
            2: StringTrie (custom trie structure)
            else: None (no buffer)
        """
        if self._buffer_option == 0:
            self._buffer = FastSet()
            self._buffer.load_file(self.configuration_settings.linux_path)

        elif self._buffer_option == 1:
            self._buffer = set()
            with open(
                self.configuration_settings.linux_path,
                encoding="utf-8",
            ) as file:
                for line in file:
                    self._buffer.add(line)

        elif self._buffer_option == 2:
            self._buffer = StringTrie()
            with open(
                self.configuration_settings.linux_path,
                encoding="utf-8",
            ) as file:
                for line in file:
                    self._buffer.insert(line)

        else:
            self._buffer = None

    async def _setup_ssl_context(
        self,
        cert_path: Path,
        key_path: Path,
        gen_path: Path,
    ) -> None:
        """Setup the SSL context for the server.

        Args:
            cert_path (Path): The path to the certificate file.
            key_path (Path): The path to the key file.
            gen_path (Path): The path to the generation directory.

        """
        if self.configuration_settings.use_ssl:
            try:
                generate_certificate_and_key(
                    gen_path,
                    str(cert_path.name),
                    str(key_path.name),
                )

                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(
                    certfile=str(gen_path / cert_path),
                    keyfile=str(gen_path / key_path),
                )
                self.ssl_context = context
                print(
                    f"[SERVER] SSL context loaded from {cert_path} and "
                    f"{key_path}",
                )
            except Exception as e:
                print(
                    "[SERVER ERROR] Failed to load SSL cert/key: "
                    f"{e}. Running without SSL.",
                    file=sys.stderr,
                )
                self.ssl_context = None
        else:
            self.ssl_context = None
            print("[SERVER] SSL is disabled by configuration.")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        search_file: Callable[[Path, str], bool],
    ) -> None:
        """Handle individual client connections using asyncio.

        This function handles individual client connections using asyncio.
        It offloads CPU-bound tasks (search operations) to the
        ProcessPoolExecutor.

        Args:
            reader (asyncio.StreamReader): The reader for the client
            connection.
            writer (asyncio.StreamWriter): The writer for the client
            connection.
            search_file (Callable): The search function.

        """
        peername = writer.get_extra_info("peername")
        client_address_str = (
            f"{peername[0]}:{peername[1]}" if peername else "UNKNOWN"
        )
        client_ip = peername[0] if peername else "N/A"
        print(f"[SERVER] Accepted connection from {client_address_str}")

        # Add connection to active connections set
        self._active_connections.add(writer)

        try:
            while self.is_running:
                start_time_total = time.perf_counter()

                # Receive data from client (non-blocking)
                data = await reader.read(MAX_CHUNK_SIZE)
                if not data:
                    print(
                        f"[SERVER] Client {client_address_str} disconnected.",
                    )
                    break  # Client disconnected

                # Decode, strip whitespace, and remove null characters
                # from the received data
                query_string = data.decode("utf-8").strip().replace("\x00", "")

                # Enforce a strict maximum message size
                if len(query_string) > MAX_CHUNK_SIZE:
                    response_message_str = (
                        "ERROR: Message exceeds maximum allowed size."
                    )
                    writer.write((response_message_str + "\n").encode("utf-8"))
                    await writer.drain()
                    continue

                # Determine the lookup strategy and dispatch to executor
                response_message_str = ""
                loop = asyncio.get_running_loop()

                if not self.configuration_settings.reread_on_query:
                    # Offload buffer check to the process pool
                    try:
                        if self._buffer is None:
                            found = await loop.run_in_executor(
                                self.process_executor,
                                check_buffer_sync,
                                query_string,
                            )

                            response_message_str = (
                                "STRING EXISTS"
                                if found
                                else "STRING NOT FOUND"
                            )

                        elif self._buffer_option == 0 and isinstance(
                            self._buffer,
                            FastSet,
                        ):
                            found = self._buffer.exists(query_string)

                            response_message_str = (
                                "STRING EXISTS"
                                if found
                                else "STRING NOT FOUND"
                            )

                        elif self._buffer_option == 1 and isinstance(
                            self._buffer,
                            set,
                        ):
                            found = query_string in self._buffer

                            response_message_str = (
                                "STRING EXISTS"
                                if found
                                else "STRING NOT FOUND"
                            )

                        elif self._buffer_option == 2 and isinstance(
                            self._buffer,
                            StringTrie,
                        ):
                            found = self._buffer.search(query_string)

                            response_message_str = (
                                "STRING EXISTS"
                                if found
                                else "STRING NOT FOUND"
                            )

                        else:
                            response_message_str = (
                                "ERROR: Invalid buffer option"
                            )

                    except Exception as e:
                        response_message_str = (
                            f"ERROR: Buffer check failed: {e}"
                        )
                        log(
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            client_ip,
                            query_string,
                            -1.0,
                        )

                else:
                    # Offload file search to the process pool
                    try:
                        response_message_str = await loop.run_in_executor(
                            self.process_executor,
                            perform_file_search_sync,
                            search_file,
                            self.configuration_settings.linux_path,
                            query_string,
                        )
                    except Exception as e:
                        response_message_str = (
                            f"ERROR: File search failed: {e}"
                        )
                        log(
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            client_ip,
                            query_string,
                            -1.0,
                        )

                # Send response back to client (non-blocking)
                response_bytes = (response_message_str + "\n").encode("utf-8")
                writer.write(response_bytes)
                await writer.drain()  # Ensure the data is actually sent

                end_time_total = time.perf_counter()
                elapsed_ms = (end_time_total - start_time_total) * 1000
                time_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if self.log_details:
                    log(time_stamp, client_ip, query_string, elapsed_ms)

                print(
                    "[SERVER] Handled "
                    f"{client_address_str}: '{query_string}' -> "
                    f"'{response_message_str[:50]}...' in "
                    f"{elapsed_ms:.2f} ms",
                )

        except ConnectionResetError:
            print(
                f"[SERVER] Client {client_address_str} forcefully "
                "disconnected.",
            )
        except asyncio.IncompleteReadError:
            print(
                f"[SERVER] Client {client_address_str} connection closed "
                "unexpectedly.",
            )
        except Exception as e:
            print(
                f"[SERVER ERROR] Error handling client "
                f"{client_address_str}: {e}",
                file=sys.stderr,
            )
        finally:
            # Remove from active connections
            self._active_connections.discard(writer)

            # Close the connection
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                print(
                    f"[SERVER] Error closing connection to "
                    f"{client_address_str}: {e}",
                )

            print(f"[SERVER] Connection with {client_address_str} closed.")

    async def start(
        self,
        search_file: Callable[[Path, str], bool],
        generation_path: Path,
        certfile_path: Path,
        key_file_path: Path,
        log_details: bool,
    ) -> None:
        """Start the hybrid TCP server.

        Args:
            search_file (Callable): The search function.
            generation_path (Path): The path to the generation directory.
            certfile_path (Path): The path to the certificate file.
            key_file_path (Path): The path to the key file.
            log_details (bool): Whether to log details.

        """
        self.log_details = log_details
        self.data_path = self.configuration_settings.linux_path

        try:
            setup_logging_queue()
            start_logging_listener()
            setup_worker_process_logging()

            # Multiprocessing Start Method
            if multiprocessing.get_start_method(allow_none=True) != "spawn":
                multiprocessing.set_start_method("spawn", force=True)
                print("[SERVER] Set multiprocessing start method to 'spawn'.")

            # Initialize ProcessPoolExecutor
            max_workers_count = cast("int", os.cpu_count()) * 2
            if self._buffer is None:
                self.process_executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=max_workers_count,
                    initializer=initialize_worker_process,
                    initargs=(
                        str(self.data_path),
                        cache.get_search_results_cache(),
                    ),
                )
            else:
                print("[SERVER] Using buffer for process pool.")
                self.process_executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=max_workers_count,
                    initializer=initialize_worker_process,
                    initargs=(str(self.data_path), self._buffer),
                )

            print(
                "[SERVER] ProcessPoolExecutor initialized with "
                f"{max_workers_count} workers.",
            )

            # SSL Context Setup
            if self.configuration_settings.use_ssl:
                await self._setup_ssl_context(
                    certfile_path,
                    key_file_path,
                    generation_path,
                )

            # Create and configure the raw socket
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            server_address = (self.ip, self.configuration_settings.port)
            raw_socket.bind(server_address)
            print(f"[SERVER] Bound raw socket to {server_address}")

            # Start ASYNCIO SERVER
            self.server_instance = await asyncio.start_server(
                lambda reader, writer: self._handle_client(
                    reader,
                    writer,
                    search_file,
                ),
                ssl=self.ssl_context,
                sock=raw_socket,
            )

            addrs = ", ".join(
                str(sock.getsockname())
                for sock in self.server_instance.sockets
            )
            print(
                "[SERVER] Server is serving on "
                f"{addrs} with "
                f"{'SSL' if self.ssl_context else 'no SSL'}.",
            )
            print("[SERVER] Press Ctrl+C to shut down.")

            await self.server_instance.serve_forever()

        except asyncio.CancelledError:
            print("[SERVER] Asyncio server task cancelled.")
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down due to KeyboardInterrupt...")
        except Exception as e:
            print(
                "[SERVER ERROR] An unhandled error occurred in main server "
                f"loop: {e}",
                file=sys.stderr,
            )
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Gracefully stop the server and clean up resources.

        This function gracefully stops the server and cleans up resources.
        It stops accepting new connections, closes all active connections,
        shuts down the ProcessPoolExecutor, stops the logging listener,
        closes the Asyncio server, and clears the SSL context.
        """
        print("[SERVER] Initiating graceful shutdown...")

        # Stop accepting new connections
        self.is_running = False

        # Close all active connections
        for writer in self._active_connections:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                print(
                    f"[SERVER] Error closing connection during shutdown: {e}",
                )
        self._active_connections.clear()

        # Shutdown Process Pool
        if self.process_executor:
            try:
                # First try graceful shutdown
                self.process_executor.shutdown(wait=True, cancel_futures=True)
                print("[SERVER] ProcessPoolExecutor shut down.")
            except Exception as e:
                print(
                    "[SERVER] Error during graceful ProcessPoolExecutor "
                    f"shutdown: {e}",
                )
                try:
                    # Force terminate all processes if graceful shutdown fails
                    for process in self.process_executor._processes.values():
                        try:
                            process.terminate()
                        except Exception:
                            pass
                except Exception as e:
                    print(
                        "[SERVER] Error during forced process termination: "
                        f"{e}",
                    )
            finally:
                # Clean up the executor's resources
                try:
                    # Get the executor's internal queue
                    if hasattr(self.process_executor, "_queue"):
                        self.process_executor._queue.close()
                        self.process_executor._queue.join_thread()

                    # Clean up the executor's internal semaphore
                    if hasattr(self.process_executor, "_shutdown_lock"):
                        self.process_executor._shutdown_lock.release()

                    # Clean up the executor's internal event
                    if hasattr(self.process_executor, "_shutdown_event"):
                        self.process_executor._shutdown_event.set()
                except Exception as e:
                    print(
                        f"[SERVER] Error cleaning up executor resources: {e}",
                    )
                finally:
                    self.process_executor = None

        # Stop Logging Listener
        try:
            stop_logging_listener()

        except Exception as e:
            print(f"[SERVER] Error stopping logging listener: {e}")

        # Close Asyncio Server
        if self.server_instance:
            try:
                self.server_instance.close()
                await self.server_instance.wait_closed()
                print("[SERVER] Asyncio server socket closed.")

            except Exception as e:
                print(f"[SERVER] Error closing asyncio server: {e}")

            finally:
                self.server_instance = None

        # Clear SSL context
        if self.ssl_context:
            self.ssl_context = None

        # Clean up multiprocessing resources
        try:
            # Clean up any remaining multiprocessing resources
            if multiprocessing.get_start_method(allow_none=True) == "spawn":
                # Force cleanup of any remaining semaphores
                # Note: _resources is not a public attribute, so we'll use a
                # safer approach
                # The resource tracker will handle cleanup automatically when
                # processes terminate
                pass
        except Exception as e:
            print(f"[SERVER] Error cleaning up multiprocessing resources: {e}")

        # Force garbage collection
        gc.collect()

        print("[SERVER] Server shutdown complete.")
