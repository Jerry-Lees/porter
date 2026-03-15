#!/usr/bin/env bash
# install.sh — Porter installer
# Sets up the Python virtual environment and all dependencies.
# Supports Debian/Ubuntu (apt), RHEL/Fedora (dnf), and Arch (pacman).

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${GREEN}[porter]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}   $*"; }
section() { echo -e "\n${CYAN}${BOLD}── $* ${NC}"; }
error()   { echo -e "${RED}[error]${NC}  $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
LAUNCHER="$SCRIPT_DIR/porter.sh"
MIN_PYTHON_MINOR=11

# ── Root / sudo helper ────────────────────────────────────────────────────────

_sudo() {
    if [ "$EUID" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

# ── Python check ──────────────────────────────────────────────────────────────

section "Checking Python"

PYTHON=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        _ver=$("$cmd" -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>/dev/null || true)
        _maj="${_ver%%.*}"
        _min="${_ver##*.}"
        if [ -n "$_ver" ] && [ "$_maj" -ge 3 ] && [ "$_min" -ge "$MIN_PYTHON_MINOR" ]; then
            PYTHON="$cmd"
            PYTHON_VER="$_ver"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.${MIN_PYTHON_MINOR}+ is required but was not found.
  Ubuntu/Debian:  sudo apt install python3.12
  Fedora/RHEL:    sudo dnf install python3.12
  Arch:           sudo pacman -S python"
fi

info "Found $PYTHON ($PYTHON_VER)"

# ── System packages ───────────────────────────────────────────────────────────

section "System packages"

if command -v apt-get &>/dev/null; then
    # Debian / Ubuntu
    PKGS_NEEDED=()
    for pkg in python3-venv python3-pip openssh-client rsync; do
        dpkg -s "$pkg" &>/dev/null 2>&1 || PKGS_NEEDED+=("$pkg")
    done
    if [ "${#PKGS_NEEDED[@]}" -gt 0 ]; then
        info "Installing: ${PKGS_NEEDED[*]}"
        _sudo apt-get install -y "${PKGS_NEEDED[@]}"
    else
        info "All apt packages already installed"
    fi

elif command -v dnf &>/dev/null; then
    # Fedora / RHEL / Rocky / Alma
    PKGS_NEEDED=()
    for pkg in python3-pip openssh-clients rsync; do
        rpm -q "$pkg" &>/dev/null || PKGS_NEEDED+=("$pkg")
    done
    # python3-venv is bundled with python3 on dnf-based systems
    if [ "${#PKGS_NEEDED[@]}" -gt 0 ]; then
        info "Installing: ${PKGS_NEEDED[*]}"
        _sudo dnf install -y "${PKGS_NEEDED[@]}"
    else
        info "All dnf packages already installed"
    fi

elif command -v pacman &>/dev/null; then
    # Arch Linux
    PKGS_NEEDED=()
    for pkg in python-pip openssh rsync; do
        pacman -Q "$pkg" &>/dev/null || PKGS_NEEDED+=("$pkg")
    done
    if [ "${#PKGS_NEEDED[@]}" -gt 0 ]; then
        info "Installing: ${PKGS_NEEDED[*]}"
        _sudo pacman -S --noconfirm "${PKGS_NEEDED[@]}"
    else
        info "All pacman packages already installed"
    fi

else
    warn "Unknown package manager — skipping system package install."
    warn "Ensure python3-venv, openssh-client, and rsync are installed."
fi

# ── Virtual environment ───────────────────────────────────────────────────────

section "Virtual environment"

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ] && \
   "$VENV_DIR/bin/python" -c "import sys" &>/dev/null && \
   "$VENV_DIR/bin/pip" --version &>/dev/null; then
    info "Existing venv found at $VENV_DIR"
else
    if [ -d "$VENV_DIR" ]; then
        warn "Existing venv is broken (stale paths?) — recreating at $VENV_DIR"
        rm -rf "$VENV_DIR"
    fi
    info "Creating venv at $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
fi

info "Upgrading pip"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip

# ── Python dependencies ───────────────────────────────────────────────────────

section "Python packages"

info "Installing porter and dependencies (textual, paramiko, PyYAML)"
"$VENV_DIR/bin/pip" install --quiet -e "$SCRIPT_DIR"

# Verify critical packages imported cleanly
"$VENV_DIR/bin/python" -c "
import textual, paramiko, yaml
from porter.app import PorterApp
print('  all packages OK')
"

# ── Launcher script ───────────────────────────────────────────────────────────

section "Launcher"

cat > "$LAUNCHER" << LAUNCHER_SCRIPT
#!/usr/bin/env bash
# porter.sh — run porter inside its virtual environment
SCRIPT_DIR="\$(cd "\$(dirname "\$(readlink -f "\${BASH_SOURCE[0]}")")" && pwd)"
VENV_DIR="\$SCRIPT_DIR/.venv"

if [ ! -f "\$VENV_DIR/bin/activate" ]; then
    echo "Porter venv not found at \$VENV_DIR" >&2
    echo "Run install.sh to set up porter." >&2
    exit 1
fi

source "\$VENV_DIR/bin/activate"
python3 -m porter "\$@"
EXIT_CODE=\$?
deactivate
exit \$EXIT_CODE
LAUNCHER_SCRIPT

chmod +x "$LAUNCHER"
info "Launcher written to $LAUNCHER"

# ── Optional symlink in PATH ──────────────────────────────────────────────────

section "PATH integration"

if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    ln -sf "$LAUNCHER" /usr/local/bin/porter
    info "Symlinked to /usr/local/bin/porter"
else
    warn "Cannot write to /usr/local/bin without elevated privileges."
    if command -v sudo &>/dev/null; then
        echo -e "  Would you like to install the symlink with sudo? [y/N] \c"
        read -r REPLY
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            sudo ln -sf "$LAUNCHER" /usr/local/bin/porter
            info "Symlinked to /usr/local/bin/porter (via sudo)"
        else
            warn "Skipping system-wide install. To run porter from anywhere, add this to your shell profile (~/.bashrc or ~/.zshrc):"
            echo "      export PATH=\"$SCRIPT_DIR:\$PATH\""
        fi
    else
        warn "sudo not available. To run porter from anywhere, add this to your shell profile:"
        echo "      export PATH=\"$SCRIPT_DIR:\$PATH\""
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────

section "Done"
info "Porter is ready."
echo -e "  Run with:  ${BOLD}porter${NC}  (if /usr/local/bin is in PATH)"
echo -e "         or:  ${BOLD}$LAUNCHER${NC}"
echo ""
