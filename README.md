# Search Algorithm Performance Analysis Server

> **A high-performance, asynchronous TCP server for exact string matching with comprehensive benchmarking and reporting capabilities.**

---

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](tests/)
[![Benchmarks](https://img.shields.io/badge/Benchmarks-Available-orange.svg)](benchmarks/)

**Built for Linux** | **SSL Security** | **Async I/O** | **Comprehensive Testing**

---

## 🚀 Overview

This project implements a sophisticated search algorithm performance analysis system featuring:

- **High-performance TCP server** with async I/O and process pool execution
- **Multiple search algorithms** including custom C-backed data structures
- **Comprehensive benchmarking suite** for performance analysis
- **Web-based reporting interface** with interactive graphs and PDF generation
- **SSL/TLS support** for secure communications
- **Daemon mode** for production deployment
- **Extensive test coverage** with 90%+ test coverage

The system is designed to handle large text files (250K+ lines) with unlimited concurrent clients while providing detailed performance metrics and comparisons across different search strategies.

---

## ✨ Key Features

### 🔍 **Search Algorithms**
- **Linear Search** - Traditional sequential file scanning
- **Hash Set** - Python built-in set for O(1) lookups
- **Memory Mapped** - Direct memory access for large files
- **Binary Search** - Optimized for sorted data
- **Shell Grep** - System-level grep integration
- **Trie Search** - Custom prefix tree implementation
- **KMP Algorithm** - Knuth-Morris-Pratt string matching
- **Boyer-Moore** - Advanced string matching algorithm
- **Rabin-Karp** - Hash-based string matching
- **FastSet** - Custom C-backed hash set implementation

### 🏗️ **Architecture**
- **Async I/O** with asyncio for non-blocking operations
- **Process Pool Executor** for CPU-intensive search operations
- **Multiple Buffer Options** (FastSet, Python Set, Trie)
- **Configurable SSL/TLS** with self-signed certificate support
- **Structured Logging** with detailed performance metrics

### 📊 **Reporting & Analytics**
- **Interactive Web Interface** with collapsible sections
- **Performance Graphs** for algorithm comparisons
- **PDF Report Generation** with comprehensive metrics
- **Real-time Statistics** and performance monitoring

---

## 🗂️ Project Structure

```
recruitment/
├── src/                           # Core source code
│   ├── server/                    # Server implementation
│   │   ├── server.py             # Main async TCP server
│   │   ├── config.py             # Configuration management
│   │   ├── file_search.py        # Search algorithm implementations
│   │   ├── client_handler.py     # Client connection handling
│   │   ├── ssl_utils.py          # SSL/TLS utilities
│   │   ├── logger.py             # Structured logging
│   │   ├── cache.py              # Shared memory cache
│   │   └── daemon.py             # Daemon mode implementation
│   ├── client/                   # Client implementations
│   │   ├── client.py             # Async TCP client
│   │   └── ssl_client.py         # SSL-enabled client
│   └── custom_data_structures/   # Custom data structures
│       ├── Trie.py               # String trie implementation
│       └── custom_chash/         # C-backed hash set
│           ├── fastset.c         # C implementation
│           ├── fastset.py        # Python wrapper
│           └── uthash.h          # Hash table library
├── tests/                        # Comprehensive test suite
│   ├── test_server.py           # Server functionality tests
│   ├── test_client.py           # Client functionality tests
│   ├── test_ssl_client.py       # SSL client tests
│   ├── test_config.py           # Configuration tests
│   ├── test_file_search.py      # Search algorithm tests
│   ├── test_ssl_utils.py        # SSL utility tests
│   ├── conftest.py              # Test configuration
│   └── ssl_constants.py         # SSL test constants
├── benchmarks/                   # Performance benchmarking
│   ├── run_benchmarks_concurrent_load.py
│   ├── run_benchmarks_parallel_load.py
│   ├── run_benchmarks_no_reread_concurrent_load.py
│   ├── run_benchmarks_no_reread_parallel_load.py
│   ├── configs/                 # Benchmark configurations
│   └── data/                    # Test datasets
├── templates/                    # Web interface templates
│   ├── index.html               # Landing page
│   └── report.html              # Performance report template
├── static/                      # Static assets
│   └── benchmarks/              # Generated benchmark results
├── docs/                        # Documentation
├── logs/                        # Application logs
├── app.py                       # Flask web application
├── run_server.py                # Server entry point
├── config.txt                   # Server configuration
├── algorithms.json              # Algorithm definitions
├── requirements.txt             # Python dependencies
├── Makefile                     # Build and test automation
├── install.sh                   # Installation script
├── run_daemon.sh                # Daemon startup script
└── stop_daemon.sh               # Daemon shutdown script
```

---

## 🛠️ Installation

### Prerequisites

- **Linux-based OS** (Ubuntu 18.04+, CentOS 7+, etc.)
- **Python 3.8+**
- **GCC compiler** (for C extensions)
- **Git**

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd recruitment
   ```

2. **Run automated installation**
   ```bash
   bash install.sh
   ```

3. **Activate virtual environment**
   ```bash
   source .venv/bin/activate
   ```

### Manual Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
make tests
```

---

## ⚙️ Configuration

### Server Configuration (`config.txt`)

```txt
linuxpath=/path/to/your/data/file.txt
REREAD_ON_QUERY=False
USE_SSL=False
PORT=5050
```

| Setting | Description | Default |
|---------|-------------|---------|
| `linuxpath` | Absolute path to data file | Required |
| `REREAD_ON_QUERY` | Re-read file on each query | `False` |
| `USE_SSL` | Enable SSL/TLS encryption | `False` |
| `PORT` | Server listening port | `5050` |

### Buffer Options

When `REREAD_ON_QUERY=False`, choose the in-memory data structure:

- **`0`** - FastSet (C-backed hash set, recommended)
- **`1`** - Python built-in set
- **`2`** - String Trie
- **`3`** - No buffer (shared memory)

---

## 🚀 Usage

### Starting the Server

#### Manual Mode
```bash
python run_server.py --mode normal --buffer 0 --ip public
```

#### Daemon Mode
```bash
# Start daemon
python run_server.py --mode daemon --buffer 0 --ip public

# Stop daemon
bash stop_daemon.sh
```

### Command Line Options

| Option | Description | Choices | Default |
|--------|-------------|---------|---------|
| `--buffer` | Buffer data structure | `0`, `1`, `2`, `3` | `1` |
| `--ip` | Network interface | `public`, `local` | `public` |
| `--mode` | Server mode | `normal`, `daemon` | `normal` |
| `--config_path` | Config file path | File path | `config.txt` |
| `--algorithm` | Search algorithm | See algorithms.json | `Shell Grep` |

### Web Interface

Start the Flask application to view performance reports:

```bash
python app.py
```

Visit `http://localhost:5000` to access:
- **Landing page** with project overview
- **Performance reports** with interactive graphs
- **PDF generation** for detailed analysis

---

## 🧪 Testing

### Run All Tests
```bash
make tests
```

### Individual Test Suites
```bash
# Server functionality
pytest tests/test_server.py -v

# Client functionality
pytest tests/test_client.py -v

# SSL functionality
pytest tests/test_ssl_client.py -v

# Search algorithms
pytest tests/test_file_search.py -v
```

### Test Coverage
```bash
# Run with coverage
pytest --cov=src tests/ -v

# Generate coverage report
pytest --cov=src --cov-report=html tests/
```

---

## 📊 Benchmarking

Before running benchmarks, ensure you have:

1. **Test data files** in `benchmarks/data/` directory
2. **Benchmark configurations** in `benchmarks/configs/` directory

### Running Benchmarks

#### Step 1: Run Benchmark Scripts

In a separate terminal, run the appropriate benchmark script:

##### Concurrent Load Testing
```bash
# Buffer mode (REREAD_ON_QUERY=False)
python -m benchmarks.run_benchmarks_no_reread_concurrent_load

# No buffer mode (REREAD_ON_QUERY=True)
python -m benchmarks.run_benchmarks_concurrent_load
```

##### Parallel Load Testing
```bash
# Buffer mode
python -m benchmarks.run_benchmarks_no_reread_parallel_load

# No buffer mode
python -m benchmarks.run_benchmarks_parallel_load
```

#### Step 2: Generate Results

Results are automatically saved to:
- `static/benchmarks/concurrent_load_benchmark_results/`
- `static/benchmarks/parallel_load_benchmark_results/`

Each benchmark generates:

- **Response Time** - Average execution time per query
- **Success Rate** - Percentage of successful queries
- **Memory Usage** - Peak memory consumption

### Viewing Results

#### Web Interface
```bash
python app.py
```
Visit `http://localhost:5000/generate-report` to see:
- Interactive performance graphs
- Algorithm comparisons
- Detailed metrics tables

Visit `http://127.0.0.1:5000/generate-report-pdf` to download
a PDF version of the report

#### Direct File Access
- **Graphs**: `static/benchmarks/*/benchmark_*.png`
- **Data**: `static/benchmarks/*/results.json`

### Benchmark Configuration

Benchmark scripts use configurations from:
- **`benchmarks/configs/reread_on_query/`** - For REREAD_ON_QUERY=True
- **`benchmarks/configs/no_reread_on_query/`** - For REREAD_ON_QUERY=False

Each config file specifies:
- Data file path
- Server settings
- Test parameters

---

## 🔧 Development

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type checking
make type-check

# Run all checks
make check
```

### Adding New Algorithms

1. **Implement in `src/server/file_search.py`**
2. **Add to `algorithms.json`**
3. **Write tests in `tests/test_file_search.py`**
4. **Benchmarks** - The benchmark system automatically detects new algorithms from `file_search.py` and imports them. Simply add the function name to `algorithms.json` and implement the function in `file_search.py`.

### Project Structure Guidelines

- **Type hints** required for all functions
- **Docstrings** for all public APIs
- **Error handling** with specific exceptions
- **Logging** for debugging and monitoring
- **Tests** for all new functionality

---

## 🏗️ Architecture

### Server Architecture

```
 ┌─────────────────┐                           ┌─────────────────┐
 │   TCP Client    │                           │    SSL Client   │
 └─────────┬───────┘                           └─────────┬───────┘
           │                                             │
           └─────────────────────────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │    Async TCP Server       │
                    │  (asyncio + ProcessPool)  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   Search Algorithms       │
                    │  (Multiple Strategies)    │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   Data Structures         │
                    │  (FastSet, Set, Trie)     │
                    └───────────────────────────┘
```

### Key Components

- **Async I/O Layer**: Handles multiple concurrent connections
- **Process Pool**: Executes CPU-intensive search operations
- **Buffer Management**: Optimizes memory usage and access patterns
- **SSL/TLS Layer**: Provides secure communication
- **Logging System**: Tracks performance and debugging information

---

## 🔒 Security

### SSL/TLS Support
- **Self-signed certificates** for development
- **Configurable encryption** levels
- **Certificate validation** for production use

### Input Validation
- **Payload size limits** (1024 bytes)
- **Null byte stripping** from inputs
- **Exception handling** for malformed data

### Network Security
- **Configurable network interfaces** (public/local)
- **Port binding** restrictions
- **Connection timeout** handling

---

## 📈 Performance

### Optimizations

- **Async I/O** for non-blocking operations
- **Process pool** for CPU-bound tasks
- **Custom C extensions** for critical paths
- **Memory mapping** for large files
- **Efficient data structures** (FastSet, Trie)

### Benchmarks

The system has been tested with:
- **Data sizes**: 10K to 1M lines
- **Concurrent clients**: 1 to 1000+
- **File formats**: Text, CSV, JSON
- **Search patterns**: Exact match, prefix, suffix

### Performance Metrics

- **Response time**: < 1ms for cached lookups
- **Throughput**: 10,000+ queries/second
- **Memory usage**: Optimized for large datasets
- **Scalability**: Linear scaling with cores

---

## 🤝 Contributing

### Development Setup

1. **Fork the repository**
2. **Create feature branch**
3. **Make changes with tests**
4. **Run quality checks**
5. **Submit pull request**

### Code Standards

- **PEP 8** compliance
- **Type hints** for all functions
- **Docstrings** for public APIs
- **Test coverage** > 90%
- **Error handling** for edge cases

---

## 🙏 Acknowledgments

- **uthash** library for C hash table implementation
- **asyncio** for asynchronous I/O capabilities
- **Flask** for web interface framework
- **pytest** for comprehensive testing framework

---

## 📞 Support

For questions, issues, or contributions:

1. **Check existing issues** in the repository
2. **Create new issue** with detailed description
3. **Review documentation** in `/docs` directory
4. **Run tests** to verify your environment

---
