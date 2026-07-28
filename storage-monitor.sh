#!/bin/sh
# Background storage monitoring service for Supabase offloading
set -eu

# Wait for Hermes to initialize
sleep 30

# Check if Supabase is configured
if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_KEY:-}${SUPABASE_SECRET_KEY:-}" ]; then
    echo "SUPABASE_URL or SUPABASE_KEY not configured. Storage monitoring disabled."
    exit 0
fi

echo "Starting Supabase storage monitoring..."

# Run monitoring loop using the Hermes venv Python (check every 5 minutes)
/opt/hermes/.venv/bin/python3 /usr/local/bin/supabase_storage.py monitor 300
