#!/bin/sh
# Deliberately not treating a non-zero exit as failure below: sqlmap exits
# non-zero for all sorts of non-fatal reasons (no injectable parameter found,
# a crawled link 404ing, batch mode auto-declining a prompt) - not just
# crashes. The worker decides success/failure by whether it can read
# container output, same pattern as the ZAP scanner entrypoint.

TARGET_URL="${TARGET_URL:?TARGET_URL environment variable is required}"

mkdir -p /output

# --batch: never wait on an interactive prompt (this runs unattended).
# --crawl=1: we're only given a bare URL, not a known injectable parameter,
#   so sqlmap needs to discover links/forms itself first; kept shallow (depth
#   1) to bound runtime - this is already gated behind the opt-in "aggressive"
#   scan type, not something to make slower/noisier by default.
# --forms: also test parameters found in HTML forms, not just URL query strings.
# --risk=1 --level=1: sqlmap's own lowest risk/thoroughness tiers. Higher
#   risk levels add payloads that can be destructive (e.g. heavy queries,
#   time-based tests that hammer the DB) - not appropriate for an automated
#   scan against a target we don't operate ourselves.
python3 /sqlmap/sqlmap.py \
  -u "$TARGET_URL" \
  --batch \
  --crawl=1 \
  --forms \
  --risk=1 \
  --level=1 \
  --output-dir=/output

echo "sqlmap exited with code $? (non-zero commonly just means no injectable parameter was found, not a crash)"
exit 0
