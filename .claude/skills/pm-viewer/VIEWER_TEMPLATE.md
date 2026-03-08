# PM Viewer Template Structure

This document describes the architecture, components, and data flow of the Project Manager dashboard (`pm_viewer.html`).

---

## HTML Structure Overview

The dashboard uses a **split-panel layout** matching the existing audit and tax viewer theme:

```
+---------------------+------------------------------------------+
|                     |                                          |
|   Left Nav Panel    |         Main Content Area                |
|   (320px, dark)     |         (flex-grow, light)               |
|                     |                                          |
|   - Title           |   Portfolio View (default):              |
|   - Search          |     - KPI Cards Row                     |
|   - Client List     |     - Client Cards Grid                 |
|   - Service Filter  |     - Upcoming Deadlines                |
|   - Refresh Button  |                                          |
|                     |   Client Detail View (on click):         |
|                     |     - Client Header                     |
|                     |     - Service Panels                    |
|                     |     - PBC Table                         |
|                     |     - Query Table                       |
|                     |     - Deadlines                         |
|                     |                                          |
+---------------------+------------------------------------------+
```

### DOM Hierarchy

```html
<body>
  <div class="app-container">
    <nav class="sidebar">
      <div class="sidebar-header">           <!-- Title + subtitle -->
      <div class="sidebar-search">           <!-- Search input -->
      <div class="sidebar-filters">          <!-- Service type filter buttons -->
      <div class="sidebar-clients">          <!-- Scrollable client list -->
      <div class="sidebar-footer">           <!-- Refresh All button -->
    </nav>
    <main class="content">
      <div id="portfolio-view">              <!-- Default view -->
        <div class="kpi-row">                <!-- 4 KPI cards -->
        <div class="client-grid">            <!-- Responsive client cards -->
        <div class="deadlines-section">      <!-- Upcoming deadlines list -->
      </div>
      <div id="client-detail-view">          <!-- Hidden until client clicked -->
        <div class="detail-header">          <!-- Back button + client info -->
        <div class="service-panels">         <!-- Horizontal service panels -->
        <div class="pbc-section">            <!-- Consolidated PBC table -->
        <div class="queries-section">        <!-- Query list table -->
        <div class="deadlines-detail">       <!-- Client-specific deadlines -->
      </div>
    </main>
  </div>
</body>
```

---

## Server API Endpoints

### GET /api/dashboard

Returns aggregated portfolio data used by the default view.

**Response:**
```json
{
  "clients": [
    {
      "folder": "Company Name Sdn Bhd",
      "legal_name": "Company Name Sdn Bhd",
      "display_name": "COMPANY NAME SDN. BHD.",
      "services": { "audit": true, "tax": true, "compilation": false },
      "overall_status": "in_progress",
      "overall_progress_pct": 45,
      "pbc_summary": { "total_items": 20, "received": 12, "outstanding": 8 },
      "queries_summary": { "total": 5, "open": 3, "resolved": 2 },
      "deadlines": [...]
    }
  ],
  "kpi": {
    "total_clients": 5,
    "pbc_outstanding": 18,
    "open_queries": 7,
    "upcoming_deadlines": 3
  },
  "deadlines": [...]
}
```

### GET /api/engagement/<client>

Returns the full `engagement.json` content for a specific client.

### GET /api/pbc/<client>

Reads `Clients/<client>/pbc_consolidated.md`, parses the markdown tables, and returns structured JSON:

```json
{
  "items": [
    {
      "ref": "S01",
      "document": "SSM Company Profile",
      "needed_for": "Audit, Tax",
      "status": "Received",
      "date_received": "2024-06-15",
      "remarks": "From SSM e-Info"
    }
  ],
  "stats": {
    "total": 20,
    "received": 12,
    "outstanding": 8,
    "not_applicable": 0
  }
}
```

### GET /api/queries/<client>

Reads `Clients/<client>/queries_consolidated.md` and returns parsed query items.

### GET /api/status/<client>

Performs a **live probe** of sub-agent folders using `StatusReader.probe_all_services()`. Returns real-time progress estimates.

### POST /api/refresh

Re-scans all sub-agent folders and updates engagement.json files. Returns updated dashboard data.

---

## JavaScript Data Flow

### Initialisation
1. `DOMContentLoaded` fires
2. `loadDashboard()` calls `GET /api/dashboard`
3. Response populates KPI cards, client cards grid, and deadlines list
4. Auto-refresh timer starts (60-second interval)

### Client Card Click
1. User clicks a client card
2. `showClientDetail(clientFolder)` hides portfolio view, shows detail view
3. Parallel fetches:
   - `GET /api/engagement/<client>` for full engagement data
   - `GET /api/pbc/<client>` for PBC table data
   - `GET /api/queries/<client>` for query list
   - `GET /api/status/<client>` for live probe results
4. Data renders into detail view components

### Refresh Flow
1. User clicks "Refresh All" button
2. `POST /api/refresh` triggers server-side re-scan
3. On success, `loadDashboard()` is called to reload all data
4. Loading spinner shown during refresh

### Error Handling
- Failed API calls show inline error messages (not alerts)
- Retry logic for transient failures (1 retry after 2 seconds)
- Graceful degradation: missing data shows "N/A" rather than breaking layout

---

## CSS Theme

### Design System (Matching Audit/Tax Viewer Theme)

**Nav Panel:**
- Background: `#1e293b` (Slate 800)
- Text: `#94a3b8` (Slate 400)
- Active/Hover: `#f8fafc` (Slate 50)
- Accent border: `#3b82f6` (Blue 500)
- Width: 320px fixed

**Content Area:**
- Background: `#f1f5f9` (Slate 100)
- Card background: `#ffffff`
- Card border: `#e2e8f0` (Slate 200)
- Card shadow: `0 1px 3px rgba(0,0,0,0.1)`

**Typography:**
- Font family: system-ui, -apple-system, sans-serif
- Headings: 600 weight
- Body: 400 weight
- Monospace (data): 'SF Mono', 'Consolas', monospace

**Status Colors:**
- Success/Received: `#22c55e` (Green 500)
- Warning/Pending: `#f59e0b` (Amber 500)
- Danger/Outstanding: `#ef4444` (Red 500)
- Info/Deadline: `#06b6d4` (Cyan 500)

**Service Colors:**
- Audit: `#3b82f6` (Blue 500)
- Tax: `#22c55e` (Green 500)
- Compilation: `#8b5cf6` (Violet 500)

---

## Component Descriptions

### KPI Cards
Four summary cards in a horizontal row at the top of the portfolio view. Each card has:
- Icon (SVG or emoji)
- Metric label
- Large numeric value
- Accent color strip on left border
- Subtle background tint matching accent color

### Client Cards
Grid of cards (2-3 per row, responsive). Each card contains:
- Company name (bold)
- Service pills (colored badges: Audit=blue, Tax=green, Compilation=purple)
- Progress bar per enabled service
- PBC outstanding count badge
- Next deadline with days-remaining
- Left border color indicates overall health: green (>75%), amber (25-75%), red (<25%)
- Hover effect: slight elevation + shadow increase

### PBC Table
Full-width sortable table in the client detail view:
- Columns: Ref, Document, Needed For, Status, Date Received, Remarks
- Status cells are color-coded (green pill for Received, red for Outstanding, amber for Pending)
- Filter buttons above table: All | Outstanding | Received
- Row click does not navigate (data is inline)

### Query Table
Table listing open queries:
- Columns: PM Ref, Service, Description, Amount (RM), Status, Date Raised
- Service column uses colored pill badges
- Status uses the same color-coding as PBC

### Timeline / Deadlines
Sorted list of upcoming deadlines:
- Each item shows: date, days remaining (badge), client name, service, description
- Color coding: red (<7 days), amber (7-30 days), green (>30 days)
- Overdue items highlighted with red background tint

### Service Panels
Horizontal panels in the client detail view (side by side):
- Service name and icon
- Status badge (not_started / in_progress / review / completed)
- Circular or linear progress indicator with percentage
- Current stage label (e.g., "Planning", "Fieldwork", "Completion")
- "Open Viewer" button linking to the sub-agent's viewer (port 8000)
