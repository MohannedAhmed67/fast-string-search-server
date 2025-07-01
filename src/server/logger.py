"""Structured debug logging (timestamp, IP, etc.)."""

import logging
import logging.handlers
import multiprocessing
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Union, cast

LOG_FILE_PATH = Path(__file__).parent.parent.parent / "logs/server.log"
_LOG_LEVEL = logging.INFO

_log_queue: Union["multiprocessing.Queue[Any]", None] = None
_listener_thread: Union[threading.Thread, None] = None
_listener_stop_event: Union[threading.Event, None] = None


def setup_logging_queue() -> None:
    """Setup the global multiprocessing queue for logging.

    This should be called ONCE in the main process before
    the ProcessPoolExecutor starts.
    """
    global _log_queue
    if _log_queue is None:
        _log_queue = cast(
            "multiprocessing.Queue[Any]",
            multiprocessing.Manager().Queue(-1),
        )


def _listener_thread_target(
    log_queue: "multiprocessing.Queue[Any]",
    stop_event: threading.Event,
) -> None:
    """Target function for the logging listener thread.

    This function continuously pulls log records from the queue and
    writes them to the log file.

    Args:
        log_queue (multiprocessing.Queue): The queue to pull log records from.
        stop_event (threading.Event): The event to stop the thread.

    """
    root_logger = logging.getLogger()
    root_logger.setLevel(_LOG_LEVEL)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "level=%(levelname)s | time=%(asctime)s | process=%(process)d | "
        "thread=%(thread)d | module=%(module)s | funcName=%(funcName)s | "
        "lineno=%(lineno)d | message=%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    print(f"[LOGGER] Listener thread started, writing to {LOG_FILE_PATH}")

    while not stop_event.is_set() or not log_queue.empty():
        try:
            record = log_queue.get(timeout=0.1)
            if record is None:
                break
            root_logger.handle(record)
        except queue.Empty:
            time.sleep(0.05)
        except Exception as e:
            print(
                f"[LOGGER ERROR] Error in logging listener: {e}",
                file=sys.stderr,
            )
    print("[LOGGER] Listener thread stopped.")


def start_logging_listener() -> None:
    """Start the dedicated listener thread for processing log messages from
    the queue.

    This should be called ONCE in the main process after setup_logging_queue().
    """
    global _listener_thread
    global _listener_stop_event
    if _log_queue is None:
        raise RuntimeError(
            "Log queue not initialized. Call setup_logging_queue() first.",
        )
    if _listener_thread is None:
        _listener_stop_event = threading.Event()
        _listener_thread = threading.Thread(
            target=_listener_thread_target,
            args=(_log_queue, _listener_stop_event),
            daemon=True,
        )
        _listener_thread.start()


def stop_logging_listener() -> None:
    """Signal the logging listener thread to stop and wait for it to finish.

    This should be called ONCE in the main process during graceful shutdown.
    """
    global _listener_stop_event, _log_queue
    if _listener_stop_event:
        if _log_queue is not None:
            try:
                _log_queue.put_nowait(None)
            except queue.Full:
                pass  # Queue might be full during shutdown, ignore
        _listener_stop_event.set()

        if _listener_thread and _listener_thread.is_alive():
            _listener_thread.join(timeout=5)
            if _listener_thread.is_alive():
                print(
                    "[LOGGER WARNING] Logging listener thread did not stop "
                    "gracefully.",
                    file=sys.stderr,
                )
        _listener_stop_event = None
        _log_queue = None


def setup_worker_process_logging() -> None:
    """Configure logging for worker processes.

    This function replaces standard handlers with a QueueHandler
    that sends messages to the main queue.
    """
    if _log_queue is None:
        raise RuntimeError(
            "Log queue not initialized for worker. Call "
            "setup_logging_queue() in main process first.",
        )

    root_logger = logging.getLogger()
    root_logger.setLevel(_LOG_LEVEL)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    queue_handler = logging.handlers.QueueHandler(_log_queue)
    root_logger.addHandler(queue_handler)


def log(
    time_stamp: str,
    client_ip: str,
    query: str,
    execution_time_ms: float,
) -> None:
    """Log the details of a query execution using the configured
    logging system.

    Args:
        time_stamp (str): The timestamp of the query execution.
        client_ip (str): The IP address of the client.
        query (str): The query string.
        execution_time_ms (float): The execution time in milliseconds.

    """
    # Use standard logging, the handlers will direct it appropriately
    logging.info(
        "Timestamp: %s, Client IP: %s, Query: '%s', Execution Time: %.2f ms",
        time_stamp,
        client_ip,
        query,
        execution_time_ms,
    )
