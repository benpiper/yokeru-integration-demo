#!/bin/bash
# Demo script to generate a welfare check and inspect the local database buffer

# We use a known public Patient ID from the Cerner Sandbox that has a valid phone number
PATIENT_ID="12508044"

echo "================================================================================"
echo "1. Triggering Welfare Check for Patient $PATIENT_ID"
echo "================================================================================"

# Run the integration agent using the CLI entrypoint
uv run yokeru-agent run "$PATIENT_ID"

echo ""
echo "================================================================================"
echo "2. Inspecting Local SQLite Database Buffer"
echo "================================================================================"

# Use the existing 'make inspect' command to cleanly format the db output
make inspect
