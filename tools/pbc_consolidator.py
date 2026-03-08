"""
PBC Consolidator — Reads, merges, and deduplicates PBC (Provided By Client) checklists
across the three sub-agent projects (Audit, Tax, Compilation).

Usage:
    from tools.pbc_consolidator import PBCConsolidator

    consolidator = PBCConsolidator(engagement_data)
    items, stats = consolidator.consolidate()
"""

import os
import re
import json
from datetime import datetime


# ---------------------------------------------------------------------------
# Alias dictionary — maps a canonical document name to all known variants.
# Used for deduplication when the same document appears across services
# under slightly different labels.
# ---------------------------------------------------------------------------

DOCUMENT_ALIASES = {
    'trial balance': [
        'trial balance', 'tb', 'trial balance (detailed)',
        'trial balance with breakdown',
    ],
    'general ledger': [
        'general ledger', 'gl', 'general ledger (detailed)', 'detailed gl',
    ],
    'audited financial statements': [
        'audited fs', 'audited financial statements', 'afs',
        'audited accounts', 'signed financial statements',
    ],
    'management accounts': [
        'management accounts', 'management financial statements',
        'unaudited accounts', 'draft accounts',
    ],
    'ssm company profile': [
        'ssm company profile', 'ssm profile', 'company profile',
        'ssm extract',
    ],
    'fixed asset register': [
        'fixed asset register', 'far', 'asset register',
        'fa register', 'ppe register',
    ],
    'bank statements': [
        'bank statements', 'bank statement', 'bank stmts',
    ],
    'bank reconciliation': [
        'bank reconciliation', 'bank recon',
        'bank reconciliation statement',
    ],
    'tax computation prior year': [
        'prior year tax computation', 'previous year tax computation',
        'py tax computation', 'tax computation (prior year)',
    ],
    'capital allowance schedule': [
        'capital allowance schedule', 'ca schedule',
        'prior year ca schedule', 'capital allowance (prior year)',
    ],
    'directors particulars': [
        'directors particulars', 'director details',
        'directors details', 'directors information',
    ],
    'shareholders list': [
        'shareholders list', 'shareholders details',
        'shareholders particulars', 'shareholder list',
        'list of shareholders',
    ],
    'form 24': [
        'form 24', 'annual return', 'ssm annual return',
    ],
    'form 49': [
        'form 49', 'form 49 (section 58)', 'return of allotment',
    ],
    'memorandum and articles': [
        'memorandum and articles', 'm&a', 'constitution',
        'company constitution',
    ],
    'board resolution': [
        'board resolution', 'board resolutions', 'directors resolution',
    ],
    'epf socso records': [
        'epf socso', 'epf/socso', 'epf socso records',
        'epf and socso records',
    ],
    'staff listing': [
        'staff listing', 'staff list', 'employee list', 'employee listing',
    ],
    'invoice samples': [
        'invoice samples', 'sample invoices', 'sales invoices',
        'revenue invoices',
    ],
}


# ---------------------------------------------------------------------------
# Hard-coded PBC items for the Compilation service (which has no formal PBC
# system). The PM infers required documents from standard MPERS compilation
# requirements.
# ---------------------------------------------------------------------------

COMPILATION_REQUIRED_DOCS = [
    {'document': 'Trial Balance', 'category': 'Financial Records', 'priority': 'high'},
    {'document': 'General Ledger', 'category': 'Financial Records', 'priority': 'high'},
    {'document': 'Prior Year Financial Statements', 'category': 'Financial Records', 'priority': 'high'},
    {'document': 'SSM Company Profile', 'category': 'Statutory & Corporate', 'priority': 'high'},
    {'document': 'Directors Particulars', 'category': 'Statutory & Corporate', 'priority': 'high'},
    {'document': 'Company Constitution / M&A', 'category': 'Statutory & Corporate', 'priority': 'medium'},
    {'document': 'Fixed Asset Register', 'category': 'Fixed Assets', 'priority': 'medium'},
    {'document': 'Bank Statements', 'category': 'Financial Records', 'priority': 'medium'},
    {'document': 'Bank Reconciliation', 'category': 'Financial Records', 'priority': 'medium'},
    {'document': 'Shareholders List', 'category': 'Statutory & Corporate', 'priority': 'medium'},
    {'document': 'Board Resolution', 'category': 'Statutory & Corporate', 'priority': 'low'},
]


# ---------------------------------------------------------------------------
# Status ranking — higher number = more favourable.
# When the same document appears with different statuses across services,
# we keep the best (most-received) status.
# ---------------------------------------------------------------------------

_STATUS_RANK = {
    'received':        4,
    'derived':         3,   # e.g. "Derived from GL"
    'pending':         2,
    'outstanding':     1,
    'not received':    1,
    'not_received':    1,
    'not applicable':  0,
    'not_applicable':  0,
    'n/a':             0,
}

# Category prefix map for PM-level reference numbers (S = Statutory, F = Financial, etc.)
_CATEGORY_PREFIX = {
    'statutory & corporate':      'S',
    'statutory & corporate documents': 'S',
    'statutory':                  'S',
    'financial records':          'F',
    'financial statements':       'F',
    'financial statements & accounts': 'F',
    'fixed assets':               'A',
    'income related':             'I',
    'expenditure related':        'E',
    'tax & compliance':           'T',
    'tax compliance':             'T',
    'confirmations':              'C',
    'supporting documents':       'D',
}

# Priority ranking for sorting (lower number = higher priority)
_PRIORITY_SORT = {
    'high':   0,
    'medium': 1,
    'low':    2,
}


class PBCConsolidator:
    """Reads PBC checklists from sub-agent projects and merges them into a
    single consolidated list with deduplication."""

    def __init__(self, engagement_data: dict):
        """
        Initialise the consolidator from the engagement.json payload.

        Args:
            engagement_data: Parsed engagement.json dict. Must contain
                ``client`` and ``services`` keys.
        """
        self.engagement = engagement_data
        self.client = engagement_data.get('client', {})
        self.services = engagement_data.get('services', {})

    # ------------------------------------------------------------------
    # Public API — read PBC from each service
    # ------------------------------------------------------------------

    def read_audit_pbc(self, audit_folder: str) -> list:
        """Scan the audit client folder for markdown files containing PBC tables.

        The audit agent may store PBC items in various locations — typically a
        ``G_Outstanding/`` section, or files with 'PBC' or 'Outstanding' in
        the name. We scan *all* ``.md`` files under the folder and look for
        markdown tables that look like checklists.

        Args:
            audit_folder: Absolute path to the audit client folder
                (e.g. ``Clients/AWP_ClientName_FYE2024/``).

        Returns:
            List of PBC item dicts.
        """
        if not audit_folder or not os.path.isdir(audit_folder):
            return []

        items = []
        for root, _dirs, files in os.walk(audit_folder):
            for fname in files:
                if not fname.lower().endswith('.md'):
                    continue
                filepath = os.path.join(root, fname)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                except (OSError, IOError):
                    continue

                # Only consider files that look like PBC checklists
                if not self._looks_like_pbc(content, fname):
                    continue

                parsed = self._parse_markdown_table(content)
                for row in parsed:
                    item = self._row_to_pbc_item(row, source='audit')
                    if item:
                        items.append(item)

        return items

    def read_tax_pbc(self, tax_folder: str) -> list:
        """Read PBC items from the tax agent's ``07_PBC_QUERY/`` subfolder.

        Looks for files matching ``PBC_*.md`` and parses their markdown
        tables.

        Args:
            tax_folder: Absolute path to the tax client folder.

        Returns:
            List of PBC item dicts.
        """
        if not tax_folder or not os.path.isdir(tax_folder):
            return []

        pbc_dir = os.path.join(tax_folder, '07_PBC_QUERY')
        if not os.path.isdir(pbc_dir):
            return []

        items = []
        for fname in sorted(os.listdir(pbc_dir)):
            if not fname.lower().startswith('pbc_') or not fname.lower().endswith('.md'):
                continue
            filepath = os.path.join(pbc_dir, fname)
            try:
                with open(filepath, 'r', encoding='utf-8') as fh:
                    content = fh.read()
            except (OSError, IOError):
                continue

            parsed = self._parse_markdown_table(content)
            for row in parsed:
                item = self._row_to_pbc_item(row, source='tax')
                if item:
                    items.append(item)

        return items

    def infer_compilation_pbc(self) -> list:
        """Return hard-coded compilation PBC items with status 'outstanding'.

        The compilation agent has no formal PBC system, so we infer required
        documents from standard MPERS compilation requirements.

        Returns:
            List of PBC item dicts.
        """
        items = []
        for doc in COMPILATION_REQUIRED_DOCS:
            items.append({
                'document':      doc['document'],
                'category':      doc['category'],
                'status':        'outstanding',
                'date_received': '',
                'remarks':       'Inferred from compilation requirements',
                'source_ref':    '',
                'priority':      doc.get('priority', 'medium'),
                'source':        'compilation',
            })
        return items

    # ------------------------------------------------------------------
    # Merge and deduplicate
    # ------------------------------------------------------------------

    def merge_pbc_items(self, audit_items: list, tax_items: list,
                        compilation_items: list) -> list:
        """Merge items from all services, deduplicate, assign references.

        Deduplication uses :pyattr:`DOCUMENT_ALIASES` to identify when the
        same document appears under different names across services.

        When duplicates are found:
        - ``needed_for`` accumulates all services that require the document.
        - The most favourable status is kept (received > pending > outstanding).
        - Remarks are concatenated.

        Each merged item receives a PM-level reference number based on its
        category (e.g. S01, F02, A03).

        Args:
            audit_items:       Items from :pymeth:`read_audit_pbc`.
            tax_items:         Items from :pymeth:`read_tax_pbc`.
            compilation_items: Items from :pymeth:`infer_compilation_pbc`.

        Returns:
            Sorted, deduplicated list of merged PBC item dicts.
        """
        # Tag each item with its service origin (if not already tagged)
        for item in audit_items:
            item.setdefault('source', 'audit')
        for item in tax_items:
            item.setdefault('source', 'tax')
        for item in compilation_items:
            item.setdefault('source', 'compilation')

        all_items = audit_items + tax_items + compilation_items

        # Deduplicate into a canonical-key -> merged-item map
        merged = {}  # canonical_key -> merged item
        for item in all_items:
            doc_name = item.get('document', '')
            canonical = self._find_alias_group(doc_name)
            if canonical is None:
                # No alias match — use normalized name as key
                canonical = self._normalize_document_name(doc_name)

            source = item.get('source', 'unknown')

            if canonical in merged:
                existing = merged[canonical]
                # Add service to needed_for
                if source not in existing['needed_for']:
                    existing['needed_for'].append(source)
                # Keep the most favourable status
                if self._status_rank(item.get('status', '')) > self._status_rank(existing.get('status', '')):
                    existing['status'] = self._normalise_status_label(item.get('status', ''))
                    existing['date_received'] = item.get('date_received', '') or existing.get('date_received', '')
                # Merge remarks (avoid duplicates)
                new_remark = (item.get('remarks') or '').strip()
                if new_remark and new_remark not in (existing.get('remarks') or ''):
                    if existing.get('remarks'):
                        existing['remarks'] += '; ' + new_remark
                    else:
                        existing['remarks'] = new_remark
                # Keep the highest priority
                if _PRIORITY_SORT.get(item.get('priority', 'medium'), 1) < _PRIORITY_SORT.get(existing.get('priority', 'medium'), 1):
                    existing['priority'] = item.get('priority', 'medium')
                # Keep source_ref from the first occurrence if we don't have one
                if not existing.get('source_ref') and item.get('source_ref'):
                    existing['source_ref'] = item['source_ref']
            else:
                merged[canonical] = {
                    'document':      item.get('document', ''),
                    'canonical':     canonical,
                    'category':      item.get('category', 'General'),
                    'status':        self._normalise_status_label(item.get('status', '')),
                    'date_received': item.get('date_received', ''),
                    'remarks':       (item.get('remarks') or '').strip(),
                    'source_ref':    item.get('source_ref', ''),
                    'priority':      item.get('priority', 'medium'),
                    'needed_for':    [source],
                }

        # Convert to list and sort: category, then priority, then document name
        items_list = list(merged.values())
        items_list.sort(key=lambda x: (
            self._category_sort_key(x.get('category', '')),
            _PRIORITY_SORT.get(x.get('priority', 'medium'), 1),
            x.get('document', '').lower(),
        ))

        # Assign PM-level reference numbers grouped by category
        ref_counters = {}
        for item in items_list:
            cat = item.get('category', 'General')
            prefix = self._category_prefix(cat)
            ref_counters.setdefault(prefix, 0)
            ref_counters[prefix] += 1
            item['ref'] = f"{prefix}{ref_counters[prefix]:02d}"

        return items_list

    # ------------------------------------------------------------------
    # Output generation
    # ------------------------------------------------------------------

    def generate_consolidated_md(self, items: list, output_path: str) -> str:
        """Write a consolidated PBC checklist as a markdown file.

        The file is organised with a summary header, stats, then items
        grouped by category.

        Args:
            items:       Merged item list from :pymeth:`merge_pbc_items`.
            output_path: Absolute path for the output ``.md`` file.

        Returns:
            The absolute path of the generated file.
        """
        company_name = self.client.get('legal_name', 'Unknown Company')
        fye_date = self.client.get('fye_date', '')
        generated_date = datetime.now().strftime('%d %B %Y')

        stats = self.generate_summary_stats(items)

        lines = []
        lines.append('# Consolidated PBC Checklist')
        lines.append('')
        lines.append(f'**Company:** {company_name}')
        if fye_date:
            lines.append(f'**Financial Year End:** {fye_date}')
        lines.append(f'**Date Generated:** {generated_date}')
        lines.append('')
        lines.append('---')
        lines.append('')

        # Summary stats
        lines.append('## Summary')
        lines.append('')
        lines.append(f'| Metric | Count |')
        lines.append(f'|--------|------:|')
        lines.append(f'| Total Items | {stats["total"]} |')
        lines.append(f'| Received | {stats["received"]} |')
        lines.append(f'| Outstanding | {stats["outstanding"]} |')
        lines.append(f'| Not Applicable | {stats["not_applicable"]} |')
        lines.append('')

        # Per-service breakdown
        lines.append('### By Service')
        lines.append('')
        lines.append('| Service | Total | Received | Outstanding |')
        lines.append('|---------|------:|---------:|------------:|')
        for svc in ('audit', 'tax', 'compilation'):
            svc_stats = stats['by_service'].get(svc, {'total': 0, 'received': 0, 'outstanding': 0})
            lines.append(
                f'| {svc.capitalize()} | {svc_stats["total"]} | '
                f'{svc_stats["received"]} | {svc_stats["outstanding"]} |'
            )
        lines.append('')
        lines.append('---')
        lines.append('')

        # Group items by category
        categories_order = []
        categories_map = {}
        for item in items:
            cat = item.get('category', 'General')
            if cat not in categories_map:
                categories_order.append(cat)
                categories_map[cat] = []
            categories_map[cat].append(item)

        for cat in categories_order:
            cat_items = categories_map[cat]
            lines.append(f'## {cat}')
            lines.append('')
            lines.append('| Ref | Document | Needed For | Status | Date Received | Remarks |')
            lines.append('|-----|----------|------------|--------|---------------|---------|')
            for item in cat_items:
                ref = item.get('ref', '')
                doc = item.get('document', '')
                needed_for = ', '.join(
                    s.capitalize() for s in item.get('needed_for', [])
                )
                status = item.get('status', '')
                date_recv = item.get('date_received', '')
                remarks = item.get('remarks', '')
                lines.append(
                    f'| {ref} | {doc} | {needed_for} | {status} | {date_recv} | {remarks} |'
                )
            lines.append('')

        lines.append('---')
        lines.append('')
        lines.append(f'*Generated by PM Agent on {generated_date}*')
        lines.append('')

        # Write to disk
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines))

        return os.path.abspath(output_path)

    def generate_summary_stats(self, items: list) -> dict:
        """Compute summary statistics from a merged item list.

        Args:
            items: Merged item list from :pymeth:`merge_pbc_items`.

        Returns:
            Dict with keys: ``total``, ``received``, ``outstanding``,
            ``not_applicable``, ``by_service``, ``by_category``.
        """
        stats = {
            'total':          0,
            'received':       0,
            'outstanding':    0,
            'not_applicable': 0,
            'by_service':     {},
            'by_category':    {},
        }

        # Initialise service buckets
        for svc in ('audit', 'tax', 'compilation'):
            stats['by_service'][svc] = {'total': 0, 'received': 0, 'outstanding': 0}

        for item in items:
            stats['total'] += 1
            status = self._normalise_status_label(item.get('status', ''))

            if status == 'Received':
                stats['received'] += 1
            elif status == 'Not Applicable':
                stats['not_applicable'] += 1
            else:
                # Pending, Outstanding, Not Received — all count as outstanding
                stats['outstanding'] += 1

            # By service
            for svc in item.get('needed_for', []):
                svc_key = svc.lower()
                if svc_key not in stats['by_service']:
                    stats['by_service'][svc_key] = {'total': 0, 'received': 0, 'outstanding': 0}
                stats['by_service'][svc_key]['total'] += 1
                if status == 'Received':
                    stats['by_service'][svc_key]['received'] += 1
                elif status != 'Not Applicable':
                    stats['by_service'][svc_key]['outstanding'] += 1

            # By category
            cat = item.get('category', 'General')
            if cat not in stats['by_category']:
                stats['by_category'][cat] = {'total': 0, 'received': 0, 'outstanding': 0}
            stats['by_category'][cat]['total'] += 1
            if status == 'Received':
                stats['by_category'][cat]['received'] += 1
            elif status != 'Not Applicable':
                stats['by_category'][cat]['outstanding'] += 1

        return stats

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def consolidate(self) -> tuple:
        """Read from all enabled services, merge, and return consolidated data.

        Returns:
            Tuple of ``(items_list, summary_stats)``.
        """
        audit_items = []
        tax_items = []
        compilation_items = []

        # Audit
        audit_cfg = self.services.get('audit', {})
        if audit_cfg.get('enabled'):
            agent_dir = audit_cfg.get('agent_dir', '')
            client_folder = audit_cfg.get('client_folder', '')
            if agent_dir and client_folder:
                full_path = os.path.join(agent_dir, client_folder)
                audit_items = self.read_audit_pbc(full_path)

        # Tax
        tax_cfg = self.services.get('tax', {})
        if tax_cfg.get('enabled'):
            agent_dir = tax_cfg.get('agent_dir', '')
            client_folder = tax_cfg.get('client_folder', '')
            if agent_dir and client_folder:
                full_path = os.path.join(agent_dir, client_folder)
                tax_items = self.read_tax_pbc(full_path)

        # Compilation — always uses inferred docs when enabled
        compilation_cfg = self.services.get('compilation', {})
        if compilation_cfg.get('enabled'):
            compilation_items = self.infer_compilation_pbc()

        items = self.merge_pbc_items(audit_items, tax_items, compilation_items)
        stats = self.generate_summary_stats(items)

        return items, stats

    # ------------------------------------------------------------------
    # Internal helpers — markdown parsing
    # ------------------------------------------------------------------

    def _parse_markdown_table(self, content: str) -> list:
        """Parse all markdown tables from *content* and return rows as dicts.

        Handles edge cases:
        - Leading/trailing pipes and whitespace
        - Separator rows (``|---|---|``)
        - Empty cells
        - Multiple tables in the same file (each with its own header row)
        - Section headings (``### A. Category Name``) above tables — injected
          as a ``_section`` key on each row so the caller can use it as the
          category when the table itself has no category column.

        Args:
            content: Full text content of a markdown file.

        Returns:
            List of dicts, one per data row, with column headers as keys
            (lowercased, stripped). An extra ``_section`` key carries the
            most-recent markdown heading above the table.
        """
        results = []
        lines = content.split('\n')

        current_section = ''
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Track markdown section headings (##, ###, ####)
            section_match = re.match(r'^#{2,4}\s+(?:[A-Z]\.\s+)?(.+)$', line)
            if section_match:
                current_section = section_match.group(1).strip()

            # Look for a line that looks like a table header (contains pipes
            # and is followed by a separator line).
            if '|' in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if self._is_separator_row(next_line):
                    headers = self._split_table_row(line)
                    headers = [h.lower().strip() for h in headers]

                    # Skip separator row
                    i += 2

                    # Read data rows
                    while i < len(lines):
                        row_line = lines[i].strip()
                        if not row_line or '|' not in row_line:
                            break
                        if self._is_separator_row(row_line):
                            i += 1
                            continue

                        cells = self._split_table_row(row_line)
                        row_dict = {'_section': current_section}
                        for col_idx, header in enumerate(headers):
                            if col_idx < len(cells):
                                row_dict[header] = cells[col_idx].strip()
                            else:
                                row_dict[header] = ''
                        results.append(row_dict)
                        i += 1
                    continue  # Don't increment i again

            i += 1

        return results

    def _split_table_row(self, line: str) -> list:
        """Split a markdown table row on ``|`` delimiters.

        Strips the outer pipes so ``| A | B | C |`` becomes ``['A', 'B', 'C']``.
        """
        # Remove leading/trailing pipe and whitespace
        line = line.strip()
        if line.startswith('|'):
            line = line[1:]
        if line.endswith('|'):
            line = line[:-1]
        return [cell.strip() for cell in line.split('|')]

    def _is_separator_row(self, line: str) -> bool:
        """Return True if *line* looks like a markdown table separator
        (e.g. ``|---|---|---:|``)."""
        stripped = line.replace(' ', '').replace('|', '').replace('-', '').replace(':', '')
        return len(stripped) == 0 and '-' in line

    def _looks_like_pbc(self, content: str, filename: str) -> bool:
        """Heuristic check: does this file contain PBC-like content?

        Returns True if the filename or content suggests it is a PBC / document
        checklist.
        """
        fname_lower = filename.lower()
        # Filename hints
        if any(kw in fname_lower for kw in ('pbc', 'outstanding', 'checklist', 'document_status')):
            return True

        content_lower = content.lower()
        # Content hints — look for PBC-related headers or keywords
        pbc_keywords = [
            'pbc', 'provided by client', 'document checklist',
            'outstanding items', 'document status', 'documents required',
        ]
        keyword_hits = sum(1 for kw in pbc_keywords if kw in content_lower)
        if keyword_hits >= 1:
            return True

        # Check for table rows with a 'status' column containing typical PBC statuses
        if re.search(r'\|\s*status\s*\|', content_lower) and \
           re.search(r'(received|outstanding|pending|not received)', content_lower):
            return True

        return False

    # ------------------------------------------------------------------
    # Internal helpers — row normalisation
    # ------------------------------------------------------------------

    def _row_to_pbc_item(self, row: dict, source: str) -> dict:
        """Convert a parsed table row dict into a standardised PBC item dict.

        Handles the various column-naming conventions used by the audit and
        tax agents.

        Args:
            row:    Dict from :pymeth:`_parse_markdown_table`.
            source: One of ``'audit'``, ``'tax'``, ``'compilation'``.

        Returns:
            Standardised PBC item dict, or ``None`` if the row is not a
            valid document entry (e.g. a summary row).
        """
        # Identify the document name — try several possible column headers
        doc_name = (
            row.get('document', '') or
            row.get('document description', '') or
            row.get('description', '') or
            row.get('item', '')
        ).strip()

        if not doc_name:
            return None

        # Skip rows that are clearly summary/total lines
        if doc_name.lower().startswith(('total', '**total', 'summary')):
            return None

        # Source reference (No., Ref, etc.)
        source_ref = (
            row.get('no.', '') or
            row.get('no', '') or
            row.get('ref', '') or
            row.get('#', '')
        ).strip()

        # Category — may or may not be present as a column; fall back
        # to the markdown section heading captured by _parse_markdown_table.
        category = (
            row.get('category', '') or
            row.get('section', '') or
            row.get('_section', '')
        ).strip()

        # Clean up section headers that are actually priority labels
        # (e.g. "HIGH PRIORITY (Required for filing)") — not real categories.
        # Extract the priority hint before clearing the category.
        section_priority = ''
        if category and re.match(r'^(high|medium|low)\s+priority', category, re.IGNORECASE):
            prio_match = re.match(r'^(high|medium|low)', category, re.IGNORECASE)
            if prio_match:
                section_priority = prio_match.group(1).lower()
            category = ''

        # Also clean up section headers that are follow-up / summary sections
        if category and re.match(r'^(summary|follow.up|note)', category, re.IGNORECASE):
            category = ''

        # Status — normalise the various formats
        raw_status = (
            row.get('status', '') or
            row.get('received', '')
        ).strip()

        status = self._parse_status(raw_status)

        # Date received
        date_received = (
            row.get('date received', '') or
            row.get('date', '') or
            row.get('received date', '')
        ).strip()

        # Remarks — also pick up "purpose" or "impact" columns as context
        remarks = (
            row.get('remarks', '') or
            row.get('notes', '') or
            row.get('comment', '') or
            row.get('comments', '') or
            row.get('purpose', '')
        ).strip()

        # Infer priority: explicit column > section header > default medium
        priority = (row.get('priority', '') or '').strip().lower()
        if priority not in ('high', 'medium', 'low'):
            priority = section_priority if section_priority else 'medium'

        return {
            'document':      doc_name,
            'category':      category if category else 'General',
            'status':        status,
            'date_received': date_received,
            'remarks':       remarks,
            'source_ref':    source_ref,
            'priority':      priority,
            'source':        source,
        }

    def _parse_status(self, raw: str) -> str:
        """Interpret a raw status string into a normalised status value.

        Handles emoji prefixes (checkmark, checkbox), descriptive text like
        'Received', 'Per SSM Profile', 'Derived from GL', etc.

        Returns one of: ``'received'``, ``'outstanding'``, ``'pending'``,
        ``'not_applicable'``.
        """
        text = raw.strip().lower()

        # Remove common emoji / unicode prefixes
        text = re.sub(r'^[\u2713\u2714\u2611\u2612\u2610\u2705\u274c\u2716\u25a1\u25a0\u25cb\u25cf\u2022]*\s*', '', text)
        # Remove leading checkbox-style markers
        text = re.sub(r'^[\u2610\u2612\u2611\u2705\u274c]*\s*', '', text)
        # Also handle literal checkmark text
        text = re.sub(r'^[✓✗☐☑]+\s*', '', text)

        text = text.strip()

        if not text:
            return 'outstanding'

        # N/A variants
        if text in ('n/a', 'not applicable', 'na', 'nil', '-'):
            return 'not_applicable'

        # Received variants
        received_patterns = [
            'received', 'per ssm', 'derived', 'obtained', 'available',
            'verified', 'provided', 'yes', 'done',
        ]
        for pat in received_patterns:
            if pat in text:
                return 'received'

        # Pending
        if 'pending' in text or 'in progress' in text or 'awaiting' in text:
            return 'pending'

        # Outstanding / Not received
        if any(kw in text for kw in ('outstanding', 'not received', 'to follow', 'missing', 'required', 'needed', 'no')):
            return 'outstanding'

        # Default: treat unknown as outstanding
        return 'outstanding'

    # ------------------------------------------------------------------
    # Internal helpers — document name normalisation & alias lookup
    # ------------------------------------------------------------------

    def _normalize_document_name(self, name: str) -> str:
        """Normalise a document name for matching purposes.

        - Lowercase
        - Strip whitespace
        - Remove parenthetical notes (e.g. ``(FY2024)``, ``(12 months)``)
        - Remove leading reference numbers (e.g. ``A1``, ``B3``)
        - Collapse multiple spaces

        Args:
            name: Raw document name string.

        Returns:
            Normalised lowercase string.
        """
        text = name.strip().lower()
        # Remove parenthetical notes
        text = re.sub(r'\([^)]*\)', '', text)
        # Remove leading reference like "A1 ", "B3 ", etc.
        text = re.sub(r'^[a-z]\d+\s+', '', text)
        # Remove unicode marks
        text = re.sub(r'[✓✗☐☑\u2713\u2714\u2611\u2612\u2610]+', '', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _find_alias_group(self, name: str) -> str:
        """Given a document name, find which alias group it belongs to.

        Args:
            name: Raw (or partially normalised) document name.

        Returns:
            The canonical name (a key in :pydata:`DOCUMENT_ALIASES`), or
            ``None`` if no alias match is found.
        """
        normalised = self._normalize_document_name(name)
        if not normalised:
            return None

        for canonical, aliases in DOCUMENT_ALIASES.items():
            for alias in aliases:
                if alias == normalised or normalised == alias:
                    return canonical
                # Also check if the normalised name *contains* the alias
                # (for cases like "Bank Statements (12 months)" -> "bank statements")
                if alias in normalised or normalised in alias:
                    # Only match if the alias is a substantial portion (> 60%)
                    longer = max(len(alias), len(normalised))
                    shorter = min(len(alias), len(normalised))
                    if shorter / longer > 0.6:
                        return canonical

        return None

    # ------------------------------------------------------------------
    # Internal helpers — status and category utilities
    # ------------------------------------------------------------------

    def _status_rank(self, status: str) -> int:
        """Return a numeric rank for a status string (higher = more favourable)."""
        normalised = status.strip().lower().replace(' ', '_')
        # Also try without underscores
        rank = _STATUS_RANK.get(normalised)
        if rank is not None:
            return rank
        normalised_space = status.strip().lower()
        rank = _STATUS_RANK.get(normalised_space)
        if rank is not None:
            return rank
        # Check for keywords
        if 'received' in normalised or 'derived' in normalised:
            return 4
        if 'pending' in normalised:
            return 2
        if 'n/a' in normalised or 'not_applicable' in normalised:
            return 0
        return 1  # default: outstanding

    def _normalise_status_label(self, status: str) -> str:
        """Return a clean, title-case status label for display purposes.

        Maps internal status codes to display labels:
        - ``received``       -> ``Received``
        - ``pending``        -> ``Pending``
        - ``outstanding``    -> ``Outstanding``
        - ``not_applicable`` -> ``Not Applicable``
        """
        key = status.strip().lower().replace(' ', '_')

        label_map = {
            'received':       'Received',
            'derived':        'Received',
            'pending':        'Pending',
            'outstanding':    'Outstanding',
            'not_received':   'Outstanding',
            'not_applicable': 'Not Applicable',
            'n/a':            'Not Applicable',
        }

        label = label_map.get(key)
        if label:
            return label

        # Keyword fallback
        if 'received' in key or 'derived' in key:
            return 'Received'
        if 'pending' in key:
            return 'Pending'
        if 'n/a' in key or 'not_applicable' in key:
            return 'Not Applicable'

        return 'Outstanding'

    def _category_prefix(self, category: str) -> str:
        """Return the reference-number prefix letter for a given category."""
        cat_lower = category.strip().lower()
        prefix = _CATEGORY_PREFIX.get(cat_lower)
        if prefix:
            return prefix
        # Fuzzy fallback — check if any key is a substring
        for key, pfx in _CATEGORY_PREFIX.items():
            if key in cat_lower or cat_lower in key:
                return pfx
        return 'G'  # General / fallback

    def _category_sort_key(self, category: str) -> int:
        """Return a sort key for category ordering.

        Statutory & Corporate first, then Financial, then others.
        """
        order = [
            'statutory', 'financial', 'fixed asset', 'income',
            'expenditure', 'tax', 'confirmation', 'supporting', 'general',
        ]
        cat_lower = category.strip().lower()
        for idx, keyword in enumerate(order):
            if keyword in cat_lower:
                return idx
        return len(order)  # Unknown categories sort last
