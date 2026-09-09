const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');

const {
  formatRelativeTime,
  formatTime,
  escapeHtml,
  filterAlerts,
  sortAlerts,
  filterIncidents
} = require('../public/app.js');

// Load seed alerts for integration testing of filter and sort logic
const seedDataPath = path.resolve(__dirname, '../data/seed_alerts.json');
const seedData = JSON.parse(fs.readFileSync(seedDataPath, 'utf-8'));
const sampleAlerts = seedData.Events;

test('formatRelativeTime: under 60 seconds returns "just now"', () => {
  const baseTime = new Date('2026-09-08T12:00:00Z').getTime();
  const alertIso = new Date(baseTime - 30 * 1000).toISOString();
  assert.strictEqual(formatRelativeTime(alertIso, baseTime), 'just now');
});

test('formatRelativeTime: 23 minutes returns "23m ago"', () => {
  const baseTime = new Date('2026-09-08T12:00:00Z').getTime();
  const alertIso = new Date(baseTime - 23 * 60 * 1000).toISOString();
  assert.strictEqual(formatRelativeTime(alertIso, baseTime), '23m ago');
});

test('formatRelativeTime: 1 hour 3 minutes returns "1h 3m ago"', () => {
  const baseTime = new Date('2026-09-08T12:00:00Z').getTime();
  const alertIso = new Date(baseTime - (63 * 60 * 1000)).toISOString();
  assert.strictEqual(formatRelativeTime(alertIso, baseTime), '1h 3m ago');
});

test('formatRelativeTime: exactly 2 hours (0 remaining minutes) returns "2h ago"', () => {
  const baseTime = new Date('2026-09-08T12:00:00Z').getTime();
  const alertIso = new Date(baseTime - (120 * 60 * 1000)).toISOString();
  assert.strictEqual(formatRelativeTime(alertIso, baseTime), '2h ago');
});

test('formatRelativeTime: 1 day 4 hours returns "1d 4h ago"', () => {
  const baseTime = new Date('2026-09-08T12:00:00Z').getTime();
  const alertIso = new Date(baseTime - (28 * 3600 * 1000)).toISOString();
  assert.strictEqual(formatRelativeTime(alertIso, baseTime), '1d 4h ago');
});

test('formatRelativeTime: exactly 3 days (0 remaining hours) returns "3d ago"', () => {
  const baseTime = new Date('2026-09-08T12:00:00Z').getTime();
  const alertIso = new Date(baseTime - (72 * 3600 * 1000)).toISOString();
  assert.strictEqual(formatRelativeTime(alertIso, baseTime), '3d ago');
});

test('formatRelativeTime: future timestamp returns "just now"', () => {
  const baseTime = new Date('2026-09-08T12:00:00Z').getTime();
  const alertIso = new Date(baseTime + 10000).toISOString();
  assert.strictEqual(formatRelativeTime(alertIso, baseTime), 'just now');
});

test('escapeHtml: properly escapes HTML entities', () => {
  assert.strictEqual(escapeHtml('<script>alert("XSS") & \'test\';</script>'), '&lt;script&gt;alert(&quot;XSS&quot;) &amp; &#039;test&#039;;&lt;/script&gt;');
  assert.strictEqual(escapeHtml(''), '');
  assert.strictEqual(escapeHtml(null), '');
  assert.strictEqual(escapeHtml(undefined), '');
  assert.strictEqual(escapeHtml('Normal text 123'), 'Normal text 123');
});

test('filterAlerts: filters by severity correctly', () => {
  const criticals = filterAlerts(sampleAlerts, { severity: 'Critical' });
  assert.strictEqual(criticals.length, 6);
  assert.ok(criticals.every(a => a.Severity === 'Critical'));

  const warnings = filterAlerts(sampleAlerts, { severity: 'Warning' });
  assert.strictEqual(warnings.length, 12);
  assert.ok(warnings.every(a => a.Severity === 'Warning'));

  const oks = filterAlerts(sampleAlerts, { severity: 'OK' });
  assert.strictEqual(oks.length, 2);
  assert.ok(oks.every(a => a.Severity === 'OK'));
});

test('filterAlerts: filters by subsystem correctly', () => {
  const powerAlerts = filterAlerts(sampleAlerts, { subsystem: 'Power' });
  assert.strictEqual(powerAlerts.length, 5);
  assert.ok(powerAlerts.every(a => a.Subsystem === 'Power'));

  const aiAlerts = filterAlerts(sampleAlerts, { subsystem: 'AI-Accelerator' });
  assert.strictEqual(aiAlerts.length, 2);
  assert.ok(aiAlerts.every(a => a.Subsystem === 'AI-Accelerator'));
});

test('filterAlerts: filters by rack location correctly', () => {
  const rack04 = filterAlerts(sampleAlerts, { rack: 'Rack-04' });
  assert.strictEqual(rack04.length, 4);
  assert.ok(rack04.every(a => a.Location.Rack === 'Rack-04'));

  const rack08 = filterAlerts(sampleAlerts, { rack: 'Rack-08' });
  assert.strictEqual(rack08.length, 5);
  assert.ok(rack08.every(a => a.Location.Rack === 'Rack-08'));
});

test('filterAlerts: free text search matches message and IDs', () => {
  const leakMatches = filterAlerts(sampleAlerts, { search: 'leak' });
  assert.strictEqual(leakMatches.length, 1);
  assert.strictEqual(leakMatches[0].EventId, 'EVT-20260908-0001');

  const xidMatches = filterAlerts(sampleAlerts, { search: 'XID 79' });
  assert.strictEqual(xidMatches.length, 1);
  assert.strictEqual(xidMatches[0].EventId, 'EVT-20260908-0003');
});

test('filterAlerts: combined filters work synchronously', () => {
  const combined = filterAlerts(sampleAlerts, {
    severity: 'Critical',
    rack: 'Rack-04',
    subsystem: 'AI-Accelerator'
  });
  assert.strictEqual(combined.length, 2);
  assert.ok(combined.every(a => a.Severity === 'Critical' && a.Location.Rack === 'Rack-04' && a.Subsystem === 'AI-Accelerator'));
});

test('sortAlerts: sorts by timestamp descending (newest first)', () => {
  const sorted = sortAlerts(sampleAlerts, 'timestamp-desc');
  for (let i = 0; i < sorted.length - 1; i++) {
    const tCurrent = new Date(sorted[i].Timestamp).getTime();
    const tNext = new Date(sorted[i + 1].Timestamp).getTime();
    assert.ok(tCurrent >= tNext, `Expected ${sorted[i].Timestamp} >= ${sorted[i + 1].Timestamp}`);
  }
});

test('sortAlerts: sorts by timestamp ascending (oldest first)', () => {
  const sorted = sortAlerts(sampleAlerts, 'timestamp-asc');
  for (let i = 0; i < sorted.length - 1; i++) {
    const tCurrent = new Date(sorted[i].Timestamp).getTime();
    const tNext = new Date(sorted[i + 1].Timestamp).getTime();
    assert.ok(tCurrent <= tNext, `Expected ${sorted[i].Timestamp} <= ${sorted[i + 1].Timestamp}`);
  }
});

test('sortAlerts: sorts by severity descending (Critical > Warning > OK)', () => {
  const score = { Critical: 3, Warning: 2, OK: 1 };
  const sorted = sortAlerts(sampleAlerts, 'severity-desc');
  for (let i = 0; i < sorted.length - 1; i++) {
    assert.ok(score[sorted[i].Severity] >= score[sorted[i + 1].Severity]);
  }
});

test('sortAlerts: sorts by rack alphabetically ascending', () => {
  const sorted = sortAlerts(sampleAlerts, 'rack-asc');
  for (let i = 0; i < sorted.length - 1; i++) {
    const rCurrent = sorted[i].Location.Rack || '';
    const rNext = sorted[i + 1].Location.Rack || '';
    assert.ok(rCurrent.localeCompare(rNext) <= 0);
  }
});

// Incidents Filtering Tests
const sampleIncidents = [
  {
    id: 'INC-DLC-2026-001',
    priority: 'P1',
    category: 'LiquidCooling',
    status: 'Active',
    title: 'CRITICAL: Direct Liquid Cooling Pressure Loss Triggering Thermal Throttling',
    root_cause_hypothesis: 'Pressure loss in Coolant Distribution Unit CDU-Row01-A',
    root_cause_component: 'CDU-Row01-A',
    root_cause_location: 'Room: DC-North-1, Row: Row-01',
    dispatch_target: 'Facilities Mechanical Team',
    blast_radius_summary: '1 CDU, 1 Manifold'
  },
  {
    id: 'INC-PWR-2026-002',
    priority: 'P2',
    category: 'Power',
    status: 'Acknowledged',
    title: 'MAJOR: PDU Branch Circuit Breaker Trip Causing Power Redundancy Loss (N-1)',
    root_cause_hypothesis: 'Branch circuit breaker trip on PDU-Row01-A',
    root_cause_component: 'PDU-Row01-A-Branch-04',
    root_cause_location: 'Room: DC-North-1, Row: Row-01, Rack: Rack-02',
    dispatch_target: 'Facilities Electrical Team',
    blast_radius_summary: '1 PDU Branch'
  },
  {
    id: 'INC-NET-2026-003',
    priority: 'P2',
    category: 'NetworkFabric',
    status: 'Resolved',
    title: 'MAJOR: ToR Switch Fan Tray Failure Causing Thermal Rise',
    root_cause_hypothesis: 'Dual fan tray failure on Switch-ToR-R04-01',
    root_cause_component: 'Switch-ToR-R04-01',
    root_cause_location: 'Room: DC-North-1, Row: Row-01, Rack: Rack-04',
    dispatch_target: 'Network Operations Team',
    blast_radius_summary: '1 ToR Switch'
  },
  {
    id: 'INC-STR-2026-004',
    priority: 'P3',
    category: 'Storage',
    status: 'Active',
    title: 'MINOR: NVMe Storage Drive Failure Causing Degraded RAID Volume',
    root_cause_hypothesis: 'Drive failure in StorageArray-02',
    root_cause_component: 'StorageArray-02',
    root_cause_location: 'Room: DC-North-1, Row: Row-01, Rack: Rack-08',
    dispatch_target: 'Data Center Hardware Logistics',
    blast_radius_summary: '1 Storage Array'
  }
];

test('filterIncidents: filters by priority', () => {
  const p1s = filterIncidents(sampleIncidents, { priority: 'P1' });
  assert.strictEqual(p1s.length, 1);
  assert.strictEqual(p1s[0].id, 'INC-DLC-2026-001');

  const p2s = filterIncidents(sampleIncidents, { priority: 'P2' });
  assert.strictEqual(p2s.length, 2);
});

test('filterIncidents: filters by category', () => {
  const cooling = filterIncidents(sampleIncidents, { category: 'LiquidCooling' });
  assert.strictEqual(cooling.length, 1);
  assert.strictEqual(cooling[0].category, 'LiquidCooling');

  const storage = filterIncidents(sampleIncidents, { category: 'Storage' });
  assert.strictEqual(storage.length, 1);
  assert.strictEqual(storage[0].id, 'INC-STR-2026-004');
});

test('filterIncidents: filters by status', () => {
  const active = filterIncidents(sampleIncidents, { status: 'Active' });
  assert.strictEqual(active.length, 2);

  const acked = filterIncidents(sampleIncidents, { status: 'Acknowledged' });
  assert.strictEqual(acked.length, 1);
  assert.strictEqual(acked[0].id, 'INC-PWR-2026-002');
});

test('filterIncidents: free text search matches title, hypothesis, component, dispatch', () => {
  const cduMatch = filterIncidents(sampleIncidents, { search: 'CDU-Row01-A' });
  assert.strictEqual(cduMatch.length, 1);

  const electricalMatch = filterIncidents(sampleIncidents, { search: 'electrical' });
  assert.strictEqual(electricalMatch.length, 1);
  assert.strictEqual(electricalMatch[0].id, 'INC-PWR-2026-002');

  const raidMatch = filterIncidents(sampleIncidents, { search: 'RAID' });
  assert.strictEqual(raidMatch.length, 1);
});
