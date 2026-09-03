#!/usr/bin/env python3
"""
Microsoft Graph OAuth2 Setup for Outlook
=========================================
Authenticates to charlesaprescott@outlook.com using Microsoft Graph API
with device code flow (no password needed, works with 2FA).

Usage:
    python scripts/outlook_auth.py          # Interactive auth
    python scripts/outlook_auth.py --check  # Check if token is valid
    python scripts/outlook_auth.py --test   # Send test email
"""
import json, os, sys, time, webbrowser
from pathlib import Path

TOKEN_FILE = Path(__file__).parent.parent / "data" / "outlook_token.json"

# Note: offline_access is NOT included here - MSAL adds it automatically
# for acquire_token_silent to work with refresh tokens
GRAPH_SCOPES = [
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/Mail.ReadWrite",
]

# You need to register an app at https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
# 1. Click "New registration" → Name: "GrantWizard Outlook"
# 2. Supported account types: "Accounts in any organizational directory (Any Microsoft account - Multitenant)"
# 3. Redirect URI: "Public client/native" → "https://login.microsoftonline.com/common/oauth2/nativeclient"
# 4. Click Register, then copy the Application (client) ID below
# 5. Under "Authentication", toggle "Allow public client flows" to ON
CLIENT_ID = os.environ.get("OUTLOOK_CLIENT_ID", "PASTE_YOUR_CLIENT_ID_HERE")
# 'common' accepts BOTH personal Microsoft accounts AND work/school accounts
# Only works if app is registered as multi-tenant ("Any Microsoft account")
AUTHORITY = os.environ.get("OUTLOOK_AUTHORITY", "https://login.microsoftonline.com/common")
USER_EMAIL = "charlesaprescott@outlook.com"

def log(msg):
    print(f"[outlook] {msg}")

def get_msal_app():
    try:
        from msal import PublicClientApplication, SerializableTokenCache
    except ImportError:
        print("Need msal: pip install msal")
        sys.exit(1)
    
    cache = SerializableTokenCache()
    if TOKEN_FILE.exists():
        try:
            cache.deserialize(TOKEN_FILE.read_text())
        except:
            pass
    
    app = PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )
    return app, cache

def authenticate():
    """Device code flow - user authenticates in browser."""
    if CLIENT_ID == "PASTE_YOUR_CLIENT_ID_HERE":
        print("\n⚠ OUTLOOK_CLIENT_ID not configured!")
        print("=" * 60)
        print("To use Outlook with OAuth2, register an app on Azure Portal:")
        print("  1. Go to: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade")
        print("  2. Click 'New registration'")
        print("  3. Name: 'GrantWizard Outlook'")
        print("  4. Supported account types: 'Accounts in any organizational directory'")
        print("  5. Redirect URI: Public client → https://login.microsoftonline.com/common/oauth2/nativeclient")
        print("  6. Click Register, copy the Application (client) ID")
        print("  7. Under Authentication → Enable 'Allow public client flows'")
        print("=" * 60)
        print("Then set: $env:OUTLOOK_CLIENT_ID='your-client-id-here'")
        print("And re-run this script.\n")
        return None
    
    app, cache = get_msal_app()
    
    # Check if we already have a valid token
    accounts = app.get_accounts()
    for acc in accounts:
        if acc.get("username", "").lower() == USER_EMAIL:
            log(f"Found existing account: {acc['username']}")
            result = app.acquire_token_silent(GRAPH_SCOPES, account=acc)
            if result and "access_token" in result:
                log("✓ Valid token found (silent refresh)")
                if TOKEN_FILE:
                    TOKEN_FILE.write_text(cache.serialize())
                return result
    
    # Need interactive auth
    log("Starting device code flow...")
    log(f"Authenticate as: {USER_EMAIL}")
    
    flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
    if "user_code" not in flow:
        print(f"Device flow failed: {flow.get('error_description', 'unknown')}")
        return None
    
    print(f"\n{'='*60}")
    print(f"1. Open this URL in your browser:")
    print(f"   {flow['verification_uri']}")
    print(f"\n2. Enter this code: {flow['user_code']}")
    print(f"{'='*60}\n")
    
    # Try to open browser automatically
    try:
        webbrowser.open(flow['verification_uri'])
        log("Browser opened (if not, copy the URL manually)")
    except:
        pass
    
    result = app.acquire_token_by_device_flow(flow)
    
    if "access_token" in result:
        TOKEN_FILE.write_text(cache.serialize())
        log("✓ Authentication successful! Token saved.")
        return result
    else:
        print(f"Auth failed: {result.get('error_description', result.get('error', 'unknown'))}")
        return None

def check_token():
    """Verify the token is valid."""
    app, cache = get_msal_app()
    accounts = app.get_accounts()
    
    for acc in accounts:
        if acc.get("username", "").lower() == USER_EMAIL:
            result = app.acquire_token_silent(GRAPH_SCOPES, account=acc)
            if result and "access_token" in result:
                # Parse JWT to see expiry
                import base64
                parts = result["access_token"].split(".")
                if len(parts) == 3:
                    padding = 4 - len(parts[1]) % 4
                    if padding != 4:
                        parts[1] += "=" * padding
                    try:
                        payload = json.loads(base64.b64decode(parts[1]))
                        exp = payload.get("exp", 0)
                        from datetime import datetime
                        expires = datetime.fromtimestamp(exp)
                        log(f"✓ Token valid until: {expires}")
                        log(f"  Scopes: {result.get('scope', 'N/A')}")
                    except:
                        log("✓ Token valid (can't parse expiry)")
                return True
    
    log("No valid token found. Run 'outlook_auth.py' without --check first.")
    return False

def send_test_email():
    """Send a test email to verify Send capability."""
    result = authenticate()
    if not result:
        return
    
    access_token = result["access_token"]
    
    import urllib.request
    
    email_data = {
        "message": {
            "subject": "GrantWizard Outlook Auth Test",
            "body": {
                "contentType": "Text",
                "content": "This is a test email from the GrantWizard pipeline.\n\nOutlook OAuth2 authentication is working!\n\n- GrantWizard Bot"
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": USER_EMAIL
                    }
                }
            ]
        },
        "saveToSentItems": True
    }
    
    body = json.dumps(email_data).encode()
    r = urllib.request.Request(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(r, timeout=15) as f:
            log(f"✓ Test email sent to {USER_EMAIL}! Status: {f.status}")
    except urllib.error.HTTPError as e:
        log(f"✗ Send failed: {e.code} {e.reason}")
        log(f"  {e.read().decode()[:300]}")
    except Exception as e:
        log(f"✗ Send failed: {e}")

def main():
    if "--check" in sys.argv:
        check_token()
    elif "--test" in sys.argv:
        send_test_email()
    else:
        authenticate()

if __name__ == "__main__":
    main()
