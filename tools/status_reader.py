"""
StatusReader - Probes sub-agent project folders to determine engagement progress.

Reads file system state from Audit, Tax, and Compilation sub-agent client folders
to estimate progress without spawning sub-agent sessions. Uses only stdlib modules.

Usage:
    from tools.status_reader import StatusReader

    reader = StatusReader()
    audit_status = reader.probe_audit_status(r"C:\\...\\Clients\\AWP_ABC_Trading_FYE2024")
    tax_status = reader.probe_tax_status(r"C:\\...\\Clients\\ABC TRADING SDN BHD YA 2025")
    compilation_status = reader.probe_compilation_status(r"C:\\...\\Clients\\ABC Trading Sdn Bhd")
"""

import os
import os.path
import glob
import datetime
import time


class StatusReader:
    """Probes sub-agent folders to estimate engagement progress without spawning agents.

    Each probe method inspects folder structure, file counts, and key artifacts
    to return a structured status dict with estimated progress percentages and
    human-readable stage labels.
    """

    # ── Audit constants ──────────────────────────────────────────────────

    AUDIT_SECTIONS = {
        "A": "Planning & administration",
        "B": "Internal control evaluation",
        "C": "Assets (PPE, bank, receivables, inventory)",
        "D": "Equity & liabilities",
        "E": "Income statement",
        "F": "Completion (going concern, related parties)",
        "G": "Financial statements",
    }

    # ── Tax constants ────────────────────────────────────────────────────

    TAX_STANDARD_FOLDERS = [
        "01_TAX_COMPUTATION",
        "02_ANALYSIS_OF_ACCOUNTS",
        "03_CAPITAL_ALLOWANCE",
        "04_DIRECTORS_DETAILS",
        "05_SHAREHOLDERS_DETAILS",
        "06_BENEFICIAL_OWNERSHIP",
        "07_PBC_QUERY",
        "08_SUPPORTING_WORKINGS",
        "09_PRIOR_YEAR_REFERENCE",
    ]

    # ── File extensions to track in recent-files scan ────────────────────

    TRACKED_EXTENSIONS = {".md", ".json", ".html", ".py", ".xlsx", ".docx"}

    # =====================================================================
    # 1. Audit probe
    # =====================================================================

    def probe_audit_status(self, audit_folder: str) -> dict:
        """Probe an audit sub-agent client folder and estimate progress.

        Args:
            audit_folder: Full path to the client folder within the audit agent,
                e.g. ``C:\\...\\Pilot - Audit - Claude\\Clients\\AWP_ABC_Trading_FYE2024``

        Returns:
            dict with keys: exists, sections_found, file_count, has_viewer,
            has_pbc, pbc_items_count, estimated_progress, stage.
        """
        result = {
            "exists": False,
            "sections_found": [],
            "file_count": 0,
            "has_viewer": False,
            "has_pbc": False,
            "pbc_items_count": 0,
            "estimated_progress": 0,
            "stage": "not_started",
        }

        if not os.path.isdir(audit_folder):
            return result

        result["exists"] = True

        # --- Detect which sections (A-G) are present ---
        sections_found = []
        for letter in self.AUDIT_SECTIONS:
            if self._audit_section_exists(audit_folder, letter):
                sections_found.append(letter)
        result["sections_found"] = sections_found

        # --- Count total .md files recursively ---
        md_pattern = os.path.join(audit_folder, "**", "*.md")
        md_files = glob.glob(md_pattern, recursive=True)
        result["file_count"] = len(md_files)

        # --- Check for audit_viewer.html ---
        viewer_path = os.path.join(audit_folder, "audit_viewer.html")
        result["has_viewer"] = os.path.isfile(viewer_path)

        # --- Check for PBC / query items ---
        pbc_count = self._count_pbc_items(audit_folder)
        result["has_pbc"] = pbc_count > 0
        result["pbc_items_count"] = pbc_count

        # --- Estimate progress ---
        progress, stage = self._estimate_audit_progress(
            sections_found, result["has_viewer"], result["file_count"]
        )
        result["estimated_progress"] = progress
        result["stage"] = stage

        return result

    # ── Audit helpers ────────────────────────────────────────────────────

    @staticmethod
    def _audit_section_exists(folder: str, letter: str) -> bool:
        """Check whether an audit section exists as a folder or prefixed .md file.

        Looks for:
        - Folders whose name starts with ``<letter>_`` or ``<letter>-``
          (e.g. ``A_Planning/``, ``B-Internal_Control/``)
        - ``.md`` files whose name starts with ``<letter>-``
          (e.g. ``A-Planning.md``)
        """
        for entry in os.listdir(folder):
            entry_upper = entry.upper()
            full_path = os.path.join(folder, entry)

            # Folder match: starts with letter followed by _ or -
            if os.path.isdir(full_path):
                if entry_upper.startswith(letter + "_") or entry_upper.startswith(letter + "-"):
                    return True

            # File match: .md file starting with letter-
            if os.path.isfile(full_path) and entry.lower().endswith(".md"):
                if entry_upper.startswith(letter + "-"):
                    return True

        return False

    @staticmethod
    def _count_pbc_items(folder: str) -> int:
        """Count files in any subfolder whose name contains PBC, Outstanding, or Query."""
        count = 0
        for entry in os.listdir(folder):
            full_path = os.path.join(folder, entry)
            if not os.path.isdir(full_path):
                continue
            name_upper = entry.upper()
            if "PBC" in name_upper or "OUTSTANDING" in name_upper or "QUERY" in name_upper:
                for item in os.listdir(full_path):
                    if os.path.isfile(os.path.join(full_path, item)):
                        count += 1
        return count

    @staticmethod
    def _estimate_audit_progress(sections: list, has_viewer: bool, file_count: int) -> tuple:
        """Return (progress_pct, stage) based on audit section heuristics.

        Progress ladder (cumulative, highest matching rule wins):
            - Folder exists but empty          ->  5%   planning
            - Section A exists                 -> 15%   planning
            - Section B exists                 -> 25%   fieldwork
            - Sections C + D exist             -> 60%   fieldwork
            - Section E exists                 -> 75%   fieldwork
            - Section F exists                 -> 90%   completion
            - Section G + viewer               -> 100%  done
        """
        s = set(sections)

        if "G" in s and has_viewer:
            return 100, "done"
        if "F" in s:
            return 90, "completion"
        if "E" in s:
            return 75, "fieldwork"
        if "C" in s and "D" in s:
            return 60, "fieldwork"
        if "B" in s:
            return 25, "fieldwork"
        if "A" in s:
            return 15, "planning"
        if file_count > 0:
            return 5, "planning"

        return 5, "planning"

    # =====================================================================
    # 2. Tax probe
    # =====================================================================

    def probe_tax_status(self, tax_folder: str) -> dict:
        """Probe a tax sub-agent client folder and estimate progress.

        Args:
            tax_folder: Full path to the client folder within the tax agent,
                e.g. ``C:\\...\\Pilot - TAX- Calude\\Clients\\ABC TRADING SDN BHD YA 2025``

        Returns:
            dict with keys: exists, folders_found, file_count, has_viewer,
            has_master_data, has_pbc, pbc_items_count, estimated_progress, stage.
        """
        result = {
            "exists": False,
            "folders_found": [],
            "file_count": 0,
            "has_viewer": False,
            "has_master_data": False,
            "has_pbc": False,
            "pbc_items_count": 0,
            "estimated_progress": 0,
            "stage": "not_started",
        }

        if not os.path.isdir(tax_folder):
            return result

        result["exists"] = True

        # --- Detect which standard subfolders exist ---
        folders_found = []
        total_md = 0
        for std_folder in self.TAX_STANDARD_FOLDERS:
            sub_path = os.path.join(tax_folder, std_folder)
            if os.path.isdir(sub_path):
                folders_found.append(std_folder)
                # Count .md files in this subfolder
                md_files = glob.glob(os.path.join(sub_path, "*.md"))
                total_md += len(md_files)
        result["folders_found"] = folders_found
        result["file_count"] = total_md

        # --- Check for tax_viewer.html ---
        viewer_path = os.path.join(tax_folder, "tax_viewer.html")
        result["has_viewer"] = os.path.isfile(viewer_path)

        # --- Check for master_data.json ---
        master_path = os.path.join(tax_folder, "master_data.json")
        result["has_master_data"] = os.path.isfile(master_path)

        # --- Check 07_PBC_QUERY for PBC items and "Outstanding" count ---
        pbc_folder = os.path.join(tax_folder, "07_PBC_QUERY")
        pbc_count = 0
        outstanding_count = 0
        if os.path.isdir(pbc_folder):
            for item in os.listdir(pbc_folder):
                item_path = os.path.join(pbc_folder, item)
                if os.path.isfile(item_path):
                    pbc_count += 1
                    outstanding_count += self._count_outstanding_in_file(item_path)

        result["has_pbc"] = pbc_count > 0
        result["pbc_items_count"] = pbc_count

        # --- Estimate progress ---
        progress, stage = self._estimate_tax_progress(
            folders_found, result["has_viewer"], outstanding_count
        )
        result["estimated_progress"] = progress
        result["stage"] = stage

        return result

    # ── Tax helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _count_outstanding_in_file(filepath: str) -> int:
        """Count occurrences of the word 'Outstanding' (case-insensitive) in a file.

        Silently returns 0 for binary or unreadable files.
        """
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            return content.lower().count("outstanding")
        except (OSError, IOError):
            return 0

    @staticmethod
    def _estimate_tax_progress(folders_found: list, has_viewer: bool, outstanding_count: int) -> tuple:
        """Return (progress_pct, stage) based on tax folder heuristics.

        Progress ladder (highest matching rule wins):
            - Folder exists but no subfolders     ->  5%   not_started
            - 01 exists with files                -> 30%   in_progress
            - 02 + 03 exist                       -> 60%   in_progress
            - 04-06 exist                         -> 80%   in_progress
            - 07 PBC resolved (no Outstanding)    -> 90%   review
            - Viewer generated                    -> 100%  done
        """
        prefixes = set()
        for f in folders_found:
            # Extract the numeric prefix (e.g. "01" from "01_TAX_COMPUTATION")
            prefix = f.split("_")[0]
            prefixes.add(prefix)

        if has_viewer:
            return 100, "done"

        if "07" in prefixes and outstanding_count == 0:
            return 90, "review"

        if "07" in prefixes and outstanding_count > 0:
            # PBC folder exists but has outstanding items
            stage = "pbc_pending"
        else:
            stage = "in_progress"

        if {"04", "05", "06"}.issubset(prefixes):
            return 80, stage

        if {"02", "03"}.issubset(prefixes):
            return 60, stage

        if "01" in prefixes:
            return 30, stage

        if len(folders_found) > 0:
            return 10, stage

        return 5, "not_started"

    # =====================================================================
    # 3. Compilation probe
    # =====================================================================

    def probe_compilation_status(self, compilation_folder: str) -> dict:
        """Probe a compilation sub-agent client folder and estimate progress.

        Args:
            compilation_folder: Full path to the client folder within the
                compilation agent, e.g.
                ``C:\\...\\Pilot - MPERS Compilation - Stand Alone - Claude\\Clients\\ABC Trading Sdn Bhd``

        Returns:
            dict with keys: exists, has_source, source_file_count, has_output,
            has_docx, has_script, estimated_progress, stage.
        """
        result = {
            "exists": False,
            "has_source": False,
            "source_file_count": 0,
            "has_output": False,
            "has_docx": False,
            "has_script": False,
            "estimated_progress": 0,
            "stage": "not_started",
        }

        if not os.path.isdir(compilation_folder):
            return result

        result["exists"] = True

        # --- Check source/ subfolder ---
        source_dir = os.path.join(compilation_folder, "source")
        if os.path.isdir(source_dir):
            source_files = [
                f for f in os.listdir(source_dir)
                if os.path.isfile(os.path.join(source_dir, f))
            ]
            result["has_source"] = len(source_files) > 0
            result["source_file_count"] = len(source_files)

        # --- Check output/ subfolder for .docx files ---
        output_dir = os.path.join(compilation_folder, "output")
        if os.path.isdir(output_dir):
            result["has_output"] = True
            docx_files = glob.glob(os.path.join(output_dir, "*.docx"))
            result["has_docx"] = len(docx_files) > 0

        # --- Check for create_*_fs.py script ---
        script_pattern = os.path.join(compilation_folder, "create_*_fs.py")
        scripts = glob.glob(script_pattern)
        result["has_script"] = len(scripts) > 0

        # --- Estimate progress ---
        progress, stage = self._estimate_compilation_progress(
            has_source=result["has_source"],
            has_script=result["has_script"],
            has_docx=result["has_docx"],
        )
        result["estimated_progress"] = progress
        result["stage"] = stage

        return result

    # ── Compilation helpers ──────────────────────────────────────────────

    @staticmethod
    def _estimate_compilation_progress(has_source: bool, has_script: bool, has_docx: bool) -> tuple:
        """Return (progress_pct, stage) based on compilation folder heuristics.

        Progress ladder (highest matching rule wins):
            - Folder exists but empty       ->  5%   not_started
            - source/ has files             -> 10%   data_received
            - create_*_fs.py exists         -> 40%   in_progress
            - output/ has .docx             -> 90%   generated
            - (manual review = 100%         -> 100%  done -- cannot detect)
        """
        if has_docx:
            return 90, "generated"
        if has_script:
            return 40, "in_progress"
        if has_source:
            return 10, "data_received"

        return 5, "not_started"

    # =====================================================================
    # 4. Recent files
    # =====================================================================

    def get_recent_files(self, folder: str, days: int = 7) -> list:
        """Return files modified within the last N days.

        Args:
            folder: Root folder to scan recursively.
            days: Look-back window in days (default 7).

        Returns:
            List of dicts sorted by modified date descending (most recent first),
            each containing: name, path, modified (ISO timestamp), size_kb.
            Limited to the top 20 results. Only includes files with tracked
            extensions (.md, .json, .html, .py, .xlsx, .docx).
        """
        if not os.path.isdir(folder):
            return []

        cutoff = time.time() - (days * 86400)
        recent = []

        for root, _dirs, files in os.walk(folder):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in self.TRACKED_EXTENSIONS:
                    continue

                fpath = os.path.join(root, fname)
                try:
                    stat = os.stat(fpath)
                except OSError:
                    continue

                if stat.st_mtime >= cutoff:
                    mod_dt = datetime.datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat()
                    recent.append({
                        "name": fname,
                        "path": fpath,
                        "modified": mod_dt,
                        "size_kb": round(stat.st_size / 1024, 1),
                    })

        # Sort by modified date descending and limit to top 20
        recent.sort(key=lambda x: x["modified"], reverse=True)
        return recent[:20]

    # =====================================================================
    # 5. Probe all services
    # =====================================================================

    def probe_all_services(self, engagement_data: dict) -> dict:
        """Probe all enabled services for a single engagement.

        Args:
            engagement_data: The full engagement.json dict. Expected to contain
                a ``services`` key with ``audit``, ``tax``, and ``compilation``
                sub-dicts, each having ``enabled`` (bool) and ``client_folder``
                (str) fields. The ``client_folder`` may be a relative path under
                the agent directory or an absolute path.

        Returns:
            dict with keys ``audit``, ``tax``, ``compilation``, each mapping to
            the corresponding probe result dict (or a minimal not-enabled dict
            if the service is disabled).
        """
        services = engagement_data.get("services", {})
        combined = {}

        # --- Audit ---
        audit_cfg = services.get("audit", {})
        if audit_cfg.get("enabled", False):
            audit_path = self._resolve_service_folder(audit_cfg)
            combined["audit"] = self.probe_audit_status(audit_path)
        else:
            combined["audit"] = {"enabled": False, "stage": "not_started", "estimated_progress": 0}

        # --- Tax ---
        tax_cfg = services.get("tax", {})
        if tax_cfg.get("enabled", False):
            tax_path = self._resolve_service_folder(tax_cfg)
            combined["tax"] = self.probe_tax_status(tax_path)
        else:
            combined["tax"] = {"enabled": False, "stage": "not_started", "estimated_progress": 0}

        # --- Compilation ---
        comp_cfg = services.get("compilation", {})
        if comp_cfg.get("enabled", False):
            comp_path = self._resolve_service_folder(comp_cfg)
            combined["compilation"] = self.probe_compilation_status(comp_path)
        else:
            combined["compilation"] = {"enabled": False, "stage": "not_started", "estimated_progress": 0}

        return combined

    # ── Shared helpers ───────────────────────────────────────────────────

    @staticmethod
    def _resolve_service_folder(service_cfg: dict) -> str:
        """Resolve the full path to a sub-agent client folder.

        Supports two modes:
        1. ``client_folder`` is already an absolute path -> use directly.
        2. ``client_folder`` is relative -> join with ``agent_dir``.
        """
        client_folder = service_cfg.get("client_folder", "")
        agent_dir = service_cfg.get("agent_dir", "")

        if os.path.isabs(client_folder):
            return client_folder

        if agent_dir and client_folder:
            return os.path.join(agent_dir, client_folder)

        # Fallback: return whatever we have
        return client_folder or agent_dir
