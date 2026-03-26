#!/bin/sh
# check-code-ratio.sh -- Check code block ratio against type-specific limits
# Usage: check-code-ratio.sh <file.md> <type-prefix>
# Exit 0 = pass, 1 = fail
# type-prefix: tut, how, ref, arch, sys, core, theory, journey

set -e

FILE="$1"
TYPE="$2"

if [ -z "$FILE" ] || [ -z "$TYPE" ]; then
  echo "Usage: $0 <file.md> <type-prefix>" >&2
  exit 2
fi

if [ ! -f "$FILE" ]; then
  echo "FAIL: File not found: $FILE" >&2
  exit 2
fi

# Set limit by type
case "$TYPE" in
  tut)     LIMIT=20 ; BLOCK_LIMIT=15 ;;
  how)     LIMIT=15 ; BLOCK_LIMIT=15 ;;
  ref)     LIMIT=10 ; BLOCK_LIMIT=15 ;;
  arch)    LIMIT=10 ; BLOCK_LIMIT=10 ;;
  sys)     LIMIT=15 ; BLOCK_LIMIT=15 ;;
  core)    LIMIT=15 ; BLOCK_LIMIT=15 ;;
  theory)  LIMIT=5  ; BLOCK_LIMIT=10 ;;
  journey) LIMIT=10 ; BLOCK_LIMIT=10 ;;
  *)       echo "FAIL: Unknown type: $TYPE" >&2; exit 2 ;;
esac

TOTAL_LINES=$(wc -l < "$FILE" | tr -d ' ')
if [ "$TOTAL_LINES" -eq 0 ]; then
  echo "FAIL: Empty file" >&2
  exit 1
fi

# Count lines inside fenced code blocks (``` ... ```)
# Also track max block size
CODE_LINES=0
MAX_BLOCK=0
CURRENT_BLOCK=0
IN_CODE=0

while IFS= read -r line; do
  case "$line" in
    '```'*)
      if [ "$IN_CODE" -eq 0 ]; then
        IN_CODE=1
        CURRENT_BLOCK=0
      else
        IN_CODE=0
        if [ "$CURRENT_BLOCK" -gt "$MAX_BLOCK" ]; then
          MAX_BLOCK=$CURRENT_BLOCK
        fi
      fi
      ;;
    *)
      if [ "$IN_CODE" -eq 1 ]; then
        CODE_LINES=$((CODE_LINES + 1))
        CURRENT_BLOCK=$((CURRENT_BLOCK + 1))
      fi
      ;;
  esac
done < "$FILE"

# Calculate ratio (integer arithmetic, multiply by 100 first)
RATIO=$((CODE_LINES * 100 / TOTAL_LINES))

# Output results
PASS=1
if [ "$RATIO" -gt "$LIMIT" ]; then
  echo "FAIL: Code ratio ${RATIO}% exceeds ${LIMIT}% limit for ${TYPE}- type (${CODE_LINES}/${TOTAL_LINES} lines)"
  PASS=0
else
  echo "PASS: Code ratio ${RATIO}% within ${LIMIT}% limit (${CODE_LINES}/${TOTAL_LINES} lines)"
fi

if [ "$MAX_BLOCK" -gt "$BLOCK_LIMIT" ]; then
  echo "FAIL: Max block ${MAX_BLOCK} lines exceeds ${BLOCK_LIMIT}-line limit for ${TYPE}- type"
  PASS=0
else
  echo "PASS: Max block ${MAX_BLOCK} lines within ${BLOCK_LIMIT}-line limit"
fi

exit $((1 - PASS))
