// dashboard.js — PROJECT AXIOM v2 Professional Dashboard

const STORAGE_KEY = 'axiom_history_v2';
const MAX_HISTORY = 20;

let currentData = null;
let activeFilter = 'ALL';
let searchQuery = '';
let ringChartInstance = null;
let trendChartInstance = null;

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────
const verdictIcon = v => v === 'PASS' ? '✓' : v === 'FAIL' ? '✗' : '?';

function fmt(str, max = 60) {
  if (!str) return '—';
  str = str.replace(/\n/g, ' ').trim();
  return str.length > max ? str.slice(0, max - 1) + '…' : str;
}

function formatTimestamp(ts) {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return ts; }
}

// ─────────────────────────────────────────────
// History
// ─────────────────────────────────────────────
function loadHistory() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); }
  catch { return []; }
}

function saveHistory(data) {
  const history = loadHistory();
  history.unshift({
    timestamp: data.metadata.timestamp,
    target: data.metadata.target,
    method: data.metadata.method,
    total: data.metadata.total_checks,
    pass: data.metadata.pass_count,
    fail: data.metadata.fail_count,
    unknown: data.metadata.unknown_count,
  });
  if (history.length > MAX_HISTORY) history.splice(MAX_HISTORY);
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(history)); }
  catch {}
}

// ─────────────────────────────────────────────
// Master render
// ─────────────────────────────────────────────
function renderAll(data) {
  currentData = data;
  saveHistory(data);
  document.getElementById('uploadOverlay').style.display = 'none';
  renderHeader(data);
  renderTargetBar(data);
  renderMetrics(data);
  renderRingChart(data);
  renderPosture(data);
  renderTable(data);
  renderPriority(data);
  renderTrend();
}

function renderHeader(data) {
  const m = data.metadata;
  const pct = m.total_checks > 0 ? Math.round((m.pass_count / m.total_checks) * 100) : 0;
  document.getElementById('headerStatus').textContent =
    `${m.target.toUpperCase()} · ${pct}% PASS · ${m.fail_count} FAIL`;
}

function renderTargetBar(data) {
  const m = data.metadata;
  document.getElementById('targetBadge').textContent = `${m.method.toUpperCase()} / ${m.target}`;
  document.getElementById('targetMeta').textContent = `Last scan: ${formatTimestamp(m.timestamp)}`;
}

function renderMetrics(data) {
  const m = data.metadata;
  animateCount('metricTotal', m.total_checks);
  animateCount('metricPass', m.pass_count);
  animateCount('metricFail', m.fail_count);
  animateCount('metricUnknown', m.unknown_count);
}

function animateCount(id, target) {
  const el = document.getElementById(id);
  let current = 0;
  const step = Math.max(1, Math.ceil(target / 25));
  const timer = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = current;
    if (current >= target) clearInterval(timer);
  }, 28);
}

// ─────────────────────────────────────────────
// Ring Chart (Donut)
// ─────────────────────────────────────────────
function renderRingChart(data) {
  const m = data.metadata;

  // Update legend values
  document.getElementById('legendPass').textContent = m.pass_count;
  document.getElementById('legendFail').textContent = m.fail_count;
  document.getElementById('legendUnknown').textContent = m.unknown_count;
  document.getElementById('ringCenterNum').textContent = m.total_checks;

  const canvas = document.getElementById('ringChart');
  const ctx = canvas.getContext('2d');

  if (ringChartInstance) { ringChartInstance.destroy(); }

  const passColor = '#00ff88';
  const failColor = '#ff3f5b';
  const unknownColor = '#ffb800';
  const emptyColor = 'rgba(0,212,255,0.06)';

  const hasData = m.total_checks > 0;

  ringChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['PASS', 'FAIL', 'UNKNOWN'],
      datasets: [{
        data: hasData
          ? [m.pass_count, m.fail_count, m.unknown_count]
          : [1, 0, 0],
        backgroundColor: hasData
          ? [passColor, failColor, unknownColor]
          : [emptyColor],
        borderColor: 'transparent',
        borderWidth: 0,
        hoverBorderColor: ['rgba(0,255,136,0.5)', 'rgba(255,63,91,0.5)', 'rgba(255,184,0,0.5)'],
        hoverBorderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '72%',
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: hasData,
          backgroundColor: 'rgba(6, 12, 20, 0.95)',
          borderColor: 'rgba(0, 212, 255, 0.2)',
          borderWidth: 1,
          titleColor: '#e0f0ff',
          bodyColor: '#7a9ab5',
          padding: 10,
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.raw}`
          }
        }
      },
      animation: { animateRotate: true, duration: 900, easing: 'easeInOutQuart' }
    }
  });
}

// ─────────────────────────────────────────────
// Posture + Self-Audit
// ─────────────────────────────────────────────
function renderPosture(data) {
  document.getElementById('postureStrip').textContent = data.posture_strip || '—';
  document.getElementById('ceoSummary').textContent = data.ceo_summary || 'No summary available.';

  const sa = data.self_audit || {};
  const chip = document.getElementById('selfAuditChip');
  const v = sa.verdict || 'UNKNOWN';
  chip.className = `self-audit-chip ${v}`;
  chip.innerHTML = `<span>${verdictIcon(v)}</span> SELF-AUDIT: ${v} — ${sa.reason || 'No data'}`;
}

// ─────────────────────────────────────────────
// Verdict Table
// ─────────────────────────────────────────────
function renderTable(data) {
  const verdicts = data.verdicts || [];
  const receipts = data.receipts || {};
  const tbody = document.getElementById('verdictTbody');
  tbody.innerHTML = '';

  const filtered = verdicts.filter(v => {
    const matchFilter = activeFilter === 'ALL' || v.verdict === activeFilter;
    const q = searchQuery.toLowerCase();
    const matchSearch = !q ||
      v.rule_id.toLowerCase().includes(q) ||
      v.verdict.toLowerCase().includes(q) ||
      (v.reason || '').toLowerCase().includes(q) ||
      (v.severity || '').toLowerCase().includes(q);
    return matchFilter && matchSearch;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="emoji">🔍</div><div>No results match your filter.</div></div></td></tr>`;
    return;
  }

  filtered.forEach((v, idx) => {
    const tr = document.createElement('tr');
    tr.id = `row-${idx}`;
    tr.innerHTML = `
      <td class="rule-id-cell">${v.rule_id}</td>
      <td><span class="verdict-badge ${v.verdict}">${verdictIcon(v.verdict)} ${v.verdict}</span></td>
      <td><span class="severity-badge ${v.severity}">${v.severity}</span></td>
      <td class="reason-cell">${fmt(v.reason, 75)}</td>
      <td class="evidence-cell" title="${(v.evidence || '').trim()}">${fmt(v.evidence, 40)}</td>
      <td class="receipt-cell">${receipts[v.rule_id] || '—'}</td>
      <td><span class="expand-arrow">▶</span></td>
    `;
    tr.addEventListener('click', () => toggleDetail(idx, v, tr));
    tbody.appendChild(tr);
  });
}

function toggleDetail(idx, v, tr) {
  // close any open detail row
  document.querySelectorAll('tr[id^="detail-"]').forEach(r => r.remove());
  document.querySelectorAll('tr.expanded').forEach(r => r.classList.remove('expanded'));

  const existing = document.getElementById(`detail-${idx}`);
  if (existing) return;

  tr.classList.add('expanded');
  const detailTr = document.createElement('tr');
  detailTr.id = `detail-${idx}`;
  detailTr.className = 'detail-row';
  detailTr.innerHTML = `
    <td colspan="7">
      <div class="detail-box">
        <div class="detail-grid">
          <div class="detail-section">
            <strong>Full Reason</strong>
            <p>${v.reason || '—'}</p>
          </div>
          <div class="detail-section">
            <strong>Evidence Collected</strong>
            <pre>${(v.evidence || '—').trim()}</pre>
          </div>
        </div>
      </div>
    </td>
  `;
  tr.insertAdjacentElement('afterend', detailTr);
}

// ─────────────────────────────────────────────
// Priority List
// ─────────────────────────────────────────────
function renderPriority(data) {
  const list = data.priority_list || [];
  const container = document.getElementById('priorityList');
  container.innerHTML = '';

  if (list.length === 0) {
    container.innerHTML = `<div class="empty-state"><div class="emoji">🎉</div><div>No FAIL items — nothing to prioritize!</div></div>`;
    return;
  }

  list.forEach((item, idx) => {
    const div = document.createElement('div');
    div.className = 'priority-item';
    // highlight code-like fix instructions
    const fixHtml = (item.fix || '').replace(/`([^`]+)`/g, '<code>$1</code>');
    div.innerHTML = `
      <div class="priority-num">${idx + 1}</div>
      <div class="priority-body">
        <div class="priority-rule">
          <span class="severity-badge ${item.severity}">${item.severity}</span>
          ${item.rule_id}
        </div>
        <div class="priority-fix">🔧 ${fixHtml}</div>
      </div>
    `;
    container.appendChild(div);
  });
}

// ─────────────────────────────────────────────
// Trend Chart (line)
// ─────────────────────────────────────────────
function renderTrend() {
  const history = loadHistory();
  const container = document.getElementById('trendContainer');

  if (history.length < 2) {
    container.innerHTML = `<div class="no-history">📈 Load 2+ scan results to see the historical trend</div>`;
    return;
  }

  container.innerHTML = `<div class="chart-wrap"><canvas id="trendChart"></canvas></div>`;
  const ctx = document.getElementById('trendChart').getContext('2d');

  const labels = history.map((h, i) => {
    const d = new Date(h.timestamp);
    return isNaN(d) ? `Run ${i + 1}` : d.toLocaleDateString();
  }).reverse();
  const failData = history.map(h => h.fail).reverse();
  const passData = history.map(h => h.pass).reverse();
  const unknownData = history.map(h => h.unknown).reverse();

  if (trendChartInstance) { trendChartInstance.destroy(); }

  trendChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'FAIL',
          data: failData,
          borderColor: '#ff3f5b',
          backgroundColor: 'rgba(255, 63, 91, 0.06)',
          borderWidth: 2,
          pointBackgroundColor: '#ff3f5b',
          pointBorderColor: 'rgba(255,63,91,0.5)',
          pointRadius: 5,
          pointHoverRadius: 7,
          tension: 0.45,
          fill: true,
        },
        {
          label: 'PASS',
          data: passData,
          borderColor: '#00ff88',
          backgroundColor: 'rgba(0, 255, 136, 0.04)',
          borderWidth: 2,
          pointBackgroundColor: '#00ff88',
          pointBorderColor: 'rgba(0,255,136,0.5)',
          pointRadius: 5,
          pointHoverRadius: 7,
          tension: 0.45,
          fill: true,
        },
        {
          label: 'UNKNOWN',
          data: unknownData,
          borderColor: '#ffb800',
          backgroundColor: 'rgba(255, 184, 0, 0.03)',
          borderWidth: 1.5,
          pointBackgroundColor: '#ffb800',
          pointRadius: 4,
          tension: 0.45,
          borderDash: [5, 5],
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: '#3a5570',
            font: { family: 'JetBrains Mono, monospace', size: 10 },
            boxWidth: 10,
            usePointStyle: true,
          }
        },
        tooltip: {
          backgroundColor: 'rgba(6, 12, 20, 0.96)',
          borderColor: 'rgba(0, 212, 255, 0.2)',
          borderWidth: 1,
          titleColor: '#e0f0ff',
          bodyColor: '#7a9ab5',
          padding: 12,
          titleFont: { family: 'JetBrains Mono, monospace', size: 11 },
          bodyFont: { family: 'JetBrains Mono, monospace', size: 11 },
        }
      },
      scales: {
        x: {
          ticks: { color: '#3a5570', font: { family: 'JetBrains Mono, monospace', size: 10 } },
          grid: { color: 'rgba(0, 212, 255, 0.04)' },
          border: { color: 'rgba(0, 212, 255, 0.08)' },
        },
        y: {
          beginAtZero: true,
          ticks: { color: '#3a5570', font: { family: 'JetBrains Mono, monospace', size: 10 }, stepSize: 1 },
          grid: { color: 'rgba(0, 212, 255, 0.04)' },
          border: { color: 'rgba(0, 212, 255, 0.08)' },
        }
      }
    }
  });
}

// ─────────────────────────────────────────────
// Filter + Search
// ─────────────────────────────────────────────
function setFilter(f) {
  activeFilter = f;
  document.querySelectorAll('.pill').forEach(p => {
    p.className = 'pill';
    if (p.dataset.filter === f) {
      const cls = f === 'ALL' ? 'active-all' : f === 'PASS' ? 'active-pass' : f === 'FAIL' ? 'active-fail' : 'active-unknown';
      p.classList.add(cls);
    }
  });
  if (currentData) renderTable(currentData);
}

document.getElementById('searchInput').addEventListener('input', e => {
  searchQuery = e.target.value;
  if (currentData) renderTable(currentData);
});

document.querySelectorAll('.pill').forEach(p => {
  p.addEventListener('click', () => setFilter(p.dataset.filter));
});

// ─────────────────────────────────────────────
// JSON Loading
// ─────────────────────────────────────────────
function loadJSON(json) {
  try {
    const data = typeof json === 'string' ? JSON.parse(json) : json;
    if (!data.metadata || !data.verdicts) throw new Error('Invalid AXIOM JSON — missing metadata or verdicts');
    renderAll(data);
  } catch (e) {
    alert(`Failed to load report:\n${e.message}`);
  }
}

// ─────────────────────────────────────────────
// File drop / browse
// ─────────────────────────────────────────────
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('jsonFileInput');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) readFile(file);
});
fileInput.addEventListener('change', e => { if (e.target.files[0]) readFile(e.target.files[0]); });
document.getElementById('loadFileBtn').addEventListener('click', () => fileInput.click());

function readFile(file) {
  const reader = new FileReader();
  reader.onload = e => loadJSON(e.target.result);
  reader.readAsText(file);
}

// ─────────────────────────────────────────────
// Sample / preset data
// ─────────────────────────────────────────────
document.getElementById('loadBrokenBtn').addEventListener('click', () => {
  if (window.AXIOM_BROKEN) { loadJSON(window.AXIOM_BROKEN); return; }
  if (window.AXIOM_AUTOLOAD) { loadJSON(window.AXIOM_AUTOLOAD); return; }
  alert('No scan data found.\nRun: python3 axiom.py --target axiom-broken-target --method docker\nThen reload index.html.');
});

document.getElementById('loadCleanBtn').addEventListener('click', () => {
  if (window.AXIOM_CLEAN) { loadJSON(window.AXIOM_CLEAN); return; }
  if (window.AXIOM_AUTOLOAD) { loadJSON(window.AXIOM_AUTOLOAD); return; }
  alert('No scan data found.\nRun: python3 axiom.py --target axiom-clean-target --method docker\nThen reload index.html.');
});

document.getElementById('clearHistoryBtn').addEventListener('click', () => {
  localStorage.removeItem(STORAGE_KEY);
  renderTrend();
});

// ─────────────────────────────────────────────
// Auto-init on load
// ─────────────────────────────────────────────
(function autoInit() {
  if (window.AXIOM_AUTOLOAD) {
    loadJSON(window.AXIOM_AUTOLOAD);
  }
})();
