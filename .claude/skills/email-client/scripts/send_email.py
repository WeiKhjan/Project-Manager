#!/usr/bin/env python3
"""
Send Email via Gmail API

Sends HTML emails through an authenticated Gmail API service.
Supports CC, BCC, file attachments, and markdown-to-HTML conversion.

Usage (as module):
    from send_email import send_email, markdown_to_html
    html = markdown_to_html(open("memo.md").read())
    msg_id = send_email(
        to="client@example.com",
        subject="PBC Summary",
        html_body=html,
        attachments=["output/tracker.xlsx"],
    )

Usage (standalone):
    python send_email.py \\
        --to "client@example.com" \\
        --subject "Acme Corp — PBC Summary" \\
        --body-file "notes/client_memo_2026-03-08.md" \\
        --attach "output/pbc_tracker.xlsx" \\
        --cc "partner@firm.com" \\
        --from-name "Jane Smith"
"""

import argparse
import base64
import mimetypes
import os
import re
import sys

from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

# Import the auth helper from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gmail_auth import get_gmail_service  # noqa: E402


# ---------------------------------------------------------------------------
# Markdown to HTML converter (regex-based, no external library)
# ---------------------------------------------------------------------------

def markdown_to_html(md_text):
    """
    Convert basic markdown text to HTML suitable for email rendering.

    Supports:
        - Headers (h1–h4)
        - Bold (**text** or __text__)
        - Italic (*text* or _text_)
        - Inline code (`code`)
        - Unordered lists (- item or * item)
        - Ordered lists (1. item)
        - Simple markdown tables
        - Horizontal rules (--- or ***)
        - Paragraphs and line breaks

    Args:
        md_text: Raw markdown string.

    Returns:
        str: HTML string wrapped in a basic email-friendly template.
    """
    if not md_text:
        return ""

    lines = md_text.strip().split("\n")
    html_parts = []
    in_ul = False
    in_ol = False
    in_table = False
    paragraph_buffer = []

    def _flush_paragraph():
        if paragraph_buffer:
            text = " ".join(paragraph_buffer)
            html_parts.append(f"<p>{_inline(text)}</p>")
            paragraph_buffer.clear()

    def _close_list():
        nonlocal in_ul, in_ol
        if in_ul:
            html_parts.append("</ul>")
            in_ul = False
        if in_ol:
            html_parts.append("</ol>")
            in_ol = False

    def _close_table():
        nonlocal in_table
        if in_table:
            html_parts.append("</table>")
            in_table = False

    def _inline(text):
        """Apply inline formatting (bold, italic, code)."""
        # Inline code
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        # Bold (**text** or __text__)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
        # Italic (*text* or _text_) — avoid matching already-processed bold
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
        text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<em>\1</em>", text)
        # Links [text](url)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        return text

    def _is_table_separator(line):
        """Check if a line is a markdown table separator (e.g., |---|---|)."""
        return bool(re.match(r"^\|[\s\-:|]+\|$", line.strip()))

    def _parse_table_row(line):
        """Split a markdown table row into cells."""
        cells = line.strip().strip("|").split("|")
        return [c.strip() for c in cells]

    for line in lines:
        stripped = line.strip()

        # --- Blank line: flush buffers ---
        if not stripped:
            _flush_paragraph()
            _close_list()
            _close_table()
            continue

        # --- Horizontal rule ---
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            _flush_paragraph()
            _close_list()
            _close_table()
            html_parts.append("<hr/>")
            continue

        # --- Headers ---
        header_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if header_match:
            _flush_paragraph()
            _close_list()
            _close_table()
            level = len(header_match.group(1))
            text = _inline(header_match.group(2))
            html_parts.append(f"<h{level}>{text}</h{level}>")
            continue

        # --- Table rows ---
        if stripped.startswith("|") and stripped.endswith("|"):
            _flush_paragraph()
            _close_list()

            # Skip separator rows
            if _is_table_separator(stripped):
                continue

            if not in_table:
                in_table = True
                html_parts.append(
                    '<table border="1" cellpadding="6" cellspacing="0" '
                    'style="border-collapse: collapse; width: 100%;">'
                )
                # First row is the header
                cells = _parse_table_row(stripped)
                row_html = "".join(
                    f"<th style=\"background-color: #f2f2f2; text-align: left;\">"
                    f"{_inline(c)}</th>"
                    for c in cells
                )
                html_parts.append(f"<tr>{row_html}</tr>")
            else:
                cells = _parse_table_row(stripped)
                row_html = "".join(
                    f"<td>{_inline(c)}</td>" for c in cells
                )
                html_parts.append(f"<tr>{row_html}</tr>")
            continue

        # Close table if we're no longer in table rows
        _close_table()

        # --- Unordered list ---
        ul_match = re.match(r"^[\-\*]\s+(.+)$", stripped)
        if ul_match:
            _flush_paragraph()
            if in_ol:
                _close_list()
            if not in_ul:
                in_ul = True
                html_parts.append("<ul>")
            html_parts.append(f"<li>{_inline(ul_match.group(1))}</li>")
            continue

        # --- Ordered list ---
        ol_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ol_match:
            _flush_paragraph()
            if in_ul:
                _close_list()
            if not in_ol:
                in_ol = True
                html_parts.append("<ol>")
            html_parts.append(f"<li>{_inline(ol_match.group(1))}</li>")
            continue

        # Close lists if this line is not a list item
        _close_list()

        # --- Regular text: accumulate into paragraph ---
        paragraph_buffer.append(stripped)

    # Flush remaining buffers
    _flush_paragraph()
    _close_list()
    _close_table()

    body_html = "\n".join(html_parts)

    # Wrap in a simple email-friendly HTML template
    return (
        '<div style="font-family: Calibri, Arial, sans-serif; '
        'font-size: 14px; color: #333; line-height: 1.6;">\n'
        f"{body_html}\n"
        "</div>"
    )


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

# Allowed attachment extensions
ALLOWED_EXTENSIONS = {".xlsx", ".pdf", ".docx", ".zip"}


def send_email(to, subject, html_body, cc=None, bcc=None, attachments=None,
               from_name=None):
    """
    Send an email via the Gmail API.

    Args:
        to (str | list): Recipient email address(es). A single string or a
            list of strings.
        subject (str): Email subject line.
        html_body (str): HTML content for the email body.
        cc (str | list | None): CC recipient(s).
        bcc (str | list | None): BCC recipient(s).
        attachments (list[str] | None): File paths to attach. Only .xlsx,
            .pdf, .docx, and .zip files are supported.
        from_name (str | None): Display name for the sender (e.g.,
            "Jane Smith"). If not provided, Gmail uses the account default.

    Returns:
        str: The Gmail message ID of the sent email.

    Raises:
        FileNotFoundError: If an attachment path does not exist.
        ValueError: If an attachment has an unsupported extension.
        Exception: On Gmail API errors.
    """
    service = get_gmail_service()

    # Normalize recipients to comma-separated strings
    def _join(addr):
        if addr is None:
            return None
        if isinstance(addr, list):
            return ", ".join(addr)
        return addr

    to_str = _join(to)
    cc_str = _join(cc)
    bcc_str = _join(bcc)

    # Decide message type based on attachments
    has_attachments = attachments and len(attachments) > 0

    if has_attachments:
        message = MIMEMultipart("mixed")
        message.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        message = MIMEMultipart()
        message.attach(MIMEText(html_body, "html", "utf-8"))

    # --- Headers ---
    message["To"] = to_str
    message["Subject"] = subject

    if from_name:
        # Gmail will still send from the authenticated account, but the
        # display name will be shown to recipients.
        message["From"] = f"{from_name} <me>"

    if cc_str:
        message["Cc"] = cc_str
    if bcc_str:
        message["Bcc"] = bcc_str

    # --- Attachments ---
    if has_attachments:
        for filepath in attachments:
            filepath = os.path.abspath(filepath)

            if not os.path.isfile(filepath):
                raise FileNotFoundError(
                    f"Attachment not found: {filepath}"
                )

            ext = os.path.splitext(filepath)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise ValueError(
                    f"Unsupported attachment type '{ext}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                )

            content_type, _ = mimetypes.guess_type(filepath)
            if content_type is None:
                content_type = "application/octet-stream"

            main_type, sub_type = content_type.split("/", 1)

            with open(filepath, "rb") as f:
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(f.read())

            encoders.encode_base64(attachment)
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(filepath),
            )
            message.attach(attachment)

    # --- Encode and send ---
    raw_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("ascii")

    sent = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw_message})
        .execute()
    )

    msg_id = sent.get("id", "unknown")
    print(f"[send_email] Email sent successfully. Message ID: {msg_id}")
    return msg_id


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def main():
    """Parse command-line arguments and send an email."""
    parser = argparse.ArgumentParser(
        description="Send an email via Gmail API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python send_email.py --to "client@example.com" '
            '--subject "Summary" --body-file memo.md\n'
            '  python send_email.py --to "a@x.com" --to "b@x.com" '
            '--subject "Report" --body "Hello" --attach report.xlsx\n'
        ),
    )

    parser.add_argument(
        "--to",
        required=True,
        action="append",
        help="Recipient email address (can be specified multiple times)",
    )
    parser.add_argument(
        "--subject",
        required=True,
        help="Email subject line",
    )
    parser.add_argument(
        "--body",
        default=None,
        help="Plain text or HTML body (use --body-file for markdown files)",
    )
    parser.add_argument(
        "--body-file",
        default=None,
        help="Path to a markdown (.md) file whose content will be converted "
             "to HTML and used as the email body",
    )
    parser.add_argument(
        "--cc",
        action="append",
        default=None,
        help="CC recipient (can be specified multiple times)",
    )
    parser.add_argument(
        "--bcc",
        action="append",
        default=None,
        help="BCC recipient (can be specified multiple times)",
    )
    parser.add_argument(
        "--attach",
        action="append",
        default=None,
        dest="attachments",
        help="File to attach (can be specified multiple times). "
             "Supported: .xlsx, .pdf, .docx, .zip",
    )
    parser.add_argument(
        "--from-name",
        default=None,
        help="Display name for the sender (e.g., 'Jane Smith')",
    )

    args = parser.parse_args()

    # --- Resolve body ---
    if args.body_file:
        body_path = os.path.abspath(args.body_file)
        if not os.path.isfile(body_path):
            print(f"[send_email] Error: Body file not found: {body_path}",
                  file=sys.stderr)
            sys.exit(1)

        with open(body_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        html_body = markdown_to_html(md_content)
        print(f"[send_email] Converted {body_path} to HTML.")

    elif args.body:
        # Treat as raw HTML if it contains tags, otherwise wrap in <p>
        if "<" in args.body and ">" in args.body:
            html_body = args.body
        else:
            html_body = f"<p>{args.body}</p>"

    else:
        print("[send_email] Error: Provide --body or --body-file.",
              file=sys.stderr)
        sys.exit(1)

    # --- Resolve recipients ---
    to_addrs = args.to if len(args.to) > 1 else args.to[0]

    # --- Send ---
    try:
        msg_id = send_email(
            to=to_addrs,
            subject=args.subject,
            html_body=html_body,
            cc=args.cc,
            bcc=args.bcc,
            attachments=args.attachments,
            from_name=args.from_name,
        )
        print(f"[send_email] Done. Message ID: {msg_id}")
    except FileNotFoundError as exc:
        print(f"[send_email] Attachment error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"[send_email] Validation error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"[send_email] Failed to send email: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
