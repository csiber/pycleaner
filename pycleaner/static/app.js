/* PyCleaner 5 — felület. Keretrendszer nélkül; minden dinamikus szöveg esc()-en megy át. */
'use strict';

const TOKEN = document.querySelector('meta[name="pyc-token"]').content;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
/* jobbról levágott útvonal (direction:rtl) — az LRM jelek tartják a helyén a perjeleket */
const ltr = v => `\u200e${esc(v)}\u200e`;
const icon = (n, cls = '') => `<svg class="ic ${cls}" aria-hidden="true"><use href="/static/icons.svg#i-${n}"/></svg>`;

function fmtB(n) {
  n = Number(n) || 0;
  if (n < 1024) return `${n} B`;
  const u = ['KB', 'MB', 'GB', 'TB'];
  let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return `${n.toFixed(n >= 100 || i === 0 ? 0 : 1).replace('.', ',')} ${u[i]}`;
}
const pct = v => String(Math.round((Number(v) || 0) * 10) / 10).replace('.', ',');
const fmtNum = n => (Number(n) || 0).toLocaleString('hu-HU');
const fmtDate = ts => new Date(ts * 1000).toLocaleDateString('hu-HU', { year: 'numeric', month: 'short', day: 'numeric' });

async function api(path, data) {
  const opt = { method: data === undefined ? 'GET' : 'POST', headers: { 'X-PyCleaner-Token': TOKEN } };
  if (data !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(data); }
  const r = await fetch('/api/' + path, opt);
  let j = null;
  try { j = await r.json(); } catch { /* nem JSON */ }
  if (!r.ok) throw new Error((j && (j.error || j.msg)) || `HTTP ${r.status}`);
  return j;
}
const dl = path => `/api/${path}${path.includes('?') ? '&' : '?'}t=${encodeURIComponent(TOKEN)}`;

/* gomb „dolgozik” állapottal */
async function busy(btn, fn) {
  if (btn) { btn.classList.add('busy'); btn.disabled = true; }
  try { return await fn(); }
  catch (e) { toast(e.message || String(e), 'err'); }
  finally { if (btn) { btn.classList.remove('busy'); btn.disabled = false; } }
}

function toast(msg, type = 'info', ms = 4200) {
  const ic = { ok: 'circle-check', err: 'triangle-alert', warn: 'triangle-alert', info: 'info' }[type] || 'info';
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `${icon(ic)}<div>${esc(msg)}</div>`;
  $('#toasts').append(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 250); }, ms);
}

/* párbeszédablak: confirm / prompt */
function dialog({ title, text = '', ok = 'Rendben', cancel = 'Mégse', danger = false, input = null }) {
  const d = $('#dlg');
  d.innerHTML = `<form method="dialog">
    <div class="dlg-body"><h3>${esc(title)}</h3><p>${text}</p>
      ${input ? `<input type="${input.type || 'text'}" id="dlgInput" placeholder="${esc(input.placeholder || '')}" autocomplete="off">` : ''}
    </div>
    <div class="dlg-foot">
      ${cancel ? `<button class="btn" value="cancel">${esc(cancel)}</button>` : ''}
      <button class="btn ${danger ? 'danger solid' : 'primary'}" value="ok">${esc(ok)}</button>
    </div></form>`;
  return new Promise(res => {
    d.onclose = () => res(d.returnValue === 'ok' ? (input ? $('#dlgInput').value : true) : (input ? null : false));
    d.showModal();
    (input ? $('#dlgInput') : $('.dlg-foot .btn:last-child', d)).focus();
  });
}

/* ── állapot ─────────────────────────────────────────────────────────────── */
const S = {
  boot: null, cats: [], scan: null, browsers: [], selected: new Set(), lastClean: null,
  mon: { cpu: [], ram: [], last: null }, config: null, schedule: null, update: null,
  large: null, dupes: null, dupSel: new Set(), largeSel: new Set(), reg: null, regSel: new Set(),
  apps: null, appSel: new Set(), histTab: 'history', diskTab: 'folders', folders: null,
};
const loaded = new Set();

/* ── navigáció ───────────────────────────────────────────────────────────── */
const PAGES = {
  overview: renderOverview, cleaner: renderCleaner, monitor: renderMonitor, disk: renderDisk,
  dupes: renderDupes, registry: renderRegistry, tweaks: renderTweaks, schedule: renderSchedule,
  history: renderHistory, settings: renderSettings,
};
function go(page) {
  if (!PAGES[page]) page = 'overview';
  $$('#nav a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  $$('.page').forEach(p => p.classList.toggle('active', p.id === `page-${page}`));
  $('#main').scrollTop = 0;
  if (location.hash !== `#${page}`) history.replaceState(null, '', `#${page}`);
  PAGES[page]();
}
$('#nav').addEventListener('click', e => { const a = e.target.closest('a[data-page]'); if (a) go(a.dataset.page); });
document.addEventListener('click', e => { const g = e.target.closest('[data-go]'); if (g) go(g.dataset.go); });

const head = (title, sub, actions = '') =>
  `<div class="head"><div><h1>${esc(title)}</h1>${sub ? `<p>${sub}</p>` : ''}</div>${actions ? `<div class="actions">${actions}</div>` : ''}</div>`;

/* ── téma és kiemelőszín ─────────────────────────────────────────────────── */
const mqLight = matchMedia('(prefers-color-scheme: light)');
function applyTheme() {
  const t = S.config?.theme || 'system';
  const root = document.documentElement;
  root.dataset.theme = t;
  root.classList.toggle('prefers-light', t === 'system' && mqLight.matches);
  const isLight = t === 'light' || (t === 'system' && mqLight.matches);
  $('#themeBtn use').setAttribute('href', `/static/icons.svg#i-${isLight ? 'sun' : 'moon'}`);
  const prof = S.config?.profiles?.[S.config.active_profile];
  if (prof?.accent) root.style.setProperty('--ac', prof.accent);
}
mqLight.addEventListener('change', applyTheme);
$('#themeBtn').addEventListener('click', async () => {
  const order = ['system', 'dark', 'light'];
  const next = order[(order.indexOf(S.config.theme) + 1) % 3];
  S.config = await api('config/option', { key: 'theme', value: next });
  applyTheme();
  toast({ system: 'Téma: a rendszert követi', dark: 'Téma: sötét', light: 'Téma: világos' }[next]);
  if ($('#page-settings').classList.contains('active')) renderSettings();
});

function sideState() {
  const prof = S.config.profiles[S.config.active_profile];
  $('#profileName').textContent = prof.name;
  const admin = S.boot.system.is_admin;
  const chip = $('#adminChip');
  chip.className = `chip ${admin ? 'ok' : ''}`;
  chip.textContent = S.boot.system.is_windows ? (admin ? 'Rendszergazda' : 'Normál jog') : S.boot.system.os.split(' ')[0];
  chip.title = admin ? 'Rendszergazdai jogokkal fut' : 'Normál felhasználói jogokkal fut';
  $$('.win-only').forEach(el => { el.hidden = !S.boot.system.is_windows; });
  const sc = S.schedule;
  $('#pillSched').textContent = sc?.enabled ? 'BE' : '';
  $('#pillUpdate').hidden = !S.update?.newer;
}

/* ── élő monitor (SSE, egyetlen kapcsolat) ───────────────────────────────── */
function startMonitor() {
  const es = new EventSource(dl('monitor'));
  es.onmessage = ev => {
    const d = JSON.parse(ev.data);
    if (d.error) return;
    S.mon.last = d;
    S.mon.cpu.push(d.cpu); S.mon.ram.push(d.ram_pct);
    if (S.mon.cpu.length > 80) { S.mon.cpu.shift(); S.mon.ram.shift(); }
    $('#pillCpu').textContent = `${Math.round(d.cpu)}%`;
    if ($('#page-overview').classList.contains('active')) updateOverviewLive();
    if ($('#page-monitor').classList.contains('active')) updateMonitor();
  };
}
const driveLabel = () => (S.boot.system.is_windows ? `${S.boot.system.drive.replace(/\\$/, '')} meghajtó` : 'Rendszerkötet (/)');
const level = p => (p >= 90 ? 'bad' : p >= 75 ? 'warn' : '');

/* ── ÁTTEKINTÉS ──────────────────────────────────────────────────────────── */
function scanTotal(onlySelected = false) {
  if (!S.scan) return null;
  return S.cats.filter(c => !c.locked && (!onlySelected || S.selected.has(c.id)))
    .reduce((a, c) => a + (S.scan[c.id]?.size || 0), 0);
}

function renderOverview() {
  const sys = S.boot.system;
  const disk = sys.disk || {};
  const rec = scanTotal(true);
  const total = disk.total || 1;
  const recW = rec ? Math.min(rec, disk.used || 0) / total * 100 : 0;
  const usedW = (disk.used || 0) / total * 100 - recW;
  const last = S.lastClean;
  const upd = S.update?.newer ? `<div class="banner">${icon('download', 'lg')}<div class="grow"><b>Elérhető a PyCleaner ${esc(S.update.latest)}</b><span>Jelenleg a ${esc(S.update.current)} verziót használod.</span></div><button class="btn primary sm" data-open-release>Letöltés</button></div>` : '';
  const adminNote = sys.is_windows && !sys.is_admin ? `<div class="banner warn">${icon('shield-alert', 'lg')}<div class="grow"><b>Normál jogokkal fut</b><span>A Windows Update gyorsítótár, a rendszernaplók és néhány registry-elem csak rendszergazdaként tisztítható.</span></div><button class="btn sm" id="ovElevate">${icon('shield-check', 'sm')}Újraindítás rendszergazdaként</button></div>` : '';
  $('#page-overview').innerHTML = `
    ${head('Áttekintés', esc(sys.os))}
    ${upd}${adminNote}
    <div class="card hero">
      <div>
        <div class="label">${S.scan ? 'Felszabadítható a kijelölt kategóriákban' : 'A gép még nincs átvizsgálva'}</div>
        <div class="big num">${S.scan ? esc(fmtB(rec)).replace(/ (\S+)$/, ' <small>$1</small>') : '—'}</div>
        <div class="muted">${esc(disk.free_fmt ? `${driveLabel()}: ${fmtB(disk.free)} szabad / ${fmtB(disk.total)}` : '')}</div>
        <div class="capbar" title="Lemezfoglaltság"><i class="used" style="width:${usedW.toFixed(2)}%"></i><i class="rec" style="width:${recW.toFixed(2)}%"></i></div>
        <div class="legend"><span><i class="used"></i>Foglalt</span><span><i class="rec"></i>Felszabadítható</span><span><i class="free"></i>Szabad</span></div>
      </div>
      <div class="cta">
        <button class="btn primary lg" id="ovScan">${icon('search')}${S.scan ? 'Újravizsgálás' : 'Gép átvizsgálása'}</button>
        <button class="btn lg" id="ovClean" ${S.scan && rec ? '' : 'disabled'}>${icon('sparkles')}Gyors tisztítás</button>
        <button class="btn ghost sm" data-go="cleaner">Részletes tisztítás ${icon('play', 'sm')}</button>
      </div>
    </div>
    <div class="grid g4">
      <div class="card stat"><span class="k">Processzor</span><span class="v num" id="ovCpu">—</span><div class="meter"><i id="ovCpuM" style="width:0"></i></div></div>
      <div class="card stat"><span class="k">Memória</span><span class="v num" id="ovRam">—</span><div class="meter"><i id="ovRamM" style="width:0"></i></div></div>
      <div class="card stat"><span class="k">${esc(driveLabel())}</span><span class="v num">${disk.used_pct != null ? pct(disk.used_pct) : '—'}<small>%</small></span><div class="meter"><i class="${level(disk.used_pct)}" style="width:${disk.used_pct || 0}%"></i></div></div>
      <div class="card stat"><span class="k">Hálózat ↓ / ↑</span><span class="v num" id="ovNet" style="font-size:16px">—</span><div class="faint" style="font-size:12px;margin-top:8px" id="ovNetT">&nbsp;</div></div>
    </div>
    <div class="grid g2">
      <div class="card">
        <div class="card-head"><div class="tile-ic ok">${icon('history')}</div><div><h3>Legutóbbi tisztítás</h3><p class="sub">${last ? esc(last.timestamp) + (last.auto ? ' · ütemezett' : '') : 'Még nem volt tisztítás'}</p></div>
        <div class="right"><button class="btn ghost sm" data-go="history">Előzmények</button></div></div>
        ${last ? `<div class="stat"><span class="v num">${esc(last.total_freed)}</span><span class="k">${fmtNum(last.total_files)} fájl törölve${last.total_errors ? `, ${fmtNum(last.total_errors)} zárolt fájl kimaradt` : ''}</span></div>` : '<p class="muted" style="margin:0">Vizsgáld át a gépet, majd indíts egy tisztítást.</p>'}
      </div>
      <div class="card">
        <div class="card-head"><div class="tile-ic">${icon('cpu')}</div><div><h3>Rendszer</h3><p class="sub">${esc(sys.processor)}</p></div></div>
        <dl class="kv">
          <dt>Operációs rendszer</dt><dd>${esc(sys.os)}</dd>
          <dt>Memória</dt><dd>${esc(sys.ram_total || '—')}</dd>
          <dt>Processzormagok</dt><dd>${esc(sys.cpu_physical ?? '—')} fizikai / ${esc(sys.cpu_count ?? '—')} logikai</dd>
          <dt>Utolsó indítás</dt><dd>${esc(sys.boot_time || '—')}</dd>
        </dl>
      </div>
    </div>`;
  $('#ovScan').onclick = e => busy(e.currentTarget, doScan).then(renderOverview);
  $('#ovClean').onclick = e => doClean(e.currentTarget, true);
  const el = $('#ovElevate'); if (el) el.onclick = e => elevate(e.currentTarget);
  updateOverviewLive();
}

function updateOverviewLive() {
  const d = S.mon.last; if (!d || !$('#ovCpu')) return;
  $('#ovCpu').innerHTML = `${Math.round(d.cpu)}<small>%</small>`;
  $('#ovCpuM').style.width = `${d.cpu}%`; $('#ovCpuM').className = level(d.cpu);
  $('#ovRam').innerHTML = `${Math.round(d.ram_pct)}<small>% · ${esc(d.ram_used)}</small>`;
  $('#ovRamM').style.width = `${d.ram_pct}%`; $('#ovRamM').className = level(d.ram_pct);
  $('#ovNet').textContent = `${fmtB(d.net_down)}/s · ${fmtB(d.net_up)}/s`;
  $('#ovNetT').textContent = `Összesen: ${d.net_recv_total} le, ${d.net_sent_total} fel`;
}

/* ── TISZTÍTÁS ───────────────────────────────────────────────────────────── */
async function doScan() {
  const r = await api('scan', {});
  S.scan = r.results; S.browsers = r.browsers; S.cats = r.categories;
  const t = scanTotal(true);
  $('#pillClean').textContent = t ? fmtB(t) : '';
  return r;
}

function renderCleaner() {
  const cats = S.cats;
  const rows = cats.map(c => {
    const r = S.scan?.[c.id];
    const on = S.selected.has(c.id) && !c.locked;
    const size = r ? (r.size ? `<b>${esc(fmtB(r.size))}</b><span>${fmtNum(r.files)} fájl</span>` : '<b class="zero">0 B</b><span>tiszta</span>') : '<b class="zero">—</b><span>&nbsp;</span>';
    const badges = (c.admin ? `<span class="chip ${c.locked ? 'warn' : ''}">${icon('shield-check', 'sm')}Rendszergazda</span>` : '')
      + (c.id === 'browser' && S.browsers.length ? `<span class="chip warn">Fut: ${esc(S.browsers.join(', '))}</span>` : '');
    const tip = c.paths.length ? esc(c.paths.join('\n')) : 'Nincs ilyen mappa ezen a gépen';
    return `<label class="cat ${on ? 'on' : ''} ${c.locked ? 'locked' : ''}" title="${tip}">
      <input type="checkbox" class="check" data-cat="${esc(c.id)}" ${on ? 'checked' : ''} ${c.locked ? 'disabled' : ''}>
      <div class="tile-ic ${c.caution ? 'warn' : ''}">${icon(c.icon)}</div>
      <div><div class="t">${esc(c.label)}${badges}</div><div class="d">${esc(c.desc)}</div>
        ${c.caution ? `<div class="c">${esc(c.caution)}</div>` : ''}
        ${c.id === 'browser' && S.browsers.length ? '<div class="c">A futó böngészők zárolt fájljai kimaradnak — a teljes tisztításhoz zárd be őket.</div>' : ''}
        ${c.id === 'custom' && !c.paths.length ? '<div class="d"><a href="#settings" data-go="settings">Mappák megadása a Beállításokban</a></div>' : ''}
        ${c.locked ? '<div class="c">Ehhez indítsd újra a PyCleanert rendszergazdaként.</div>' : ''}
      </div>
      <div class="size">${size}</div></label>`;
  }).join('');
  const res = S.lastResult;
  $('#page-cleaner').innerHTML = `
    ${head('Tisztítás', 'Jelöld ki, mit takarítson a PyCleaner. A méretek a beolvasás után pontosak — csak azt számolja, amit ténylegesen törölne.',
      `<button class="btn ghost" id="clAll">Mind</button><button class="btn ghost" id="clNone">Egyik sem</button>`)}
    ${res ? `<div class="card" style="margin-bottom:14px"><div class="card-head"><div class="tile-ic ok">${icon('circle-check')}</div><div><h3>Kész: ${esc(res.total_freed)} felszabadítva</h3><p class="sub">${fmtNum(res.total_files)} fájl törölve ${res.duration_s} mp alatt${res.total_errors ? ` · ${fmtNum(res.total_errors)} használatban lévő fájl kimaradt` : ''}${res.backup ? ' · mentés készült' : ''}</p></div><div class="right"><button class="icon-btn" id="resClose" title="Bezárás">${icon('x')}</button></div></div>
      <div class="result-list">${res.details.map(d => `<div><span>${esc(d.category)}</span><span class="num">${esc(d.freed)} · ${fmtNum(d.files)} fájl</span></div>`).join('')}</div>
      ${res.skipped_admin?.length ? `<p class="c" style="color:var(--warn);margin:10px 0 0">Rendszergazdai jog hiányában kimaradt: ${esc(res.skipped_admin.join(', '))}</p>` : ''}</div>` : ''}
    <div class="cats">${rows}</div>
    <div class="dock">
      <div class="sum"><b class="num" id="clSum">${S.scan ? esc(fmtB(scanTotal(true))) : '—'}</b><span>${S.selected.size} kategória kijelölve</span></div>
      <label class="row" style="gap:8px"><span class="muted">Csak a régebbiek, mint</span>
        <select id="clAge"><option value="0">bármilyen kor</option><option value="1">1 nap</option><option value="7">1 hét</option><option value="30">1 hónap</option></select></label>
      <button class="btn" id="clScan">${icon('search')}${S.scan ? 'Újraolvasás' : 'Beolvasás'}</button>
      <button class="btn primary" id="clGo" ${S.selected.size ? '' : 'disabled'}>${icon('sparkles')}Tisztítás</button>
    </div>`;
  $('#clAge').value = S.minAge || '0';
  $('#clAge').onchange = e => { S.minAge = e.target.value; };
  $$('#page-cleaner .check').forEach(cb => cb.onchange = () => {
    cb.checked ? S.selected.add(cb.dataset.cat) : S.selected.delete(cb.dataset.cat);
    renderCleaner(); $('#pillClean').textContent = S.scan && scanTotal(true) ? fmtB(scanTotal(true)) : '';
  });
  $('#clAll').onclick = () => { S.cats.filter(c => !c.locked).forEach(c => S.selected.add(c.id)); renderCleaner(); };
  $('#clNone').onclick = () => { S.selected.clear(); renderCleaner(); };
  $('#clScan').onclick = e => busy(e.currentTarget, doScan).then(renderCleaner);
  $('#clGo').onclick = e => doClean(e.currentTarget, false);
  const rc = $('#resClose'); if (rc) rc.onclick = () => { S.lastResult = null; renderCleaner(); };
}

async function doClean(btn, quick) {
  const ids = quick ? S.cats.filter(c => c.default && !c.locked).map(c => c.id) : [...S.selected];
  if (!ids.length) return;
  const risky = ids.filter(i => ['trash', 'custom'].includes(i)).map(i => S.cats.find(c => c.id === i)?.label);
  if (risky.length && !await dialog({ title: 'Végleges törlés', danger: true, ok: 'Törlés',
    text: `A kijelöltek között ez is szerepel: <b>${esc(risky.join(', '))}</b>. Ezek a fájlok nem kerülnek a Lomtárba, nem állíthatók vissza.` })) return;
  await busy(btn, async () => {
    const r = await api('clean', { categories: ids, min_age_days: quick ? 0 : Number(S.minAge || 0) });
    S.lastResult = r; S.lastClean = r;
    toast(`Kész: ${r.total_freed} felszabadítva (${fmtNum(r.total_files)} fájl)`, 'ok');
    await doScan();
  });
  if ($('#page-cleaner').classList.contains('active')) renderCleaner(); else renderOverview();
}

/* ── MONITOR ─────────────────────────────────────────────────────────────── */
function spark(values, alt = false) {
  const n = 80, w = 400, h = 100;
  const pts = values.slice(-n);
  const off = n - pts.length;
  const xy = pts.map((v, i) => [((off + i) / (n - 1)) * w, h - (Math.max(0, Math.min(100, v)) / 100) * (h - 4) - 2]);
  const line = xy.map(p => p.map(x => x.toFixed(1)).join(',')).join(' ');
  const area = xy.length ? `M${xy[0][0]},${h} L${line.replace(/ /g, ' L')} L${xy[xy.length - 1][0]},${h} Z` : '';
  return `<svg class="spark ${alt ? 'alt' : ''}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <line class="grid-l" x1="0" x2="${w}" y1="${h / 2}" y2="${h / 2}"/><line class="grid-l" x1="0" x2="${w}" y1="${h * 0.1}" y2="${h * 0.1}"/>
    ${xy.length ? `<path class="area" d="${area}"/><polyline class="line" points="${line}"/>` : ''}</svg>`;
}
function renderMonitor() {
  $('#page-monitor').innerHTML = `
    ${head('Élő monitor', 'Másfél másodpercenként frissülő terhelés és a legtöbb memóriát használó folyamatok.')}
    <div class="grid g2">
      <div class="card"><div class="card-head"><div class="tile-ic">${icon('cpu')}</div><div><h3>Processzor</h3><p class="sub" id="mCpuSub">—</p></div><div class="right"><span class="stat"><span class="v num" id="mCpu">—</span></span></div></div><div id="mCpuG"></div></div>
      <div class="card"><div class="card-head"><div class="tile-ic">${icon('memory-stick')}</div><div><h3>Memória</h3><p class="sub" id="mRamSub">—</p></div><div class="right"><span class="stat"><span class="v num" id="mRam">—</span></span></div></div><div id="mRamG"></div></div>
    </div>
    <div class="grid g3">
      <div class="card stat"><span class="k">Lapozófájl / swap</span><span class="v num" id="mSwap">—</span><div class="meter"><i id="mSwapM" style="width:0"></i></div></div>
      <div class="card stat"><span class="k">Rendszermeghajtó</span><span class="v num" id="mDisk">—</span><div class="meter"><i id="mDiskM" style="width:0"></i></div></div>
      <div class="card stat"><span class="k">Hálózat ↓ / ↑</span><span class="v num" id="mNet" style="font-size:17px">—</span><div class="faint" style="font-size:12px;margin-top:8px" id="mNetT">&nbsp;</div></div>
    </div>
    <div class="card"><div class="card-head"><div class="tile-ic">${icon('activity')}</div><div><h3>Folyamatok</h3><p class="sub">Memóriahasználat szerint</p></div></div>
      <div class="table-wrap"><table class="tbl"><thead><tr><th>Folyamat</th><th class="r">PID</th><th class="r">CPU</th><th class="r">Memória</th></tr></thead><tbody id="mProcs"><tr><td colspan="4"><div class="skeleton"></div></td></tr></tbody></table></div></div>`;
  updateMonitor();
}
function updateMonitor() {
  const d = S.mon.last; if (!d || !$('#mCpu')) return;
  $('#mCpu').innerHTML = `${Math.round(d.cpu)}<small>%</small>`;
  $('#mCpuSub').textContent = `${d.cpu_count} logikai mag · frissítve ${d.ts}`;
  $('#mRam').innerHTML = `${Math.round(d.ram_pct)}<small>%</small>`;
  $('#mRamSub').textContent = `${d.ram_used} / ${d.ram_total} · ${d.ram_available} szabad`;
  $('#mCpuG').innerHTML = spark(S.mon.cpu);
  $('#mRamG').innerHTML = spark(S.mon.ram, true);
  $('#mSwap').innerHTML = `${Math.round(d.swap_pct)}<small>% · ${esc(d.swap_used)} / ${esc(d.swap_total)}</small>`;
  $('#mSwapM').style.width = `${d.swap_pct}%`; $('#mSwapM').className = level(d.swap_pct);
  $('#mDisk').innerHTML = `${pct(d.disk_pct)}<small>% · ${esc(d.disk_free)} szabad</small>`;
  $('#mDiskM').style.width = `${d.disk_pct}%`; $('#mDiskM').className = level(d.disk_pct);
  $('#mNet').textContent = `${fmtB(d.net_down)}/s · ${fmtB(d.net_up)}/s`;
  $('#mNetT').textContent = `Indítás óta: ${d.net_recv_total} le, ${d.net_sent_total} fel`;
  $('#mProcs').innerHTML = d.processes.map(p => `<tr><td>${esc(p.name)}</td><td class="r num faint">${p.pid}</td><td class="r num">${p.cpu.toFixed(1)}%</td><td class="r num">${esc(p.rss_fmt)}</td></tr>`).join('');
}

/* ── közös: mappaválasztó ────────────────────────────────────────────────── */
function pathPicker(id, value) {
  return `<div class="path-input"><input type="text" id="${id}" value="${esc(value)}" spellcheck="false">
    ${S.boot.can_pick_folder ? `<button class="btn" data-pick="${id}">${icon('folder-open')}Tallózás</button>` : ''}</div>`;
}
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-pick]'); if (!b) return;
  const r = await api('pick_folder', {});
  if (r.path) { $('#' + b.dataset.pick).value = r.path; }
});
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-reveal]'); if (!b) return;
  await api('files/reveal', { path: b.dataset.reveal }).catch(err => toast(err.message, 'err'));
});
document.addEventListener('click', e => {
  if (e.target.closest('[data-open-release]')) api('open_url', { url: S.update?.url || 'https://github.com/csiber/pycleaner/releases' });
});

async function trashFiles(paths, btn) {
  if (!paths.length) return [];
  const ok = await dialog({ title: `${paths.length} fájl a Lomtárba`, ok: 'Lomtárba helyezés', danger: true,
    text: 'A kijelölt fájlok a Lomtárba kerülnek, onnan még visszaállíthatók.' });
  if (!ok) return [];
  const r = await busy(btn, () => api('files/delete', { paths }));
  if (!r) return [];
  const good = r.results.filter(x => x.ok).map(x => x.path);
  const bad = r.results.filter(x => !x.ok);
  if (good.length) toast(`${good.length} fájl a Lomtárba került`, 'ok');
  if (bad.length) toast(`${bad.length} fájl nem törölhető: ${bad[0].error}`, 'err', 6000);
  return good;
}

/* ── LEMEZELEMZŐ ─────────────────────────────────────────────────────────── */
function renderDisk() {
  const tab = S.diskTab;
  const drives = (S.boot.system.drives || []).map(d => `
    <div class="bar-row"><div class="name">${esc(d.mount)}<span>${esc(d.fstype)} · ${esc(d.total_fmt)}</span></div>
      <div class="track"><i class="${level(d.used_pct)}" style="width:${d.used_pct}%;${level(d.used_pct) ? `background:var(--${level(d.used_pct)})` : ''}"></i></div>
      <div class="val">${esc(d.free_fmt)}<div class="faint" style="font-size:11.5px;font-weight:500">szabad</div></div></div>`).join('');
  $('#page-disk').innerHTML = `
    ${head('Lemezelemző', 'Mi foglalja a helyet? Meghajtók, a személyes mappák mérete és a legnagyobb fájlok.')}
    ${drives ? `<div class="card" style="margin-bottom:14px"><div class="card-head"><div class="tile-ic">${icon('hard-drive')}</div><div><h3>Meghajtók</h3></div></div><div class="bars">${drives}</div></div>` : ''}
    <div class="tabs"><button data-dtab="folders" class="${tab === 'folders' ? 'on' : ''}">Személyes mappák</button><button data-dtab="large" class="${tab === 'large' ? 'on' : ''}">Nagy fájlok</button></div>
    <div id="diskBody"></div>`;
  $$('[data-dtab]').forEach(b => b.onclick = () => { S.diskTab = b.dataset.dtab; renderDisk(); });
  tab === 'folders' ? renderFolders() : renderLarge();
}
async function renderFolders() {
  const body = $('#diskBody');
  const draw = () => {
    if (S.diskTab !== 'folders' || !$('#diskBody')) return; // közben fület váltottak
    const f = S.folders;
    const max = Math.max(1, ...f.map(x => x.size));
    body.innerHTML = `<div class="card"><div class="card-head"><div><h3>Személyes mappák</h3><p class="sub">Kattints a névre a megnyitáshoz</p></div><div class="right"><button class="btn sm" id="fRe">${icon('refresh-cw', 'sm')}Frissítés</button></div></div>
      <div class="bars">${f.map(x => `<div class="bar-row"><div class="name"><a href="#" data-reveal="${esc(x.path)}">${esc(x.name)}</a><span>${fmtNum(x.files)} fájl</span></div><div class="track"><i style="width:${(x.size / max * 100).toFixed(1)}%"></i></div><div class="val">${esc(x.size_fmt)}</div></div>`).join('')}</div></div>`;
    $('#fRe').onclick = e => busy(e.currentTarget, async () => { S.folders = await api('folders'); draw(); });
  };
  if (S.folders) return draw();
  body.innerHTML = `<div class="card"><div class="skeleton" style="margin:8px 0"></div><div class="skeleton" style="margin:14px 0;width:70%"></div><div class="skeleton" style="width:85%"></div><p class="faint" style="margin:14px 0 0">Mappák mérése…</p></div>`;
  try { S.folders = await api('folders'); draw(); } catch (e) { toast(e.message, 'err'); }
}
function renderLarge() {
  const L = S.large;
  const rows = L?.files?.map(f => `<tr>
    <td class="w"><input type="checkbox" class="check" data-lf="${esc(f.path)}" ${S.largeSel.has(f.path) ? 'checked' : ''}></td>
    <td class="file-cell"><b>${esc(f.name)}</b><span>${ltr(f.path)}</span></td>
    <td class="w"><span class="chip">${esc(f.ext || '—')}</span></td>
    <td class="r num w"><b>${esc(f.size_fmt)}</b></td>
    <td class="w"><button class="icon-btn" title="Megmutatás a mappában" data-reveal="${esc(f.path)}">${icon('folder-open')}</button></td></tr>`).join('');
  $('#diskBody').innerHTML = `<div class="card">
    <div class="row" style="margin-bottom:${L ? 16 : 0}px">
      ${pathPicker('lfPath', S.lfPath || S.boot.home)}
      <label class="row" style="gap:8px"><span class="muted">Legalább</span><select id="lfMin">${[50, 100, 250, 500, 1000, 4000].map(v => `<option value="${v}">${v >= 1000 ? v / 1000 + ' GB' : v + ' MB'}</option>`).join('')}</select></label>
      <button class="btn primary" id="lfGo">${icon('search')}Keresés</button>
    </div>
    ${L ? (L.files.length ? `<div class="row" style="margin-bottom:8px"><span class="muted grow">${L.files.length} fájl, összesen ${esc(fmtB(L.files.reduce((a, f) => a + f.size, 0)))}</span>
      <button class="btn danger sm" id="lfDel" ${S.largeSel.size ? '' : 'disabled'}>${icon('trash-2', 'sm')}Kijelöltek Lomtárba (${S.largeSel.size})</button></div>
      <div class="table-wrap"><table class="tbl"><thead><tr><th></th><th>Fájl</th><th>Típus</th><th class="r">Méret</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
      : `<div class="empty"><div class="tile-ic ok">${icon('circle-check', 'lg')}</div><b>Nincs ekkora fájl</b>ebben a mappában.</div>`) : ''}
  </div>`;
  $('#lfMin').value = S.lfMin || '100';
  $('#lfGo').onclick = e => busy(e.currentTarget, async () => {
    S.lfPath = $('#lfPath').value; S.lfMin = $('#lfMin').value;
    S.large = await api('large_files', { path: S.lfPath, min_mb: Number(S.lfMin) });
    S.largeSel.clear(); renderLarge();
  });
  $$('[data-lf]').forEach(cb => cb.onchange = () => { cb.checked ? S.largeSel.add(cb.dataset.lf) : S.largeSel.delete(cb.dataset.lf); renderLarge(); });
  const del = $('#lfDel');
  if (del) del.onclick = async e => {
    const gone = await trashFiles([...S.largeSel], e.currentTarget);
    S.large.files = S.large.files.filter(f => !gone.includes(f.path));
    gone.forEach(p => S.largeSel.delete(p)); renderLarge();
  };
}

/* ── DUPLIKÁTUMOK ────────────────────────────────────────────────────────── */
function renderDupes() {
  const D = S.dupes;
  const groups = D?.groups?.map((g, gi) => `<div class="group">
    <div class="group-h">${icon('copy', 'sm')}<span><b>${g.files.length} példány</b> · ${esc(g.size_fmt)} darabonként</span><span style="margin-left:auto">felesleges: <b>${esc(g.wasted_fmt)}</b></span></div>
    ${g.files.map((f, fi) => `<div class="group-f">
      <input type="checkbox" class="check" data-dp="${esc(f.path)}" ${S.dupSel.has(f.path) ? 'checked' : ''}>
      <span class="p" title="${esc(f.path)}">${ltr(f.path)}</span>
      <span class="faint num">${fi === 0 ? '<span class="chip ac">legújabb</span> ' : ''}${esc(fmtDate(f.mtime))}</span>
      <button class="icon-btn" title="Megmutatás a mappában" data-reveal="${esc(f.path)}">${icon('folder-open', 'sm')}</button></div>`).join('')}
  </div>`).join('');
  const selBytes = D ? D.groups.reduce((a, g) => a + g.files.filter(f => S.dupSel.has(f.path)).length * g.size, 0) : 0;
  $('#page-dupes').innerHTML = `
    ${head('Duplikátumok', 'Azonos tartalmú fájlok keresése. Előbb méret, majd tartalom (BLAKE2b) alapján — a fájlnév nem számít.')}
    <div class="card">
      <div class="row">${pathPicker('dpPath', S.dpPath || S.boot.home)}
        <label class="row" style="gap:8px"><span class="muted">Legalább</span><select id="dpMin">${[[10, '10 KB'], [100, '100 KB'], [1024, '1 MB'], [10240, '10 MB']].map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
        <button class="btn primary" id="dpGo">${icon('search')}Keresés</button></div>
    </div>
    ${D ? (D.groups.length ? `<div class="card">
      <div class="card-head"><div class="tile-ic warn">${icon('copy')}</div><div><h3>${D.groups.length} csoport · ${esc(D.total_wasted_fmt)} felesleges</h3><p class="sub">${fmtNum(D.scanned)} fájl átvizsgálva itt: ${esc(D.root)}</p></div>
        <div class="right"><button class="btn sm" id="dpAuto">Mindenhol a legújabb marad</button><button class="btn danger sm" id="dpDel" ${S.dupSel.size ? '' : 'disabled'}>${icon('trash-2', 'sm')}Lomtárba (${S.dupSel.size} · ${esc(fmtB(selBytes))})</button></div></div>
      ${groups}</div>` : `<div class="card empty"><div class="tile-ic ok">${icon('circle-check', 'lg')}</div><b>Nincs duplikátum</b>${fmtNum(D.scanned)} fájl átvizsgálva.</div>`) : ''}`;
  $('#dpMin').value = S.dpMin || '100';
  $('#dpGo').onclick = e => busy(e.currentTarget, async () => {
    S.dpPath = $('#dpPath').value; S.dpMin = $('#dpMin').value;
    toast('Keresés folyamatban — nagy mappánál ez percekig is tarthat.');
    S.dupes = await api('duplicates', { path: S.dpPath, min_kb: Number(S.dpMin) });
    S.dupSel.clear(); renderDupes();
  });
  $$('[data-dp]').forEach(cb => cb.onchange = () => {
    const g = S.dupes.groups.find(x => x.files.some(f => f.path === cb.dataset.dp));
    if (cb.checked && g.files.every(f => f.path === cb.dataset.dp || S.dupSel.has(f.path))) {
      cb.checked = false; toast('Minden csoportból legalább egy példánynak meg kell maradnia.', 'warn'); return;
    }
    cb.checked ? S.dupSel.add(cb.dataset.dp) : S.dupSel.delete(cb.dataset.dp); renderDupes();
  });
  const auto = $('#dpAuto');
  if (auto) auto.onclick = () => { S.dupSel.clear(); S.dupes.groups.forEach(g => g.files.slice(1).forEach(f => S.dupSel.add(f.path))); renderDupes(); };
  const del = $('#dpDel');
  if (del) del.onclick = async e => {
    const gone = await trashFiles([...S.dupSel], e.currentTarget);
    S.dupes.groups.forEach(g => { g.files = g.files.filter(f => !gone.includes(f.path)); });
    S.dupes.groups = S.dupes.groups.filter(g => g.files.length > 1);
    gone.forEach(p => S.dupSel.delete(p)); renderDupes();
  };
}

/* ── REGISTRY ────────────────────────────────────────────────────────────── */
function renderRegistry() {
  const R = S.reg;
  const admin = S.boot.system.is_admin;
  const items = R?.issues?.map(i => {
    const lock = i.admin && !admin;
    return `<div class="list-item"><input type="checkbox" class="check" data-reg="${i.id}" ${S.regSel.has(i.id) ? 'checked' : ''} ${lock ? 'disabled' : ''}>
      <div style="min-width:0"><div class="t">${esc(i.title)} ${i.admin ? `<span class="chip ${lock ? 'warn' : ''}">${i.hive}</span>` : ''}</div><div class="d" title="${esc(i.detail)}">${esc(i.detail)}</div></div>
      <span class="faint mono" title="${esc(i.hive + '\\' + i.key)}" style="font-size:11px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(i.key.split('\\').slice(-2).join('\\'))}</span></div>`;
  }).join('');
  $('#page-registry').innerHTML = `
    ${head('Registry', 'Óvatos keresés: csak egyértelműen elavult bejegyzéseket jelez (törölt programok maradványai). Minden javítás előtt automatikus .reg mentés készül.',
      `<button class="btn ghost" id="rgBk">${icon('archive')}Mentések mappája</button><button class="btn primary" id="rgScan">${icon('search')}Keresés</button>`)}
    ${R ? (R.issues.length ? `<div class="card"><div class="card-head"><div class="tile-ic warn">${icon('list-tree')}</div><div><h3>${R.issues.length} elavult bejegyzés</h3><p class="sub">${admin ? '' : 'A HKLM-bejegyzésekhez rendszergazdai jog kell. '}A javítás visszavonható: a mentett .reg fájlra duplán kattintva.</p></div>
      <div class="right"><button class="btn sm" id="rgAll">Mind kijelölése</button><button class="btn primary sm" id="rgFix" ${S.regSel.size ? '' : 'disabled'}>${icon('wrench', 'sm')}Javítás (${S.regSel.size})</button></div></div>${items}</div>`
      : `<div class="card empty"><div class="tile-ic ok">${icon('shield-check', 'lg')}</div><b>Rendben van</b>Nem találtam elavult bejegyzést.</div>`)
      : `<div class="card empty"><div class="tile-ic">${icon('list-tree', 'lg')}</div><b>Még nem kerestél</b>A keresés csak olvas, semmit nem módosít.</div>`}`;
  $('#rgScan').onclick = e => busy(e.currentTarget, async () => { S.reg = await api('registry/scan'); S.regSel.clear(); renderRegistry(); });
  $('#rgBk').onclick = () => api('registry/backups/open', {});
  $$('[data-reg]').forEach(cb => cb.onchange = () => { const id = Number(cb.dataset.reg); cb.checked ? S.regSel.add(id) : S.regSel.delete(id); renderRegistry(); });
  const all = $('#rgAll'); if (all) all.onclick = () => { R.issues.filter(i => !(i.admin && !admin)).forEach(i => S.regSel.add(i.id)); renderRegistry(); };
  const fix = $('#rgFix');
  if (fix) fix.onclick = async e => {
    if (!await dialog({ title: `${S.regSel.size} registry-bejegyzés javítása`, ok: 'Javítás', danger: true,
      text: 'A kijelölt bejegyzések törlődnek a rendszerleíró adatbázisból. Előtte automatikus .reg mentés készül, amelyre duplán kattintva visszaállíthatók.' })) return;
    busy(e.currentTarget, async () => {
    const r = await api('registry/fix', { ids: [...S.regSel] });
    const ok = r.results.filter(x => x.ok).length, bad = r.results.filter(x => !x.ok);
    if (ok) toast(`${ok} bejegyzés javítva, mentés: registry-backups`, 'ok');
    if (bad.length) toast(bad[0].msg, 'err', 6000);
    S.reg = await api('registry/scan'); S.regSel.clear(); renderRegistry();
    });
  };
}

/* ── WINDOWS-FINOMHANGOLÁS ───────────────────────────────────────────────── */
async function elevate(btn) {
  await busy(btn, async () => {
    const r = await api('admin/relaunch', {});
    if (r.ok) { toast('Újraindítás rendszergazdaként…', 'ok'); setTimeout(showGoodbye, 600); }
    else toast(r.msg, 'warn');
  });
}
function renderTweaks() {
  const admin = S.boot.system.is_admin;
  const apps = S.apps;
  const appRows = apps ? [...apps].sort((a, b) => b.installed - a.installed).map(a => `<label class="list-item" style="cursor:${a.installed ? 'pointer' : 'default'}">
      <input type="checkbox" class="check" data-app="${esc(a.id)}" ${S.appSel.has(a.id) ? 'checked' : ''} ${a.installed ? '' : 'disabled'}>
      <div><div class="t">${esc(a.name)}</div><div class="d mono">${esc(a.id)}</div></div>
      <span class="chip ${a.installed ? 'ac' : ''}">${a.installed ? 'Telepítve' : 'Nincs fent'}</span></label>`).join('')
    : '<div class="skeleton" style="margin:10px 0"></div><div class="skeleton" style="width:80%;margin:16px 0"></div><div class="skeleton" style="width:60%"></div>';
  $('#page-tweaks').innerHTML = `
    ${head('Windows-finomhangolás', 'Előtelepített alkalmazások és a OneDrive eltávolítása. Nagyobb módosítás előtt érdemes visszaállítási pontot készíteni.')}
    <div class="grid g2">
      <div class="card"><div class="card-head"><div class="tile-ic ${admin ? 'ok' : 'warn'}">${icon(admin ? 'shield-check' : 'shield-alert')}</div><div><h3>${admin ? 'Rendszergazdaként fut' : 'Normál jogokkal fut'}</h3><p class="sub">${admin ? 'Minden funkció elérhető.' : 'A visszaállítási ponthoz és a rendszermappákhoz emelt jog kell.'}</p></div></div>
        ${admin ? '' : `<button class="btn" id="twElev">${icon('shield-check')}Újraindítás rendszergazdaként</button>`}</div>
      <div class="card"><div class="card-head"><div class="tile-ic">${icon('rotate-ccw')}</div><div><h3>Visszaállítási pont</h3><p class="sub">A Windows saját biztonsági pontja; ha valami gond lenne, ide vissza lehet állni.</p></div></div>
        <button class="btn" id="twRp" ${admin ? '' : 'disabled'}>${icon('rotate-ccw')}Visszaállítási pont létrehozása</button></div>
    </div>
    <div class="card"><div class="card-head"><div class="tile-ic">${icon('package-x')}</div><div><h3>Előtelepített alkalmazások</h3><p class="sub">Csak az aktuális felhasználónál távolítja el őket; a Microsoft Store-ból bármikor visszatelepíthetők. Az Xbox-fiókhoz és a játékokhoz szükséges részeket szándékosan nem listázzuk.</p></div>
      <div class="right"><button class="btn sm" id="twDef" ${apps ? '' : 'disabled'}>Ajánlottak</button><button class="btn danger sm" id="twRm" ${S.appSel.size ? '' : 'disabled'}>${icon('trash-2', 'sm')}Eltávolítás (${S.appSel.size})</button></div></div>
      <div>${appRows}</div></div>
    <div class="card"><div class="card-head"><div class="tile-ic warn">${icon('cloud-off')}</div><div><h3>OneDrive eltávolítása</h3><p class="sub">Leállítja és eltávolítja a OneDrive-ot. A felhőben tárolt fájlok a fiókodban megmaradnak; a csak felhőben lévő („online”) fájlok helyben nem lesznek elérhetők.</p></div>
      <div class="right"><button class="btn danger" id="twOd">${icon('cloud-off')}Eltávolítás</button></div></div></div>`;
  const el = $('#twElev'); if (el) el.onclick = e => elevate(e.currentTarget);
  $('#twRp').onclick = e => busy(e.currentTarget, async () => { const r = await api('tweaks/restore_point', {}); toast(r.msg, r.ok ? 'ok' : 'err', 6000); });
  $('#twOd').onclick = async e => {
    if (!await dialog({ title: 'OneDrive eltávolítása', danger: true, ok: 'Eltávolítás', text: 'Biztosan eltávolítod a OneDrive-ot? Előtte érdemes ellenőrizni, hogy minden fontos fájl szinkronizálva van-e.' })) return;
    busy(e.currentTarget, async () => { const r = await api('tweaks/onedrive', {}); toast(r.msg, r.ok ? 'ok' : 'err', 7000); });
  };
  $$('[data-app]').forEach(cb => cb.onchange = () => { cb.checked ? S.appSel.add(cb.dataset.app) : S.appSel.delete(cb.dataset.app); renderTweaks(); });
  const def = $('#twDef'); if (def) def.onclick = () => { S.appSel = new Set(S.apps.filter(a => a.installed && a.default).map(a => a.id)); renderTweaks(); };
  $('#twRm').onclick = async e => {
    const names = S.apps.filter(a => S.appSel.has(a.id)).map(a => a.name);
    if (!await dialog({ title: `${names.length} alkalmazás eltávolítása`, danger: true, ok: 'Eltávolítás', text: esc(names.join(', ')) })) return;
    await busy(e.currentTarget, async () => {
      const r = await api('tweaks/apps/remove', { ids: [...S.appSel] });
      const ok = r.results.filter(x => x.status === 'removed').length, bad = r.results.filter(x => !x.ok);
      toast(`${ok} alkalmazás eltávolítva`, ok ? 'ok' : 'info');
      if (bad.length) toast(`Nem sikerült: ${bad.map(b => b.id).join(', ')}`, 'err', 7000);
      S.appSel.clear(); S.apps = (await api('tweaks/apps')).apps;
    });
    renderTweaks();
  };
  if (!apps) api('tweaks/apps').then(r => { S.apps = r.apps; if ($('#page-tweaks').classList.contains('active')) renderTweaks(); }).catch(err => toast(err.message, 'err'));
}

/* ── ÜTEMEZŐ ─────────────────────────────────────────────────────────────── */
function renderSchedule() {
  const s = S.schedule;
  const allowed = S.cats.filter(c => !['trash', 'custom'].includes(c.id) && !c.admin);
  const next = s.enabled && s.last_run ? new Date(new Date(s.last_run).getTime() + s.interval_hours * 3600e3) : null;
  $('#page-schedule').innerHTML = `
    ${head('Ütemező', 'Automatikus háttértisztítás, amíg a PyCleaner fut.')}
    <div class="card">
      <div class="setting"><div><div class="t">Automatikus tisztítás</div><div class="d">${s.enabled ? `Utoljára: ${esc(s.last_run ? s.last_run.replace('T', ' ') : 'még nem futott')}${next ? ` · következő: ${esc(next.toLocaleString('hu-HU'))}` : ''}` : 'Kikapcsolva'}</div></div><input type="checkbox" class="switch" id="scOn" ${s.enabled ? 'checked' : ''}></div>
      <div class="setting"><div><div class="t">Gyakoriság</div><div class="d">Ennyi időnként fut le, ha a program nyitva van.</div></div>
        <select id="scInt">${[[6, '6 óránként'], [12, '12 óránként'], [24, 'naponta'], [72, '3 naponta'], [168, 'hetente']].map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></div>
      <div class="setting" style="align-items:start"><div><div class="t">Kategóriák</div><div class="d">Az ütemező csak biztonságos, nem végleges kategóriákat takaríthat.</div></div>
        <div style="display:grid;gap:10px">${allowed.map(c => `<label class="row" style="gap:10px;flex-wrap:nowrap"><input type="checkbox" class="check" data-sc="${c.id}" ${s.categories.includes(c.id) ? 'checked' : ''}>${esc(c.label)}</label>`).join('')}</div></div>
    </div>
    <div class="banner" style="margin-top:14px">${icon('info', 'lg')}<div class="grow"><b>Tipp</b><span>A PyCleaner bezárásakor az ütemező is leáll. Ha rendszeres takarítást szeretnél, indítsd el a programot bejelentkezéskor (Win+R → <span class="mono">shell:startup</span>, ide egy parancsikon).</span></div></div>`;
  $('#scInt').value = String(s.interval_hours);
  const save = async () => {
    S.schedule = await api('schedule', { enabled: $('#scOn').checked, interval_hours: Number($('#scInt').value),
      categories: $$('[data-sc]').filter(x => x.checked).map(x => x.dataset.sc) });
    sideState(); renderSchedule(); toast('Ütemezés mentve', 'ok', 2000);
  };
  $('#scOn').onchange = save; $('#scInt').onchange = save; $$('[data-sc]').forEach(x => x.onchange = save);
}

/* ── ELŐZMÉNYEK + MENTÉSEK ───────────────────────────────────────────────── */
async function renderHistory() {
  const tab = S.histTab;
  $('#page-history').innerHTML = `
    ${head('Előzmények', 'A korábbi tisztítások és a törlés előtt készült mentések.',
      `<a class="btn" href="${dl('export/html')}" download>${icon('file-text')}HTML-riport</a><a class="btn" href="${dl('export/json')}" download>${icon('download')}JSON</a>`)}
    <div class="tabs"><button data-htab="history" class="${tab === 'history' ? 'on' : ''}">Tisztítások</button><button data-htab="backups" class="${tab === 'backups' ? 'on' : ''}">Mentések</button></div>
    <div id="histBody"><div class="card"><div class="skeleton"></div></div></div>`;
  $$('[data-htab]').forEach(b => b.onclick = () => { S.histTab = b.dataset.htab; renderHistory(); });
  try { tab === 'history' ? await drawHistory() : await drawBackups(); } catch (e) { toast(e.message, 'err'); }
}
async function drawHistory() {
  const h = await api('history');
  const total = h.reduce((a, e) => a + (e.total_freed_bytes || 0), 0);
  const files = h.reduce((a, e) => a + (e.total_files || 0), 0);
  const label = id => S.cats.find(c => c.id === id)?.label || id;
  $('#histBody').innerHTML = `
    <div class="grid g3" style="margin-bottom:14px">
      <div class="card stat"><span class="k">Összesen felszabadítva</span><span class="v num">${esc(fmtB(total))}</span></div>
      <div class="card stat"><span class="k">Tisztítások</span><span class="v num">${fmtNum(h.length)}</span></div>
      <div class="card stat"><span class="k">Törölt fájlok</span><span class="v num">${fmtNum(files)}</span></div>
    </div>
    <div class="card">${h.length ? `<div class="card-head"><h3>Napló</h3><div class="right"><button class="btn ghost sm" id="hClr">${icon('trash', 'sm')}Előzmények törlése</button></div></div>
      <div class="table-wrap"><table class="tbl"><thead><tr><th>Időpont</th><th>Kategóriák</th><th class="r">Felszabadítva</th><th class="r">Fájl</th><th>Mód</th></tr></thead><tbody>
      ${h.map(e => `<tr><td class="num w">${esc(e.timestamp)}</td><td class="muted">${esc((e.categories || []).map(label).join(', '))}</td><td class="r num"><b>${esc(e.total_freed)}</b></td><td class="r num">${fmtNum(e.total_files)}</td><td class="w"><span class="chip ${e.auto ? 'ac' : ''}">${e.auto ? 'Ütemezett' : 'Kézi'}</span></td></tr>`).join('')}
      </tbody></table></div>` : `<div class="empty"><div class="tile-ic">${icon('history', 'lg')}</div><b>Még nincs előzmény</b>Az első tisztítás után itt jelenik meg.</div>`}</div>`;
  const c = $('#hClr');
  if (c) c.onclick = async () => { if (await dialog({ title: 'Előzmények törlése', text: 'Az összes korábbi tisztítás naplója törlődik.', ok: 'Törlés', danger: true })) { await api('history/clear', {}); S.lastClean = null; renderHistory(); } };
}
async function drawBackups() {
  const r = await api('backups');
  const prof = S.config.profiles[S.config.active_profile];
  $('#histBody').innerHTML = `<div class="card">
    <div class="card-head"><div class="tile-ic">${icon('archive')}</div><div><h3>Törlés előtti mentések</h3><p class="sub">${prof.auto_backup ? `Bekapcsolva · legfeljebb ${prof.backup_max_mb} MB / mentés, az utolsó ${prof.backup_keep} marad meg` : 'Kikapcsolva — a Beállításokban kapcsolható be'}</p></div>
      <div class="right"><button class="btn sm" id="bkOpen">${icon('folder-open', 'sm')}Mappa megnyitása</button></div></div>
    ${r.backups.length ? r.backups.map(b => `<div class="list-item">${icon('archive')}<div><div class="t mono">${esc(b.name)}</div><div class="d">${esc(b.date)} · ${esc(fmtB(b.size))}</div></div>
      <div class="row"><a class="btn sm" href="${dl('backups/file/' + encodeURIComponent(b.name))}" download>${icon('download', 'sm')}Letöltés</a><button class="icon-btn danger" data-bkdel="${esc(b.name)}" title="Törlés">${icon('trash-2')}</button></div></div>`).join('')
      : '<div class="empty"><b>Nincs mentés</b>Bekapcsolt mentésnél minden tisztítás előtt egy ZIP készül a törlendő fájlokból.</div>'}</div>`;
  $('#bkOpen').onclick = () => api('backups/open', {});
  $$('[data-bkdel]').forEach(b => b.onclick = async () => { await api('backups/delete', { name: b.dataset.bkdel }); drawBackups(); });
}

/* ── BEÁLLÍTÁSOK ─────────────────────────────────────────────────────────── */
const ACCENTS = ['#2bb8e8', '#4f8cff', '#8b6cff', '#3ccf8a', '#ff8a3d', '#f2557a'];
function renderSettings() {
  const cfg = S.config, pid = cfg.active_profile, prof = cfg.profiles[pid];
  const profiles = Object.entries(cfg.profiles);
  const u = S.update;
  $('#page-settings').innerHTML = `
    ${head('Beállítások', 'Megjelenés, profilok, mentések és frissítések.')}
    <div class="card"><h3>Megjelenés</h3><p class="sub">A kiemelőszín profilonként tárolódik.</p>
      <div class="setting"><div class="t">Téma</div><div class="seg" id="stTheme">${[['system', 'Rendszer', 'monitor-x'], ['dark', 'Sötét', 'moon'], ['light', 'Világos', 'sun']].map(([v, l]) => `<button data-v="${v}" class="${cfg.theme === v ? 'on' : ''}">${l}</button>`).join('')}</div></div>
      <div class="setting"><div class="t">Kiemelőszín</div><div class="swatches">${ACCENTS.map(a => `<button data-ac="${a}" class="${prof.accent === a ? 'on' : ''}" style="background:${a}" title="${a}"></button>`).join('')}</div></div>
    </div>
    <div class="card"><div class="card-head"><div><h3>Profil: ${esc(prof.name)}</h3><p class="sub">Külön profil tartozhat például a saját és a családi géphez, saját mappákkal.</p></div>
      <div class="right"><select id="stProf">${profiles.map(([id, p]) => `<option value="${esc(id)}" ${id === pid ? 'selected' : ''}>${esc(p.name)}${p.has_password ? ' 🔒' : ''}</option>`).join('')}</select>
      <button class="btn sm" id="stNew">${icon('user', 'sm')}Új profil</button>${pid !== 'default' ? `<button class="btn danger sm" id="stDel">${icon('trash-2', 'sm')}</button>` : ''}</div></div>
      <div class="setting"><div><div class="t">Profil neve</div></div><input type="text" id="stName" value="${esc(prof.name)}" maxlength="40" style="width:260px"></div>
      <div class="setting"><div><div class="t">Profiljelszó</div><div class="d">${prof.has_password ? 'Be van állítva. Üresen mentve törlődik.' : 'Váltáskor kéri. Csak a profilváltást védi, nem titkosít.'}</div></div>
        <div class="row"><input type="password" id="stPw" placeholder="${prof.has_password ? 'új jelszó' : 'nincs jelszó'}" style="width:180px" autocomplete="new-password"><button class="btn sm" id="stPwSave">Mentés</button></div></div>
      <div class="setting"><div><div class="t">Mentés törlés előtt</div><div class="d">Tisztítás előtt ZIP-be menti a törlendő fájlokat. Gyorsítótáraknál ritkán kell, de biztonságot ad.</div></div><input type="checkbox" class="switch" id="stBk" ${prof.auto_backup ? 'checked' : ''}></div>
      <div class="setting"><div><div class="t">Mentés mérete és száma</div><div class="d">Ennél nagyobb mentés nem készül; a régebbiek automatikusan törlődnek.</div></div>
        <div class="row"><input type="number" id="stBkMb" value="${prof.backup_max_mb}" min="10" max="10000" style="width:96px"><span class="muted">MB, utolsó</span><input type="number" id="stBkKeep" value="${prof.backup_keep}" min="1" max="100" style="width:72px"><span class="muted">db</span></div></div>
      <div class="setting" style="align-items:start"><div><div class="t">Egyéni mappák</div><div class="d">Ezek teljes tartalmát üríti az „Egyéni mappák” kategória. Rendszer- és személyes mappát nem fogad el.</div></div>
        <div style="min-width:min(420px,100%)"><div class="tags">${prof.custom_dirs.map((d, i) => `<span class="tag">${esc(d)}<button data-rmdir="${i}" title="Eltávolítás">${icon('x', 'sm')}</button></span>`).join('') || '<span class="faint">Nincs megadva</span>'}</div>
          <div class="row">${pathPicker('stDir', '')}<button class="btn" id="stDirAdd">Hozzáadás</button></div></div></div>
    </div>
    <div class="card"><div class="card-head"><div class="tile-ic">${icon('download')}</div><div><h3>Frissítések</h3><p class="sub">${u ? (u.ok ? (u.newer ? `Új verzió érhető el: ${esc(u.latest)}` : `A legfrissebb verziót használod (${esc(u.current)}).`) : 'A legutóbbi ellenőrzés nem sikerült (nincs internet?).') : `Telepített verzió: ${esc(S.boot.version)}`}</p></div>
      <div class="right">${u?.newer ? '<button class="btn primary sm" data-open-release>Letöltés</button>' : ''}<button class="btn sm" id="stUpd">${icon('refresh-cw', 'sm')}Ellenőrzés</button></div></div>
      <div class="setting"><div><div class="t">Indításkor ellenőrizze</div><div class="d">Csak a GitHubon közzétett legújabb verziószámot kérdezi le, adatot nem küld.</div></div><input type="checkbox" class="switch" id="stUpdAuto" ${cfg.check_updates ? 'checked' : ''}></div>
    </div>
    <div class="card"><div class="card-head"><img src="/static/logo.svg" width="38" height="38" alt=""><div><h3>PyCleaner ${esc(S.boot.version)}</h3><p class="sub">Nyílt forráskódú (MIT) · <a href="#" data-open-release>GitHub</a></p></div></div>
      <dl class="kv"><dt>Adatok helye</dt><dd class="mono" title="${esc(S.boot.data_dir)}">${esc(S.boot.data_dir)}</dd><dt>Python</dt><dd>${esc(S.boot.system.python)}</dd><dt>Ablak</dt><dd>${S.boot.native ? 'natív (WebView2)' : 'böngésző'}</dd></dl></div>`;

  const saveProf = async (changes, msg = 'Mentve') => { S.config = await api('config/profile', changes); applyTheme(); sideState(); renderSettings(); toast(msg, 'ok', 1800); };
  $$('#stTheme button').forEach(b => b.onclick = async () => { S.config = await api('config/option', { key: 'theme', value: b.dataset.v }); applyTheme(); renderSettings(); });
  $$('[data-ac]').forEach(b => b.onclick = () => saveProf({ accent: b.dataset.ac }, 'Kiemelőszín mentve'));
  $('#stName').onchange = e => saveProf({ name: e.target.value });
  $('#stPwSave').onclick = () => saveProf({ password: $('#stPw').value }, $('#stPw').value ? 'Jelszó beállítva' : 'Jelszó törölve');
  $('#stBk').onchange = e => saveProf({ auto_backup: e.target.checked });
  $('#stBkMb').onchange = e => saveProf({ backup_max_mb: Number(e.target.value) });
  $('#stBkKeep').onchange = e => saveProf({ backup_keep: Number(e.target.value) });
  $$('[data-rmdir]').forEach(b => b.onclick = () => { const d = [...prof.custom_dirs]; d.splice(Number(b.dataset.rmdir), 1); saveProf({ custom_dirs: d }); });
  $('#stDirAdd').onclick = async () => {
    const r = await api('config/validate_dir', { path: $('#stDir').value });
    if (!r.ok) return toast(r.msg, 'err');
    await saveProf({ custom_dirs: [...prof.custom_dirs, r.path] }, 'Mappa hozzáadva');
    refreshCats();
  };
  $('#stProf').onchange = e => switchProfile(e.target.value);
  $('#stNew').onclick = async () => {
    const name = await dialog({ title: 'Új profil', text: 'Add meg az új profil nevét.', ok: 'Létrehozás', input: { placeholder: 'pl. Családi gép' } });
    if (name) { S.config = await api('config/profile/new', { name }); applyTheme(); sideState(); renderSettings(); refreshCats(); }
  };
  const del = $('#stDel');
  if (del) del.onclick = async () => {
    if (!await dialog({ title: 'Profil törlése', text: `Törlöd a(z) „${esc(prof.name)}” profilt?`, ok: 'Törlés', danger: true })) return;
    const r = await api('config/profile/delete', { id: pid }); S.config = r.config; applyTheme(); sideState(); renderSettings(); refreshCats();
  };
  $('#stUpd').onclick = e => busy(e.currentTarget, async () => { S.update = await api('update'); sideState(); renderSettings(); });
  $('#stUpdAuto').onchange = async e => { S.config = await api('config/option', { key: 'check_updates', value: e.target.checked }); };
}

async function switchProfile(id) {
  const p = S.config.profiles[id];
  let password = '';
  if (p.has_password) {
    password = await dialog({ title: `Profil: ${p.name}`, text: 'Ez a profil jelszóval védett.', ok: 'Váltás', input: { type: 'password', placeholder: 'Jelszó' } });
    if (password === null) { if ($('#stProf')) $('#stProf').value = S.config.active_profile; return; }
  }
  const r = await api('config/profile/switch', { id, password });
  if (!r.ok) { toast('Hibás jelszó', 'err'); if ($('#stProf')) $('#stProf').value = S.config.active_profile; return; }
  S.config = r.config; applyTheme(); sideState(); refreshCats();
  toast(`Aktív profil: ${p.name}`, 'ok', 2000);
  if ($('#page-settings').classList.contains('active')) renderSettings();
}
$('#profileBtn').addEventListener('click', async () => {
  const ids = Object.keys(S.config.profiles);
  if (ids.length < 2) return go('settings');
  const next = ids[(ids.indexOf(S.config.active_profile) + 1) % ids.length];
  switchProfile(next);
});
async function refreshCats() {
  S.cats = (await api('bootstrap')).categories;
  S.selected = new Set([...S.selected].filter(id => S.cats.some(c => c.id === id && !c.locked)));
}

/* ── kilépés ─────────────────────────────────────────────────────────────── */
function showGoodbye() { $('#goodbye').hidden = false; }
$('#exitBtn').addEventListener('click', async () => {
  if (!await dialog({ title: 'Kilépés', text: 'Leállítod a PyCleanert? Az ütemező is leáll.', ok: 'Kilépés' })) return;
  try { await api('exit', {}); } catch { /* a szerver már leállhatott */ }
  showGoodbye();
});

/* ── indulás ─────────────────────────────────────────────────────────────── */
(async function init() {
  try {
    S.boot = await api('bootstrap');
  } catch (e) {
    document.body.innerHTML = `<div class="goodbye"><h2>Nem érem el a PyCleaner szolgáltatást</h2><p>${esc(e.message)}</p></div>`;
    return;
  }
  S.cats = S.boot.categories; S.config = S.boot.config; S.schedule = S.boot.schedule;
  S.selected = new Set(S.cats.filter(c => c.default && !c.locked).map(c => c.id));
  applyTheme(); sideState();
  api('history').then(h => { S.lastClean = h[0] || null; if ($('#page-overview').classList.contains('active')) renderOverview(); }).catch(() => {});
  go(location.hash.slice(1) || 'overview');
  startMonitor();
  if (S.config.check_updates) api('update').then(u => { S.update = u; sideState(); if ($('#page-overview').classList.contains('active')) renderOverview(); }).catch(() => {});
})();
