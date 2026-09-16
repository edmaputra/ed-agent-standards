#!/usr/bin/env bash
#
# ensure-structure.sh - PreInvocation lifecycle hook for Antigravity.
# Automatically scans and writes project-structure.json if missing.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="."

# Read stdin JSON payload from Antigravity lifecycle hook
STDIN_INPUT=$(cat || true)

if [ -n "$STDIN_INPUT" ]; then
    PARSED_ROOT=$(python3 -c "
import sys, json
try:
    data = json.loads('''$STDIN_INPUT''')
    paths = data.get('workspacePaths', [])
    if paths:
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

# Determine potential structure file locations
TARGET_JSON=""
if [ -d "$WORKSPACE_ROOT/.agents" ]; then
    TARGET_JSON="$WORKSPACE_ROOT/.agents/project-structure.json"
else
    TARGET_JSON="$WORKSPACE_ROOT/project-structure.json"
fi

# Check if structure file already exists
if [ -f "$TARGET_JSON" ]; then
    # Already exists, output empty JSON to continue without delay
    echo "{}"
    exit 0
fi

# Run scanner to generate project structure
python3 "$SCRIPT_DIR/scan-structure.py" "$WORKSPACE_ROOT" > /dev/null 2>&1 || true

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
