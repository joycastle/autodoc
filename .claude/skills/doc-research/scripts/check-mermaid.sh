#!/bin/sh
# check-mermaid.sh -- Check Mermaid diagram limits
# Usage: check-mermaid.sh <file.md> <type-prefix>
# Checks: max 3 diagrams, line limits per type, participant limits
# Exit 0 = pass, 1 = fail

set -e

FILE="$1"
TYPE="$2"

if [ -z "$FILE" ]; then
  echo "Usage: $0 <file.md> [type-prefix]" >&2
  exit 2
fi

if [ ! -f "$FILE" ]; then
  echo "FAIL: File not found: $FILE" >&2
  exit 2
fi

# Set block line limit by type (default 15)
case "$TYPE" in
  arch|theory|journey) BLOCK_LIMIT=10 ;;
  *)                   BLOCK_LIMIT=15 ;;
esac

# Parse mermaid blocks
BLOCK_COUNT=0
MAX_LINES=0
MAX_PARTICIPANTS=0
CURRENT_LINES=0
CURRENT_PARTICIPANTS=0
IN_MERMAID=0
FAIL=0

while IFS= read -r line; do
  case "$line" in
    '```mermaid'*)
      IN_MERMAID=1
      BLOCK_COUNT=$((BLOCK_COUNT + 1))
      CURRENT_LINES=0
      CURRENT_PARTICIPANTS=0
      ;;
    '```')
      if [ "$IN_MERMAID" -eq 1 ]; then
        IN_MERMAID=0
        if [ "$CURRENT_LINES" -gt "$MAX_LINES" ]; then
          MAX_LINES=$CURRENT_LINES
        fi
        if [ "$CURRENT_PARTICIPANTS" -gt "$MAX_PARTICIPANTS" ]; then
          MAX_PARTICIPANTS=$CURRENT_PARTICIPANTS
        fi
      fi
      ;;
    *)
      if [ "$IN_MERMAID" -eq 1 ]; then
        CURRENT_LINES=$((CURRENT_LINES + 1))
        # Count participants in sequence diagrams
        case "$line" in
          *participant*) CURRENT_PARTICIPANTS=$((CURRENT_PARTICIPANTS + 1)) ;;
        esac
      fi
      ;;
  esac
done < "$FILE"

# Check limits
if [ "$BLOCK_COUNT" -gt 3 ]; then
  echo "FAIL: ${BLOCK_COUNT} Mermaid diagrams (max 3)"
  FAIL=1
else
  echo "PASS: ${BLOCK_COUNT} Mermaid diagram(s) (max 3)"
fi

if [ "$BLOCK_COUNT" -gt 0 ]; then
  if [ "$MAX_LINES" -gt "$BLOCK_LIMIT" ]; then
    echo "FAIL: Largest Mermaid block ${MAX_LINES} lines (max ${BLOCK_LIMIT} for ${TYPE:-default})"
    FAIL=1
  else
    echo "PASS: Largest Mermaid block ${MAX_LINES} lines (max ${BLOCK_LIMIT})"
  fi

  if [ "$MAX_PARTICIPANTS" -gt 6 ]; then
    echo "FAIL: Max ${MAX_PARTICIPANTS} participants (max 6)"
    FAIL=1
  else
    echo "PASS: Max ${MAX_PARTICIPANTS} participants (max 6)"
  fi
fi

exit $FAIL
