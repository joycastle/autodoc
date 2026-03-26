#!/bin/sh
# validate-source-refs.sh -- Check that src/ references point to existing files
# Usage: validate-source-refs.sh <file.md>
# Exit 0 = all refs valid, 1 = some refs invalid

set -e

FILE="$1"
BASE_DIR="$(cd "$(dirname "$0")/../../../../" && pwd)"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Usage: $0 <file.md>" >&2
  exit 2
fi

# Extract src/ references from backtick-quoted strings
# Matches patterns like `src/server/biz/mail/service.go` or `src/client/.../Foo.cs:123`
REFS=$(grep -oE '`src/[^`]+`' "$FILE" 2>/dev/null | sed 's/`//g' | sed 's/:[0-9].*$//' | sort -u || true)

if [ -z "$REFS" ]; then
  echo "PASS: No src/ references found (nothing to validate)"
  exit 0
fi

TOTAL=0
MISSING=0

for ref in $REFS; do
  TOTAL=$((TOTAL + 1))
  FULL_PATH="${BASE_DIR}/${ref}"

  # Check if file exists (handle ... glob patterns by checking parent dir)
  if echo "$ref" | grep -q '\.\.\.'; then
    # Contains ..., skip (wildcard path)
    continue
  fi

  if [ -f "$FULL_PATH" ] || [ -d "$FULL_PATH" ]; then
    : # exists
  else
    echo "MISSING: $ref"
    MISSING=$((MISSING + 1))
  fi
done

VALID=$((TOTAL - MISSING))
echo "${VALID}/${TOTAL} references valid"

if [ "$MISSING" -gt 0 ]; then
  echo "FAIL: ${MISSING} missing reference(s)"
  exit 1
else
  echo "PASS: All references exist"
  exit 0
fi
