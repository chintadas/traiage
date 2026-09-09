const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');

const {
  formatRelativeTime,
  formatTime,
  escapeHtml,
  filterAlerts,
  sortAlerts
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
