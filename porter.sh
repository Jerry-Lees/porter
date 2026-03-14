#!/usr/bin/env bash
# porter.sh — run porter inside its virtual environment
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Porter venv not found at $VENV_DIR" >&2
    echo "Run install.sh to set up porter." >&2
    exit 1
fi

source "$VENV_DIR/bin/activate"
python -m porter "$@"
EXIT_CODE=$?
deactivate
exit $EXIT_CODE
