#!/bin/sh
# Runs one of the app's Python files with its requirements, from the repo folder, through the first way that works
# (the uv ladder, SETUP.md): uv already there; else install uv; else Python 3.11 or newer in .venv; else a plain stop.
# Usage: scripts/run.sh server.py | scripts/run.sh scripts/setup.py --status
set -eu
cd "${0%/*}/.."

UV_INSTALLER="https://astral.sh/uv/install.sh"   # uv's official one-line installer, as its docs give it
UV_RUN="run --python 3.12 --with-requirements requirements.txt python"   # the command SETUP.md used before this script
PYTHONS="python3.13 python3.12 python3.11 python3"   # newest first; 3.11 is the floor (config.py needs tomllib)

find_uv() {
    if command -v uv >/dev/null 2>&1; then UV=uv
    elif [ -x "$HOME/.local/bin/uv" ]; then UV="$HOME/.local/bin/uv"   # just installed: not on the agent's PATH yet
    else UV=""
    fi
}

find_uv
if [ -n "$UV" ]; then
    echo "Using uv." >&2
    exec "$UV" $UV_RUN "$@"
fi

if command -v curl >/dev/null 2>&1 && curl -LsSf "$UV_INSTALLER" | sh >/dev/null 2>&1; then
    find_uv
    if [ -n "$UV" ]; then
        echo "Installed uv." >&2
        exec "$UV" $UV_RUN "$@"
    fi
fi

for py in $PYTHONS; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
        [ -x .venv/bin/python ] || "$py" -m venv .venv
        stamp=$(cksum < requirements.txt)
        marker=".venv/.requirements-${stamp%% *}"   # reinstall only when requirements.txt changes
        if [ ! -e "$marker" ]; then
            .venv/bin/python -m pip install -q -r requirements.txt
            : > "$marker"
        fi
        echo "Using $py in .venv." >&2
        exec .venv/bin/python "$@"
    fi
done

echo "Setup needs uv or Python 3.11 or newer, and neither could be found or installed. Install uv (https://docs.astral.sh/uv/getting-started/installation/), then run this again." >&2
exit 1
