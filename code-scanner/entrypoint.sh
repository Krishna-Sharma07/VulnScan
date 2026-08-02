#!/bin/sh
# Deliberately no 'set -e': bandit and (legacy) safety both exit non-zero
# when they find issues - that's normal signal, not a script crash - same
# reasoning as the ZAP/sqlmap entrypoints.
set -u

UPLOAD_ZIP="/code/upload.zip"
SRC_DIR="/code/src"

if [ ! -f "$UPLOAD_ZIP" ]; then
  echo "No upload.zip found at $UPLOAD_ZIP - nothing to scan" >&2
  exit 1
fi

# Zip-bomb guard: read the uncompressed total from `unzip -l`'s summary
# line before extracting anything, and refuse anything absurd for a source
# code upload. 500MB uncompressed is already generous for a code repo.
MAX_UNCOMPRESSED_BYTES=524288000
TOTAL_UNCOMPRESSED=$(unzip -l "$UPLOAD_ZIP" | tail -1 | awk '{print $1}')
if [ -z "$TOTAL_UNCOMPRESSED" ] || [ "$TOTAL_UNCOMPRESSED" -gt "$MAX_UNCOMPRESSED_BYTES" ]; then
  echo "Upload rejected: uncompressed size ($TOTAL_UNCOMPRESSED bytes) exceeds the ${MAX_UNCOMPRESSED_BYTES}-byte cap" >&2
  exit 1
fi

mkdir -p "$SRC_DIR"
# Zip-slip note: Info-Zip's `unzip` has refused to write outside the target
# directory for any entry path containing ".." (or an absolute path) since
# well before this base image's version - no extra flag needed to get that
# protection, and none is passed here that would turn it off.
unzip -q -o "$UPLOAD_ZIP" -d "$SRC_DIR"

# bandit: static analysis for common Python security issues (hardcoded
# passwords, eval/exec use, insecure deserialization, weak crypto, etc.) -
# never executes any of the uploaded code, only parses it.
bandit -r "$SRC_DIR" -f json -o /code/bandit-report.json -q
echo "bandit exited with code $? (non-zero commonly just means issues were found, not a crash)"

# safety: checks pinned dependency versions in any requirements*.txt against
# a known-vulnerability database - also never installs or runs anything.
REQUIREMENTS_FILES=$(find "$SRC_DIR" -iname 'requirements*.txt' 2>/dev/null)
if [ -n "$REQUIREMENTS_FILES" ]; then
  # Concatenate every requirements file found (a repo may split them, e.g.
  # requirements.txt + requirements-dev.txt) into one list for a single pass.
  cat $REQUIREMENTS_FILES > /code/combined-requirements.txt
  safety check -r /code/combined-requirements.txt --json > /code/safety-report.json
  echo "safety exited with code $? (non-zero commonly just means vulnerable packages were found, not a crash)"
else
  echo "[]" > /code/safety-report.json
  echo "No requirements*.txt found - skipping dependency scan"
fi

exit 0
