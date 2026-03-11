"""
PM Dashboard Server — Lightweight HTTP server for the Project Manager dashboard.

Serves pm_viewer.html and provides JSON API endpoints for engagement data,
PBC tracking, query lists, and live sub-agent status probes.

Port: 8100
Dependencies: Python stdlib only (http.server, json, os, re, urllib)

Usage:
    python server.py
    # Opens http://localhost:8100 in the default browser
"""

import http.server
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so we can import from tools/
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.pm_engine import PMEngine
from tools.status_reader import StatusReader

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PORT = 8100
CLIENTS_DIR = os.path.realpath(os.path.join(PROJECT_ROOT, "Clients"))

# Instantiate core tools
engine = PMEngine(CLIENTS_DIR)
status_reader = StatusReader()

# MIME types for static file serving
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

# Whitelist of static file extensions that can be served
ALLOWED_STATIC_EXTENSIONS = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico"}


def _is_safe_client_folder(client_folder: str) -> bool:
    """Validate that a client folder name resolves within CLIENTS_DIR."""
    resolved = os.path.realpath(os.path.join(CLIENTS_DIR, client_folder))
    return resolved.startswith(CLIENTS_DIR + os.sep) or resolved == CLIENTS_DIR


# ---------------------------------------------------------------------------
# Markdown table parser (for PBC and query files)
# ---------------------------------------------------------------------------

def parse_markdown_table(content: str) -> list:
    """Parse markdown tables from content and return rows as list of dicts."""
    results = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Look for table header row followed by separator
        if "|" in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            separator_clean = next_line.replace(" ", "").replace("|", "").replace("-", "").replace(":", "")
            if len(separator_clean) == 0 and "-" in next_line:
                # This is a table header + separator
                headers = split_table_row(line)
                headers = [h.strip().lower() for h in headers]
                i += 2  # skip header and separator
                while i < len(lines):
                    row_line = lines[i].strip()
                    if not row_line or "|" not in row_line:
                        break
                    # skip any additional separator rows
                    sep_check = row_line.replace(" ", "").replace("|", "").replace("-", "").replace(":", "")
                    if len(sep_check) == 0 and "-" in row_line:
                        i += 1
                        continue
                    cells = split_table_row(row_line)
                    row_dict = {}
                    for col_idx, header in enumerate(headers):
                        if col_idx < len(cells):
                            row_dict[header] = cells[col_idx].strip()
                        else:
                            row_dict[header] = ""
                    results.append(row_dict)
                    i += 1
                continue
        i += 1
    return results


def split_table_row(line: str) -> list:
    """Split a markdown table row on pipe delimiters."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def get_dashboard_data() -> dict:
    """Build aggregated dashboard data for all clients."""
    engagements = engine.list_engagements()
    all_deadlines = engine.get_all_deadlines()

    total_pbc_outstanding = 0
    total_open_queries = 0
    upcoming_deadline_count = 0

    enriched_clients = []
    for eng in engagements:
        folder = eng["folder"]
        try:
            full_data = engine.load_engagement(folder)
        except FileNotFoundError:
            full_data = {}

        pbc_summary = full_data.get("pbc_summary", {})
        queries_summary = full_data.get("queries_summary", {})
        deadlines = full_data.get("deadlines", [])

        total_pbc_outstanding += pbc_summary.get("outstanding", 0)
        total_open_queries += queries_summary.get("open", 0)

        # Count upcoming deadlines (within 30 days)
        for dl in deadlines:
            dl_date = dl.get("date", dl.get("deadline", ""))
            if dl_date:
                try:
                    dt = datetime.strptime(dl_date, "%Y-%m-%d")
                    days_remaining = (dt - datetime.now()).days
                    if 0 <= days_remaining <= 30:
                        upcoming_deadline_count += 1
                except ValueError:
                    pass

        # Also check per-service deadlines
        services = full_data.get("services", {})
        for svc_key, svc_data in services.items():
            if svc_data.get("enabled") and svc_data.get("deadline"):
                try:
                    dt = datetime.strptime(svc_data["deadline"], "%Y-%m-%d")
                    days_remaining = (dt - datetime.now()).days
                    if 0 <= days_remaining <= 30:
                        upcoming_deadline_count += 1
                except ValueError:
                    pass

        client_info = full_data.get("client", {})
        enriched_clients.append({
            "folder": folder,
            "legal_name": eng.get("legal_name", folder),
            "display_name": eng.get("display_name", ""),
            "fye_date": client_info.get("fye_date", ""),
            "services": eng.get("services", {}),
            "services_detail": {
                k: {
                    "enabled": v.get("enabled", False),
                    "status": v.get("status", "not_started"),
                    "progress_pct": v.get("progress_pct", 0),
                    "deadline": v.get("deadline", ""),
                }
                for k, v in services.items()
            },
            "overall_status": eng.get("overall_status", "not_started"),
            "overall_progress_pct": eng.get("overall_progress_pct", 0),
            "pbc_summary": pbc_summary,
            "queries_summary": queries_summary,
            "deadlines": deadlines,
        })

    # Enrich deadlines with days remaining
    enriched_deadlines = []
    for dl in all_deadlines:
        dl_date = dl.get("deadline", "")
        days_remaining = None
        if dl_date:
            try:
                dt = datetime.strptime(dl_date, "%Y-%m-%d")
                days_remaining = (dt - datetime.now()).days
            except ValueError:
                pass
        enriched_deadlines.append({
            **dl,
            "days_remaining": days_remaining,
        })

    return {
        "clients": enriched_clients,
        "kpi": {
            "total_clients": len(enriched_clients),
            "pbc_outstanding": total_pbc_outstanding,
            "open_queries": total_open_queries,
            "upcoming_deadlines": upcoming_deadline_count,
        },
        "deadlines": enriched_deadlines,
    }


def get_pbc_data(client_folder: str) -> dict:
    """Read and parse pbc_consolidated.md for a client."""
    pbc_path = os.path.join(CLIENTS_DIR, client_folder, "pbc_consolidated.md")
    if not os.path.isfile(pbc_path):
        return {"items": [], "stats": {"total": 0, "received": 0, "outstanding": 0, "not_applicable": 0}}

    with open(pbc_path, "r", encoding="utf-8") as f:
        content = f.read()

    rows = parse_markdown_table(content)
    items = []
    received = 0
    outstanding = 0
    not_applicable = 0

    for row in rows:
        # Skip summary/metric rows
        doc = row.get("document", "") or row.get("item", "") or row.get("description", "")
        if not doc or doc.lower().startswith(("total", "metric", "**")):
            continue

        status = row.get("status", "Outstanding")
        status_lower = status.strip().lower()
        if "received" in status_lower or "derived" in status_lower:
            received += 1
        elif "n/a" in status_lower or "not applicable" in status_lower:
            not_applicable += 1
        else:
            outstanding += 1

        items.append({
            "ref": row.get("ref", ""),
            "document": doc,
            "needed_for": row.get("needed for", ""),
            "status": status,
            "date_received": row.get("date received", ""),
            "remarks": row.get("remarks", ""),
        })

    total = received + outstanding + not_applicable
    return {
        "items": items,
        "stats": {
            "total": total,
            "received": received,
            "outstanding": outstanding,
            "not_applicable": not_applicable,
        },
    }


def get_queries_data(client_folder: str) -> dict:
    """Read and parse queries_consolidated.md for a client."""
    queries_path = os.path.join(CLIENTS_DIR, client_folder, "queries_consolidated.md")
    if not os.path.isfile(queries_path):
        return {"items": [], "stats": {"total": 0, "open": 0, "resolved": 0}}

    with open(queries_path, "r", encoding="utf-8") as f:
        content = f.read()

    rows = parse_markdown_table(content)
    items = []
    open_count = 0
    resolved_count = 0

    for row in rows:
        desc = row.get("description", "") or row.get("query", "") or row.get("item", "")
        if not desc or desc.lower().startswith(("total", "summary", "**")):
            continue

        status = row.get("status", "Open")
        status_lower = status.strip().lower()
        if "resolved" in status_lower or "closed" in status_lower or "answered" in status_lower:
            resolved_count += 1
        else:
            open_count += 1

        items.append({
            "pm_ref": row.get("pm ref", row.get("ref", row.get("no.", ""))),
            "service": row.get("service", ""),
            "description": desc,
            "amount": row.get("amount", row.get("amount (rm)", "")),
            "status": status,
            "date_raised": row.get("date raised", row.get("date", "")),
        })

    return {
        "items": items,
        "stats": {
            "total": open_count + resolved_count,
            "open": open_count,
            "resolved": resolved_count,
        },
    }


def get_status_data(client_folder: str) -> dict:
    """Live probe sub-agent folders for a client using StatusReader."""
    try:
        engagement = engine.load_engagement(client_folder)
    except FileNotFoundError:
        return {"error": f"Engagement not found: {client_folder}"}

    probe_results = status_reader.probe_all_services(engagement)
    return probe_results


def refresh_all() -> dict:
    """Re-scan all sub-agent folders and update engagement.json files."""
    engagements = engine.list_engagements()
    updated = []

    for eng in engagements:
        folder = eng["folder"]
        try:
            data = engine.load_engagement(folder)
        except FileNotFoundError:
            continue

        # Probe all services and update progress
        probe_results = status_reader.probe_all_services(data)
        services = data.get("services", {})

        for svc_key in ("audit", "tax", "compilation"):
            svc = services.get(svc_key, {})
            if not svc.get("enabled"):
                continue
            probe = probe_results.get(svc_key, {})
            if probe.get("exists") or probe.get("enabled") is not False:
                estimated = probe.get("estimated_progress", svc.get("progress_pct", 0))
                stage = probe.get("stage", svc.get("status", "not_started"))
                if estimated > 0:
                    svc["progress_pct"] = estimated
                if stage and stage != "not_started":
                    svc["status"] = stage

        engine.save_engagement(folder, data)
        updated.append(folder)

    return {"updated": updated, "count": len(updated)}


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------

class PMDashboardHandler(http.server.BaseHTTPRequestHandler):
    """Custom HTTP handler for the PM Dashboard."""

    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        query_params = urllib.parse.parse_qs(parsed.query)

        # Route: Serve dashboard HTML
        if path == "" or path == "/" or path == "/index.html":
            self._serve_file("pm_viewer.html")
            return

        # Route: /api/dashboard
        if path == "/api/dashboard":
            data = get_dashboard_data()
            self._send_json(data)
            return

        # Route: /api/engagements
        if path == "/api/engagements":
            data = engine.list_engagements()
            self._send_json(data)
            return

        # Route: /api/engagement/<client>
        match = re.match(r"^/api/engagement/(.+)$", path)
        if match:
            client_folder = urllib.parse.unquote(match.group(1))
            if not _is_safe_client_folder(client_folder):
                self._send_json({"error": "Invalid client folder"}, status=403)
                return
            try:
                data = engine.load_engagement(client_folder)
                self._send_json(data)
            except FileNotFoundError:
                self._send_json({"error": "Engagement not found"}, status=404)
            return

        # Route: /api/pbc/<client>
        match = re.match(r"^/api/pbc/(.+)$", path)
        if match:
            client_folder = urllib.parse.unquote(match.group(1))
            if not _is_safe_client_folder(client_folder):
                self._send_json({"error": "Invalid client folder"}, status=403)
                return
            data = get_pbc_data(client_folder)
            self._send_json(data)
            return

        # Route: /api/queries/<client>
        match = re.match(r"^/api/queries/(.+)$", path)
        if match:
            client_folder = urllib.parse.unquote(match.group(1))
            if not _is_safe_client_folder(client_folder):
                self._send_json({"error": "Invalid client folder"}, status=403)
                return
            data = get_queries_data(client_folder)
            self._send_json(data)
            return

        # Route: /api/status/<client>
        match = re.match(r"^/api/status/(.+)$", path)
        if match:
            client_folder = urllib.parse.unquote(match.group(1))
            if not _is_safe_client_folder(client_folder):
                self._send_json({"error": "Invalid client folder"}, status=403)
                return
            data = get_status_data(client_folder)
            self._send_json(data)
            return

        # Route: Static file serving
        self._serve_file(path.lstrip("/"))

    def do_POST(self):
        """Handle POST requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Route: /api/refresh
        if path == "/api/refresh":
            data = refresh_all()
            self._send_json(data)
            return

        self._send_json({"error": "Not found"}, status=404)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._add_cors_headers()
        self.end_headers()

    # --- Helper methods ---

    def _send_json(self, data, status=200):
        """Send a JSON response with proper headers."""
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath):
        """Serve a static file from the project root."""
        # Security: resolve to absolute path and verify it stays within PROJECT_ROOT
        full_path = os.path.realpath(os.path.join(PROJECT_ROOT, filepath))
        project_root_real = os.path.realpath(PROJECT_ROOT)
        if not (full_path.startswith(project_root_real + os.sep) or full_path == project_root_real):
            self._send_json({"error": "Forbidden"}, status=403)
            return

        # Only serve whitelisted static file extensions
        ext = os.path.splitext(full_path)[1].lower()
        if ext not in ALLOWED_STATIC_EXTENSIONS:
            self._send_json({"error": "Forbidden"}, status=403)
            return

        if not os.path.isfile(full_path):
            self._send_json({"error": "Not found"}, status=404)
            return

        ext = os.path.splitext(full_path)[1].lower()
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        try:
            with open(full_path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self._add_cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except IOError:
            self._send_json({"error": "Internal server error"}, status=500)

    def _add_cors_headers(self):
        """Add CORS headers restricted to localhost only."""
        self.send_header("Access-Control-Allow-Origin", f"http://localhost:{PORT}")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        """Custom log format."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {args[0]}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """Start the PM Dashboard server."""
    print("=" * 60)
    print("  PROJECT MANAGER DASHBOARD SERVER")
    print("=" * 60)
    print(f"  Port:        {PORT}")
    print(f"  Project:     {PROJECT_ROOT}")
    print(f"  Clients dir: {CLIENTS_DIR}")
    print(f"  URL:         http://localhost:{PORT}")
    print("=" * 60)
    print()

    # Check if Clients directory exists
    if not os.path.isdir(CLIENTS_DIR):
        print(f"[WARN] Clients directory not found: {CLIENTS_DIR}")
        print("       Dashboard will show no data until engagements are created.")
        print()

    server = http.server.HTTPServer(("127.0.0.1", PORT), PMDashboardHandler)
    print(f"Server running on http://localhost:{PORT}")
    print("Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


if __name__ == "__main__":
    main()
