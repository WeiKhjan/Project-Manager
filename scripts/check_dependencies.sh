#!/usr/bin/env bash
# -------------------------------------------------------------------
# First-run dependency checker for Project Manager Agent Teams
# Called by Claude Code SessionStart hook.
# Checks Python availability and required pip packages.
# Uses a marker file to skip checks on subsequent runs.
# -------------------------------------------------------------------

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MARKER_FILE="$PROJECT_DIR/.deps_verified"
REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"
LOG_FILE="$PROJECT_DIR/.deps_check.log"

# If marker exists and is less than 7 days old, skip checks
if [ -f "$MARKER_FILE" ]; then
    if [ "$(uname)" = "Darwin" ]; then
        marker_age=$(( $(date +%s) - $(stat -f %m "$MARKER_FILE") ))
    else
        marker_age=$(( $(date +%s) - $(stat -c %Y "$MARKER_FILE") ))
    fi
    # Re-check every 7 days (604800 seconds)
    if [ "$marker_age" -lt 604800 ]; then
        exit 0
    fi
fi

echo "=== Project Manager: Dependency Check ===" > "$LOG_FILE"
echo "Date: $(date)" >> "$LOG_FILE"
ERRORS=0

# --- Check Python ---
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python is not installed or not in PATH." >> "$LOG_FILE"
    echo "  Install Python 3.8+ from https://www.python.org/downloads/" >> "$LOG_FILE"
    ERRORS=1
else
    PY_VERSION=$($PYTHON_CMD --version 2>&1)
    echo "OK: $PY_VERSION found ($PYTHON_CMD)" >> "$LOG_FILE"
fi

# --- Check pip ---
if [ -n "$PYTHON_CMD" ]; then
    PIP_CMD=""
    if $PYTHON_CMD -m pip --version &>/dev/null; then
        PIP_CMD="$PYTHON_CMD -m pip"
    elif command -v pip3 &>/dev/null; then
        PIP_CMD="pip3"
    elif command -v pip &>/dev/null; then
        PIP_CMD="pip"
    fi

    if [ -z "$PIP_CMD" ]; then
        echo "ERROR: pip is not installed." >> "$LOG_FILE"
        echo "  Run: $PYTHON_CMD -m ensurepip --upgrade" >> "$LOG_FILE"
        ERRORS=1
    else
        echo "OK: pip found ($($PIP_CMD --version 2>&1))" >> "$LOG_FILE"
    fi
fi

# --- Check required Python packages ---
if [ -n "$PYTHON_CMD" ] && [ -n "${PIP_CMD:-}" ] && [ -f "$REQUIREMENTS_FILE" ]; then
    MISSING_PKGS=()
    while IFS= read -r pkg || [ -n "$pkg" ]; do
        # Skip empty lines and comments
        pkg=$(echo "$pkg" | sed 's/#.*//' | xargs)
        [ -z "$pkg" ] && continue

        # Normalize: pip uses hyphens and underscores interchangeably
        if ! $PYTHON_CMD -c "import importlib; importlib.import_module('$(echo "$pkg" | sed "s/-/_/g" | sed "s/google_api_python_client/googleapiclient/" | sed "s/google_auth_oauthlib/google_auth_oauthlib/" | sed "s/google_auth$/google.auth/")')" &>/dev/null; then
            MISSING_PKGS+=("$pkg")
        fi
    done < "$REQUIREMENTS_FILE"

    if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
        echo "MISSING: ${MISSING_PKGS[*]}" >> "$LOG_FILE"
        echo "Installing missing packages..." >> "$LOG_FILE"
        $PIP_CMD install "${MISSING_PKGS[@]}" >> "$LOG_FILE" 2>&1
        if [ $? -eq 0 ]; then
            echo "OK: All missing packages installed successfully." >> "$LOG_FILE"
        else
            echo "ERROR: Failed to install some packages. Run manually:" >> "$LOG_FILE"
            echo "  $PIP_CMD install -r $REQUIREMENTS_FILE" >> "$LOG_FILE"
            ERRORS=1
        fi
    else
        echo "OK: All required Python packages are installed." >> "$LOG_FILE"
    fi
fi

# --- Summary ---
if [ "$ERRORS" -eq 0 ]; then
    echo "" >> "$LOG_FILE"
    echo "All dependency checks passed." >> "$LOG_FILE"
    # Write marker file so we skip next time
    date > "$MARKER_FILE"
else
    echo "" >> "$LOG_FILE"
    echo "Some checks FAILED. See errors above." >> "$LOG_FILE"
    # Print log to stderr so Claude Code hook can surface it
    cat "$LOG_FILE" >&2
    exit 1
fi
