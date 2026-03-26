#!/bin/sh
# check-format.sh -- Check markdown formatting rules
# Usage: check-format.sh <file.md>
# Checks: numbered headings, emoji, horizontal rules
# Exit 0 = pass, 1 = fail

set -e

FILE="$1"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Usage: $0 <file.md>" >&2
  exit 2
fi

FAIL=0

# Check 1: Numbered headings (e.g., "## 1. Foo", "## Step 1:", "## 步骤一")
NUMBERED=$(grep -nE '^#{1,4}\s+(\d+[\.\):]|步骤[一二三四五六七八九十]|第[一二三四五六七八九十]步|Step\s+\d)' "$FILE" 2>/dev/null || true)
if [ -n "$NUMBERED" ]; then
  echo "FAIL: Numbered headings found:"
  echo "$NUMBERED"
  FAIL=1
else
  echo "PASS: No numbered headings"
fi

# Check 2: Horizontal rules (--- on its own line, not inside code blocks)
# Simple check: lines that are exactly --- (may have leading spaces)
IN_CODE=0
HR_LINES=""
LINENUM=0
while IFS= read -r line; do
  LINENUM=$((LINENUM + 1))
  case "$line" in
    '```'*)
      if [ "$IN_CODE" -eq 0 ]; then IN_CODE=1; else IN_CODE=0; fi
      ;;
    *)
      if [ "$IN_CODE" -eq 0 ]; then
        cleaned=$(echo "$line" | sed 's/^[[:space:]]*//')
        if [ "$cleaned" = "---" ]; then
          HR_LINES="${HR_LINES}${LINENUM}: ${line}\n"
        fi
      fi
      ;;
  esac
done < "$FILE"

if [ -n "$HR_LINES" ]; then
  echo "FAIL: Horizontal rules (---) found:"
  printf "%b" "$HR_LINES"
  FAIL=1
else
  echo "PASS: No horizontal rules"
fi

# Check 3: Heading depth > 4
DEEP=$(grep -nE '^#{5,}' "$FILE" 2>/dev/null || true)
if [ -n "$DEEP" ]; then
  echo "FAIL: Headings deeper than 4 levels:"
  echo "$DEEP"
  FAIL=1
else
  echo "PASS: Heading depth <= 4"
fi

exit $FAIL
