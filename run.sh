#!/bin/bash
# Always change to the project directory before running axiom.py
cd "$(dirname "$0")"

# Activate virtual environment if available
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python3 axiom.py "$@"
