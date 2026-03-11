#!/usr/bin/env python3
"""
Gmail OAuth2 Authentication Module

Handles authentication with the Gmail API using OAuth2 credentials.
Provides a reusable `get_gmail_service()` function that returns an
authenticated Gmail API service object.

Setup:
    1. Place your OAuth2 credentials.json at .claude/gmail/credentials.json
    2. Run this script directly to complete the initial auth flow
    3. Token is saved to .claude/gmail/token.json for future use

Usage:
    from gmail_auth import get_gmail_service
    service = get_gmail_service()
"""

import os
import stat
import sys
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scope — send-only permission
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Resolve paths relative to the project root.
# The project root is four levels up from this script:
#   .claude/skills/email-client/scripts/gmail_auth.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))

GMAIL_DIR = os.path.join(PROJECT_ROOT, ".claude", "gmail")
CREDENTIALS_PATH = os.path.join(GMAIL_DIR, "credentials.json")
TOKEN_PATH = os.path.join(GMAIL_DIR, "token.json")


def _ensure_gmail_dir():
    """Create the .claude/gmail directory if it does not exist."""
    os.makedirs(GMAIL_DIR, exist_ok=True)


def _print_setup_instructions():
    """Print clear instructions when credentials.json is missing."""
    print("=" * 64)
    print("  GMAIL API — CREDENTIALS NOT FOUND")
    print("=" * 64)
    print()
    print("  The file 'credentials.json' was not found at:")
    print(f"    {CREDENTIALS_PATH}")
    print()
    print("  To set up Gmail API access:")
    print()
    print("  1. Go to https://console.cloud.google.com/")
    print("  2. Create a project and enable the Gmail API.")
    print("  3. Go to APIs & Services > Credentials.")
    print("  4. Create an OAuth 2.0 Client ID (Desktop app).")
    print("  5. Download the JSON file.")
    print("  6. Save it as:")
    print(f"       {CREDENTIALS_PATH}")
    print()
    print("  Then re-run this script to complete the OAuth flow.")
    print("=" * 64)


def get_gmail_service():
    """
    Return an authenticated Gmail API service object.

    - If a valid token exists at TOKEN_PATH, it is loaded and reused.
    - If the token is expired but has a refresh token, it is refreshed
      automatically.
    - If no token exists, the full OAuth2 flow is initiated (opens a
      browser window for the user to authorize access).

    Returns:
        googleapiclient.discovery.Resource: Authenticated Gmail service.

    Raises:
        SystemExit: If credentials.json is missing and the OAuth flow
                    cannot be started.
    """
    _ensure_gmail_dir()

    creds = None

    # --- Attempt to load existing token ---
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"[gmail_auth] Warning: Could not read token.json ({exc}). "
                  "Re-authenticating...")
            creds = None

    # --- Refresh or run new auth flow ---
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[gmail_auth] Refreshing expired token...")
            try:
                creds.refresh(Request())
            except Exception as exc:
                print(f"[gmail_auth] Token refresh failed ({exc}). "
                      "Running full auth flow...")
                creds = None

        if not creds:
            # Need to run the full OAuth flow
            if not os.path.exists(CREDENTIALS_PATH):
                _print_setup_instructions()
                sys.exit(1)

            print("[gmail_auth] Starting OAuth2 authorization flow...")
            print("[gmail_auth] A browser window will open. Please sign in "
                  "and grant Gmail send permission.")
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
            print("[gmail_auth] Authorization successful.")

        # Save the token for future runs with restricted permissions
        with open(TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
        # Restrict token file to owner-only read/write (0o600)
        try:
            os.chmod(TOKEN_PATH, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # chmod may not fully apply on Windows, but best effort
        print(f"[gmail_auth] Token saved to {TOKEN_PATH}")

    # --- Build and return the Gmail service ---
    service = build("gmail", "v1", credentials=creds)
    return service


# --- Direct execution: run the auth flow interactively ---
if __name__ == "__main__":
    print("[gmail_auth] Gmail API Authentication Setup")
    print(f"[gmail_auth] Project root : {PROJECT_ROOT}")
    print(f"[gmail_auth] Credentials  : {CREDENTIALS_PATH}")
    print(f"[gmail_auth] Token        : {TOKEN_PATH}")
    print()

    svc = get_gmail_service()

    # Quick verification — fetch the authenticated user's email address
    try:
        profile = svc.users().getProfile(userId="me").execute()
        print(f"[gmail_auth] Authenticated as: {profile.get('emailAddress')}")
        print("[gmail_auth] Setup complete. You can now send emails.")
    except Exception as exc:
        print(f"[gmail_auth] Service created but profile check failed: {exc}")
        print("[gmail_auth] The token was saved. Try running send_email.py.")
