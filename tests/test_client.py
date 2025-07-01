"""Handles server initialization and communication."""

import asyncio
from unittest.mock import patch

import pytest
import pytest_asyncio  # For async fixtures and event_loop

from src.client.client import Client

SERVER_IP = "127.0.0.1"
DEFAULT_TEST_PORT = 5050


@pytest_asyncio.fixture
async def free_port():
    """Fixture to get a free TCP port."""
    return DEFAULT_TEST_PORT


@pytest_asyncio.fixture
async def echo_server(free_port):
    """A mock server that echoes back any data it receives."""

    async def handle_echo(reader, writer):
        try:
            while True:
                data = await reader.read(1024)
                if not data:  # Client closed connection
                    break
                writer.write(data)
                await writer.drain()
        except (ConnectionResetError, asyncio.CancelledError, BrokenPipeError):
            # These errors are expected if client disconnects abruptly
            pass
        finally:
            if writer and not writer.is_closing():
                writer.close()
                try:
                    # Wait for close to complete, but
                    # handle errors if already closed by peer
                    await asyncio.wait_for(writer.wait_closed(), timeout=0.1)
                except (
                    ConnectionResetError,
                    BrokenPipeError,
                    asyncio.TimeoutError,
                    OSError,
                ):
                    pass

    server = await asyncio.start_server(handle_echo, SERVER_IP, free_port)
    # Give the server a moment to start accepting connections
    await asyncio.sleep(0.01)
    yield (SERVER_IP, free_port), server  # Yield address and server object

    # Cleanup: close server
    server.close()
    try:
        await asyncio.wait_for(server.wait_closed(), timeout=1.0)
    except asyncio.TimeoutError:
        # Log a warning if server cleanup takes too long
        print(
            f"Warning: Mock echo_server on port {free_port} took too long to "
            "close.",
        )
    except (
        OSError,
        ConnectionResetError,
        BrokenPipeError,
    ):  # server.wait_closed can also raise if sockets are problematic
        pass


@pytest_asyncio.fixture
async def no_response_server(free_port):
    """A mock server that reads data then closes without sending anything."""

    async def handle_no_response(reader, writer):
        try:
            await reader.read(100)  # Consume client's message
        except (ConnectionResetError, asyncio.CancelledError, BrokenPipeError):
            pass
        finally:
            if writer and not writer.is_closing():
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=0.1)
                except (
                    ConnectionResetError,
                    BrokenPipeError,
                    asyncio.TimeoutError,
                    OSError,
                ):
                    pass

    server = await asyncio.start_server(
        handle_no_response,
        SERVER_IP,
        free_port,
    )
    await asyncio.sleep(0.01)
    yield (SERVER_IP, free_port), server

    server.close()
    try:
        await asyncio.wait_for(server.wait_closed(), timeout=1.0)
    except asyncio.TimeoutError:
        print(
            "Warning: Mock no_response_server on port "
            f"{free_port} took too long to close.",
        )
    except (OSError, ConnectionResetError, BrokenPipeError):
        pass


@pytest_asyncio.fixture
async def client_instance(free_port):
    """Fixture to create a Client instance for tests."""
    # Default to a non-existent port;
    # tests requiring a server will override ip/port
    cl = Client(SERVER_IP, free_port)
    yield cl
    # Ensure client is closed if it was connected
    # and not already closing by the test
    if cl.writer and not cl.writer.is_closing():
        try:
            await cl.close()
        except (ConnectionResetError, BrokenPipeError, OSError):
            # If connection was already aggressively closed by server,
            # client.close() might encounter issues
            # This ensures the test doesn't fail during
            # cleanup if server caused abrupt disconnect
            if (
                cl.writer and not cl.writer.is_closing()
            ):  # Try a simpler close if wait_closed failed
                cl.writer.close()


class TestClientConnection:
    async def test_connect_success(self, echo_server, client_instance, capfd):
        (host, port), _server_obj = echo_server
        client_instance.ip = host
        client_instance.port = port

        await client_instance.connect()
        assert client_instance.reader is not None
        assert client_instance.writer is not None

        peername = client_instance.writer.get_extra_info("peername")
        assert peername[0] == host
        assert peername[1] == port

        out, _ = capfd.readouterr()
        assert f"Connected to server at {host}:{port}" in out

        await client_instance.close()

    async def test_connect_refused(
        self,
        free_port,
        client_instance,
        capfd,
    ) -> None:
        # free_port is guaranteed to be unused, so connection should be refused
        client_instance.port = free_port

        with pytest.raises(ConnectionRefusedError):
            await client_instance.connect()

        assert client_instance.reader is None
        assert client_instance.writer is None
        out, _ = capfd.readouterr()
        assert (
            "Connection refused by the server at "
            f"{client_instance.ip}:{free_port}." in out
        )

    @patch("asyncio.open_connection")
    async def test_connect_other_error(
        self,
        mock_open_connection,
        client_instance,
        capfd,
    ) -> None:
        # Test generic Exception during connection
        mock_open_connection.side_effect = OSError(
            "Simulated OS error during connect",
        )
        client_instance.ip = "dummy_ip_other_error"
        client_instance.port = 12345  # Actual port doesn't matter due to mock

        with pytest.raises(OSError, match="Simulated OS error during connect"):
            await client_instance.connect()

        out, _ = capfd.readouterr()
        assert (
            "Error connecting to server at dummy_ip_other_error:12345: "
            "Simulated OS error during connect" in out
        )


class TestClientSendMessage:
    async def test_send_message_success(
        self,
        echo_server,
        client_instance,
        capfd,
    ) -> None:
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port

        await client_instance.connect()
        capfd.readouterr()  # Clear output from connect

        query = "hello server"
        rtt = await client_instance.send_message(query)

        assert isinstance(rtt, float)
        assert rtt >= 0  # Roundtrip time should be non-negative

        out, _ = capfd.readouterr()
        assert f"Response from server: {query}" in out
        assert "ms" in out  # Check for time print format

        await client_instance.close()

    async def test_send_message_not_connected(
        self,
        client_instance,
        capfd,
    ) -> None:
        # Client is instantiated but .connect() is not called
        rtt = await client_instance.send_message(
            "test message to disconnected client",
        )
        assert rtt is None
        out, _ = capfd.readouterr()
        assert "Client not connected. Call .connect() first." in out

    async def test_send_message_server_sends_no_data(
        self,
        no_response_server,
        client_instance,
        capfd,
    ) -> None:
        (host, port), _ = no_response_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

        # Server will read this message then close without sending a response
        rtt = await client_instance.send_message("ping to no_response_server")
        assert rtt is None

        out, _ = capfd.readouterr()
        assert (
            "Server closed the connection "
            "unexpectedly or sent no data." in out
        )
        await client_instance.close()

    async def test_send_message_incomplete_read_mocked(
        self,
        echo_server,
        client_instance,
        capfd,
    ) -> None:
        # This test mocks the reader's read method to
        # directly simulate IncompleteReadError
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

        # Patch the .read() method of the specific StreamReader instance
        async def mock_read_incomplete(*args, **kwargs) -> None:
            raise asyncio.IncompleteReadError(
                partial=b"some data",
                expected=100,
            )  # Changed expected to 100 for realism

        with patch.object(
            client_instance.reader,
            "read",
            side_effect=mock_read_incomplete,
        ) as mocked_read_method:
            with pytest.raises(asyncio.IncompleteReadError):
                await client_instance.send_message("test_incomplete_read_mock")

            out, _ = capfd.readouterr()
            assert "An unexpected error occurred during send:" in out
            mocked_read_method.assert_awaited_once_with(1024)

        await client_instance.close()

    @patch("time.perf_counter")
    async def test_send_message_time_measurement(
        self,
        mock_perf_counter,
        echo_server,
        client_instance,
        capfd,
    ) -> None:
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

        # Simulate time.perf_counter() return values (in seconds)
        mock_perf_counter.side_effect = [100.0, 100.5]

        query = "time_measurement_test"
        rtt = await client_instance.send_message(query)

        expected_rtt_ms = (100.5 - 100.0) * 1000
        assert rtt == pytest.approx(expected_rtt_ms)

        out, _ = capfd.readouterr()
        assert f"Time: {expected_rtt_ms:.2f} ms" in out
        assert f"Response from server: {query}" in out
        await client_instance.close()

    async def test_send_message_writer_drain_fails(
        self,
        echo_server,
        client_instance,
        capfd,
    ) -> None:
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

        # Patch writer.drain to simulate a failure
        # (e.g., connection reset during drain)
        with patch.object(
            client_instance.writer,
            "drain",
            side_effect=ConnectionResetError("Simulated drain failure"),
        ) as mock_drain:
            with pytest.raises(ConnectionResetError):
                await client_instance.send_message("test_drain_failure")

            out, _ = capfd.readouterr()
            # ConnectionResetError during drain is
            # caught by its specific except block
            assert (
                "Server closed the connection "
                "unexpectedly or sent no data." in out
            )
            mock_drain.assert_awaited_once()

        # The connection is now effectively broken. Closing should handle this.
        await client_instance.close()
        out_close, _ = capfd.readouterr()
        assert "Closing connection..." in out_close


class TestClientClose:
    async def test_close_connected_client(
        self,
        echo_server,
        client_instance,
        capfd,
    ) -> None:
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()  # Clear connect output

        await client_instance.close()
        out, _ = capfd.readouterr()
        assert "Closing connection..." in out
        assert "Connection closed." in out
        assert client_instance.writer is None

        # Test behavior of send_message after client.close()
        rtt_after_close = await client_instance.send_message(
            "message_after_close",
        )
        assert rtt_after_close is None
        out_after_close, _ = capfd.readouterr()
        # Since writer is not None, it attempts write,
        # which fails on closed writer
        # This is caught by the generic Exception in send_message
        assert (
            "Client not connected. Call "
            ".connect() first." in out_after_close
        )

    async def test_close_not_connected_client(
        self,
        client_instance,
        capfd,
    ) -> None:
        # Client is instantiated but .connect() was never called
        await client_instance.close()
        out, _ = capfd.readouterr()
        assert "No active connection to close." in out

    async def test_double_close(
        self,
        echo_server,
        client_instance,
        capfd,
    ) -> None:
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()

        await client_instance.close()  # First close
        out1, _ = capfd.readouterr()
        assert "Closing connection..." in out1
        assert "Connection closed." in out1

        await client_instance.close()  # Second close
        out2, _ = capfd.readouterr()
        # StreamWriter.close() is idempotent. wait_closed() on
        # an already closed writer returns immediately.
        # Since self.writer is still set, it will print the messages again.
        assert "Closing connection..." in out2
        assert "No active connection to close." in out2
