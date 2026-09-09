// TRAIAGE - Alert & Incident Triage Controller

let allAlerts = [];
let filteredAlerts = [];
let selectedAlert = null;
let statsData = null;

// Raw Alerts Filter State
const filterState = {
  severity: 'all',
  subsystem: 'all',
  rack: 'all',
  search: '',
  sortBy: 'timestamp-desc'
};

// Incidents State & Filter
let allIncidents = [];
let filteredIncidents = [];
const incFilterState = {
  priority: 'all',
  category: 'all',
  status: 'all',
  search: ''
};

// DOM Elements: Common & Tabs
let tabRawAlerts, tabGroupedAlerts, tabRawCountEl, tabGroupedCountEl;
let rawAlertsView, groupedIncidentsView;

// DOM Elements: Raw Alerts
let tableBody, visibleCountEl, totalCountEl, activeChipsEl, emptyStateEl, alertsTableEl;
let searchInput, clearSearchBtn, filterSeverity, filterSubsystem, filterRack, sortBySelect, resetFiltersBtn, emptyResetBtn;
let inspectorDrawer, drawerBackdrop, drawerEventId, drawerContent, closeDrawerBtn, toastNotification;
let kpiTotal, kpiCritical, kpiWarning, kpiOk, kpiCards;

// DOM Elements: Grouped Incidents
let kpiIncTotal, kpiIncP1, kpiIncP2, kpiIncP3, kpiIncCards;
let incSearchInput, clearIncSearchBtn, filterIncPriority, filterIncCategory, filterIncStatus, resetIncFiltersBtn, emptyIncResetBtn;
let visibleIncCountEl, totalIncCountEl, activeIncChipsEl, incidentsListEl, emptyIncStateEl;

function initDomElements() {
  if (typeof document === 'undefined') return;

  // View Tabs
  tabRawAlerts = document.getElementById('tabRawAlerts');
  tabGroupedAlerts = document.getElementById('tabGroupedAlerts');
  tabRawCountEl = document.getElementById('tabRawCount');
  tabGroupedCountEl = document.getElementById('tabGroupedCount');
  rawAlertsView = document.getElementById('rawAlertsView');
  groupedIncidentsView = document.getElementById('groupedIncidentsView');

  // Raw Alerts View Elements
  tableBody = document.getElementById('alertsTableBody');
  visibleCountEl = document.getElementById('visibleCount');
  totalCountEl = document.getElementById('totalCount');
  activeChipsEl = document.getElementById('activeChips');
  emptyStateEl = document.getElementById('emptyState');
  alertsTableEl = document.getElementById('alertsTable');

  searchInput = document.getElementById('searchInput');
  clearSearchBtn = document.getElementById('clearSearchBtn');
  filterSeverity = document.getElementById('filterSeverity');
  filterSubsystem = document.getElementById('filterSubsystem');
  filterRack = document.getElementById('filterRack');
  sortBySelect = document.getElementById('sortBy');
  resetFiltersBtn = document.getElementById('resetFiltersBtn');
  emptyResetBtn = document.getElementById('emptyResetBtn');

  inspectorDrawer = document.getElementById('inspectorDrawer');
  drawerBackdrop = document.getElementById('drawerBackdrop');
  drawerEventId = document.getElementById('drawerEventId');
  drawerContent = document.getElementById('drawerContent');
  closeDrawerBtn = document.getElementById('closeDrawerBtn');
  toastNotification = document.getElementById('toastNotification');

  kpiTotal = document.getElementById('kpiTotal');
  kpiCritical = document.getElementById('kpiCritical');
  kpiWarning = document.getElementById('kpiWarning');
  kpiOk = document.getElementById('kpiOk');
  kpiCards = document.querySelectorAll('.kpi-card[data-severity-filter]');

  // Grouped Incidents Elements
  kpiIncTotal = document.getElementById('kpiIncTotal');
  kpiIncP1 = document.getElementById('kpiIncP1');
  kpiIncP2 = document.getElementById('kpiIncP2');
  kpiIncP3 = document.getElementById('kpiIncP3');
  kpiIncCards = document.querySelectorAll('.kpi-card[data-priority-filter]');

  incSearchInput = document.getElementById('incSearchInput');
  clearIncSearchBtn = document.getElementById('clearIncSearchBtn');
  filterIncPriority = document.getElementById('filterIncPriority');
  filterIncCategory = document.getElementById('filterIncCategory');
  filterIncStatus = document.getElementById('filterIncStatus');
  resetIncFiltersBtn = document.getElementById('resetIncFiltersBtn');
  emptyIncResetBtn = document.getElementById('emptyIncResetBtn');

  visibleIncCountEl = document.getElementById('visibleIncCount');
  totalIncCountEl = document.getElementById('totalIncCount');
  activeIncChipsEl = document.getElementById('activeIncChips');
  incidentsListEl = document.getElementById('incidentsList');
  emptyIncStateEl = document.getElementById('emptyIncState');
}

// Initialize Application
async function init() {
  initDomElements();
  setupEventListeners();
  await loadStats();
  await loadAlerts();
  await loadIncidents();
}

// Load Telemetry Stats
async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error('Failed to load stats');
    statsData = await res.json();

    kpiTotal.textContent = statsData.total;
    kpiCritical.textContent = statsData.critical;
    kpiWarning.textContent = statsData.warning;
    kpiOk.textContent = statsData.ok;
    totalCountEl.textContent = statsData.total;
    tabRawCountEl.textContent = statsData.total;

    // Populate Subsystems Dropdown
    filterSubsystem.innerHTML = '<option value="all">All Subsystems</option>';
    statsData.subsystems.forEach(sub => {
      const opt = document.createElement('option');
      opt.value = sub;
      opt.textContent = sub;
      filterSubsystem.appendChild(opt);
    });

    // Populate Racks Dropdown
    filterRack.innerHTML = '<option value="all">All Racks</option>';
    statsData.racks.forEach(rack => {
      const opt = document.createElement('option');
      opt.value = rack;
      opt.textContent = rack;
      filterRack.appendChild(opt);
    });
  } catch (err) {
    console.error('Error loading stats:', err);
  }
}

// Load Alerts
async function loadAlerts() {
  try {
    const res = await fetch('/api/alerts');
    if (!res.ok) throw new Error('Failed to load alerts');
    const data = await res.json();
    allAlerts = data.alerts || [];
    applyFilters();
  } catch (err) {
    console.error('Error loading alerts:', err);
  }
}

// Apply Filters & Search & Sort
// Pure Filter Logic
function filterAlerts(alerts, state) {
  let result = [...alerts];

  // Severity
  if (state.severity && state.severity !== 'all') {
    result = result.filter(a => a.Severity.toLowerCase() === state.severity.toLowerCase());
  }

  // Subsystem
  if (state.subsystem && state.subsystem !== 'all') {
    result = result.filter(a => a.Subsystem.toLowerCase() === state.subsystem.toLowerCase());
  }

  // Rack
  if (state.rack && state.rack !== 'all') {
    result = result.filter(a => (a.Location?.Rack || '').toLowerCase() === state.rack.toLowerCase());
  }

  // Search
  if (state.search) {
    const q = state.search.toLowerCase().trim();
    result = result.filter(a => {
      const corpus = [
        a.EventId,
        a.MessageId,
        a.Message,
        a.OriginOfCondition,
        a.Subsystem,
        a.Resolution,
        a.Location?.Rack,
        a.Location?.Chassis
      ].filter(Boolean).join(' ').toLowerCase();
      return corpus.includes(q);
    });
  }

  return result;
}

// Pure Sort Logic
function sortAlerts(alerts, sortBy = 'timestamp-desc') {
  const result = [...alerts];
  const severityScore = { critical: 3, warning: 2, ok: 1 };

  if (sortBy === 'severity-desc') {
    result.sort((a, b) => (severityScore[b.Severity.toLowerCase()] || 0) - (severityScore[a.Severity.toLowerCase()] || 0));
  } else if (sortBy === 'rack-asc') {
    result.sort((a, b) => (a.Location?.Rack || '').localeCompare(b.Location?.Rack || ''));
  } else if (sortBy === 'timestamp-asc') {
    result.sort((a, b) => new Date(a.Timestamp) - new Date(b.Timestamp));
  } else {
    // timestamp-desc (default)
    result.sort((a, b) => new Date(b.Timestamp) - new Date(a.Timestamp));
  }

  return result;
}

// Apply Filters & Search & Sort
function applyFilters() {
  const filtered = filterAlerts(allAlerts, filterState);
  filteredAlerts = sortAlerts(filtered, filterState.sortBy);
  renderTable();
  renderActiveChips();
  updateKPIHighlight();
}

// Render Table
function renderTable() {
  visibleCountEl.textContent = filteredAlerts.length;

  if (filteredAlerts.length === 0) {
    alertsTableEl.style.display = 'none';
    emptyStateEl.style.display = 'block';
    return;
  }

  alertsTableEl.style.display = 'table';
  emptyStateEl.style.display = 'none';

  tableBody.innerHTML = filteredAlerts.map(alert => {
    const sevClass = alert.Severity.toLowerCase();
    const timeFormatted = formatTime(alert.Timestamp);
    const loc = alert.Location || {};
    const locString = `${loc.Row || ''} / ${loc.Rack || ''}`;
    const chassisString = loc.Chassis ? `${loc.Chassis} (${loc.Slot || ''})` : '';

    return `
      <tr class="row-${sevClass}" onclick="openInspector('${alert.EventId}')">
        <td>
          <div style="font-weight: 600; color: #f3f4f6; font-size: 0.82rem; display: flex; align-items: center; gap: 0.35rem;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--color-cyan); flex-shrink: 0;">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            ${timeFormatted.relative}
          </div>
          <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted); margin-top: 0.15rem;">
            ${timeFormatted.time} • ${timeFormatted.date}
          </div>
        </td>
        <td>
          <span class="badge-severity ${sevClass}">
            <span class="alert-pulse ${sevClass === 'critical' ? 'red' : sevClass === 'warning' ? 'amber' : ''}"></span>
            ${alert.Severity}
          </span>
        </td>
        <td>
          <span class="badge-subsystem">${escapeHtml(alert.Subsystem)}</span>
        </td>
        <td>
          <div class="location-chip">
            <span class="location-rack">${escapeHtml(locString)}</span>
            <span class="location-detail">${escapeHtml(chassisString)}</span>
          </div>
        </td>
        <td>
          <div class="event-msg-container">
            <span class="event-id-tag">${escapeHtml(alert.EventId)}</span>
            <span class="event-msg">${escapeHtml(alert.Message)}</span>
          </div>
        </td>
        <td>
          <span class="message-id-code">${escapeHtml(alert.MessageId)}</span>
        </td>
        <td style="text-align: center;">
          <button class="btn-inspect" onclick="event.stopPropagation(); openInspector('${alert.EventId}')" title="Inspect Redfish JSON">
            Inspect
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// Render Active Filter Chips
function renderActiveChips() {
  const chips = [];

  if (filterState.severity !== 'all') {
    chips.push({ label: `Severity: ${filterState.severity}`, key: 'severity' });
  }
  if (filterState.subsystem !== 'all') {
    chips.push({ label: `Subsystem: ${filterState.subsystem}`, key: 'subsystem' });
  }
  if (filterState.rack !== 'all') {
    chips.push({ label: `Rack: ${filterState.rack}`, key: 'rack' });
  }
  if (filterState.search) {
    chips.push({ label: `Query: "${filterState.search}"`, key: 'search' });
  }

  activeChipsEl.innerHTML = chips.map(chip => `
    <span class="filter-chip">
      ${escapeHtml(chip.label)}
      <button onclick="removeFilter('${chip.key}')" aria-label="Remove filter">&times;</button>
    </span>
  `).join('');
}

function removeFilter(key) {
  if (key === 'severity') {
    filterState.severity = 'all';
    filterSeverity.value = 'all';
  } else if (key === 'subsystem') {
    filterState.subsystem = 'all';
    filterSubsystem.value = 'all';
  } else if (key === 'rack') {
    filterState.rack = 'all';
    filterRack.value = 'all';
  } else if (key === 'search') {
    filterState.search = '';
    searchInput.value = '';
    clearSearchBtn.style.display = 'none';
  }
  applyFilters();
}

function resetAllFilters() {
  filterState.severity = 'all';
  filterState.subsystem = 'all';
  filterState.rack = 'all';
  filterState.search = '';
  filterState.sortBy = 'timestamp-desc';

  filterSeverity.value = 'all';
  filterSubsystem.value = 'all';
  filterRack.value = 'all';
  searchInput.value = '';
  sortBySelect.value = 'timestamp-desc';
  clearSearchBtn.style.display = 'none';

  applyFilters();
}

function updateKPIHighlight() {
  kpiCards.forEach(card => {
    const f = card.getAttribute('data-severity-filter');
    if (f === filterState.severity) {
      card.classList.add('active');
    } else {
      card.classList.remove('active');
    }
  });
}

// Open Redfish Inspector
function openInspector(eventId) {
  const alert = allAlerts.find(a => a.EventId === eventId);
  if (!alert) return;

  selectedAlert = alert;
  drawerEventId.textContent = alert.EventId;

  const sevClass = alert.Severity.toLowerCase();
  const loc = alert.Location || {};
  const jsonStr = JSON.stringify(alert, null, 2);

  drawerContent.innerHTML = `
    <!-- Summary Card -->
    <div class="drawer-card">
      <div class="drawer-section-title">
        <span>Event Overview</span>
        <span class="badge-severity ${sevClass}">${alert.Severity}</span>
      </div>
      <div class="drawer-msg">${escapeHtml(alert.Message)}</div>
      <div class="drawer-kv-grid">
        <div class="drawer-k">Subsystem:</div>
        <div class="drawer-v">${escapeHtml(alert.Subsystem)}</div>

        <div class="drawer-k">MessageId:</div>
        <div class="drawer-v">${escapeHtml(alert.MessageId)}</div>

        <div class="drawer-k">Timestamp:</div>
        <div class="drawer-v">${alert.Timestamp} <span style="color: var(--color-cyan); font-family: var(--font-sans); font-size: 0.78rem;">(${formatRelativeTime(alert.Timestamp)})</span></div>

        <div class="drawer-k">Physical Location:</div>
        <div class="drawer-v">${loc.DataCenter} / ${loc.Room} / ${loc.Row} / ${loc.Rack}</div>

        <div class="drawer-k">Chassis / Slot:</div>
        <div class="drawer-v">${loc.Chassis || 'N/A'} (Slot ${loc.Slot || 'N/A'})</div>
      </div>
    </div>

    <!-- Redfish Origin -->
    <div class="drawer-card">
      <div class="drawer-section-title">Origin of Condition</div>
      <div style="font-family: var(--font-mono); font-size: 0.78rem; color: #38bdf8; background: #070a11; padding: 0.6rem 0.8rem; border-radius: 6px; word-break: break-all; border: 1px solid var(--border-color);">
        ${escapeHtml(alert.OriginOfCondition)}
      </div>
    </div>

    <!-- Recommended Operator Resolution -->
    <div class="drawer-card">
      <div class="drawer-section-title">Recommended Resolution</div>
      <div class="resolution-box">
        <strong>Action: </strong> ${escapeHtml(alert.Resolution || 'Review telemetry and monitor node.')}
      </div>
    </div>

    <!-- DMTF Redfish JSON Block -->
    <div class="drawer-card">
      <div class="json-viewer-header">
        <div class="drawer-section-title" style="margin: 0;">Redfish Event Record JSON</div>
        <button class="btn-copy-json" onclick="copyAlertJson()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          Copy JSON
        </button>
      </div>
      <pre class="json-code-block"><code>${escapeHtml(jsonStr)}</code></pre>
    </div>
  `;

  inspectorDrawer.classList.add('open');
  drawerBackdrop.classList.add('show');
}

function closeInspector() {
  inspectorDrawer.classList.remove('open');
  drawerBackdrop.classList.remove('show');
  selectedAlert = null;
}

function copyAlertJson() {
  if (!selectedAlert) return;
  navigator.clipboard.writeText(JSON.stringify(selectedAlert, null, 2)).then(() => {
    showToast('Redfish JSON copied to clipboard!');
  }).catch(err => {
    console.error('Failed to copy JSON:', err);
  });
}

function showToast(msg) {
  toastNotification.textContent = msg;
  toastNotification.classList.add('show');
  setTimeout(() => {
    toastNotification.classList.remove('show');
  }, 2200);
}

// View Switching
function switchView(viewName) {
  if (viewName === 'raw') {
    if (tabRawAlerts) tabRawAlerts.classList.add('active');
    if (tabGroupedAlerts) tabGroupedAlerts.classList.remove('active');
    if (rawAlertsView) rawAlertsView.style.display = 'block';
    if (groupedIncidentsView) groupedIncidentsView.style.display = 'none';
  } else if (viewName === 'grouped') {
    if (tabGroupedAlerts) tabGroupedAlerts.classList.add('active');
    if (tabRawAlerts) tabRawAlerts.classList.remove('active');
    if (groupedIncidentsView) groupedIncidentsView.style.display = 'block';
    if (rawAlertsView) rawAlertsView.style.display = 'none';
    if (!allIncidents || allIncidents.length === 0) {
      loadIncidents();
    }
  }
}

// Load Incidents
async function loadIncidents() {
  try {
    const res = await fetch('/api/incidents');
    if (!res.ok) throw new Error('Failed to load incidents');
    const data = await res.json();
    allIncidents = data.incidents || [];

    const total = allIncidents.length;
    const p1Count = allIncidents.filter(i => i.priority === 'P1').length;
    const p2Count = allIncidents.filter(i => i.priority === 'P2').length;
    const p3Count = allIncidents.filter(i => i.priority === 'P3').length;

    if (kpiIncTotal) kpiIncTotal.textContent = total;
    if (kpiIncP1) kpiIncP1.textContent = p1Count;
    if (kpiIncP2) kpiIncP2.textContent = p2Count;
    if (kpiIncP3) kpiIncP3.textContent = p3Count;
    if (tabGroupedCountEl) tabGroupedCountEl.textContent = total;
    if (totalIncCountEl) totalIncCountEl.textContent = total;

    applyIncFilters();
  } catch (err) {
    console.error('Error loading incidents:', err);
  }
}

// Pure Incident Filtering
function filterIncidents(incidents, state) {
  let result = [...incidents];

  if (state.priority && state.priority !== 'all') {
    result = result.filter(inc => inc.priority.toLowerCase() === state.priority.toLowerCase());
  }

  if (state.category && state.category !== 'all') {
    result = result.filter(inc => inc.category.toLowerCase() === state.category.toLowerCase());
  }

  if (state.status && state.status !== 'all') {
    result = result.filter(inc => inc.status.toLowerCase() === state.status.toLowerCase());
  }

  if (state.search && state.search.trim()) {
    const q = state.search.toLowerCase().trim();
    result = result.filter(inc => {
      const corpus = `${inc.id} ${inc.title} ${inc.root_cause_hypothesis} ${inc.root_cause_component} ${inc.root_cause_location} ${inc.dispatch_target} ${inc.category} ${inc.blast_radius_summary}`.toLowerCase();
      return corpus.includes(q);
    });
  }

  return result;
}

function applyIncFilters() {
  filteredIncidents = filterIncidents(allIncidents, incFilterState);
  if (visibleIncCountEl) visibleIncCountEl.textContent = filteredIncidents.length;
  renderActiveIncChips();
  renderIncidents();
}

function renderActiveIncChips() {
  if (!activeIncChipsEl) return;
  activeIncChipsEl.innerHTML = '';

  const chips = [];
  if (incFilterState.priority !== 'all') chips.push({ type: 'priority', label: `Priority: ${incFilterState.priority}` });
  if (incFilterState.category !== 'all') chips.push({ type: 'category', label: `Category: ${incFilterState.category}` });
  if (incFilterState.status !== 'all') chips.push({ type: 'status', label: `Status: ${incFilterState.status}` });
  if (incFilterState.search) chips.push({ type: 'search', label: `"${incFilterState.search}"` });

  chips.forEach(chip => {
    const el = document.createElement('div');
    el.className = 'chip';
    el.innerHTML = `<span>${escapeHtml(chip.label)}</span><button class="chip-remove" data-type="${chip.type}">&times;</button>`;
    el.querySelector('.chip-remove').addEventListener('click', () => {
      if (chip.type === 'priority') { incFilterState.priority = 'all'; if (filterIncPriority) filterIncPriority.value = 'all'; }
      if (chip.type === 'category') { incFilterState.category = 'all'; if (filterIncCategory) filterIncCategory.value = 'all'; }
      if (chip.type === 'status') { incFilterState.status = 'all'; if (filterIncStatus) filterIncStatus.value = 'all'; }
      if (chip.type === 'search') { incFilterState.search = ''; if (incSearchInput) { incSearchInput.value = ''; clearIncSearchBtn.style.display = 'none'; } }
      applyIncFilters();
    });
    activeIncChipsEl.appendChild(el);
  });
}

function renderIncidents() {
  if (!incidentsListEl) return;

  if (filteredIncidents.length === 0) {
    incidentsListEl.innerHTML = '';
    if (emptyIncStateEl) emptyIncStateEl.style.display = 'block';
    return;
  }

  if (emptyIncStateEl) emptyIncStateEl.style.display = 'none';

  const categoryIcons = {
    LiquidCooling: '💧',
    Power: '⚡',
    NetworkFabric: '🌐',
    ComputeHost: '🖥️',
    Storage: '💾',
    Environmental: '🌡️',
    Management: '⚙️'
  };

  const html = filteredIncidents.map(inc => {
    const prioLower = inc.priority.toLowerCase();
    const catIcon = categoryIcons[inc.category] || '⚠️';
    const statusLower = inc.status.toLowerCase();
    
    // Timing
    const timeFormatted = formatTime(inc.first_event_time);
    const latestFormatted = formatTime(inc.latest_event_time);
    const durationText = inc.first_event_time !== inc.latest_event_time
      ? `Span: ${timeFormatted.time} → ${latestFormatted.time}`
      : `Triggered: ${timeFormatted.time}`;

    // Redundancy Pill Class
    let redundancyClass = 'redundancy-optimal';
    if (inc.redundancy_status.includes('N-0')) redundancyClass = 'redundancy-n0';
    else if (inc.redundancy_status.includes('N-1')) redundancyClass = 'redundancy-n1';

    // Playbook steps HTML
    const playbookHtml = (inc.dispatch_playbook || []).map((step, idx) => `
      <li class="playbook-step">
        <span class="step-num">${idx + 1}</span>
        <span>${escapeHtml(step)}</span>
      </li>
    `).join('');

    // Impacted nodes tags
    const impactedNodesHtml = (inc.impacted_nodes || []).slice(0, 8).map(node => `
      <span class="node-tag">${escapeHtml(node)}</span>
    `).join('') + ((inc.impacted_nodes && inc.impacted_nodes.length > 8) ? `<span class="node-tag">+${inc.impacted_nodes.length - 8} more</span>` : '');

    // Correlated Alerts table rows
    const childRowsHtml = (inc.dependent_alert_ids || []).map(alertId => {
      const alertObj = allAlerts.find(a => a.Id === alertId);
      const isRoot = alertId === inc.root_cause_alert_id;
      const sev = alertObj ? alertObj.Severity : 'Warning';
      const msg = alertObj ? alertObj.Message : `Redfish Alert ${alertId}`;
      const timeStr = alertObj ? formatRelativeTime(alertObj.Timestamp) : 'telemetry';

      return `
        <tr class="${isRoot ? 'is-root' : ''}">
          <td style="font-family: var(--font-mono); font-weight: 600;">
            ${escapeHtml(alertId)}
            ${isRoot ? '<span class="root-indicator-pill">Root Cause</span>' : ''}
          </td>
          <td>
            <span class="badge badge-${sev.toLowerCase()}">${sev}</span>
          </td>
          <td style="color: var(--text-muted);">${timeStr}</td>
          <td style="max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(msg)}">
            ${escapeHtml(msg)}
          </td>
          <td>
            <button class="btn-child-inspect" onclick="openInspector('${escapeHtml(alertId)}')">
              Inspect
            </button>
          </td>
        </tr>
      `;
    }).join('');

    // Action button based on status
    let actionBtnHtml = '';
    if (inc.status === 'Active') {
      actionBtnHtml = `<button class="btn-ack" onclick="updateIncidentStatus('${escapeHtml(inc.id)}', 'Acknowledged')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        Acknowledge
      </button>`;
    } else if (inc.status === 'Acknowledged') {
      actionBtnHtml = `<button class="btn-ack" style="color: #6ee7b7; border-color: rgba(16, 185, 129, 0.4);" onclick="updateIncidentStatus('${escapeHtml(inc.id)}', 'Resolved')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
        Mark Resolved
      </button>`;
    }

    return `
      <article class="incident-card priority-${prioLower}" id="card-${escapeHtml(inc.id)}">
        <!-- Top Header -->
        <div class="incident-header">
          <div class="incident-header-left">
            <span class="priority-badge ${prioLower}">
              ${prioLower === 'p1' ? '<span class="alert-pulse red"></span>' : ''}
              ${prioLower === 'p2' ? '<span class="alert-pulse amber"></span>' : ''}
              ${escapeHtml(inc.priority)} CRITICAL
            </span>
            <span class="incident-id">${escapeHtml(inc.id)}</span>
            <span class="category-chip">${catIcon} ${escapeHtml(inc.category)}</span>
            <span class="status-badge ${statusLower}">${escapeHtml(inc.status)}</span>
          </div>
          <div class="incident-header-right">
            ${actionBtnHtml}
          </div>
        </div>

        <!-- Title & Timing -->
        <div class="incident-title-row">
          <h2 class="incident-title">${escapeHtml(inc.title)}</h2>
          <div class="incident-timing">
            <div class="timing-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
              <span>First seen: ${timeFormatted.relative} (${timeFormatted.time})</span>
            </div>
            <div class="timing-item">
              <span style="color: var(--color-cyan);">⚡ ${inc.dependent_alerts_count} Correlated Redfish Alerts</span>
            </div>
          </div>
        </div>

        <!-- Hypothesis Callout Panel -->
        <div class="hypothesis-panel">
          <div class="hypothesis-header">
            <div class="hypothesis-tag">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
              </svg>
              AI Root-Cause Hypothesis & Topology Traversal
            </div>
            <button class="btn-inspect-root" onclick="openInspector('${escapeHtml(inc.root_cause_alert_id)}')">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
              Inspect Root Alert (${escapeHtml(inc.root_cause_alert_id)})
            </button>
          </div>
          <p class="hypothesis-text">${escapeHtml(inc.root_cause_hypothesis)}</p>
          <div class="root-cause-meta">
            <div class="root-cause-node">
              <span>Originating Node:</span>
              <span class="node-highlight">${escapeHtml(inc.root_cause_component)}</span>
            </div>
            <div class="root-cause-node">
              <span>Location:</span>
              <span style="color: #cbd5e1;">${escapeHtml(inc.root_cause_location)}</span>
            </div>
          </div>
        </div>

        <!-- Impact & Redundancy Grid -->
        <div class="incident-impact-grid">
          <div class="impact-box">
            <div class="impact-box-label">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              </svg>
              Redundancy Health
            </div>
            <span class="redundancy-pill ${redundancyClass}">
              ${escapeHtml(inc.redundancy_status)}
            </span>
          </div>
          <div class="impact-box">
            <div class="impact-box-label">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <circle cx="12" cy="12" r="6"></circle>
                <circle cx="12" cy="12" r="2"></circle>
              </svg>
              Blast Radius Summary
            </div>
            <div class="blast-radius-desc">${escapeHtml(inc.blast_radius_summary)}</div>
            <div class="impacted-nodes-tags">${impactedNodesHtml}</div>
          </div>
        </div>

        <!-- Dispatch & Playbook -->
        <div class="dispatch-section">
          <div class="dispatch-header">
            <div class="dispatch-target-badge">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
              Dispatch: ${escapeHtml(inc.dispatch_target)}
            </div>
            <span style="color: var(--text-muted); font-size: 0.72rem;">Operational Playbook (${(inc.dispatch_playbook || []).length} steps)</span>
          </div>
          <ul class="playbook-list">
            ${playbookHtml}
          </ul>
        </div>

        <!-- Collapsible Correlated Alerts Accordion -->
        <div class="correlated-alerts-toggle" onclick="toggleCorrelatedAlerts('${escapeHtml(inc.id)}')">
          <div class="toggle-left">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path>
            </svg>
            <span>Correlated Redfish Alerts (${inc.dependent_alerts_count})</span>
          </div>
          <svg class="toggle-icon" id="toggle-icon-${escapeHtml(inc.id)}" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>

        <div class="correlated-alerts-panel" id="panel-${escapeHtml(inc.id)}">
          <table class="child-alerts-table">
            <thead>
              <tr>
                <th>Alert ID</th>
                <th>Severity</th>
                <th>Age</th>
                <th>Message</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${childRowsHtml}
            </tbody>
          </table>
        </div>
      </article>
    `;
  }).join('');

  incidentsListEl.innerHTML = html;
}

// Update Incident Status
async function updateIncidentStatus(incidentId, newStatus) {
  try {
    const res = await fetch(`/api/incidents/${encodeURIComponent(incidentId)}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (!res.ok) throw new Error('Failed to update status');
    const updated = await res.json();

    const target = allIncidents.find(i => i.id === incidentId);
    if (target) {
      target.status = updated.status;
    }
    applyIncFilters();
    showToast(`Incident ${incidentId} marked as ${newStatus}`);
  } catch (err) {
    console.error('Error updating status:', err);
    showToast(`Failed to update status for ${incidentId}`);
  }
}

// Toggle Child Alerts
function toggleCorrelatedAlerts(incidentId) {
  const panel = document.getElementById(`panel-${incidentId}`);
  const icon = document.getElementById(`toggle-icon-${incidentId}`);
  if (!panel) return;

  const isShowing = panel.classList.contains('show');
  if (isShowing) {
    panel.classList.remove('show');
    if (icon && icon.parentElement) icon.parentElement.classList.remove('expanded');
  } else {
    panel.classList.add('show');
    if (icon && icon.parentElement) icon.parentElement.classList.add('expanded');
  }
}

// Reset Incident Filters
function resetAllIncFilters() {
  incFilterState.priority = 'all';
  incFilterState.category = 'all';
  incFilterState.status = 'all';
  incFilterState.search = '';

  if (filterIncPriority) filterIncPriority.value = 'all';
  if (filterIncCategory) filterIncCategory.value = 'all';
  if (filterIncStatus) filterIncStatus.value = 'all';
  if (incSearchInput) {
    incSearchInput.value = '';
    clearIncSearchBtn.style.display = 'none';
  }

  applyIncFilters();
}

// Event Listeners
function setupEventListeners() {
  // Tab Switching
  if (tabRawAlerts) {
    tabRawAlerts.addEventListener('click', () => switchView('raw'));
  }
  if (tabGroupedAlerts) {
    tabGroupedAlerts.addEventListener('click', () => switchView('grouped'));
  }

  // Raw Alerts Search Input
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      filterState.search = e.target.value;
      clearSearchBtn.style.display = filterState.search ? 'block' : 'none';
      applyFilters();
    });
  }

  if (clearSearchBtn) {
    clearSearchBtn.addEventListener('click', () => {
      filterState.search = '';
      searchInput.value = '';
      clearSearchBtn.style.display = 'none';
      applyFilters();
    });
  }

  // Raw Alerts Filters
  if (filterSeverity) {
    filterSeverity.addEventListener('change', (e) => {
      filterState.severity = e.target.value;
      applyFilters();
    });
  }

  if (filterSubsystem) {
    filterSubsystem.addEventListener('change', (e) => {
      filterState.subsystem = e.target.value;
      applyFilters();
    });
  }

  if (filterRack) {
    filterRack.addEventListener('change', (e) => {
      filterState.rack = e.target.value;
      applyFilters();
    });
  }

  if (sortBySelect) {
    sortBySelect.addEventListener('change', (e) => {
      filterState.sortBy = e.target.value;
      applyFilters();
    });
  }

  // Raw Alerts Reset
  if (resetFiltersBtn) resetFiltersBtn.addEventListener('click', resetAllFilters);
  if (emptyResetBtn) emptyResetBtn.addEventListener('click', resetAllFilters);

  // Raw Alerts KPI Cards
  if (kpiCards) {
    kpiCards.forEach(card => {
      card.addEventListener('click', () => {
        const targetSev = card.getAttribute('data-severity-filter');
        if (filterState.severity === targetSev) {
          filterState.severity = 'all';
          filterSeverity.value = 'all';
        } else {
          filterState.severity = targetSev;
          filterSeverity.value = targetSev;
        }
        applyFilters();
      });
    });
  }

  // Incident Search Input
  if (incSearchInput) {
    incSearchInput.addEventListener('input', (e) => {
      incFilterState.search = e.target.value;
      if (clearIncSearchBtn) clearIncSearchBtn.style.display = incFilterState.search ? 'block' : 'none';
      applyIncFilters();
    });
  }

  if (clearIncSearchBtn) {
    clearIncSearchBtn.addEventListener('click', () => {
      incFilterState.search = '';
      if (incSearchInput) incSearchInput.value = '';
      clearIncSearchBtn.style.display = 'none';
      applyIncFilters();
    });
  }

  // Incident Filters
  if (filterIncPriority) {
    filterIncPriority.addEventListener('change', (e) => {
      incFilterState.priority = e.target.value;
      applyIncFilters();
    });
  }

  if (filterIncCategory) {
    filterIncCategory.addEventListener('change', (e) => {
      incFilterState.category = e.target.value;
      applyIncFilters();
    });
  }

  if (filterIncStatus) {
    filterIncStatus.addEventListener('change', (e) => {
      incFilterState.status = e.target.value;
      applyIncFilters();
    });
  }

  // Incident Reset
  if (resetIncFiltersBtn) resetIncFiltersBtn.addEventListener('click', resetAllIncFilters);
  if (emptyIncResetBtn) emptyIncResetBtn.addEventListener('click', resetAllIncFilters);

  // Incident KPI Cards
  if (kpiIncCards) {
    kpiIncCards.forEach(card => {
      card.addEventListener('click', () => {
        const targetPrio = card.getAttribute('data-priority-filter');
        if (incFilterState.priority === targetPrio) {
          incFilterState.priority = 'all';
          if (filterIncPriority) filterIncPriority.value = 'all';
        } else {
          incFilterState.priority = targetPrio;
          if (filterIncPriority) filterIncPriority.value = targetPrio;
        }
        applyIncFilters();
      });
    });
  }

  // Drawer Close
  if (closeDrawerBtn) closeDrawerBtn.addEventListener('click', closeInspector);
  if (drawerBackdrop) drawerBackdrop.addEventListener('click', closeInspector);
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeInspector();
  });
}

// Helpers
function formatRelativeTime(isoString, nowMs = Date.now()) {
  const alertTime = new Date(isoString).getTime();
  const diffSec = Math.max(0, Math.floor((nowMs - alertTime) / 1000));

  if (diffSec < 60) {
    return 'just now';
  }

  const totalMin = Math.floor(diffSec / 60);
  if (totalMin < 60) {
    return `${totalMin}m ago`;
  }

  const totalHours = Math.floor(totalMin / 60);
  const remMin = totalMin % 60;
  if (totalHours < 24) {
    return remMin > 0 ? `${totalHours}h ${remMin}m ago` : `${totalHours}h ago`;
  }

  const days = Math.floor(totalHours / 24);
  const remHours = totalHours % 24;
  return remHours > 0 ? `${days}d ${remHours}h ago` : `${days}d ago`;
}

function formatTime(isoString, nowMs = Date.now()) {
  const d = new Date(isoString);
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  const date = d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  const relative = formatRelativeTime(isoString, nowMs);
  return { time, date, relative };
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Browser Initialization
if (typeof window !== 'undefined') {
  window.switchView = switchView;
  window.updateIncidentStatus = updateIncidentStatus;
  window.toggleCorrelatedAlerts = toggleCorrelatedAlerts;
  window.resetAllIncFilters = resetAllIncFilters;
  window.openInspector = openInspector;
  window.copyAlertJson = copyAlertJson;

  window.addEventListener('DOMContentLoaded', init);

  // Auto-refresh relative time every 30 seconds
  setInterval(() => {
    if (typeof filteredAlerts !== 'undefined' && filteredAlerts && filteredAlerts.length > 0) {
      renderTable();
    }
  }, 30000);
}

// Node.js module export for unit testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    formatRelativeTime,
    formatTime,
    escapeHtml,
    filterAlerts,
    sortAlerts,
    filterIncidents
  };
}
