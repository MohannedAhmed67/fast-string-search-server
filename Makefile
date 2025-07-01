SRC = .

format:
	black $(SRC)

lint:
	ruff check $(SRC)

type-check:
	mypy $(SRC)

check:
	make format
	make lint
	make type-check

tests:
	PYTHONPATH=. pytest tests/test_*.py -v

clean:
	find . -type f -name "*.pyc" -delete
