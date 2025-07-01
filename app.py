"""Flask web application for generating and displaying search algorithm
performance reports.

This app processes benchmark results, generates summary statistics,
and renders a detailed HTML report with graphs and tables for comparison.
"""

import asyncio
import json
import os
from datetime import datetime
from multiprocessing import Process
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    current_app,
    render_template,
    request,
    send_file,
    url_for,
)
from pyppeteer import launch
from pyppeteer.errors import TimeoutError

app = Flask(__name__)


def process_results(results: dict[Any, Any]) -> dict[str, dict[str, float]]:
    """Process raw benchmark results to compute average response time,
    success rate, and memory usage for each algorithm.

    Args:
        results (dict): Raw results loaded from JSON files.

    Returns:
        Dict[str, Dict[str, float]]: Processed results
        with averages for each metric per algorithm.

    """
    processed_results: dict[str, dict[str, list[float]]] = {}
    for _data_size, main_results in results.items():
        for algorithm, results in main_results.items():
            ret = processed_results.get(algorithm, {})
            for clients, result in results.items():
                if clients == "memory_usage":
                    new_memory_usage = ret.get("memory_usage", [])
                    new_memory_usage.append(result[1])
                    ret["memory_usage"] = new_memory_usage
                else:
                    new_response_time = ret.get("avg_response_time", [])
                    new_response_time.append(result["average_execution_time"])
                    ret["avg_response_time"] = new_response_time

                    new_success_rate = ret.get("success_rate", [])
                    new_success_rate.append(
                        float(result["success_count"]) / float(clients),
                    )
                    ret["success_rate"] = new_success_rate

            processed_results[algorithm] = ret

    # Convert lists to averages
    final_results: dict[str, dict[str, float]] = {}
    for algorithm, results in processed_results.items():
        final_results[algorithm] = {
            "avg_response_time": sum(results["avg_response_time"])
            / len(results["avg_response_time"]),
            "success_rate": sum(results["success_rate"])
            / len(results["success_rate"]),
            "memory_usage": sum(results["memory_usage"])
            / len(results["memory_usage"])
            / 1024
            / 1024,
        }

    return final_results


def sort_by_avg_response_time(
    dictionary: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Sort algorithms by their average response time (ascending).

    Args:
        dictionary (Dict[str, Dict[str, float]]):
        Processed results per algorithm.

    Returns:
        Dict[str, Dict[str, float]]: Sorted dictionary by avg_response_time.

    """
    return dict(
        sorted(
            dictionary.items(),
            key=lambda item: item[1]["avg_response_time"],
        ),
    )


@app.route("/")
def index() -> str:
    """Render the landing page.

    Returns:
        str: Rendered HTML for the index page.

    """
    return render_template("index.html")


def generate_report(report_type: str) -> str:
    with open(
        Path(__file__).parent
        / "static"
        / "benchmarks"
        / "concurrent_load_benchmark_results"
        / "buffer"
        / "results.json",
        encoding="utf-8",
    ) as f:
        buffer_mode_concurrent: dict[str, dict[str, float]] = process_results(
            dict(json.load(f)),
        )

    with open(
        Path(__file__).parent
        / "static"
        / "benchmarks"
        / "concurrent_load_benchmark_results"
        / "no_buffer"
        / "results.json",
        encoding="utf-8",
    ) as f:
        no_buffer_mode_concurrent: dict[str, dict[str, float]] = (
            process_results(dict(json.load(f)))
        )

    with open(
        Path(__file__).parent
        / "static"
        / "benchmarks"
        / "parallel_load_benchmark_results"
        / "buffer"
        / "results.json",
        encoding="utf-8",
    ) as f:
        buffer_mode_parallel: dict[str, dict[str, float]] = process_results(
            dict(json.load(f)),
        )

    with open(
        Path(__file__).parent
        / "static"
        / "benchmarks"
        / "parallel_load_benchmark_results"
        / "no_buffer"
        / "results.json",
        encoding="utf-8",
    ) as f:
        no_buffer_mode_parallel: dict[str, dict[str, float]] = process_results(
            dict(json.load(f)),
        )

    with open(
        Path(__file__).parent
        / "static"
        / "benchmarks"
        / "concurrent_load_benchmark_results"
        / "buffer"
        / "results.json",
        encoding="utf-8",
    ) as f:
        data_sizes: list[str] = []
        temp_dict: dict[Any, Any] = dict(json.load(f))
        for data_size in temp_dict:
            data_sizes.append(data_size + "K")

    buffer_mode: dict[str, dict[str, float]] = buffer_mode_concurrent
    for algorithm, results in buffer_mode_parallel.items():
        for entry in results.keys():
            buffer_mode[algorithm][entry] += results[entry]
            buffer_mode[algorithm][entry] /= 2

    no_buffer_mode: dict[str, dict[str, float]] = no_buffer_mode_concurrent
    for algorithm, results in no_buffer_mode_parallel.items():
        for entry in results.keys():
            no_buffer_mode[algorithm][entry] += results[entry]
            no_buffer_mode[algorithm][entry] /= 2

    buffer_mode = sort_by_avg_response_time(buffer_mode)
    no_buffer_mode = sort_by_avg_response_time(no_buffer_mode)

    for index, algorithm in enumerate(buffer_mode.keys()):
        buffer_mode[algorithm]["index"] = index + 1

    for index, algorithm in enumerate(no_buffer_mode.keys()):
        no_buffer_mode[algorithm]["index"] = index + 1

    # Initialize the lists for graph paths
    graphs_nobuffer_concurrent: dict[str, list[tuple[str, str]]] = {
        "10K": [],
        "100K": [],
        "200K": [],
        "250K": [],
        "500K": [],
        "1000K": [],
    }
    graphs_buffer_concurrent: dict[str, list[tuple[str, str]]] = {
        "10K": [],
        "100K": [],
        "200K": [],
        "250K": [],
        "500K": [],
        "1000K": [],
    }
    graphs_nobuffer_parallel: dict[str, list[tuple[str, str]]] = {
        "10K": [],
        "100K": [],
        "200K": [],
        "250K": [],
        "500K": [],
        "1000K": [],
    }
    graphs_buffer_parallel: dict[str, list[tuple[str, str]]] = {
        "10K": [],
        "100K": [],
        "200K": [],
        "250K": [],
        "500K": [],
        "1000K": [],
    }

    # Set up the root directory
    root = Path(__file__).parent / "static/benchmarks/"

    # Loop through load types, modes, and config files
    for load in [
        "concurrent_load_benchmark_results",
        "parallel_load_benchmark_results",
    ]:
        for mode in ["buffer", "no_buffer"]:
            for config_file in [
                "config10.txt",
                "config100.txt",
                "config200.txt",
                "config250.txt",
                "config500.txt",
                "config1000.txt",
            ]:
                # Ensure the config_file is a directory
                config_dir = root / load / mode / config_file

                # Only walk if it's a directory
                if config_dir.is_dir():
                    for current_root, _dirs, files in os.walk(config_dir):
                        for file in files:
                            if file.endswith(".png"):
                                # Build the full path for the image file
                                full_path = Path(current_root) / file

                                # Format the key as 10K, 100K, etc.
                                config_key = (
                                    config_file.replace("config", "").replace(
                                        ".txt",
                                        "",
                                    )
                                    + "K"
                                )

                                if load == "concurrent_load_benchmark_results":
                                    if mode == "buffer":
                                        graphs_buffer_concurrent[
                                            config_key
                                        ].append(
                                            (
                                                str(full_path),
                                                file.replace(".png", "")
                                                .replace("benchmark_", "")
                                                .replace("buffer_", "")
                                                .replace("_", " "),
                                            ),
                                        )
                                    else:
                                        graphs_nobuffer_concurrent[
                                            config_key
                                        ].append(
                                            (
                                                str(full_path),
                                                file.replace(".png", "")
                                                .replace("benchmark_", "")
                                                .replace("_", " "),
                                            ),
                                        )
                                elif mode == "buffer":
                                    graphs_buffer_parallel[config_key].append(
                                        (
                                            str(full_path),
                                            file.replace(".png", "")
                                            .replace("benchmark_", "")
                                            .replace("buffer_", "")
                                            .replace("_", " "),
                                        ),
                                    )
                                else:
                                    graphs_nobuffer_parallel[
                                        config_key
                                    ].append(
                                        (
                                            str(full_path),
                                            file.replace(".png", "")
                                            .replace("benchmark_", "")
                                            .replace("_", " "),
                                        ),
                                    )

    for algorithm, results in buffer_mode.items():
        if results["index"] == 1:
            fastest_algorithm_buffer: dict[str, Any] = {
                "name": algorithm,
                "results": results,
            }
            break

    for algorithm, results in no_buffer_mode.items():
        if results["index"] == 1:
            fastest_algorithm_no_buffer: dict[str, Any] = {
                "name": algorithm,
                "results": results,
            }
            break

    # Generate HTML for PDF (using Flask paths)
    html_report: str = render_template(
        report_type,
        report_date=datetime.now().strftime("%B %d, %Y"),
        data_sizes=data_sizes,
        buffer_mode=buffer_mode,
        no_buffer_mode=no_buffer_mode,
        graphs_buffer_concurrent=graphs_buffer_concurrent,
        graphs_nobuffer_concurrent=graphs_nobuffer_concurrent,
        graphs_buffer_parallel=graphs_buffer_parallel,
        graphs_nobuffer_parallel=graphs_nobuffer_parallel,
        fastest_algorithm_buffer=fastest_algorithm_buffer,
        fastest_algorithm_no_buffer=fastest_algorithm_no_buffer,
        pdf=True,
    )

    return html_report


@app.route("/generate-report")
def show_report() -> str:
    """Generate and render the detailed benchmark report.

    Returns:
        str: Rendered HTML for the report page.

    """
    html_report = generate_report("report.html")
    return html_report


@app.route("/generate-report-pdf-utility")
def show_report_pdf_utility() -> str:
    """Generate and render the detailed benchmark report.

    Returns:
        str: Rendered HTML for the report page.

    """
    html_report = generate_report("report_pdf.html")
    return html_report


def generate_pdf_process(report_url: str, output_path: Path) -> None:
    """Generate a PDF from a report URL and save it to a specified path.

    Args:
        report_url (str): The URL of the report to generate.
        output_path (Path): The path to save the generated PDF.

    """

    async def task() -> None:
        """Generate a PDF from a report URL and save it to a specified path.

        Args:
            report_url (str): The URL of the report to generate.
            output_path (Path): The path to save the generated PDF.

        """
        for attempt in range(3):
            try:
                browser = await launch(headless=True, args=["--no-sandbox"])
                page = await browser.newPage()

                print(
                    "[INFO] Attempt {attempt + 1}: Navigating to "
                    f"{report_url}",
                )
                await page.goto(
                    report_url,
                    {"waitUntil": "networkidle2", "timeout": 15000},
                )

                await page.pdf(
                    {
                        "path": str(output_path),
                        "format": "A4",
                        "printBackground": True,
                        "margin": {
                            "top": "20mm",
                            "bottom": "20mm",
                            "left": "15mm",
                            "right": "15mm",
                        },
                    },
                )
                await browser.close()
                print("[INFO] PDF successfully created")
                return
            except TimeoutError as e:
                print(f"[WARN] Attempt {attempt + 1} failed with TimeoutError")
                if attempt == 2:
                    raise e
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[ERROR] Attempt {attempt + 1} failed:", e)
                raise e

    asyncio.run(task())


@app.route("/generate-report-pdf")
def show_report_pdf() -> Any:
    try:
        report_url = request.url_root.strip("/") + url_for(
            "show_report_pdf_utility",
        )
        output_path = Path("docs") / "report_output.pdf"

        proc = Process(
            target=generate_pdf_process,
            args=(report_url, output_path),
        )
        proc.start()
        proc.join()

        if not output_path.exists():
            return "PDF generation failed", 500

        return send_file(output_path, as_attachment=True)
    except Exception:
        current_app.logger.error("PDF generation failed", exc_info=True)
        return "PDF generation failed", 500


if __name__ == "__main__":
    """Run the Flask application."""

    # Create the docs directory if it doesn't exist
    os.makedirs("docs", exist_ok=True)

    app.run(debug=True)
