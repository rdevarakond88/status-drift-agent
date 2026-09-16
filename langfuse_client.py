#!/usr/bin/env python3
"""Minimal stdlib-only Langfuse ingestion client, shared by the historical
backfill (import_historical_traces.py) and the live tracing wired into
prompt_contract_layer.call_claude. Uses urllib rather than requests so
neither caller needs anything installed beyond the standard library -
tracing must never be the reason this pipeline needs a venv.

Credentials come from langfuse/.env (the local self-hosted stack's
auto-provisioned keys) or LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY/
LANGFUSE_HOST env vars if set. Missing credentials are not an error -
load_credentials() returns None and callers treat tracing as an optional,
best-effort side effect.
"""

import base64
import json
import os
import urllib.request

_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "langfuse", ".env")


def load_credentials():
    creds = {}
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                creds[k] = v
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", creds.get("LANGFUSE_INIT_PROJECT_PUBLIC_KEY"))
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", creds.get("LANGFUSE_INIT_PROJECT_SECRET_KEY"))
    if not public_key or not secret_key:
        return None
    return {
        "public_key": public_key,
        "secret_key": secret_key,
        "host": os.environ.get("LANGFUSE_HOST", "http://localhost:3000"),
    }


def push_batch(events, creds, timeout=10):
    body = json.dumps({"batch": events}).encode("utf-8")
    auth = base64.b64encode(f"{creds['public_key']}:{creds['secret_key']}".encode()).decode()
    req = urllib.request.Request(
        f"{creds['host']}/api/public/ingestion",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def usage_details(usage):
    """Maps an Anthropic-shaped usage dict (input_tokens, output_tokens,
    cache_read_input_tokens, cache_creation_input_tokens,
    output_tokens_details.thinking_tokens) to Langfuse's usageDetails
    shape. Returns None if there's nothing to report."""
    if not usage:
        return None
    details = {
        "input": usage.get("input_tokens"),
        "output": usage.get("output_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
    }
    thinking = (usage.get("output_tokens_details") or {}).get("thinking_tokens")
    if thinking:
        details["thinking"] = thinking
    details = {k: v for k, v in details.items() if v is not None}
    return details or None
