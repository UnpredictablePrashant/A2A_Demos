const form = document.getElementById('task-form');
const input = document.getElementById('task-input');
const runState = document.getElementById('run-state');
const resultBox = document.getElementById('result-box');
const submitBtn = document.getElementById('submit-btn');
const eventStream = document.getElementById('event-stream');
const alphaDb = document.getElementById('alpha-db');
const betaDb = document.getElementById('beta-db');
const inspector = document.getElementById('inspector');
const configTable = document.getElementById('config-table');
const agentsTable = document.getElementById('agents-table');
const agentsTotal = document.getElementById('agents-total');
const agentsDetected = document.getElementById('agents-detected');
const agentsUndetected = document.getElementById('agents-undetected');
const agentsTs = document.getElementById('agents-ts');
const statusRunId = document.getElementById('status-run-id');
const statusAlpha = document.getElementById('status-alpha');
const statusBetaTask = document.getElementById('status-beta-task');
const statusBeta = document.getElementById('status-beta');
const statusAlphaCreated = document.getElementById('status-alpha-created');
const statusAlphaCompleted = document.getElementById('status-alpha-completed');
const statusBetaCreated = document.getElementById('status-beta-created');
const statusBetaCompleted = document.getElementById('status-beta-completed');
const alphaOutput = document.getElementById('alpha-output');
const betaOutput = document.getElementById('beta-output');
const graphStage = document.getElementById('graph-stage');
const edgeList = document.getElementById('edge-list');
const sessionsTable = document.getElementById('sessions-table');
const activityGrid = document.getElementById('agent-activity-grid');

let currentRunId = null;
let ws = null;
let detectedAgents = [];
let activityPulseMap = {};

function setRunState(state) {
  runState.className = `badge ${state}`;
  if (state === 'running') runState.textContent = 'Running';
  if (state === 'done') runState.textContent = 'Completed';
  if (state === 'failed') runState.textContent = 'Failed';
  if (state === 'idle') runState.textContent = 'Idle';
}

function truncate(text, max = 1400) {
  if (!text) return '';
  return text.length <= max ? text : `${text.slice(0, max)} ...`;
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString();
}

function formatTs(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString();
}

function toTitle(value) {
  if (!value) return '';
  return value
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function setInspector(title, data) {
  const payload = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  inspector.textContent = `${title}\n\n${payload}`;
}

function renderAgentActivityCards(rows) {
  activityGrid.innerHTML = '';
  activityPulseMap = {};

  const filtered = rows.filter((x) => x.detected);
  if (!filtered.length) {
    const empty = document.createElement('article');
    empty.className = 'agent-card';
    empty.innerHTML = '<h3>No detected agents</h3><p>Start agents or update .env agent URLs.</p>';
    activityGrid.appendChild(empty);
    return;
  }

  filtered.forEach((row) => {
    const card = document.createElement('article');
    card.className = 'agent-card';

    const pulseId = `pulse-${String(row.id).toLowerCase()}`;
    card.innerHTML = `
      <h3>${toTitle(row.card_name || row.id)}</h3>
      <p>${row.url || '(no url)'}</p>
      <span class="pulse" id="${pulseId}"></span>
    `;
    card.onclick = () => setInspector('Agent Activity Card', row);
    activityGrid.appendChild(card);
    activityPulseMap[String(row.id).toLowerCase()] = document.getElementById(pulseId);
  });
}

function markAgentActivity(source, message) {
  const activate = (el) => {
    if (!el) return;
    el.classList.add('active');
    setTimeout(() => el.classList.remove('active'), 700);
  };

  const sourceId = String(source || '').toLowerCase();
  if (sourceId && activityPulseMap[sourceId]) {
    activate(activityPulseMap[sourceId]);
  }

  Object.entries(activityPulseMap).forEach(([id, el]) => {
    if (message && message.toLowerCase().includes(id)) {
      activate(el);
    }
  });
}

function addEvent(event) {
  markAgentActivity(event.source || '', event.message || '');

  const div = document.createElement('div');
  div.className = `event ${event.kind || 'log'}`;
  div.onclick = () => setInspector('Event Detail', event);

  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = `${formatTime(event.ts)} | ${event.source} | ${event.kind}${event.run_id ? ` | run=${event.run_id}` : ''}`;

  const pre = document.createElement('pre');
  pre.textContent = truncate(event.message, 2000);

  div.appendChild(meta);
  div.appendChild(pre);
  eventStream.appendChild(div);
  eventStream.scrollTop = eventStream.scrollHeight;

  const total = eventStream.querySelectorAll('.event').length;
  if (total > 200) {
    eventStream.removeChild(eventStream.firstChild);
  }
}

function renderAlphaTable(rows) {
  alphaDb.innerHTML = '';
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${row.local_id}</td><td title="${row.beta_task_id || ''}">${row.beta_task_id || ''}</td><td>${row.beta_status}</td><td title="${formatTs(row.created_at)}">${formatTs(row.created_at)}</td><td title="${formatTs(row.completed_at)}">${formatTs(row.completed_at)}</td>`;
    tr.onclick = () => setInspector('Alpha DB Row', row);
    alphaDb.appendChild(tr);
  });
}

function renderBetaTable(rows) {
  betaDb.innerHTML = '';
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td title="${row.task_id}">${row.task_id}</td><td>${row.status}</td><td>${row.source_agent}</td><td title="${formatTs(row.created_at)}">${formatTs(row.created_at)}</td><td title="${formatTs(row.completed_at)}">${formatTs(row.completed_at)}</td>`;
    tr.onclick = () => setInspector('Beta DB Row', row);
    betaDb.appendChild(tr);
  });
}

function updateStatusSummary(summary) {
  if (!summary) return;
  statusAlpha.textContent = summary.alpha_status || 'n/a';
  statusBeta.textContent = summary.beta_status || 'n/a';
  statusBetaTask.textContent = summary.beta_task_id || '-';
  statusAlphaCreated.textContent = formatTs(summary.alpha_created_at);
  statusAlphaCompleted.textContent = formatTs(summary.alpha_completed_at);
  statusBetaCreated.textContent = formatTs(summary.beta_created_at);
  statusBetaCompleted.textContent = formatTs(summary.beta_completed_at);
}

async function refreshDb() {
  try {
    const res = await fetch('/api/db');
    if (!res.ok) return;
    const data = await res.json();
    renderAlphaTable(data.alpha || []);
    renderBetaTable(data.beta || []);
    updateStatusSummary(data.summary || {});
  } catch (_) {
    // ignore transient errors
  }
}

function renderConfig(rows) {
  configTable.innerHTML = '';
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${row.key}</td><td title="${row.value}">${row.value}</td><td>${row.source}</td>`;
    tr.onclick = () => setInspector('Config Detail', row);
    configTable.appendChild(tr);
  });
}

function renderAgents(data) {
  const rows = data.agents || [];
  detectedAgents = rows.filter((x) => x.detected).map((x) => String(x.id).toLowerCase());

  agentsTotal.textContent = String(data.total_added ?? rows.length);
  agentsDetected.textContent = String(data.detected ?? 0);
  agentsUndetected.textContent = String(data.undetected ?? 0);
  agentsTs.textContent = data.timestamp ? formatTime(data.timestamp) : '-';

  agentsTable.innerHTML = '';
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${row.id}</td><td>${row.folder}</td><td>${row.process_status}</td><td>${row.detected ? 'yes' : 'no'}</td><td title="${row.url || ''}">${row.url || ''}</td>`;
    tr.onclick = () => setInspector('Agent Detection Detail', row);
    agentsTable.appendChild(tr);
  });

  renderAgentActivityCards(rows);
}

function renderEdgeList(edges) {
  edgeList.innerHTML = '';
  edges.forEach((edge) => {
    const li = document.createElement('li');
    li.className = 'path-item';
    li.textContent = `${toTitle(edge.from)} -> ${toTitle(edge.to)} (${edge.type}) x${edge.count}`;
    li.onclick = () => setInspector('Interaction Edge', edge);
    edgeList.appendChild(li);
  });
}

function layoutNodes(nodes, width, height) {
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.max(90, Math.min(width, height) * 0.34);
  const out = {};
  const sorted = [...nodes].sort((a, b) => a.id.localeCompare(b.id));

  sorted.forEach((node, idx) => {
    const angle = (Math.PI * 2 * idx) / Math.max(sorted.length, 1) - Math.PI / 2;
    out[node.id] = {
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
    };
  });
  return out;
}

function renderGraph(graph) {
  if (!graphStage) return;

  const nodes = (graph.nodes || []).filter((n) => {
    if (n.id === 'user') return true;
    if (detectedAgents.includes(n.id)) return true;
    if (n.id.endsWith('_db') && detectedAgents.includes(n.id.replace(/_db$/, ''))) return true;
    return false;
  });

  const nodeIds = new Set(nodes.map((n) => n.id));
  const edges = (graph.edges || []).filter((e) => nodeIds.has(e.from) && nodeIds.has(e.to));

  renderEdgeList(edges);

  const width = graphStage.clientWidth || 900;
  const height = graphStage.clientHeight || 380;
  const points = layoutNodes(nodes, width, height);

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

  edges.forEach((edge) => {
    const from = points[edge.from];
    const to = points[edge.to];
    if (!from || !to) return;

    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', from.x);
    line.setAttribute('y1', from.y);
    line.setAttribute('x2', to.x);
    line.setAttribute('y2', to.y);
    line.setAttribute('class', 'graph-edge');
    line.style.strokeWidth = String(1.4 + Math.min(4, edge.count * 0.45));
    line.style.cursor = 'pointer';
    line.addEventListener('click', () => setInspector('Interaction Edge', edge));
    svg.appendChild(line);

    const lx = (from.x + to.x) / 2;
    const ly = (from.y + to.y) / 2;
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', lx);
    text.setAttribute('y', ly - 6);
    text.setAttribute('class', 'graph-edge-label');
    text.textContent = `${edge.type} x${edge.count}`;
    text.style.cursor = 'pointer';
    text.addEventListener('click', () => setInspector('Interaction Edge', edge));
    svg.appendChild(text);
  });

  nodes.forEach((node) => {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', `graph-node ${node.kind}`);
    g.style.cursor = 'pointer';

    const p = points[node.id];
    const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', p.x);
    c.setAttribute('cy', p.y);
    c.setAttribute('r', 30);

    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', p.x);
    t.setAttribute('y', p.y);
    t.textContent = node.id.endsWith('_db')
      ? `${toTitle(node.id.replace(/_db$/, ''))} DB`
      : node.id === 'user'
        ? 'User'
        : toTitle(node.id);

    g.appendChild(c);
    g.appendChild(t);
    g.addEventListener('click', () => {
      const related = edges.filter((e) => e.from === node.id || e.to === node.id);
      setInspector(`Node: ${toTitle(node.id)}`, { node, related_edges: related });
    });
    svg.appendChild(g);
  });

  graphStage.innerHTML = '';
  graphStage.appendChild(svg);
}

function renderSessions(rows) {
  sessionsTable.innerHTML = '';
  rows.forEach((session) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td title="${session.id}">${session.id.slice(0, 12)}...</td>
      <td>${session.status}</td>
      <td title="${formatTs(session.created_at)}">${formatTs(session.created_at)}</td>
      <td>${session.event_count}</td>
      <td><a href="/sessions/${session.id}" target="_blank" rel="noreferrer">open</a></td>
    `;
    tr.onclick = (ev) => {
      if (ev.target.tagName.toLowerCase() === 'a') return;
      currentRunId = session.id;
      statusRunId.textContent = currentRunId;
      setInspector('Session Summary', session);
      refreshCurrentSession();
    };
    sessionsTable.appendChild(tr);
  });
}

async function refreshSessions() {
  try {
    const res = await fetch('/api/sessions');
    if (!res.ok) return;
    const data = await res.json();
    renderSessions(data.sessions || []);
  } catch (_) {
    // ignore
  }
}

async function refreshCurrentSession() {
  if (!currentRunId) return;
  try {
    const res = await fetch(`/api/sessions/${currentRunId}`);
    if (!res.ok) return;

    const data = await res.json();
    renderGraph(data.graph || { nodes: [], edges: [], events: [] });

    if (data.run?.result) {
      alphaOutput.textContent = data.run.result;
      resultBox.textContent = data.run.result;
    }

    if (data.run?.beta_result) {
      betaOutput.textContent = data.run.beta_result;
    } else if (data.run?.status === 'running') {
      betaOutput.textContent = '(waiting for beta result)';
    } else if (!data.run?.result) {
      betaOutput.textContent = '(no beta result)';
    }
  } catch (_) {
    // ignore
  }
}

async function refreshConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    const data = await res.json();
    renderConfig(data.config || []);
  } catch (_) {
    // ignore
  }
}

async function refreshAgents() {
  try {
    const res = await fetch('/api/agents');
    if (!res.ok) return;
    const data = await res.json();
    renderAgents(data);
    if (currentRunId) {
      refreshCurrentSession();
    }
  } catch (_) {
    // ignore
  }
}

async function pollRun() {
  if (!currentRunId) return;

  try {
    const res = await fetch(`/api/tasks/${currentRunId}`);
    if (!res.ok) return;

    const run = await res.json();
    updateStatusSummary(run.db_summary || {});
    await refreshCurrentSession();

    if (run.status === 'running') {
      setRunState('running');
      setTimeout(pollRun, 700);
      return;
    }

    if (run.status === 'completed') {
      setRunState('done');
      resultBox.textContent = run.result || '(empty result)';
      alphaOutput.textContent = run.result || '(empty result)';
      submitBtn.disabled = false;
      refreshSessions();
      return;
    }

    setRunState('failed');
    resultBox.textContent = run.result || 'Task failed';
    alphaOutput.textContent = run.result || 'Task failed';
    submitBtn.disabled = false;
    refreshSessions();
  } catch (_) {
    setTimeout(pollRun, 1200);
  }
}

function connectEvents() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/events`);

  ws.onmessage = (ev) => {
    try {
      const event = JSON.parse(ev.data);
      addEvent(event);
      if (event.run_id && currentRunId && event.run_id === currentRunId) {
        refreshCurrentSession();
      }
    } catch (_) {
      // no-op
    }
  };

  ws.onclose = () => {
    setTimeout(connectEvents, 1000);
  };
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  submitBtn.disabled = true;
  setRunState('running');
  resultBox.textContent = '';
  alphaOutput.textContent = '';
  betaOutput.textContent = '';

  const res = await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    setRunState('failed');
    submitBtn.disabled = false;
    resultBox.textContent = 'Failed to submit task';
    return;
  }

  const data = await res.json();
  currentRunId = data.run_id;
  statusRunId.textContent = currentRunId;
  refreshSessions();
  pollRun();
});

setRunState('idle');
connectEvents();
refreshDb();
refreshConfig();
refreshAgents();
refreshSessions();
setInterval(refreshDb, 1200);
setInterval(refreshConfig, 8000);
setInterval(refreshAgents, 3000);
setInterval(refreshSessions, 3000);
