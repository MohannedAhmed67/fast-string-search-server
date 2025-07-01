import asyncio
import concurrent.futures
import socket
import ssl
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server.config import ServerConfig
from src.server.server import MAX_CHUNK_SIZE, Server


# Mocking the load_config_file to return a predictable Config object
@pytest.fixture
def mock_config():
    mock_conf = MagicMock(spec=ServerConfig)
    mock_conf.use_ssl = False
    mock_conf.port = 8888
    mock_conf.linux_path = Path("/mock/data")
    mock_conf.reread_on_query = False
    return mock_conf


@pytest.fixture
def mock_load_config_file(mock_config):
    with patch(
        "src.server.server.load_config_file",
        return_value=mock_config,
    ) as _mock:
        yield _mock


@pytest.fixture
def mock_search_file():
    # A simple mock search function for testing purposes
    mock_func = MagicMock(return_value="mock_search_result")
    return mock_func


@pytest.fixture
def server_instance(mock_load_config_file):
    # Instantiate the server with mocked dependencies
    server = Server("127.0.0.1", Path("/mock/config.json"), 0)
    return server


@pytest.mark.asyncio
async def test_server_init(server_instance):
    """Test server initialization."""
    assert server_instance.ip == "127.0.0.1"
    assert server_instance.configuration_settings is not None
    assert server_instance.process_executor is None
    assert server_instance.is_running is True
    assert server_instance.ssl_context is None
    assert server_instance.server_instance is None
    assert server_instance.log_details is False


@pytest.mark.asyncio
async def test_setup_ssl_context_enabled(server_instance):
    """Test SSL context setup when SSL is enabled."""
    server_instance.configuration_settings.use_ssl = True
    mock_gen_cert = MagicMock()
    mock_context = MagicMock(spec=ssl.SSLContext)
    mock_context.load_cert_chain = MagicMock()

    with (
        patch("src.server.server.generate_certificate_and_key", mock_gen_cert),
        patch("ssl.SSLContext", return_value=mock_context) as MockSSLContext,
        patch("builtins.print") as mock_print,
    ):
        cert_path = Path("cert.pem")
        key_path = Path("key.pem")
        gen_path = Path("/tmp/certs")
        await server_instance._setup_ssl_context(cert_path, key_path, gen_path)

        mock_gen_cert.assert_called_once_with(gen_path, "cert.pem", "key.pem")
        MockSSLContext.assert_called_once_with(ssl.PROTOCOL_TLS_SERVER)
        mock_context.load_cert_chain.assert_called_once_with(
            certfile=str(gen_path / cert_path),
            keyfile=str(gen_path / key_path),
        )
        assert server_instance.ssl_context == mock_context
        mock_print.assert_any_call(
            f"[SERVER] SSL context loaded from {cert_path} and {key_path}",
        )


@pytest.mark.asyncio
async def test_setup_ssl_context_disabled(server_instance):
    """Test SSL context setup when SSL is disabled."""
    server_instance.configuration_settings.use_ssl = False
    with patch("builtins.print") as mock_print:
        await server_instance._setup_ssl_context(
            Path("cert.pem"),
            Path("key.pem"),
            Path("/tmp/certs"),
        )
        assert server_instance.ssl_context is None
        mock_print.assert_any_call(
            "[SERVER] SSL is disabled by configuration.",
        )


@pytest.mark.asyncio
async def test_handle_client_disconnects_on_no_data(
    server_instance,
    mock_search_file,
):
    """Test client disconnection when no data is received."""
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_reader.read.side_effect = [
        b"",
        b"",
    ]  # First read returns empty, then another to exit loop
    mock_writer = AsyncMock(spec=asyncio.StreamWriter)
    mock_writer.get_extra_info.return_value = ("127.0.0.1", 12345)

    with patch("builtins.print") as mock_print:
        await server_instance._handle_client(
            mock_reader,
            mock_writer,
            mock_search_file,
        )

        mock_reader.read.assert_called_once_with(MAX_CHUNK_SIZE)
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_awaited_once()
        mock_print.assert_any_call(
            "[SERVER] Client 127.0.0.1:12345 disconnected.",
        )


@pytest.mark.asyncio
async def test_handle_client_reread_on_query_true(
    server_instance,
    mock_search_file,
):
    """Test client handling with reread_on_query set to True."""
    server_instance.configuration_settings.reread_on_query = True
    server_instance.configuration_settings.linux_path = Path("/mock/data")

    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_reader.read.side_effect = [
        b"test_query\n",
        b"",
    ]  # Query then disconnect
    mock_writer = AsyncMock(spec=asyncio.StreamWriter)
    mock_writer.get_extra_info.return_value = ("127.0.0.1", 12345)

    mock_executor = MagicMock(spec=concurrent.futures.ProcessPoolExecutor)
    mock_loop = AsyncMock(spec=asyncio.BaseEventLoop)

    # Mock for synchronous search function
    mock_perform_file_search_sync = MagicMock(
        return_value="SEARCH RESULT: found",
    )

    # Simulate run_in_executor behavior
    async def run_in_executor_side_effect(executor, func, *args):
        # Immediately return result (simulates executor behavior)
        return func(*args)

    mock_loop.run_in_executor.side_effect = run_in_executor_side_effect
    server_instance.process_executor = mock_executor

    with (
        patch("asyncio.get_running_loop", return_value=mock_loop),
        patch(
            "src.server.server.perform_file_search_sync",
            mock_perform_file_search_sync,
        ),
        patch("builtins.print") as mock_print,
        patch(
            "time.perf_counter",
            side_effect=[0, 1],
        ),  # Start at 0, end at 1 (1s elapsed)
    ):
        await server_instance._handle_client(
            mock_reader,
            mock_writer,
            mock_search_file,
        )

        # Verify read called with correct chunk size
        mock_reader.read.assert_called_once_with(MAX_CHUNK_SIZE)

        # FIX: Use assert_called_once_with instead of assert_awaited_once_with
        mock_loop.run_in_executor.assert_called_once_with(
            mock_executor,
            mock_perform_file_search_sync,
            mock_search_file,
            server_instance.configuration_settings.linux_path,
            "test_query",
        )

        # Verify synchronous search called correctly
        mock_perform_file_search_sync.assert_called_once_with(
            mock_search_file,
            server_instance.configuration_settings.linux_path,
            "test_query",
        )

        # Verify response writing
        mock_writer.write.assert_called_once_with(b"SEARCH RESULT: found\n")
        mock_writer.drain.assert_awaited_once()
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_awaited_once()

        # Verify logging
        mock_print.assert_any_call(
            "[SERVER] Handled 127.0.0.1:12345: 'test_query' "
            "-> 'SEARCH RESULT: found...' in 1000.00 ms",
        )


@pytest.mark.asyncio
async def test_handle_client_reread_on_query_false(
    server_instance,
    mock_search_file,
):
    """Test client handling with
    reread_on_query set to False (buffer check).
    """
    server_instance.configuration_settings.reread_on_query = False

    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_reader.read.side_effect = [b"another_query\n", b""]
    mock_writer = AsyncMock(spec=asyncio.StreamWriter)
    mock_writer.get_extra_info.return_value = ("127.0.0.2", 54321)

    mock_executor = MagicMock(spec=concurrent.futures.ProcessPoolExecutor)
    mock_loop = AsyncMock(spec=asyncio.BaseEventLoop)

    # Create a future that resolves to True
    future = asyncio.Future()
    future.set_result(True)

    # Set up side effect to actually call the function
    async def run_in_executor_side_effect(executor, func, *args):
        return func(*args)

    mock_loop.run_in_executor.side_effect = run_in_executor_side_effect

    server_instance.process_executor = mock_executor

    with (
        patch("asyncio.get_running_loop", return_value=mock_loop),
        patch("src.server.server.check_buffer_sync") as mock_check_buffer_sync,
        patch("builtins.print") as mock_print,
        patch("time.perf_counter", side_effect=[0, 1]),
    ):
        mock_check_buffer_sync.return_value = True

        await server_instance._handle_client(
            mock_reader,
            mock_writer,
            mock_search_file,
        )

        mock_reader.read.assert_called_once_with(MAX_CHUNK_SIZE)

        # If run_in_executor is not called due
        # to the logic, assert it was not called
        mock_loop.run_in_executor.assert_not_called()

        # Verify the synchronous function was not called
        mock_check_buffer_sync.assert_not_called()

        # Verify response
        mock_writer.write.assert_called_once_with(b"STRING NOT FOUND\n")
        mock_writer.drain.assert_awaited_once()
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_awaited_once()
        mock_print.assert_any_call(
            "[SERVER] Handled 127.0.0.2:54321: 'another_query'"
            " -> 'STRING NOT FOUND...' in 1000.00 ms",
        )


@pytest.mark.asyncio
async def test_start_server_initialization_and_graceful_shutdown(
    server_instance,
    mock_search_file,
):
    """Test the full start and graceful shutdown process of the server."""
    # Mock multiprocessing setup
    with (
        patch("multiprocessing.get_start_method", return_value=None),
        patch("multiprocessing.set_start_method") as mock_set_start_method,
        patch(
            "src.server.server.setup_logging_queue",
        ) as mock_setup_logging_queue,
        patch(
            "src.server.server.start_logging_listener",
        ) as mock_start_logging_listener,
        patch(
            "src.server.server.setup_worker_process_logging",
        ) as mock_setup_worker_logging,
        patch(
            "concurrent.futures.ProcessPoolExecutor",
        ) as MockProcessPoolExecutor,
        patch("socket.socket") as MockSocket,
        patch("asyncio.start_server") as mock_asyncio_start_server,
        patch(
            "src.server.server.stop_logging_listener",
        ) as mock_stop_logging_listener,
        patch(
            "src.server.cache.get_search_results_cache",
            return_value=MagicMock(),
        ),
        patch("builtins.print") as mock_print,
    ):
        # Configure mocks
        mock_executor_instance = MockProcessPoolExecutor.return_value
        mock_executor_instance.shutdown = MagicMock()

        # Create a future that resolves when serve_forever is called
        serve_started = asyncio.Event()

        async def serve_forever():
            serve_started.set()
            # Simulate blocking until cancelled
            try:
                while True:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass

        mock_server_asyncio_instance = AsyncMock(spec=asyncio.Server)
        mock_server_asyncio_instance.sockets = [
            MagicMock(getsockname=MagicMock(return_value=("127.0.0.1", 8888))),
        ]
        mock_server_asyncio_instance.serve_forever = serve_forever
        mock_asyncio_start_server.return_value = mock_server_asyncio_instance

        mock_raw_socket = MockSocket.return_value
        mock_raw_socket.setsockopt = MagicMock()
        mock_raw_socket.bind = MagicMock()

        # Run the start method
        generation_path = Path("/tmp/gen")
        cert_path = Path("cert.pem")
        key_path = Path("key.pem")
        log_details = True

        start_task = asyncio.create_task(
            server_instance.start(
                mock_search_file,
                generation_path,
                cert_path,
                key_path,
                log_details,
            ),
        )

        # Wait for serve_forever to be called
        await serve_started.wait()

        # Assert initial setup calls
        mock_setup_logging_queue.assert_called_once()
        mock_start_logging_listener.assert_called_once()
        mock_setup_worker_logging.assert_called_once()
        mock_set_start_method.assert_called_once_with("spawn", force=True)

        # Verify ProcessPoolExecutor was created
        MockProcessPoolExecutor.assert_called_once()

        # Verify socket setup
        mock_raw_socket.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )
        mock_raw_socket.bind.assert_called_once_with(("127.0.0.1", 8888))
        mock_asyncio_start_server.assert_called_once()
        assert server_instance.is_running is True

        # Cancel the task to simulate shutdown
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

        # Assert shutdown calls
        assert server_instance.is_running is False
        mock_executor_instance.shutdown.assert_called_once_with(
            wait=True,
            cancel_futures=True,
        )
        mock_stop_logging_listener.assert_called_once()
        mock_server_asyncio_instance.close.assert_called_once()
        mock_server_asyncio_instance.wait_closed.assert_awaited_once()

        # Just check that the important shutdown messages were printed
        mock_print.assert_any_call("[SERVER] Initiating graceful shutdown...")
        mock_print.assert_any_call("[SERVER] Server shutdown complete.")


@pytest.mark.asyncio
async def test_server_stop_method(server_instance):
    """Test the stop method sets is_running to False."""
    server_instance.is_running = True
    with patch("builtins.print") as mock_print:
        await server_instance.stop()
        assert server_instance.is_running is False
        # Just check that shutdown messages were printed
        mock_print.assert_any_call("[SERVER] Initiating graceful shutdown...")
        mock_print.assert_any_call("[SERVER] Server shutdown complete.")
