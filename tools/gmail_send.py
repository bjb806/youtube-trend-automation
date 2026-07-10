"""Send an email with a PDF attachment via the Gmail API.

First-time setup (must be run locally, once, with a browser available):
    python tools/gmail_send.py --to you@example.com --subject test \\
        --body-file some.txt --attachment some.pdf
    -> opens a browser for OAuth consent, writes token.json

After that, the same command works headlessly (token.json holds a refresh
token) as long as the OAuth consent screen is in "production" status - in
"testing" status Google expires the refresh token every 7 days, which would
silently break the daily cloud run.

CLI:
    python tools/gmail_send.py --to you@example.com --subject "..." \\
        --body-file .tmp/email_body.txt --attachment .tmp/report_20260709.pdf
"""
import argparse
import base64
import os
import sys
from email.message import EmailMessage

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"


class GmailAuthError(Exception):
    """Raised when Gmail auth needs a manual, interactive re-authorization."""


def materialize_credential_files():
    """In a cloud sandbox there's no local credentials.json/token.json - only
    env vars. Write them out once per run so the rest of this module can work
    unchanged whether running locally or in the cloud."""
    if not os.path.exists(CREDENTIALS_PATH) and os.environ.get("GMAIL_CREDENTIALS_JSON"):
        with open(CREDENTIALS_PATH, "w") as f:
            f.write(os.environ["GMAIL_CREDENTIALS_JSON"])
    if not os.path.exists(TOKEN_PATH) and os.environ.get("GMAIL_TOKEN_JSON"):
        with open(TOKEN_PATH, "w") as f:
            f.write(os.environ["GMAIL_TOKEN_JSON"])


def get_credentials():
    materialize_credential_files()
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise GmailAuthError(
                f"Gmail token refresh failed ({e}). Run this script locally once "
                "to re-authorize (needs a browser)."
            ) from e
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        return creds

    if not os.path.exists(CREDENTIALS_PATH):
        raise GmailAuthError(
            f"{CREDENTIALS_PATH} not found. Download an OAuth client (Desktop app) "
            "from Google Cloud Console and save it as credentials.json."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
    return creds


def send_email(to, subject, body_text, attachment_path=None):
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body_text)

    if attachment_path:
        with open(attachment_path, "rb") as f:
            attachment_data = f.read()
        message.add_attachment(
            attachment_data, maintype="application", subtype="pdf",
            filename=os.path.basename(attachment_path),
        )

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": encoded_message}).execute()
    return result["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--attachment")
    args = parser.parse_args()

    with open(args.body_file, "r", encoding="utf-8") as f:
        body_text = f.read()

    try:
        message_id = send_email(args.to, args.subject, body_text, args.attachment)
    except GmailAuthError as e:
        print(f"[error] Gmail auth needs manual attention: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"[ok] sent message {message_id} to {args.to}")


if __name__ == "__main__":
    main()
