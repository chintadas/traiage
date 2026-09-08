// TRAIAGE - Raw Alerts View Controller

let allAlerts = [];
let filteredAlerts = [];
let selectedAlert = null;
let statsData = null;

// Filter State
const filterState = {
  severity: 'all',
  subsystem: 'all',
  rack: 'all',
  search: '',
  sortBy: 'timestamp-desc'
};

// DOM Elements
const tableBody = document.getElementById('alertsTableBody');
const visibleCountEl = document.getElementById('visibleCount');
const totalCountEl = document.getElementById('totalCount');
const tabRawCountEl = document.getElementById('tabRawCount');
const activeChipsEl = document.getElementById('activeChips');
const emptyStateEl = document.getElementById('emptyState');
const alertsTableEl = document.getElementById('alertsTable');

const searchInput = document.getElementById('searchInput');
const clearSearchBtn = document.getElementById('clearSearchBtn');
const filterSeverity = document.getElementById('filterSeverity');
const filterSubsystem = document.getElementById('filterSubsystem');
const filterRack = document.getElementById('filterRack');
const sortBySelect = document.getElementById('sortBy');
const resetFiltersBtn = document.getElementById('resetFiltersBtn');
const emptyResetBtn = document.getElementById('emptyResetBtn');

// Inspector Elements
const inspectorDrawer = document.getElementById('inspectorDrawer');
const drawerBackdrop = document.getElementById('drawerBackdrop');
const drawerEventId = document.getElementById('drawerEventId');
const drawerContent = document.getElementById('drawerContent');
const closeDrawerBtn = document.getElementById('closeDrawerBtn');
const toastNotification = document.getElementById('toastNotification');

// KPI Elements
const kpiTotal = document.getElementById('kpiTotal');
const kpiCritical = document.getElementById('kpiCritical');
const kpiWarning = document.getElementById('kpiWarning');
const kpiOk = document.getElementById('kpiOk');
const kpiRacks = document.getElementById('kpiRacks');
const kpiCards = document.querySelectorAll('.kpi-card[data-severity-filter]');

// Initialize Application
async function init() {
  setupEventListeners();
  await loadStats();
  await loadAlerts();
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
    kpiRacks.textContent = statsData.racks_affected;
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
function applyFilters() {
  let result = [...allAlerts];

  // Severity
  if (filterState.severity !== 'all') {
    result = result.filter(a => a.Severity.toLowerCase() === filterState.severity.toLowerCase());
  }

  // Subsystem
  if (filterState.subsystem !== 'all') {
    result = result.filter(a => a.Subsystem.toLowerCase() === filterState.subsystem.toLowerCase());
  }

  // Rack
  if (filterState.rack !== 'all') {
    result = result.filter(a => (a.Location?.Rack || '').toLowerCase() === filterState.rack.toLowerCase());
  }

  // Search
  if (filterState.search) {
    const q = filterState.search.toLowerCase().trim();
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

  // Sort
  const severityScore = { critical: 3, warning: 2, ok: 1 };
  if (filterState.sortBy === 'severity-desc') {
    result.sort((a, b) => (severityScore[b.Severity.toLowerCase()] || 0) - (severityScore[a.Severity.toLowerCase()] || 0));
  } else if (filterState.sortBy === 'rack-asc') {
    result.sort((a, b) => (a.Location?.Rack || '').localeCompare(b.Location?.Rack || ''));
  } else if (filterState.sortBy === 'timestamp-asc') {
    result.sort((a, b) => new Date(a.Timestamp) - new Date(b.Timestamp));
  } else {
    // timestamp-desc (default)
    result.sort((a, b) => new Date(b.Timestamp) - new Date(a.Timestamp));
  }

  filteredAlerts = result;
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
          <div style="font-family: var(--font-mono); font-size: 0.8rem; color: #e5e7eb;">${timeFormatted.time}</div>
          <div style="font-size: 0.7rem; color: var(--text-muted);">${timeFormatted.date}</div>
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
        <div class="drawer-v">${alert.Timestamp}</div>

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

// Event Listeners
function setupEventListeners() {
  // Search Input
  searchInput.addEventListener('input', (e) => {
    filterState.search = e.target.value;
    clearSearchBtn.style.display = filterState.search ? 'block' : 'none';
    applyFilters();
  });

  clearSearchBtn.addEventListener('click', () => {
    filterState.search = '';
    searchInput.value = '';
    clearSearchBtn.style.display = 'none';
    applyFilters();
  });

  // Severity Select
  filterSeverity.addEventListener('change', (e) => {
    filterState.severity = e.target.value;
    applyFilters();
  });

  // Subsystem Select
  filterSubsystem.addEventListener('change', (e) => {
    filterState.subsystem = e.target.value;
    applyFilters();
  });

  // Rack Select
  filterRack.addEventListener('change', (e) => {
    filterState.rack = e.target.value;
    applyFilters();
  });

  // Sort Select
  sortBySelect.addEventListener('change', (e) => {
    filterState.sortBy = e.target.value;
    applyFilters();
  });

  // Reset Buttons
  resetFiltersBtn.addEventListener('click', resetAllFilters);
  emptyResetBtn.addEventListener('click', resetAllFilters);

  // KPI card quick clicks
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

  // Drawer Close
  closeDrawerBtn.addEventListener('click', closeInspector);
  drawerBackdrop.addEventListener('click', closeInspector);
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeInspector();
  });
}

// Helpers
function formatTime(isoString) {
  const d = new Date(isoString);
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  const date = d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  return { time, date };
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Boot
window.addEventListener('DOMContentLoaded', init);
