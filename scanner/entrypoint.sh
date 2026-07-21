#!/bin/bash
# Deliberately no 'set -e': zap-baseline.py / zap-full-scan.py exit non-zero
# when they find alerts (that's normal signal, not a script failure), so
# aborting on non-zero would treat every scan with results as broken.
set -uo pipefail

TARGET_URL="${TARGET_URL:?TARGET_URL environment variable is required}"
SCAN_TYPE="${SCAN_TYPE:-baseline}"

mkdir -p /zap/wrk
cd /zap/wrk

if [ "$SCAN_TYPE" = "aggressive" ]; then
  /zap/zap-full-scan.py -t "$TARGET_URL" -J report.json -m 2
else
  /zap/zap-baseline.py -t "$TARGET_URL" -J report.json -m 1
fi

echo "ZAP scan script exited with code $? (non-zero commonly just means alerts were found, not a crash)"
exit 0
