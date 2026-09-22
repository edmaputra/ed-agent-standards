#!/usr/bin/env bash
#
# ensure-structure.sh - PreInvocation lifecycle hook for Antigravity.
# Automatically scans and writes project-structure.json if missing.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="."

# Find Python interpreter
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

# Read stdin JSON payload from Antigravity lifecycle hook
STDIN_INPUT=$(cat || true)

if [ -n "$STDIN_INPUT" ] && [ -n "$PYTHON_BIN" ]; then
    PARSED_ROOT=$(printf '%s' "$STDIN_INPUT" | "$PYTHON_BIN" -c "
import sys, json
try:
    data = json.load(sys.stdin)
    paths = data.get('workspacePaths', [])
    if paths and isinstance(paths, list) and paths[0]:
        print(paths[0])
    else:
        print('.')
except Exception:
    print('.')
" 2>/dev/null || echo ".")
    if [ -n "$PARSED_ROOT" ] && [ -d "$PARSED_ROOT" ]; then
        WORKSPACE_ROOT="$PARSED_ROOT"
    fi
fi

# Determine structure file location and check if it already exists
TARGET_JSON=""
if [ -f "$WORKSPACE_ROOT/project-structure.json" ]; then
    TARGET_JSON="$WORKSPACE_ROOT/project-structure.json"
elif [ -f "$WORKSPACE_ROOT/.agents/project-structure.json" ]; then
    TARGET_JSON="$WORKSPACE_ROOT/.agents/project-structure.json"
elif [ -d "$WORKSPACE_ROOT/.agents" ]; then
    TARGET_JSON="$WORKSPACE_ROOT/.agents/project-structure.json"
else
    TARGET_JSON="$WORKSPACE_ROOT/project-structure.json"
fi

if [ -f "$TARGET_JSON" ]; then
    # Already exists, output empty JSON to continue without delay
    echo "{}"
    exit 0
fi

if [ -z "$PYTHON_BIN" ]; then
    # Python is not available
    echo "{}"
    exit 0
fi

# Run scanner to generate project structure
"$PYTHON_BIN" "$SCRIPT_DIR/scan-structure.py" "$WORKSPACE_ROOT" > /dev/null 2>&1 || true

if [ -f "$TARGET_JSON" ]; then
    cat <<EOF
{
  "injectSteps": [
    {
      "ephemeralMessage": "[Project Scanner] Generated project structure map at $(basename "$TARGET_JSON"). Use this map for fast navigation."
    }
  ]
}
EOF
else
    echo "{}"
fi
