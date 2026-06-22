#!/bin/sh
# Run all tests using Python's built-in unittest
# Usage: ./tests/run.sh [test_file...]

cd "$(dirname "$0")/.."

if [ $# -gt 0 ]; then
    python3 -m unittest "$@"
else
    python3 -m unittest discover -s tests -p "test_*.py" -v
fi
