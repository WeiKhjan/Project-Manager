"""
pm_engine.py - Core Data Management Layer for Project Manager Agent

Handles CRUD operations for client engagements stored as JSON files.
Each client engagement lives in Clients/<legal_name>/engagement.json
alongside a status_log.md for timestamped activity tracking.

No external dependencies -- uses only stdlib (json, os, datetime).
"""

import json
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# Project root -- all relative paths resolve from here
# ---------------------------------------------------------------------------
PROJECT_ROOT = r"C:\Users\khjan\Downloads\Pilot - Project Manager Main Agent"

# ---------------------------------------------------------------------------
# Sub-agent registry
# Maps service keys to their respective agent project directories,
# client-folder naming patterns, and human-readable descriptions.
# ---------------------------------------------------------------------------
SUB_AGENTS = {
    "audit": {
        "dir": r"C:\Users\khjan\Downloads\Pilot - Audit - Claude",
        "folder_pattern": "Clients/AWP_{client_name}_FYE{year}",
        "description": "Statutory Audit (ISA/MPERS/MFRS)",
    },
    "tax": {
        "dir": r"C:\Users\khjan\Downloads\Pilot - TAX- Calude",
        "folder_pattern": "Clients/{client_name} YA {ya_year}",
        "description": "Form C Tax Computation (ITA 1967)",
    },
    "compilation": {
        "dir": r"C:\Users\khjan\Downloads\Pilot - MPERS Compilation - Stand Alone - Claude",
        "folder_pattern": "Clients/{legal_name}",
        "description": "MPERS Financial Statements (ISRS 4410)",
    },
}


class PMEngine:
    """Core data-management layer for the Project Manager agent.

    Parameters
    ----------
    clients_dir : str, optional
        Path to the directory that holds all client folders.
        Defaults to ``Clients/`` relative to ``PROJECT_ROOT``.
    """

    def __init__(self, clients_dir: str = None):
        if clients_dir is None:
            self.clients_dir = os.path.join(PROJECT_ROOT, "Clients")
        else:
            self.clients_dir = clients_dir

        # Resolve to absolute path for safe comparisons
        self.clients_dir = os.path.realpath(self.clients_dir)

        # Ensure the Clients directory exists on initialisation
        os.makedirs(self.clients_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. create_engagement
    # ------------------------------------------------------------------
    def create_engagement(self, client_data: dict, services: dict) -> dict:
        """Create a new client engagement.

        Parameters
        ----------
        client_data : dict
            Keys: legal_name, display_name, registration_no, tax_file_no,
            fye_date, fy_start, reporting_framework, principal_activities,
            contact_person, contact_email, contact_phone.
        services : dict
            Keys: audit (bool), tax (bool), compilation (bool).

        Returns
        -------
        dict
            The full engagement data structure that was persisted.
        """
        legal_name = client_data.get("legal_name", "").strip()
        if not legal_name:
            raise ValueError("client_data must include a non-empty 'legal_name'.")

        # Create folder structure: Clients/<legal_name>/{notes, output}
        client_dir = self._safe_client_path(legal_name)
        os.makedirs(os.path.join(client_dir, "notes"), exist_ok=True)
        os.makedirs(os.path.join(client_dir, "output"), exist_ok=True)

        now_iso = datetime.now().isoformat()

        # Build the services block
        services_block = {}
        for svc_key in ("audit", "tax", "compilation"):
            enabled = bool(services.get(svc_key, False))
            agent_info = SUB_AGENTS.get(svc_key, {})
            client_folder = ""
            if enabled:
                client_folder = self._resolve_sub_agent_folder(
                    svc_key, client_data
                )
            services_block[svc_key] = {
                "enabled": enabled,
                "agent_dir": agent_info.get("dir", "") if enabled else "",
                "client_folder": client_folder,
                "status": "not_started",
                "progress_pct": 0,
                "deadline": "",
                "notes": "",
            }

        # Full engagement schema
        engagement = {
            "_meta": {
                "version": "1.0",
                "created": now_iso,
                "lastModified": now_iso,
            },
            "client": {
                "legal_name": legal_name,
                "display_name": client_data.get("display_name", ""),
                "registration_no": client_data.get("registration_no", ""),
                "tax_file_no": client_data.get("tax_file_no", ""),
                "fye_date": client_data.get("fye_date", ""),
                "fy_start": client_data.get("fy_start", ""),
                "reporting_framework": client_data.get(
                    "reporting_framework", "MPERS"
                ),
                "principal_activities": client_data.get(
                    "principal_activities", ""
                ),
                "contact_person": client_data.get("contact_person", ""),
                "contact_email": client_data.get("contact_email", ""),
                "contact_phone": client_data.get("contact_phone", ""),
            },
            "services": services_block,
            "pbc_summary": {
                "total_items": 0,
                "received": 0,
                "outstanding": 0,
                "not_applicable": 0,
                "last_updated": "",
            },
            "queries_summary": {
                "total": 0,
                "open": 0,
                "resolved": 0,
                "last_updated": "",
            },
            "deadlines": [],
        }

        # Persist engagement.json
        engagement_path = os.path.join(client_dir, "engagement.json")
        self._write_json(engagement_path, engagement)

        # Create initial status_log.md
        log_path = os.path.join(client_dir, "status_log.md")
        enabled_services = [
            k for k in ("audit", "tax", "compilation") if services.get(k)
        ]
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"# Status Log - {legal_name}\n\n")
            f.write(
                f"**[{now_iso}]** Engagement created. "
                f"Services enabled: {', '.join(enabled_services) or 'none'}.\n"
            )

        return engagement

    # ------------------------------------------------------------------
    # 2. load_engagement
    # ------------------------------------------------------------------
    def load_engagement(self, client_name: str) -> dict:
        """Load and return the engagement.json for a given client folder.

        Parameters
        ----------
        client_name : str
            Name of the client folder inside ``Clients/``.

        Returns
        -------
        dict
            Parsed engagement data.

        Raises
        ------
        FileNotFoundError
            If the engagement.json does not exist.
        """
        path = self._safe_client_path(client_name, "engagement.json")
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"No engagement.json found for client '{client_name}'."
            )
        return self._read_json(path)

    # ------------------------------------------------------------------
    # 3. save_engagement
    # ------------------------------------------------------------------
    def save_engagement(self, client_name: str, data: dict) -> None:
        """Write engagement.json, updating the lastModified timestamp.

        Parameters
        ----------
        client_name : str
            Name of the client folder inside ``Clients/``.
        data : dict
            Full engagement data to persist.
        """
        data.setdefault("_meta", {})
        data["_meta"]["lastModified"] = datetime.now().isoformat()

        path = self._safe_client_path(client_name, "engagement.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._write_json(path, data)

    # ------------------------------------------------------------------
    # 4. list_engagements
    # ------------------------------------------------------------------
    def list_engagements(self) -> list:
        """Scan Clients/ and return a summary list of all engagements.

        Returns
        -------
        list[dict]
            Each dict contains: folder, legal_name, display_name,
            services (dict of enabled booleans), overall_status,
            overall_progress_pct.
        """
        results = []
        if not os.path.isdir(self.clients_dir):
            return results

        for folder_name in sorted(os.listdir(self.clients_dir)):
            eng_path = os.path.join(
                self.clients_dir, folder_name, "engagement.json"
            )
            if not os.path.isfile(eng_path):
                continue

            try:
                data = self._read_json(eng_path)
            except (json.JSONDecodeError, IOError):
                continue

            client_info = data.get("client", {})
            svcs = data.get("services", {})

            # Compute overall progress as weighted average of enabled services
            enabled_svcs = {
                k: v for k, v in svcs.items() if v.get("enabled")
            }
            if enabled_svcs:
                total_pct = sum(
                    v.get("progress_pct", 0) for v in enabled_svcs.values()
                )
                overall_progress = total_pct // len(enabled_svcs)
            else:
                overall_progress = 0

            # Derive overall status from individual service statuses
            overall_status = self._derive_overall_status(enabled_svcs)

            results.append(
                {
                    "folder": folder_name,
                    "legal_name": client_info.get("legal_name", folder_name),
                    "display_name": client_info.get("display_name", ""),
                    "services": {
                        k: v.get("enabled", False) for k, v in svcs.items()
                    },
                    "overall_status": overall_status,
                    "overall_progress_pct": overall_progress,
                }
            )

        return results

    # ------------------------------------------------------------------
    # 5. update_service_status
    # ------------------------------------------------------------------
    def update_service_status(
        self,
        client_name: str,
        service: str,
        status: str,
        progress_pct: int,
        notes: str = "",
    ) -> None:
        """Update the status of a specific service in engagement.json.

        Parameters
        ----------
        client_name : str
            Client folder name.
        service : str
            One of 'audit', 'tax', 'compilation'.
        status : str
            New status string (e.g. 'not_started', 'in_progress',
            'review', 'completed').
        progress_pct : int
            Progress percentage (0-100).
        notes : str, optional
            Free-text notes to store against the service.
        """
        if service not in ("audit", "tax", "compilation"):
            raise ValueError(
                f"Unknown service '{service}'. "
                f"Must be one of: audit, tax, compilation."
            )

        data = self.load_engagement(client_name)
        svc = data.get("services", {}).get(service, {})
        svc["status"] = status
        svc["progress_pct"] = max(0, min(100, int(progress_pct)))
        if notes:
            svc["notes"] = notes
        data["services"][service] = svc

        self.save_engagement(client_name, data)

        # Also append to status log
        self.add_status_log(
            client_name,
            f"Service [{service}] updated -> status={status}, "
            f"progress={progress_pct}%"
            + (f", notes: {notes}" if notes else ""),
        )

    # ------------------------------------------------------------------
    # 6. get_sub_agent_folder
    # ------------------------------------------------------------------
    def get_sub_agent_folder(self, client_name: str, service: str) -> str:
        """Return the full absolute path to the client's folder within
        the sub-agent project directory.

        Parameters
        ----------
        client_name : str
            Client folder name (matches legal_name).
        service : str
            One of 'audit', 'tax', 'compilation'.

        Returns
        -------
        str
            Absolute path to the sub-agent client folder.
        """
        if service not in SUB_AGENTS:
            raise ValueError(
                f"Unknown service '{service}'. "
                f"Must be one of: {', '.join(SUB_AGENTS.keys())}."
            )

        data = self.load_engagement(client_name)
        return self._resolve_sub_agent_folder(
            service, data.get("client", {})
        )

    # ------------------------------------------------------------------
    # 7. get_all_deadlines
    # ------------------------------------------------------------------
    def get_all_deadlines(self) -> list:
        """Collect and return all deadlines across every engagement,
        sorted by date ascending.

        Returns
        -------
        list[dict]
            Each dict: client_name, service, deadline, description.
        """
        all_deadlines = []

        if not os.path.isdir(self.clients_dir):
            return all_deadlines

        for folder_name in os.listdir(self.clients_dir):
            eng_path = os.path.join(
                self.clients_dir, folder_name, "engagement.json"
            )
            if not os.path.isfile(eng_path):
                continue

            try:
                data = self._read_json(eng_path)
            except (json.JSONDecodeError, IOError):
                continue

            legal_name = data.get("client", {}).get("legal_name", folder_name)

            # Collect per-service deadlines
            for svc_key, svc_data in data.get("services", {}).items():
                if svc_data.get("enabled") and svc_data.get("deadline"):
                    all_deadlines.append(
                        {
                            "client_name": legal_name,
                            "service": svc_key,
                            "deadline": svc_data["deadline"],
                            "description": (
                                f"{svc_key.capitalize()} deadline for "
                                f"{legal_name}"
                            ),
                        }
                    )

            # Collect top-level deadlines list
            for dl in data.get("deadlines", []):
                all_deadlines.append(
                    {
                        "client_name": legal_name,
                        "service": dl.get("service", ""),
                        "deadline": dl.get("date", dl.get("deadline", "")),
                        "description": dl.get("description", ""),
                    }
                )

        # Sort by deadline string (ISO or any date format -- lexicographic
        # sort works for ISO and common formats like YYYY-MM-DD)
        all_deadlines.sort(key=lambda d: d.get("deadline", ""))
        return all_deadlines

    # ------------------------------------------------------------------
    # 8. add_status_log
    # ------------------------------------------------------------------
    def add_status_log(self, client_name: str, entry: str) -> None:
        """Append a timestamped entry to the client's status_log.md.

        Parameters
        ----------
        client_name : str
            Client folder name.
        entry : str
            Free-text log entry.
        """
        log_path = self._safe_client_path(client_name, "status_log.md")
        timestamp = datetime.now().isoformat()
        line = f"**[{timestamp}]** {entry}\n"

        # If file does not exist yet, create it with a header
        if not os.path.isfile(log_path):
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"# Status Log - {client_name}\n\n")

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)

    # ==================================================================
    # Private helpers
    # ==================================================================

    def _safe_client_path(self, client_name: str, *sub_paths) -> str:
        """Resolve a client path and verify it stays within clients_dir.

        Raises ValueError if the resolved path escapes the clients directory.
        """
        if ".." in client_name or "/" in client_name or "\\" in client_name:
            raise ValueError(
                f"Invalid client name '{client_name}': must not contain "
                f"path separators or '..'."
            )
        resolved = os.path.realpath(
            os.path.join(self.clients_dir, client_name, *sub_paths)
        )
        if not resolved.startswith(self.clients_dir + os.sep) and resolved != self.clients_dir:
            raise ValueError(
                f"Path traversal blocked for client name '{client_name}'."
            )
        return resolved

    def _resolve_sub_agent_folder(
        self, service: str, client_info: dict
    ) -> str:
        """Resolve the sub-agent folder path by interpolating the
        folder_pattern for the given service.

        Parameters
        ----------
        service : str
            Service key (audit, tax, compilation).
        client_info : dict
            The ``client`` block from the engagement schema.

        Returns
        -------
        str
            Absolute path to the sub-agent client folder.
        """
        agent = SUB_AGENTS[service]
        pattern = agent["folder_pattern"]
        legal_name = client_info.get("legal_name", "")
        fye_date = client_info.get("fye_date", "")

        # Extract the FYE year from fye_date (e.g. "31 December 2024" -> "2024")
        fye_year = self._extract_year(fye_date)

        if service == "audit":
            # Sanitise: spaces -> underscores, strip Sdn Bhd etc. for short name
            sanitised_name = legal_name.replace(" ", "_")
            folder_rel = pattern.format(
                client_name=sanitised_name, year=fye_year
            )

        elif service == "tax":
            # Tax uses UPPERCASE client name; YA year is typically FYE year + 1
            # when FYE is *not* 31 December, otherwise same year.
            upper_name = legal_name.upper()
            ya_year = self._compute_ya_year(fye_date, fye_year)
            folder_rel = pattern.format(
                client_name=upper_name, ya_year=ya_year
            )

        elif service == "compilation":
            # Compilation uses legal_name as-is
            folder_rel = pattern.format(legal_name=legal_name)

        else:
            folder_rel = pattern

        return os.path.join(agent["dir"], folder_rel)

    @staticmethod
    def _extract_year(date_str: str) -> str:
        """Extract a four-digit year from a date string.

        Handles formats like:
        - "31 December 2024"
        - "2024-12-31"
        - "31/12/2024"

        Returns
        -------
        str
            The year as a string, or empty string if not found.
        """
        if not date_str:
            return ""
        # Try to find a 4-digit number that looks like a year
        for token in date_str.replace("/", " ").replace("-", " ").split():
            if len(token) == 4 and token.isdigit():
                return token
        return ""

    @staticmethod
    def _compute_ya_year(fye_date: str, fye_year: str) -> str:
        """Compute the Year of Assessment (YA) for Malaysian tax.

        The YA is the calendar year following the basis period.
        For a company with FYE 31 December 2024, YA = 2025.
        For a company with FYE 30 June 2024, YA = 2025 as well
        (YA = FYE year + 1).

        In Malaysian tax law, YA is always FYE year + 1.

        Parameters
        ----------
        fye_date : str
            The financial year end date string.
        fye_year : str
            The extracted year from fye_date.

        Returns
        -------
        str
            The Year of Assessment as a string.
        """
        if not fye_year:
            return ""
        try:
            return str(int(fye_year) + 1)
        except ValueError:
            return ""

    @staticmethod
    def _derive_overall_status(enabled_services: dict) -> str:
        """Derive an overall engagement status from individual service
        statuses.

        Priority order:
        - If any service is 'in_progress' or 'review' -> 'in_progress'
        - If all services are 'completed' -> 'completed'
        - If all services are 'not_started' -> 'not_started'
        - Otherwise -> 'in_progress'

        Parameters
        ----------
        enabled_services : dict
            Subset of services block where enabled is True.

        Returns
        -------
        str
            Overall status string.
        """
        if not enabled_services:
            return "not_started"

        statuses = {v.get("status", "not_started") for v in enabled_services.values()}

        if all(s == "completed" for s in statuses):
            return "completed"
        if all(s == "not_started" for s in statuses):
            return "not_started"
        return "in_progress"

    @staticmethod
    def _read_json(path: str) -> dict:
        """Read and parse a JSON file.

        Parameters
        ----------
        path : str
            Absolute path to the JSON file.

        Returns
        -------
        dict
            Parsed JSON content.
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: str, data: dict) -> None:
        """Write a dict to a JSON file with pretty formatting.

        Parameters
        ----------
        path : str
            Absolute path to the JSON file.
        data : dict
            Data to serialize.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
