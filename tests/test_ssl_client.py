"""Tests for the SSL-enabled client."""

import asyncio
import ssl
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio

from src.client.ssl_client import SslClient
from tests.ssl_constants import CERTS_DIR, SERVER_CRT, SERVER_KEY

# Add the project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

# --- Configuration for SSL Certificates ---
# (CERTS_DIR, SERVER_CRT, SERVER_KEY are now imported)

SERVER_IP = "127.0.0.1"
DEFAULT_TEST_PORT = 5050

# --- SSL Context Fixtures ---


@pytest_asyncio.fixture
async def server_ssl_context():
    """Fixture to create an SSLContext for the server."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=SERVER_CRT, keyfile=SERVER_KEY)
    yield context


# --- General Fixtures ---


@pytest_asyncio.fixture
async def free_port():
    """Fixture to get a free TCP port."""
    yield DEFAULT_TEST_PORT


@pytest_asyncio.fixture
async def echo_server(
    free_port,
    server_ssl_context,
):  # Removed event_loop_module argument
    """A mock SSL server that echoes back any data it receives."""

    async def handle_echo(reader, writer):
        try:
            while True:
                data = await reader.read(1024)
                if not data:  # Client closed connection
                    break
                writer.write(data)
                await writer.drain()
        except (
            ConnectionResetError,
            asyncio.CancelledError,
            BrokenPipeError,
            ssl.SSLError,
        ):
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
        handle_echo,
        SERVER_IP,
        free_port,
        ssl=server_ssl_context,
    )
    await asyncio.sleep(0.01)
    yield (SERVER_IP, free_port), server

    server.close()
    try:
        await asyncio.wait_for(server.wait_closed(), timeout=1.0)
    except asyncio.TimeoutError:
        print(
            f"Warning: Mock echo_server on port {free_port} took too long to "
            "close.",
        )
    except (OSError, ConnectionResetError, BrokenPipeError):
        pass


@pytest_asyncio.fixture
async def no_response_server(free_port, server_ssl_context):
    """A mock SSL server that reads data
    then closes without sending anything.
    """

    async def handle_no_response(reader, writer):
        try:
            await reader.read(100)  # Consume client's message
        except (
            ConnectionResetError,
            asyncio.CancelledError,
            BrokenPipeError,
            ssl.SSLError,
        ):
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
        ssl=server_ssl_context,
    )
    await asyncio.sleep(0.01)
    yield (SERVER_IP, free_port), server

    server.close()
    try:
        await asyncio.wait_for(server.wait_closed(), timeout=1.0)
    except asyncio.TimeoutError:
        print(
            "Warning: Mock no_response_server on "
            f"port {free_port} took too long to close.",
        )
    except (OSError, ConnectionResetError, BrokenPipeError):
        pass


@pytest_asyncio.fixture
async def reset_connection_server(free_port, server_ssl_context):
    """A mock SSL server that reads data
    then aborts (resets) the connection.
    """
    data_read_event = asyncio.Event()

    async def handle_reset(reader, writer):
        try:
            await reader.read(100)
            data_read_event.set()
            if writer.transport:
                writer.transport.abort()
        except (
            ConnectionResetError,
            asyncio.CancelledError,
            BrokenPipeError,
            ssl.SSLError,
        ):
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
        handle_reset,
        SERVER_IP,
        free_port,
        ssl=server_ssl_context,
    )
    await asyncio.sleep(0.01)
    yield (SERVER_IP, free_port), server, data_read_event

    server.close()
    try:
        await asyncio.wait_for(server.wait_closed(), timeout=1.0)
    except asyncio.TimeoutError:
        print(
            "Warning: Mock reset_connection_server on "
            f"port {free_port} took too long to close.",
        )
    except (OSError, ConnectionResetError, BrokenPipeError):
        pass


@pytest_asyncio.fixture
async def client_instance(free_port):
    """Fixture to create an SslClient instance for tests."""
    cl = SslClient(SERVER_IP, free_port, CERTS_DIR / "cert.pem")
    yield cl
    if cl.writer and not cl.writer.is_closing():
        try:
            await cl.close()
        except (ConnectionResetError, BrokenPipeError, OSError, ssl.SSLError):
            if cl.writer and not cl.writer.is_closing():
                cl.writer.close()


# --- Test Classes ---


class TestSslClientConnection:
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
        assert f"Connected securely to server at {host}:{port}" in out

        await client_instance.close()

    async def test_connect_refused(self, free_port, client_instance, capfd):
        client_instance.port = free_port

        with pytest.raises(ConnectionRefusedError):
            await client_instance.connect()

        assert client_instance.reader is None
        assert client_instance.writer is None
        out, _ = capfd.readouterr()
        assert (
            f"Connection refused by the server "
            f"at {client_instance.ip}:{free_port}. "
            "Is the server running?" in out
        )

    @patch("asyncio.open_connection")
    async def test_connect_other_error(
        self,
        mock_open_connection,
        client_instance,
        capfd,
    ):
        mock_open_connection.side_effect = OSError(
            "Simulated OS error during connect",
        )
        client_instance.ip = "dummy_ip_other_error"
        client_instance.port = 12345

        with pytest.raises(OSError, match="Simulated OS error during connect"):
            await client_instance.connect()

        out, _ = capfd.readouterr()
        assert (
            "Unexpected error connecting to server at "
            "dummy_ip_other_error:12345: Simulated OS error during connect"
            in out
        )

    async def test_connect_ssl_error_invalid_ca(self, echo_server, capfd):
        # Temporarily create a client with a non-existent CA path
        invalid_ca_path = Path("non_existent_ca.crt")
        client_with_invalid_ca = SslClient(
            SERVER_IP,
            echo_server[0][1],
            invalid_ca_path,
        )

        with patch.object(
            client_with_invalid_ca.ssl_context,
            "load_verify_locations",
        ) as mock_load_verify:
            mock_load_verify.side_effect = FileNotFoundError(
                "Simulated CA file not found",
            )
            with pytest.raises(ssl.SSLError):
                await client_with_invalid_ca.connect()

            out, _ = capfd.readouterr()
            assert "Error: CA certificate file not found at" in out
            assert "SSL/TLS error during connection to" in out

    async def test_connect_ssl_error_bad_server_cert(self, free_port, capfd):
        client_instance = SslClient(SERVER_IP, free_port, CERTS_DIR)

        with patch("asyncio.open_connection") as mock_open_connection:
            mock_open_connection.side_effect = ssl.SSLError(
                "CERTIFICATE_VERIFY_FAILED",
            )

            with pytest.raises(
                ssl.SSLError,
                match="CERTIFICATE_VERIFY_FAILED",
            ):
                await client_instance.connect()

            out, _ = capfd.readouterr()
            assert "SSL/TLS error during connection to" in out

        if client_instance.writer and not client_instance.writer.is_closing():
            await client_instance.close()


class TestSslClientSendMessage:
    async def test_send_message_success(
        self,
        echo_server,
        client_instance,
        capfd,
    ):
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port

        await client_instance.connect()
        ret, _ = capfd.readouterr()

        query = "hello server"
        rtt = await client_instance.send_message(query)

        assert isinstance(rtt, float)
        assert rtt >= 0

        out, _ = capfd.readouterr()
        assert f"Response from server: {query}" in out
        assert "ms" in out

        await client_instance.close()

    async def test_send_message_not_connected(self, client_instance, capfd):
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
    ):
        (host, port), _ = no_response_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

        rtt_result = None
        exception_caught = False

        try:
            rtt_result = await client_instance.send_message(
                "ping to no_response_server",
            )
        except (
            ConnectionResetError,
            BrokenPipeError,
            OSError,
            asyncio.IncompleteReadError,
            ssl.SSLError,
        ):
            exception_caught = True

        if exception_caught:
            out, _ = capfd.readouterr()
            assert (
                "Connection reset by the server during message exchange."
                in out
                or "OS Error during send:" in out
                or "An unexpected error occurred during send: "
                "IncompleteReadError" in out
                or "An unexpected error occurred during send: "
                "SSLError" in out
            )
        else:
            assert rtt_result is None
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
    ):
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

        async def mock_read_incomplete(*args, **kwargs):
            raise asyncio.IncompleteReadError(
                partial=b"some data",
                expected=100,
            )

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
    ):
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

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
    ):
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

        with patch.object(
            client_instance.writer,
            "drain",
            side_effect=ConnectionResetError("Simulated drain failure"),
        ) as mock_drain:
            with pytest.raises(ConnectionResetError):
                await client_instance.send_message("test_drain_failure")

            out, _ = capfd.readouterr()
            assert (
                "Server closed the connection "
                "unexpectedly or sent no data." in out
            )
            mock_drain.assert_awaited_once()

        await client_instance.close()
        out_close, _ = capfd.readouterr()
        assert "Closing connection..." in out_close


class TestSslClientClose:
    async def test_close_connected_client(
        self,
        echo_server,
        client_instance,
        capfd,
    ):
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()
        capfd.readouterr()

        await client_instance.close()
        out, _ = capfd.readouterr()
        assert "Closing connection..." in out
        assert "Connection closed." in out
        assert client_instance.writer is None

        rtt_after_close = await client_instance.send_message(
            "message_after_close",
        )
        assert rtt_after_close is None
        out_after_close, _ = capfd.readouterr()
        assert (
            "Client not connected. Call "
            ".connect() first." in out_after_close
        )

    async def test_close_not_connected_client(self, client_instance, capfd):
        await client_instance.close()
        out, _ = capfd.readouterr()
        assert "No active connection to close." in out

    async def test_double_close(self, echo_server, client_instance, capfd):
        (host, port), _ = echo_server
        client_instance.ip = host
        client_instance.port = port
        await client_instance.connect()

        await client_instance.close()
        out1, _ = capfd.readouterr()
        assert "Closing connection..." in out1
        assert "Connection closed." in out1

        await client_instance.close()
        out2, _ = capfd.readouterr()
        assert "Closing connection..." in out2
        assert "No active connection to close." in out2
