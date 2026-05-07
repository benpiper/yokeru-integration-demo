#!/bin/bash
# End-to-end demo: dispatch a welfare check, then close the loop via webhook.
#
# Proves the full lifecycle:
#   1. Agent fetches patient from FHIR, buffers to SQLite, dispatches to Yokeru.
#   2. DB row shows status=DELIVERED, outcome=NULL.
#   3. Yokeru "calls back" via the webhook with call.completed.
#   4. DB row now shows outcome=completed + completed_at timestamp.
#
# Prerequisites:
#   - The webhook server must be running: uv run yokeru-agent serve --port 8000
#   - jq, sqlite3, and openssl must be available.

set -euo pipefail

SERVER_URL="http://localhost:8000"
SECRET="replace-with-a-long-random-string"        # must match YOKERU_WEBHOOK_SIGNING_SECRET in .env
PATIENT_ID="12508044"                              # Cerner sandbox patient with a phone number
DB="integration_state.db"

# ── Helpers ──────────────────────────────────────────────────────────────────
banner() { printf '\n%s\n  %s\n%s\n\n' "$(printf '=%.0s' {1..72})" "$1" "$(printf '=%.0s' {1..72})"; }
row()    { sqlite3 -column -header "$DB" "$1"; }

# ── Step 1: Dispatch welfare check ───────────────────────────────────────────
banner "STEP 1 — Dispatch welfare check for patient $PATIENT_ID"
uv run yokeru-agent run --no-replay "$PATIENT_ID"

# ── Step 2: Grab the correlation_id from the most-recent row ─────────────────
CID=$(sqlite3 "$DB" "SELECT correlation_id FROM call_buffer WHERE patient_id='$PATIENT_ID' ORDER BY created_at DESC LIMIT 1;")
echo ""
echo "  ➜ correlation_id = $CID"

banner "STEP 2 — Database after dispatch (outcome should be NULL)"
row "SELECT correlation_id, patient_id, status, outcome, completed_at, updated_at
     FROM call_buffer WHERE correlation_id='$CID';"

# ── Step 3: Simulate Yokeru calling back via webhook ─────────────────────────
banner "STEP 3 — Yokeru sends call.completed webhook"

EVENT_ID="evt-e2e-$(date +%s)"
PAYLOAD=$(cat <<EOF
{
  "event_id": "$EVENT_ID",
  "event_type": "call.completed",
  "correlation_id": "$CID",
  "occurred_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "detail": {"duration_s": 42, "disposition": "answered"}
}
EOF
)

SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')

echo "  Sending POST /webhooks/yokeru with event_id=$EVENT_ID"
echo ""
RESPONSE=$(curl -s -X POST "$SERVER_URL/webhooks/yokeru" \
  -H "Content-Type: application/json" \
  -H "X-Yokeru-Signature: sha256=$SIGNATURE" \
  -d "$PAYLOAD")

echo "$RESPONSE" | jq .

# ── Step 4: Show the updated row ─────────────────────────────────────────────
banner "STEP 4 — Database after webhook (outcome should be 'completed')"
row "SELECT correlation_id, patient_id, status, outcome, completed_at, updated_at
     FROM call_buffer WHERE correlation_id='$CID';"

# ── Step 5: Show the stored webhook event ────────────────────────────────────
banner "STEP 5 — webhook_events table"
row "SELECT event_id, event_type, received_at FROM webhook_events WHERE event_id='$EVENT_ID';"

echo ""
echo "  ✅  End-to-end lifecycle complete."
echo "      Dispatch → Buffer → Deliver → Webhook → Outcome stamped."
echo ""
