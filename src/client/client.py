"""Handles server initialization and communication."""

import asyncio
import time
from typing import Optional, Union


class Client:
    """Asynchronous Client for connecting to a TCP server."""

    def __init__(self, ip: str, port: int):
        """Initialize a new asynchronous client instance.

        Args:
            ip (str): The IP address of the server to connect to.
            port (int): The port number of the server to connect to.

        """
        self.ip = ip
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

    async def connect(self) -> None:
        """Establish the asynchronous connection to the server.

        This method must be called and awaited before sending any messages.

        Raises:
            ConnectionRefusedError: If the server actively
            refuses the connection.
            Exception: For other connection-related errors.

        """
        try:
            # Establish an asynchronous connection
            self.reader, self.writer = await asyncio.open_connection(
                self.ip,
                self.port,
            )
            peername = self.writer.get_extra_info("peername")
            print(f"Connected to server at {peername[0]}:{peername[1]}")

        except ConnectionRefusedError:
            print(
                f"Connection refused by the server at {self.ip}:{self.port}.",
            )
            raise

        except Exception as e:
            print(f"Error connecting to server at {self.ip}:{self.port}: {e}")
            raise

    async def send_message(self, query_string: str) -> Union[float, None]:
        """Communicate with the server by sending the
        query string and receiving the response.

        Args:
            query_string (str): The string that will be
            sent by the client to the server.

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
                    "Server closed the connection unexpectedly or sent "
                    "no data.",
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
        """Close the asynchronous connection to the server.

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
