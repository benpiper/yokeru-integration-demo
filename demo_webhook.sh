#!/bin/bash
# Demo script to test the Yokeru Integration Agent Webhook endpoints

SERVER_URL="http://localhost:8000"
# Match this to your YOKERU_WEBHOOK_SIGNING_SECRET in .env
SECRET="replace-with-a-long-random-string"

echo "================================================================================"
echo "1. Testing /healthz endpoint"
echo "================================================================================"
curl -s -w "\nHTTP Status: %{http_code}\n\n" "$SERVER_URL/healthz"


echo "================================================================================"
echo "2. Testing /metrics endpoint (Prometheus)"
echo "================================================================================"
curl -s "$SERVER_URL/metrics" | grep "yokeru" | head -n 10
echo -e "\n..."


echo "================================================================================"
echo "3. Testing /webhooks/yokeru (Valid Signature)"
echo "================================================================================"

# 1. Define the payload matching the WebhookEvent Pydantic schema
PAYLOAD=$(cat <<EOF
{
  "event_id": "test-event-12345",
  "event_type": "call.completed",
  "correlation_id": "demo-correlation-id-001",
  "occurred_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "detail": {
    "duration_seconds": 45,
    "disposition": "answered"
  }
}
EOF
)

# 2. Generate the HMAC-SHA256 signature using OpenSSL
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')

# 3. Send the request
curl -s -X POST "$SERVER_URL/webhooks/yokeru" \
  -H "Content-Type: application/json" \
  -H "X-Yokeru-Signature: sha256=$SIGNATURE" \
  -d "$PAYLOAD" | jq .


echo -e "\n================================================================================"
echo "4. Testing /webhooks/yokeru (Invalid Signature)"
echo "================================================================================"

curl -s -w "\nHTTP Status: %{http_code}\n" -X POST "$SERVER_URL/webhooks/yokeru" \
  -H "Content-Type: application/json" \
  -H "X-Yokeru-Signature: sha256=abcdef1234567890" \
  -d "$PAYLOAD"

echo "================================================================================"
