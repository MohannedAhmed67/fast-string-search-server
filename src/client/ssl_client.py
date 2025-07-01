"""SSL-enabled version of the client."""

import asyncio
import ssl
import sys
import time
from pathlib import Path
from typing import Optional, Union


class SslClient:
    """Asynchronous SSL Client for connecting to a secure TCP server."""

    def __init__(self, ip: str, port: int, cafile_path: Path):
        """Initialize a new asynchronous SSL client instance.

        Args:
            ip (str): The IP address of the server to connect to.
            port (int): The port number of the server to connect to.
            cafile_path (Path): The file path to the CA certificate.

        """
        self.ip = ip
        self.port = port
        self.cafile_path = cafile_path
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

        # Create and configure the SSL context for the client
        self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED

        try:
            self.ssl_context.load_verify_locations(
                cafile=str(self.cafile_path),
            )
        except FileNotFoundError:
            print(
                "Error: CA certificate file not found at "
                f"{self.cafile_path}. SSL verification might fail.",
            )
            # Depending on strictness, you might raise
            # here or proceed with a warning
            # For this example, we'll let it proceed but log the error.
        except Exception as e:
            print(
                f"Error loading CA certificate from {self.cafile_path}: {e}",
                file=sys.stderr,
            )
            # Similar to above, decide on error handling strategy

    async def connect(self) -> None:
        """Establishes the asynchronous SSL connection to the server.

        This method must be called and awaited before sending any messages.

        Raises:
            ConnectionRefusedError: If the server
            actively refuses the connection.
            ssl.SSLError: If there's an SSL/TLS handshake
            or certificate verification error.
            Exception: For other connection-related errors.

        """
        try:
            # Establish an asynchronous connection with SSL context
            # server_hostname is crucial for certificate validation
            # if check_hostname is True
            self.reader, self.writer = await asyncio.open_connection(
                self.ip,
                self.port,
                ssl=self.ssl_context,
                server_hostname=self.ip,
            )
            peername = self.writer.get_extra_info("peername")
            print(
                f"Connected securely to server at {peername[0]}:{peername[1]}",
            )
        except ConnectionRefusedError:
            print(
                "Connection refused by the server at "
                f"{self.ip}:{self.port}. Is the server running?",
            )
            raise

        except ssl.SSLError as e:
            print(
                f"SSL/TLS error during connection to "
                f"{self.ip}:{self.port}: {e}",
            )
            raise

        except Exception as e:
            print(
                f"Unexpected error connecting to server at "
                f"{self.ip}:{self.port}: {e}",
            )
            raise

    async def send_message(self, query_string: str) -> Union[float, None]:
        """Communicates with the server by sending the
        query string and receiving the response.

        Args:
            query_string (str): The string that will
            be sent by the client to the server.

        Returns:
            float: The roundtrip time in milliseconds.
            None: If there is any error, or if the client is not connected.

        """
        if self.writer is None or self.reader is None:
            print("Client not connected. Call .connect() first.")
            return None

        try:
            start = time.perf_counter()

            # Send the query string to the server
            self.writer.write(query_string.encode("utf-8"))
            await self.writer.drain()  # Ensure data is sent

            # Receive the response from the server
            data = await self.reader.read(1024)  # Read up to 1024 bytes
            if not data:
                print(
                    "Server closed the connection "
                    "unexpectedly or sent no data. "
                    f"Query string: {query_string}",
                )
                return None

            response = data.decode("utf-8")

            end = time.perf_counter()
            elapsed_time = (end - start) * 1000

            print(f"Time: {elapsed_time:.2f} ms")
            print("Response from server:", response.strip())

            return elapsed_time

        except (ConnectionResetError, BrokenPipeError) as e:
            print("Server closed the connection unexpectedly or sent no data.")
            raise e

        except OSError as e:
            print(f"OS Error during send: {e}")
            raise e
        except Exception as e:
            print(f"An unexpected error occurred during send: {e}")
            raise e

    async def close(self) -> None:
        """Closes the asynchronous connection to the server.

        This method must be called and awaited after sending a message.
        """
        print("Closing connection...")
        if self.writer and not self.writer.is_closing():
            try:
                self.writer.close()
                await self.writer.wait_closed()
                print("Connection closed.")
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                print(f"Error during close cleanup: {e}")
                raise
            finally:
                self.reader = None
                self.writer = None
        elif self.writer and self.writer.is_closing():
            try:
                await self.writer.wait_closed()
                print("Connection already closing, waited for it.")
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                print(f"Error during close cleanup (already closing): {e}")
                raise
        else:
            print("No active connection to close.")
        self.reader = None
        self.writer = None  # Ensure state is reset
