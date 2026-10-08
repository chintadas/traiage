// TRAIAGE - Incident Detail Controller

let currentIncident = null;
let allAlerts = [];
let allIncidents = [];

// DOM Elements
const breadcrumbIncidentTitle = document.getElementById('breadcrumbIncidentTitle');
const incidentSeverityBadge = document.getElementById('incidentSeverityBadge');
const incidentTitle = document.getElementById('incidentTitle');
const incidentStatusBadge = document.getElementById('incidentStatusBadge');
const incidentTimeAgo = document.getElementById('incidentTimeAgo');
const incidentLocation = document.getElementById('incidentLocation');
const incidentDetailSummary = document.getElementById('incidentDetailSummary');

const alertsCountBadge = document.getElementById('alertsCountBadge');
const alertsTableBody = document.getElementById('alertsTableBody');

const causeChainContainer = document.getElementById('causeChainContainer');
const hypothesisText = document.getElementById('hypothesisText');
const actionsListContainer = document.getElementById('actionsListContainer');
const actionsCountBadge = document.getElementById('actionsCountBadge');

const inspectorDrawer = document.getElementById('inspectorDrawer');
const drawerBackdrop = document.getElementById('drawerBackdrop');
const drawerEventId = document.getElementById('drawerEventId');
const drawerContent = document.getElementById('drawerContent');
const closeDrawerBtn = document.getElementById('closeDrawerBtn');
const toastNotification = document.getElementById('toastNotification');

// Priority to severity mapping
const prioMap = {
  P1: { label: 'CRITICAL', class: 'badge-critical' },
  P2: { label: 'MAJOR', class: 'badge-major' },
  P3: { label: 'MINOR', class: 'badge-minor' },
  P4: { label: 'INFO', class: 'badge-info' }
};

// Relative Time Formatter
function formatRelativeTime(isoString, nowMs = Date.now()) {
  if (!isoString) return 'recently';
  const alertTime = new Date(isoString).getTime();
  const diffSec = Math.max(0, Math.floor((nowMs - alertTime) / 1000));

  if (diffSec < 60) return 'just now';
  const totalMin = Math.floor(diffSec / 60);
  if (totalMin < 60) return `${totalMin}m ago`;
  const totalHours = Math.floor(totalMin / 60);
  const remMin = totalMin % 60;
  if (totalHours < 24) {
    return remMin > 0 ? `${totalHours}h ${remMin}m ago` : `${totalHours}h ago`;
  }
  const days = Math.floor(totalHours / 24);
  const remHours = totalHours % 24;
  return remHours > 0 ? `${days}d ${remHours}h ago` : `${days}d ago`;
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

function showToast(msg) {
  if (!toastNotification) return;
  toastNotification.textContent = msg;
  toastNotification.classList.add('show');
  setTimeout(() => {
    toastNotification.classList.remove('show');
  }, 2200);
}

// Accordion Toggle
function toggleAccordion(id) {
  const card = document.getElementById(id);
  if (card) {
    card.classList.toggle('open');
  }
}
window.toggleAccordion = toggleAccordion;

// Initialize
async function initDetail() {
  const params = new URLSearchParams(window.location.search);
  const incidentId = params.get('id');

  try {
    // Fetch both alerts and incidents
    const [incidentsRes, alertsRes] = await Promise.all([
      fetch('/api/incidents'),
      fetch('/api/alerts')
    ]);

    if (!incidentsRes.ok || !alertsRes.ok) {
      throw new Error('Failed to load incident telemetry');
    }

    const incData = await incidentsRes.json();
    const alertData = await alertsRes.json();

    allIncidents = incData.incidents || [];
    allAlerts = alertData.alerts || [];

    // Find requested incident, or default to the first one
    if (incidentId) {
      currentIncident = allIncidents.find(i => i.id.toLowerCase() === incidentId.toLowerCase());
    }
    if (!currentIncident && allIncidents.length > 0) {
      currentIncident = allIncidents[0];
    }

    if (!currentIncident) {
      incidentTitle.textContent = 'Incident Not Found';
      incidentDetailSummary.textContent = 'The requested incident could not be found in active telemetry.';
      return;
    }

    renderIncidentDetail(currentIncident);
  } catch (err) {
    console.error('Error initializing incident detail:', err);
    incidentTitle.textContent = 'Telemetry Connection Error';
    incidentDetailSummary.textContent = 'Unable to fetch incident details from backend API.';
  }
}

function renderIncidentDetail(inc) {
  // Breadcrumb & Page Title
  document.title = `${inc.title} - TRAIAGE`;
  breadcrumbIncidentTitle.textContent = inc.title;

  // Header Title & Severity
  incidentTitle.textContent = inc.title;
  const sevInfo = prioMap[inc.priority] || { label: inc.priority || 'INFO', class: 'badge-info' };
  incidentSeverityBadge.textContent = sevInfo.label;
  incidentSeverityBadge.className = `badge ${sevInfo.class}`;

  // Status Badge & Recency
  const s = (inc.status || '').toLowerCase();
  let statusClass = 'badge-new';
  let statusText = 'NEW';
  if (s === 'assigned' || s === 'investigating') {
    statusClass = 'badge-assigned';
    statusText = 'ASSIGNED';
  } else if (s === 'acknowledged') {
    statusClass = 'badge-assigned';
    statusText = 'ACKNOWLEDGED';
  } else if (s === 'resolved') {
    statusClass = 'badge-resolved';
    statusText = 'RESOLVED';
  } else if (s === 'unassigned') {
    statusClass = 'badge-unassigned';
    statusText = 'UNASSIGNED';
  }

  incidentStatusBadge.textContent = statusText;
  incidentStatusBadge.className = `badge ${statusClass}`;

  const timeAgo = formatRelativeTime(inc.latest_event_time || inc.first_event_time || inc.last_seen);
  incidentTimeAgo.textContent = timeAgo;

  // Location
  incidentLocation.textContent = inc.root_cause_location || inc.root_cause_component || 'Facility Wide';

  // Detail narrative description
  incidentDetailSummary.textContent = inc.impact_summary || inc.root_cause_hypothesis || 'Incident telemetry active.';

  // Correlated Alerts Table
  const alertIds = inc.dependent_alert_ids && inc.dependent_alert_ids.length > 0
    ? inc.dependent_alert_ids
    : (inc.alert_ids || [inc.root_cause_alert_id]);

  alertsCountBadge.textContent = `${alertIds.length} Correlated`;

  const rowsHtml = alertIds.map(alertId => {
    const alertObj = allAlerts.find(a => a.EventId === alertId);
    const isRoot = alertId === inc.root_cause_alert_id;
    const msg = alertObj ? alertObj.Message : `Alert ${alertId}`;
    const started = alertObj ? formatRelativeTime(alertObj.Timestamp) : '—';
    const loc = alertObj?.Location
      ? [alertObj.Location.Rack, alertObj.Location.Chassis].filter(Boolean).join(', ')
      : (alertObj?.OriginOfCondition || '—');
    const sev = alertObj ? alertObj.Severity : 'Warning';
    
    let sevBadgeClass = 'badge-major';
    if (sev === 'Critical') sevBadgeClass = 'badge-critical';
    else if (sev === 'OK') sevBadgeClass = 'badge-minor';

    let alertStatus = isRoot ? 'Triggered' : 'Active';

    return `
      <tr style="cursor: pointer;" onclick="openInspector('${escapeHtml(alertId)}')" title="Click to view Redfish Event ${escapeHtml(alertId)}">
        <td>
          ${escapeHtml(msg)}
          ${isRoot ? '<span class="root-indicator-pill">Root Cause</span>' : ''}
        </td>
        <td class="mono-cell">${escapeHtml(started)}</td>
        <td class="mono-cell" title="${escapeHtml(loc)}">${escapeHtml(loc)}</td>
        <td><span class="badge ${sevBadgeClass}">${escapeHtml(sev)}</span></td>
        <td><span class="badge badge-unassigned">${alertStatus}</span></td>
      </tr>
    `;
  }).join('');

  alertsTableBody.innerHTML = rowsHtml;

  // Root Cause Hypothesis Section
  hypothesisText.textContent = inc.root_cause_hypothesis || 'No root cause hypothesis generated.';

  // Build Causal Chain visualization
  const chainSteps = [];
  if (inc.root_cause_component) chainSteps.push(inc.root_cause_component);
  if (inc.category) chainSteps.push(`${inc.category} Cascade`);
  if (inc.dispatch_target) chainSteps.push(`${inc.dispatch_target} Impact`);

  if (chainSteps.length > 1) {
    causeChainContainer.innerHTML = chainSteps.map((step, idx) => `
      <span class="chain-node">${escapeHtml(step)}</span>
      ${idx < chainSteps.length - 1 ? '<span class="chain-arrow">&rarr;</span>' : ''}
    `).join('');
  } else {
    causeChainContainer.innerHTML = `
      <span class="chain-node">${escapeHtml(inc.root_cause_location || 'Component')}</span>
      <span class="chain-arrow">&rarr;</span>
      <span class="chain-node">${escapeHtml(inc.title)}</span>
    `;
  }

  // Suggested Actions Section
  const playbook = inc.dispatch_playbook || inc.recommended_actions || [];
  if (actionsCountBadge) {
    actionsCountBadge.textContent = `${playbook.length} Playbook Steps`;
  }

  if (playbook.length === 0) {
    actionsListContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No automated playbook actions currently registered for this incident category.</div>';
  } else {
    actionsListContainer.innerHTML = playbook.map((step, idx) => {
      let btnLabel = 'Execute Step';
      let btnClass = 'action-btn';
      if (idx === 0) {
        btnLabel = 'Dispatch Tech';
        btnClass = 'action-btn primary';
      } else if (idx === 1) {
        btnLabel = 'Run Diagnostic';
      } else {
        btnLabel = 'Mark Verified';
      }

      return `
        <div class="action-item">
          <div class="action-step-num">${idx + 1}</div>
          <div class="action-content">
            <div class="action-title">${escapeHtml(step)}</div>
            <div class="action-desc">Target team: ${escapeHtml(inc.dispatch_target || 'Site Operations')}</div>
          </div>
          <button class="${btnClass}" onclick="handleActionClick(${idx + 1}, '${escapeHtml(inc.id)}')">${btnLabel}</button>
        </div>
      `;
    }).join('');
  }
}

// Action Handler
window.handleActionClick = function(stepNum, incidentId) {
  showToast(`Playbook step ${stepNum} acknowledged for ${incidentId}`);
};

// DMTF Redfish Inspector Drawer
window.openInspector = function(eventId) {
  const alertObj = allAlerts.find(a => a.EventId === eventId);
  if (!alertObj || !inspectorDrawer || !drawerBackdrop) return;

  drawerEventId.textContent = alertObj.EventId;

  const jsonStr = JSON.stringify(alertObj, null, 2);

  drawerContent.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
      <span class="badge ${alertObj.Severity === 'Critical' ? 'badge-critical' : 'badge-major'}">${escapeHtml(alertObj.Severity)}</span>
      <button class="btn-ack" onclick="navigator.clipboard.writeText(document.getElementById('rawJsonCode').innerText); showToast('Redfish JSON copied to clipboard');">
        📋 Copy JSON
      </button>
    </div>
    <div style="margin-bottom: 1rem;">
      <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Message</div>
      <div style="font-weight: 600; color: var(--text-primary); margin-top: 0.2rem;">${escapeHtml(alertObj.Message)}</div>
    </div>
    <div style="margin-bottom: 1rem;">
      <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Resource URI</div>
      <div class="mono-cell" style="margin-top: 0.2rem; word-break: break-all;">${escapeHtml(alertObj.OriginOfCondition)}</div>
    </div>
    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.4rem;">Redfish Payload</div>
    <pre class="json-code-box"><code id="rawJsonCode">${escapeHtml(jsonStr)}</code></pre>
  `;

  inspectorDrawer.classList.add('open');
  drawerBackdrop.classList.add('show');
};

function closeInspector() {
  if (inspectorDrawer) inspectorDrawer.classList.remove('open');
  if (drawerBackdrop) drawerBackdrop.classList.remove('show');
}

if (closeDrawerBtn) closeDrawerBtn.addEventListener('click', closeInspector);
if (drawerBackdrop) drawerBackdrop.addEventListener('click', closeInspector);
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeInspector();
});

// Start on DOM ready
document.addEventListener('DOMContentLoaded', initDetail);
