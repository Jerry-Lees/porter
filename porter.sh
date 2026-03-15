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
python3 -m porter "$@"
EXIT_CODE=$?
deactivate

# Restore terminal — reset raw mode, echo, and mouse tracking that Textual may have
# left enabled after a SIGKILL or crash. No-op when porter exits cleanly.
stty sane
printf '\033[?1000l\033[?1002l\033[?1003l\033[?1006l'

exit $EXIT_CODE
