---
name: email-client
description: Send client communication emails (PBC summaries, queries, progress reports) via Gmail API with optional attachments
argument-hint: "[client name] [email type: pbc|query|progress|general]"
---

# Email Client — Gmail Automation Skill

Send professional client emails directly from the Project Manager agent using the Gmail API. Supports multiple email types, markdown-to-HTML conversion, and file attachments.

## Workflow

1. **Load engagement details**
   Read `engagement.json` from the project root to retrieve:
   - Client contact email(s)
   - Client name / entity name
   - Engagement manager name and email
   - Any CC recipients configured for the engagement

2. **Load or generate the memo**
   - Look for the most recent memo matching `notes/client_memo_YYYY-MM-DD.md`.
   - If no suitable memo exists, invoke `/client-summary` to generate one first.
   - The memo content becomes the email body.

3. **Convert markdown to HTML**
   - Use the `markdown_to_html()` helper in `send_email.py` to convert the memo's markdown into clean HTML suitable for email clients.

4. **Optionally attach files**
   - Check the `output/` directory for relevant Excel, PDF, or Word files.
   - Prompt the user to confirm which attachments to include (if any).

5. **Send the email**
   - Call `send_email.py` with the composed subject, HTML body, recipients, and attachments.
   - Log the sent message ID for audit purposes.

## Email Types

| Type       | Flag       | Typical Subject Pattern                        | Description                                      |
|------------|------------|------------------------------------------------|--------------------------------------------------|
| PBC        | `pbc`      | `[Client] — PBC Summary as at DD MMM YYYY`    | Summary of outstanding Prepared By Client items  |
| Query      | `query`    | `[Client] — Open Queries as at DD MMM YYYY`   | Consolidated list of open audit/review queries   |
| Progress   | `progress` | `[Client] — Engagement Progress Update`       | High-level progress report for the client        |
| General    | `general`  | *(user-specified)*                             | Free-form email with custom subject and body     |

## Example Email Structure

```
From: Engagement Manager <manager@firm.com>
To: client.contact@clientcorp.com
CC: partner@firm.com
Subject: Acme Corp — PBC Summary as at 08 Mar 2026

<html>
  <body style="font-family: Calibri, Arial, sans-serif; font-size: 14px; color: #333;">
    <p>Dear John,</p>

    <p>Please find below the updated PBC summary for Acme Corp as at 08 March 2026.</p>

    <h3>Outstanding Items (5)</h3>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
      <tr><th>#</th><th>Item</th><th>Due Date</th><th>Status</th></tr>
      <tr><td>1</td><td>Bank confirmation letters</td><td>15 Mar 2026</td><td>Pending</td></tr>
      ...
    </table>

    <p>Please let us know if you have any questions.</p>

    <p>Kind regards,<br/>
    Jane Smith<br/>
    Engagement Manager</p>
  </body>
</html>
```

## Usage Examples

```bash
# Send a PBC summary email to the client
/email-client "Acme Corp" pbc

# Send a query summary with an attachment
/email-client "Acme Corp" query

# Send a general email (will prompt for subject and body)
/email-client "Acme Corp" general

# Send a progress report
/email-client "Acme Corp" progress
```

## Standalone Script Usage

The underlying Python script can also be called directly:

```bash
python .claude/skills/email-client/scripts/send_email.py \
  --to "client@example.com" \
  --subject "Acme Corp — PBC Summary" \
  --body-file "notes/client_memo_2026-03-08.md" \
  --attach "output/pbc_tracker.xlsx"
```

## First-Time Setup

Before this skill can send emails, you need to configure Gmail API access:

### Step 1 — Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., "PM Agent Email").
3. Navigate to **APIs & Services > Library**.
4. Search for **Gmail API** and click **Enable**.

### Step 2 — Configure OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** user type (or Internal if using Google Workspace).
3. Fill in the required fields (app name, support email).
4. Add the scope: `https://www.googleapis.com/auth/gmail.send`.
5. Add your email as a test user.

### Step 3 — Create OAuth Credentials

1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. Select **Desktop app** as the application type.
4. Download the JSON file.
5. Save it as `.claude/gmail/credentials.json` in the project root.

### Step 4 — Run the Auth Flow

```bash
python .claude/skills/email-client/scripts/gmail_auth.py
```

This will open your browser for Google authorization. After granting access, the token is saved automatically.

### Step 5 — Install Dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## Token Storage

- **credentials.json** — stored at `.claude/gmail/credentials.json` (do NOT commit to version control)
- **token.json** — stored at `.claude/gmail/token.json` (auto-generated after first auth, gitignored)

Both files are excluded via `.gitignore`. If the token expires or is revoked, delete `token.json` and re-run the auth script.
