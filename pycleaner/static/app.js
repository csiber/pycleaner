/* PyCleaner 5 — felület. Keretrendszer nélkül; minden dinamikus szöveg esc()-en megy át,
   minden felirat t()-n (magyar forrásszöveg → angol fordítás az i18n-en.json-ből). */
'use strict';

const TOKEN = document.querySelector('meta[name="pyc-token"]').content;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
/* jobbról levágott útvonal (direction:rtl) — az LRM jelek tartják a helyén a perjeleket */
const ltr = v => `\u200e${esc(v)}\u200e`;
const icon = (n, cls = '') => `<svg class="ic ${cls}" aria-hidden="true"><use href="/static/icons.svg#i-${n}"/></svg>`;

/* ── nyelv ───────────────────────────────────────────────────────────────── */
const L = { lang: 'hu', en: {} };
function t(s, v) {
  let o = (L.lang === 'en' && L.en[s]) || s;
  if (v) o = o.replace(/\{(\w+)\}/g, (m, k) => (v[k] ?? m));
  return o;
}
const tt = (s, v) => esc(t(s, v));            /* fordítás + escape HTML-be */
const LOC = () => (L.lang === 'en' ? 'en-GB' : 'hu-HU');
const DEC = () => (L.lang === 'en' ? '.' : ',');

function fmtB(n) {
  n = Number(n) || 0;
  if (n < 1024) return `${Math.round(n)} B`;
  const u = ['KB', 'MB', 'GB', 'TB'];
  let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return `${n.toFixed(n >= 100 || i === 0 ? 0 : 1).replace('.', DEC())} ${u[i]}`;
}
const pct = v => String(Math.round((Number(v) || 0) * 10) / 10).replace('.', DEC());
const fmtNum = n => (Number(n) || 0).toLocaleString(LOC());
const fmtDate = ts => new Date(ts * 1000).toLocaleDateString(LOC(), { year: 'numeric', month: 'short', day: 'numeric' });
const fmtDT = iso => (iso ? new Date(iso).toLocaleString(LOC(), { dateStyle: 'medium', timeStyle: 'short' }) : '—');

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
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* gomb „dolgozik” állapottal */
async function busy(btn, fn) {
  if (btn) { btn.classList.add('busy'); btn.disabled = true; }
  try { return await fn(); }
  catch (e) { toast(e.message || String(e), 'err'); }
  finally { if (btn) { btn.classList.remove('busy'); btn.disabled = false; } }
}

/* háttérmunka követése: onTick(job) minden lekérdezésnél */
async function pollJob(id, onTick) {
  for (;;) {
    const j = await api(`jobs/${id}`);
    onTick && onTick(j);
    if (j.status !== 'running') return j;
    await sleep(1000);
  }
}

function toast(msg, type = 'info', ms = 4200) {
  const ic = { ok: 'circle-check', err: 'triangle-alert', warn: 'triangle-alert', info: 'info' }[type] || 'info';
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `${icon(ic)}<div>${esc(msg)}</div>`;
  $('#toasts').append(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 250); }, ms);
}

/* párbeszédablak: confirm / prompt. A text HTML — a hívó escape-eli. */
function dialog({ title, text = '', ok, cancel, danger = false, input = null }) {
  const d = $('#dlg');
  ok = ok || t('Rendben');
  cancel = cancel === undefined ? t('Mégse') : cancel;
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
  boot: null, cats: [], scan: null, browsers: [], selected: new Set(), lastClean: null, lastResult: null,
  mon: { cpu: [], ram: [], last: null }, config: null, schedule: null, update: null, task: null,
  large: null, dupes: null, dupSel: new Set(), largeSel: new Set(), reg: null, regSel: new Set(),
  apps: null, appSel: new Set(), histTab: 'history', diskTab: 'folders', folders: null,
  startup: null, upd: null, updSel: new Set(), updJob: null, progs: null, progQ: '', progSort: 'name',
  uninst: null, health: null, healthJob: null,
};
/* a gyári profil neve tárolt adat — megjelenítéskor fordítjuk */
const profName = p => (p.name === 'Alapértelmezett' ? t('Alapértelmezett') : p.name);
const isActive = page => $(`#page-${page}`).classList.contains('active');

/* ── navigáció ───────────────────────────────────────────────────────────── */
const PAGES = {
  overview: renderOverview, cleaner: renderCleaner, monitor: renderMonitor, disk: renderDisk, dupes: renderDupes,
  health: renderHealth, startup: renderStartup, updates: renderUpdates, programs: renderPrograms,
  registry: renderRegistry, tweaks: renderTweaks, schedule: renderSchedule, history: renderHistory, settings: renderSettings,
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
document.addEventListener('click', e => { const g = e.target.closest('[data-go]'); if (g) { e.preventDefault(); go(g.dataset.go); } });

const head = (title, sub, actions = '') =>
  `<div class="head"><div><h1>${esc(title)}</h1>${sub ? `<p>${esc(sub)}</p>` : ''}</div>${actions ? `<div class="actions">${actions}</div>` : ''}</div>`;
const empty = (ic, title, text, cls = '') =>
  `<div class="empty"><div class="tile-ic ${cls}">${icon(ic, 'lg')}</div><b>${esc(title)}</b>${esc(text)}</div>`;
const winOnly = () => (S.boot.system.is_windows ? '' : `<div class="card">${empty('info', t('Csak Windowson'), t('Ez a funkció Windows 10/11 alatt érhető el.'))}</div>`);

/* a statikus feliratok (navigáció stb.) fordítása */
function translateStatic() {
  $$('[data-i18n]').forEach(el => {
    if (!el.dataset.hu) el.dataset.hu = el.textContent.trim();
    el.textContent = t(el.dataset.hu);
  });
  document.documentElement.lang = L.lang;
  $('#profileBtn').title = t('Profil váltása');
  $('#themeBtn').title = t('Téma váltása');
  $('#exitBtn').title = t('Kilépés');
}
async function setLanguage(code) {
  L.lang = code === 'en' ? 'en' : 'hu';
  if (L.lang === 'en' && !Object.keys(L.en).length) {
    try { L.en = await (await fetch('/static/i18n-en.json')).json(); } catch { L.en = {}; }
  }
  translateStatic();
}

/* ── téma és kiemelőszín ─────────────────────────────────────────────────── */
const mqLight = matchMedia('(prefers-color-scheme: light)');
function applyTheme() {
  const th = S.config?.theme || 'system';
  const root = document.documentElement;
  root.dataset.theme = th;
  root.classList.toggle('prefers-light', th === 'system' && mqLight.matches);
  const isLight = th === 'light' || (th === 'system' && mqLight.matches);
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
  toast({ system: t('Téma: a rendszert követi'), dark: t('Téma: sötét'), light: t('Téma: világos') }[next]);
  if (isActive('settings')) renderSettings();
});

function sideState() {
  const prof = S.config.profiles[S.config.active_profile];
  $('#profileName').textContent = profName(prof);
  const admin = S.boot.system.is_admin;
  const chip = $('#adminChip');
  chip.className = `chip ${admin ? 'ok' : ''}`;
  chip.textContent = S.boot.system.is_windows ? (admin ? t('Rendszergazda') : t('Normál jog')) : S.boot.system.os.split(' ')[0];
  chip.title = admin ? t('Rendszergazdai jogokkal fut') : t('Normál felhasználói jogokkal fut');
  $$('.win-only').forEach(el => { el.hidden = !S.boot.system.is_windows; });
  $('#pillSched').textContent = S.schedule?.enabled ? t('BE') : '';
  $('#pillUpdate').hidden = !S.update?.newer;
  $('#pillUpd').textContent = S.upd?.packages?.length ? S.upd.packages.length : '';
  $('#pillHealth').textContent = S.health ? S.health.score : '';
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
    if (isActive('overview')) updateOverviewLive();
    if (isActive('monitor')) updateMonitor();
  };
}
const level = p => (p >= 90 ? 'bad' : p >= 75 ? 'warn' : '');
const driveLabel = () => (S.boot.system.is_windows ? t('{d} meghajtó', { d: S.boot.system.drive.replace(/\\$/, '') }) : t('Rendszerkötet (/)'));

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
  const upd = S.update?.newer ? `<div class="banner">${icon('download', 'lg')}<div class="grow"><b>${tt('Elérhető a PyCleaner {v}', { v: S.update.latest })}</b><span>${tt('Jelenleg a {v} verziót használod.', { v: S.update.current })}</span></div><button class="btn primary sm" data-open-release>${tt('Letöltés')}</button></div>` : '';
  const adminNote = sys.is_windows && !sys.is_admin ? `<div class="banner warn">${icon('shield-alert', 'lg')}<div class="grow"><b>${tt('Normál jogokkal fut')}</b><span>${tt('A Windows Update gyorsítótár, a rendszernaplók és néhány registry-elem csak rendszergazdaként tisztítható.')}</span></div><button class="btn sm" id="ovElevate">${icon('shield-check', 'sm')}${tt('Újraindítás rendszergazdaként')}</button></div>` : '';
  const H = S.health;
  const healthCard = sys.is_windows ? `
      <div class="card">
        <div class="card-head"><div class="tile-ic ${H ? (H.score >= 85 ? 'ok' : H.score >= 60 ? 'warn' : 'bad') : ''}">${icon('heart-pulse')}</div><div><h3>${tt('Gépállapot')}</h3><p class="sub">${H ? tt('{n} pont a 100-ból', { n: H.score }) : tt('Lemezek, védelem, frissítések, akkumulátor egy felmérésben')}</p></div>
        <div class="right"><button class="btn ghost sm" data-go="health">${tt(H ? 'Részletek' : 'Felmérés')}</button></div></div>
        ${H ? `<div class="result-list">${H.findings.filter(f => f.level === 'bad' || f.level === 'warn').slice(0, 3).map(f => `<div><span>${esc(f.title)}</span><span class="chip ${f.level}">${tt(f.level === 'bad' ? 'Sürgős' : 'Figyelem')}</span></div>`).join('') || `<div><span>${tt('Minden rendben.')}</span><span class="chip ok">${tt('Rendben')}</span></div>`}</div>` : `<p class="muted" style="margin:0">${tt('Egy perc alatt átnézi a gép állapotát, és javaslatokat ad.')}</p>`}
      </div>` : '';
  $('#page-overview').innerHTML = `
    ${head(t('Áttekintés'), sys.os)}
    ${upd}${adminNote}
    <div class="card hero">
      <div>
        <div class="label">${tt(S.scan ? 'Felszabadítható a kijelölt kategóriákban' : 'A gép még nincs átvizsgálva')}</div>
        <div class="big num">${S.scan ? esc(fmtB(rec)).replace(/ (\S+)$/, ' <small>$1</small>') : '—'}</div>
        <div class="muted">${disk.free_fmt ? tt('{d}: {f} szabad / {t}', { d: driveLabel(), f: fmtB(disk.free), t: fmtB(disk.total) }) : ''}</div>
        <div class="capbar"><i class="used" style="width:${usedW.toFixed(2)}%"></i><i class="rec" style="width:${recW.toFixed(2)}%"></i></div>
        <div class="legend"><span><i class="used"></i>${tt('Foglalt')}</span><span><i class="rec"></i>${tt('Felszabadítható')}</span><span><i class="free"></i>${tt('Szabad')}</span></div>
      </div>
      <div class="cta">
        <button class="btn primary lg" id="ovScan">${icon('search')}${tt(S.scan ? 'Újravizsgálás' : 'Gép átvizsgálása')}</button>
        <button class="btn lg" id="ovClean" ${S.scan && rec ? '' : 'disabled'}>${icon('sparkles')}${tt('Gyors tisztítás')}</button>
        <button class="btn ghost sm" data-go="cleaner">${tt('Részletes tisztítás')} ${icon('play', 'sm')}</button>
      </div>
    </div>
    <div class="grid g4">
      <div class="card stat"><span class="k">${tt('Processzor')}</span><span class="v num" id="ovCpu">—</span><div class="meter"><i id="ovCpuM" style="width:0"></i></div></div>
      <div class="card stat"><span class="k">${tt('Memória')}</span><span class="v num" id="ovRam">—</span><div class="meter"><i id="ovRamM" style="width:0"></i></div></div>
      <div class="card stat"><span class="k">${esc(driveLabel())}</span><span class="v num">${disk.used_pct != null ? pct(disk.used_pct) : '—'}<small>%</small></span><div class="meter"><i class="${level(disk.used_pct)}" style="width:${disk.used_pct || 0}%"></i></div></div>
      <div class="card stat"><span class="k">${tt('Hálózat ↓ / ↑')}</span><span class="v num" id="ovNet" style="font-size:16px">—</span><div class="faint" style="font-size:12px;margin-top:8px" id="ovNetT">&nbsp;</div></div>
    </div>
    <div class="grid ${sys.is_windows ? 'g3' : 'g2'}">
      ${healthCard}
      <div class="card">
        <div class="card-head"><div class="tile-ic ok">${icon('history')}</div><div><h3>${tt('Legutóbbi tisztítás')}</h3><p class="sub">${last ? esc(last.timestamp) + (last.auto ? ' · ' + tt('ütemezett') : '') : tt('Még nem volt tisztítás')}</p></div>
        <div class="right"><button class="btn ghost sm" data-go="history">${tt('Előzmények')}</button></div></div>
        ${last ? `<div class="stat"><span class="v num">${esc(last.total_freed)}</span><span class="k">${tt('{n} fájl törölve', { n: fmtNum(last.total_files) })}${last.total_errors ? ', ' + tt('{n} zárolt fájl kimaradt', { n: fmtNum(last.total_errors) }) : ''}</span></div>` : `<p class="muted" style="margin:0">${tt('Vizsgáld át a gépet, majd indíts egy tisztítást.')}</p>`}
      </div>
      <div class="card">
        <div class="card-head"><div class="tile-ic">${icon('cpu')}</div><div><h3>${tt('Rendszer')}</h3><p class="sub">${esc(sys.processor)}</p></div></div>
        <dl class="kv">
          <dt>${tt('Memória')}</dt><dd>${esc(sys.ram_total || '—')}</dd>
          <dt>${tt('Processzormagok')}</dt><dd>${tt('{p} fizikai / {l} logikai', { p: sys.cpu_physical ?? '—', l: sys.cpu_count ?? '—' })}</dd>
          <dt>${tt('Utolsó indítás')}</dt><dd>${esc(sys.boot_time || '—')}</dd>
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
  $('#ovNetT').textContent = t('Összesen: {d} le, {u} fel', { d: d.net_recv_total, u: d.net_sent_total });
}

/* ── TISZTÍTÁS ───────────────────────────────────────────────────────────── */
async function doScan() {
  const r = await api('scan', {});
  S.scan = r.results; S.browsers = r.browsers; S.cats = r.categories;
  const tot = scanTotal(true);
  $('#pillClean').textContent = tot ? fmtB(tot) : '';
  return r;
}

function renderCleaner() {
  const rows = S.cats.map(c => {
    const r = S.scan?.[c.id];
    const on = S.selected.has(c.id) && !c.locked;
    const size = r ? (r.size ? `<b>${esc(fmtB(r.size))}</b><span>${tt('{n} fájl', { n: fmtNum(r.files) })}</span>` : `<b class="zero">0 B</b><span>${tt('tiszta')}</span>`) : '<b class="zero">—</b><span>&nbsp;</span>';
    const badges = (c.admin ? `<span class="chip ${c.locked ? 'warn' : ''}">${icon('shield-check', 'sm')}${tt('Rendszergazda')}</span>` : '')
      + (c.id === 'browser' && S.browsers.length ? `<span class="chip warn">${tt('Fut: {b}', { b: S.browsers.join(', ') })}</span>` : '');
    const tip = c.paths.length ? esc(c.paths.join('\n')) : tt('Nincs ilyen mappa ezen a gépen');
    return `<label class="cat ${on ? 'on' : ''} ${c.locked ? 'locked' : ''}" title="${tip}">
      <input type="checkbox" class="check" data-cat="${esc(c.id)}" ${on ? 'checked' : ''} ${c.locked ? 'disabled' : ''}>
      <div class="tile-ic ${c.caution ? 'warn' : ''}">${icon(c.icon)}</div>
      <div><div class="t">${esc(c.label)}${badges}</div><div class="d">${esc(c.desc)}</div>
        ${c.caution ? `<div class="c">${esc(c.caution)}</div>` : ''}
        ${c.id === 'browser' && S.browsers.length ? `<div class="c">${tt('A futó böngészők zárolt fájljai kimaradnak — a teljes tisztításhoz zárd be őket.')}</div>` : ''}
        ${c.id === 'custom' && !c.paths.length ? `<div class="d"><a href="#settings" data-go="settings">${tt('Mappák megadása a Beállításokban')}</a></div>` : ''}
        ${c.locked ? `<div class="c">${tt('Ehhez indítsd újra a PyCleanert rendszergazdaként.')}</div>` : ''}
      </div>
      <div class="size">${size}</div></label>`;
  }).join('');
  const res = S.lastResult;
  $('#page-cleaner').innerHTML = `
    ${head(t('Tisztítás'), t('Jelöld ki, mit takarítson a PyCleaner. A méretek a beolvasás után pontosak — csak azt számolja, amit ténylegesen törölne.'),
      `<button class="btn ghost" id="clAll">${tt('Mind')}</button><button class="btn ghost" id="clNone">${tt('Egyik sem')}</button>`)}
    ${res ? `<div class="card" style="margin-bottom:14px"><div class="card-head"><div class="tile-ic ok">${icon('circle-check')}</div><div><h3>${tt('Kész: {s} felszabadítva', { s: res.total_freed })}</h3><p class="sub">${tt('{n} fájl törölve {s} mp alatt', { n: fmtNum(res.total_files), s: res.duration_s })}${res.total_errors ? ' · ' + tt('{n} használatban lévő fájl kimaradt', { n: fmtNum(res.total_errors) }) : ''}${res.backup ? ' · ' + tt('mentés készült') : ''}</p></div><div class="right"><button class="icon-btn" id="resClose" title="${tt('Bezárás')}">${icon('x')}</button></div></div>
      <div class="result-list">${res.details.map(d => `<div><span>${esc(d.category)}</span><span class="num">${esc(d.freed)} · ${tt('{n} fájl', { n: fmtNum(d.files) })}</span></div>`).join('')}</div>
      ${res.skipped_admin?.length ? `<p class="c" style="color:var(--warn);margin:10px 0 0">${tt('Rendszergazdai jog hiányában kimaradt: {l}', { l: res.skipped_admin.join(', ') })}</p>` : ''}</div>` : ''}
    <div class="cats">${rows}</div>
    <div class="dock">
      <div class="sum"><b class="num">${S.scan ? esc(fmtB(scanTotal(true))) : '—'}</b><span>${tt('{n} kategória kijelölve', { n: S.selected.size })}</span></div>
      <label class="row" style="gap:8px"><span class="muted">${tt('Csak a régebbiek, mint')}</span>
        <select id="clAge"><option value="0">${tt('bármilyen kor')}</option><option value="1">${tt('1 nap')}</option><option value="7">${tt('1 hét')}</option><option value="30">${tt('1 hónap')}</option></select></label>
      <button class="btn" id="clScan">${icon('search')}${tt(S.scan ? 'Újraolvasás' : 'Beolvasás')}</button>
      <button class="btn primary" id="clGo" ${S.selected.size ? '' : 'disabled'}>${icon('sparkles')}${tt('Tisztítás')}</button>
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
  if (risky.length && !await dialog({ title: t('Végleges törlés'), danger: true, ok: t('Törlés'),
    text: tt('A kijelöltek között ez is szerepel: {l}. Ezek a fájlok nem kerülnek a Lomtárba, nem állíthatók vissza.', { l: risky.join(', ') }) })) return;
  await busy(btn, async () => {
    const r = await api('clean', { categories: ids, min_age_days: quick ? 0 : Number(S.minAge || 0) });
    S.lastResult = r; S.lastClean = r;
    toast(t('Kész: {s} felszabadítva ({n} fájl)', { s: r.total_freed, n: fmtNum(r.total_files) }), 'ok');
    await doScan();
  });
  if (isActive('cleaner')) renderCleaner(); else renderOverview();
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
    ${head(t('Élő monitor'), t('Másfél másodpercenként frissülő terhelés és a legtöbb memóriát használó folyamatok.'))}
    <div class="grid g2">
      <div class="card"><div class="card-head"><div class="tile-ic">${icon('cpu')}</div><div><h3>${tt('Processzor')}</h3><p class="sub" id="mCpuSub">—</p></div><div class="right"><span class="stat"><span class="v num" id="mCpu">—</span></span></div></div><div id="mCpuG"></div></div>
      <div class="card"><div class="card-head"><div class="tile-ic">${icon('memory-stick')}</div><div><h3>${tt('Memória')}</h3><p class="sub" id="mRamSub">—</p></div><div class="right"><span class="stat"><span class="v num" id="mRam">—</span></span></div></div><div id="mRamG"></div></div>
    </div>
    <div class="grid g3">
      <div class="card stat"><span class="k">${tt('Lapozófájl / swap')}</span><span class="v num" id="mSwap">—</span><div class="meter"><i id="mSwapM" style="width:0"></i></div></div>
      <div class="card stat"><span class="k">${tt('Rendszermeghajtó')}</span><span class="v num" id="mDisk">—</span><div class="meter"><i id="mDiskM" style="width:0"></i></div></div>
      <div class="card stat"><span class="k">${tt('Hálózat ↓ / ↑')}</span><span class="v num" id="mNet" style="font-size:17px">—</span><div class="faint" style="font-size:12px;margin-top:8px" id="mNetT">&nbsp;</div></div>
    </div>
    <div class="card"><div class="card-head"><div class="tile-ic">${icon('activity')}</div><div><h3>${tt('Folyamatok')}</h3><p class="sub">${tt('Memóriahasználat szerint')}</p></div></div>
      <div class="table-wrap"><table class="tbl"><thead><tr><th>${tt('Folyamat')}</th><th class="r">PID</th><th class="r">CPU</th><th class="r">${tt('Memória')}</th></tr></thead><tbody id="mProcs"><tr><td colspan="4"><div class="skeleton"></div></td></tr></tbody></table></div></div>`;
  updateMonitor();
}
function updateMonitor() {
  const d = S.mon.last; if (!d || !$('#mCpu')) return;
  $('#mCpu').innerHTML = `${Math.round(d.cpu)}<small>%</small>`;
  $('#mCpuSub').textContent = t('{n} logikai mag · frissítve {ts}', { n: d.cpu_count, ts: d.ts });
  $('#mRam').innerHTML = `${Math.round(d.ram_pct)}<small>%</small>`;
  $('#mRamSub').textContent = t('{u} / {t} · {a} szabad', { u: d.ram_used, t: d.ram_total, a: d.ram_available });
  $('#mCpuG').innerHTML = spark(S.mon.cpu);
  $('#mRamG').innerHTML = spark(S.mon.ram, true);
  $('#mSwap').innerHTML = `${Math.round(d.swap_pct)}<small>% · ${esc(d.swap_used)} / ${esc(d.swap_total)}</small>`;
  $('#mSwapM').style.width = `${d.swap_pct}%`; $('#mSwapM').className = level(d.swap_pct);
  $('#mDisk').innerHTML = `${pct(d.disk_pct)}<small>% · ${tt('{f} szabad', { f: d.disk_free })}</small>`;
  $('#mDiskM').style.width = `${d.disk_pct}%`; $('#mDiskM').className = level(d.disk_pct);
  $('#mNet').textContent = `${fmtB(d.net_down)}/s · ${fmtB(d.net_up)}/s`;
  $('#mNetT').textContent = t('Indítás óta: {d} le, {u} fel', { d: d.net_recv_total, u: d.net_sent_total });
  $('#mProcs').innerHTML = d.processes.map(p => `<tr><td>${esc(p.name)}</td><td class="r num faint">${p.pid}</td><td class="r num">${pct(p.cpu)}%</td><td class="r num">${esc(p.rss_fmt)}</td></tr>`).join('');
}

/* ── közös: mappaválasztó, megmutatás, Lomtár ────────────────────────────── */
function pathPicker(id, value) {
  return `<div class="path-input"><input type="text" id="${id}" value="${esc(value)}" spellcheck="false">
    ${S.boot.can_pick_folder ? `<button class="btn" data-pick="${id}">${icon('folder-open')}${tt('Tallózás')}</button>` : ''}</div>`;
}
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-pick]'); if (!b) return;
  const r = await api('pick_folder', {});
  if (r.path) { $('#' + b.dataset.pick).value = r.path; }
});
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-reveal]'); if (!b) return;
  e.preventDefault();
  await api('files/reveal', { path: b.dataset.reveal }).catch(err => toast(err.message, 'err'));
});
document.addEventListener('click', e => {
  if (e.target.closest('[data-open-release]')) { e.preventDefault(); api('open_url', { url: S.update?.url || 'https://github.com/csiber/pycleaner/releases' }); }
});

async function trashFiles(paths, btn) {
  if (!paths.length) return [];
  const ok = await dialog({ title: t('{n} fájl a Lomtárba', { n: paths.length }), ok: t('Lomtárba helyezés'), danger: true,
    text: tt('A kijelölt fájlok a Lomtárba kerülnek, onnan még visszaállíthatók.') });
  if (!ok) return [];
  const r = await busy(btn, () => api('files/delete', { paths }));
  if (!r) return [];
  const good = r.results.filter(x => x.ok).map(x => x.path);
  const bad = r.results.filter(x => !x.ok);
  if (good.length) toast(t('{n} fájl a Lomtárba került', { n: good.length }), 'ok');
  if (bad.length) toast(t('{n} fájl nem törölhető: {e}', { n: bad.length, e: bad[0].error }), 'err', 6000);
  return good;
}

/* ── LEMEZELEMZŐ ─────────────────────────────────────────────────────────── */
function renderDisk() {
  const tab = S.diskTab;
  const drives = (S.boot.system.drives || []).map(d => `
    <div class="bar-row"><div class="name">${esc(d.mount)}<span>${esc(d.fstype)} · ${esc(d.total_fmt)}</span></div>
      <div class="track"><i style="width:${d.used_pct}%;${level(d.used_pct) ? `background:var(--${level(d.used_pct)})` : ''}"></i></div>
      <div class="val">${esc(d.free_fmt)}<div class="faint" style="font-size:11.5px;font-weight:500">${tt('szabad')}</div></div></div>`).join('');
  $('#page-disk').innerHTML = `
    ${head(t('Lemezelemző'), t('Mi foglalja a helyet? Meghajtók, a személyes mappák mérete és a legnagyobb fájlok.'))}
    ${drives ? `<div class="card" style="margin-bottom:14px"><div class="card-head"><div class="tile-ic">${icon('hard-drive')}</div><div><h3>${tt('Meghajtók')}</h3></div></div><div class="bars">${drives}</div></div>` : ''}
    <div class="tabs"><button data-dtab="folders" class="${tab === 'folders' ? 'on' : ''}">${tt('Személyes mappák')}</button><button data-dtab="large" class="${tab === 'large' ? 'on' : ''}">${tt('Nagy fájlok')}</button></div>
    <div id="diskBody"></div>`;
  $$('[data-dtab]').forEach(b => b.onclick = () => { S.diskTab = b.dataset.dtab; renderDisk(); });
  tab === 'folders' ? renderFolders() : renderLarge();
}
async function renderFolders() {
  const body = $('#diskBody');
  const draw = () => {
    if (S.diskTab !== 'folders' || !$('#diskBody')) return; /* közben fület váltottak */
    const f = S.folders;
    const max = Math.max(1, ...f.map(x => x.size));
    const names = { 'Asztal': 'Asztal', 'Dokumentumok': 'Dokumentumok', 'Letöltések': 'Letöltések', 'Képek': 'Képek', 'Videók': 'Videók', 'Zene': 'Zene', 'Ideiglenes': 'Ideiglenes' };
    $('#diskBody').innerHTML = `<div class="card"><div class="card-head"><div><h3>${tt('Személyes mappák')}</h3><p class="sub">${tt('Kattints a névre a megnyitáshoz')}</p></div><div class="right"><button class="btn sm" id="fRe">${icon('refresh-cw', 'sm')}${tt('Frissítés')}</button></div></div>
      <div class="bars">${f.map(x => `<div class="bar-row"><div class="name"><a href="#" data-reveal="${esc(x.path)}">${tt(names[x.name] || x.name)}</a><span>${tt('{n} fájl', { n: fmtNum(x.files) })}</span></div><div class="track"><i style="width:${(x.size / max * 100).toFixed(1)}%"></i></div><div class="val">${esc(x.size_fmt)}</div></div>`).join('')}</div></div>`;
    $('#fRe').onclick = e => busy(e.currentTarget, async () => { S.folders = await api('folders'); draw(); });
  };
  if (S.folders) return draw();
  body.innerHTML = `<div class="card"><div class="skeleton" style="margin:8px 0"></div><div class="skeleton" style="margin:14px 0;width:70%"></div><div class="skeleton" style="width:85%"></div><p class="faint" style="margin:14px 0 0">${tt('Mappák mérése…')}</p></div>`;
  try { S.folders = await api('folders'); draw(); } catch (e) { toast(e.message, 'err'); }
}
function renderLarge() {
  const Lf = S.large;
  const rows = Lf?.files?.map(f => `<tr>
    <td class="w"><input type="checkbox" class="check" data-lf="${esc(f.path)}" ${S.largeSel.has(f.path) ? 'checked' : ''}></td>
    <td class="file-cell"><b>${esc(f.name)}</b><span>${ltr(f.path)}</span></td>
    <td class="w"><span class="chip">${esc(f.ext || '—')}</span></td>
    <td class="r num w"><b>${esc(f.size_fmt)}</b></td>
    <td class="w"><button class="icon-btn" title="${tt('Megmutatás a mappában')}" data-reveal="${esc(f.path)}">${icon('folder-open')}</button></td></tr>`).join('');
  $('#diskBody').innerHTML = `<div class="card">
    <div class="row" style="margin-bottom:${Lf ? 16 : 0}px">
      ${pathPicker('lfPath', S.lfPath || S.boot.home)}
      <label class="row" style="gap:8px"><span class="muted">${tt('Legalább')}</span><select id="lfMin">${[50, 100, 250, 500, 1000, 4000].map(v => `<option value="${v}">${v >= 1000 ? v / 1000 + ' GB' : v + ' MB'}</option>`).join('')}</select></label>
      <button class="btn primary" id="lfGo">${icon('search')}${tt('Keresés')}</button>
    </div>
    ${Lf ? (Lf.files.length ? `<div class="row" style="margin-bottom:8px"><span class="muted grow">${tt('{n} fájl, összesen {s}', { n: Lf.files.length, s: fmtB(Lf.files.reduce((a, f) => a + f.size, 0)) })}</span>
      <button class="btn danger sm" id="lfDel" ${S.largeSel.size ? '' : 'disabled'}>${icon('trash-2', 'sm')}${tt('Kijelöltek Lomtárba ({n})', { n: S.largeSel.size })}</button></div>
      <div class="table-wrap"><table class="tbl"><thead><tr><th></th><th>${tt('Fájl')}</th><th>${tt('Típus')}</th><th class="r">${tt('Méret')}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
      : empty('circle-check', t('Nincs ekkora fájl'), t('ebben a mappában.'), 'ok')) : ''}
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
  const groups = D?.groups?.map(g => `<div class="group">
    <div class="group-h">${icon('copy', 'sm')}<span><b>${tt('{n} példány', { n: g.files.length })}</b> · ${tt('{s} darabonként', { s: g.size_fmt })}</span><span style="margin-left:auto">${tt('felesleges:')} <b>${esc(g.wasted_fmt)}</b></span></div>
    ${g.files.map((f, fi) => `<div class="group-f">
      <input type="checkbox" class="check" data-dp="${esc(f.path)}" ${S.dupSel.has(f.path) ? 'checked' : ''}>
      <span class="p" title="${esc(f.path)}">${ltr(f.path)}</span>
      <span class="faint num">${fi === 0 ? `<span class="chip ac">${tt('legújabb')}</span> ` : ''}${esc(fmtDate(f.mtime))}</span>
      <button class="icon-btn" title="${tt('Megmutatás a mappában')}" data-reveal="${esc(f.path)}">${icon('folder-open', 'sm')}</button></div>`).join('')}
  </div>`).join('');
  const selBytes = D ? D.groups.reduce((a, g) => a + g.files.filter(f => S.dupSel.has(f.path)).length * g.size, 0) : 0;
  $('#page-dupes').innerHTML = `
    ${head(t('Duplikátumok'), t('Azonos tartalmú fájlok keresése. Előbb méret, majd tartalom (BLAKE2b) alapján — a fájlnév nem számít.'))}
    <div class="card">
      <div class="row">${pathPicker('dpPath', S.dpPath || S.boot.home)}
        <label class="row" style="gap:8px"><span class="muted">${tt('Legalább')}</span><select id="dpMin">${[[10, '10 KB'], [100, '100 KB'], [1024, '1 MB'], [10240, '10 MB']].map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
        <button class="btn primary" id="dpGo">${icon('search')}${tt('Keresés')}</button></div>
    </div>
    ${D ? (D.groups.length ? `<div class="card">
      <div class="card-head"><div class="tile-ic warn">${icon('copy')}</div><div><h3>${tt('{n} csoport · {s} felesleges', { n: D.groups.length, s: D.total_wasted_fmt })}</h3><p class="sub">${tt('{n} fájl átvizsgálva itt: {p}', { n: fmtNum(D.scanned), p: D.root })}</p></div>
        <div class="right"><button class="btn sm" id="dpAuto">${tt('Mindenhol a legújabb marad')}</button><button class="btn danger sm" id="dpDel" ${S.dupSel.size ? '' : 'disabled'}>${icon('trash-2', 'sm')}${tt('Lomtárba ({n} · {s})', { n: S.dupSel.size, s: fmtB(selBytes) })}</button></div></div>
      ${groups}</div>` : `<div class="card">${empty('circle-check', t('Nincs duplikátum'), t('{n} fájl átvizsgálva.', { n: fmtNum(D.scanned) }), 'ok')}</div>`) : ''}`;
  $('#dpMin').value = S.dpMin || '100';
  $('#dpGo').onclick = e => busy(e.currentTarget, async () => {
    S.dpPath = $('#dpPath').value; S.dpMin = $('#dpMin').value;
    toast(t('Keresés folyamatban — nagy mappánál ez percekig is tarthat.'));
    S.dupes = await api('duplicates', { path: S.dpPath, min_kb: Number(S.dpMin) });
    S.dupSel.clear(); renderDupes();
  });
  $$('[data-dp]').forEach(cb => cb.onchange = () => {
    const g = S.dupes.groups.find(x => x.files.some(f => f.path === cb.dataset.dp));
    if (cb.checked && g.files.every(f => f.path === cb.dataset.dp || S.dupSel.has(f.path))) {
      cb.checked = false; toast(t('Minden csoportból legalább egy példánynak meg kell maradnia.'), 'warn'); return;
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

/* ── GÉPÁLLAPOT ──────────────────────────────────────────────────────────── */
const LVL = { bad: ['Sürgős', 'bad', 'circle-x'], warn: ['Figyelem', 'warn', 'circle-alert'], info: ['Tudnivaló', 'ac', 'info'], ok: ['Rendben', 'ok', 'circle-check'] };
function renderHealth() {
  if (!S.boot.system.is_windows) { $('#page-health').innerHTML = head(t('Gépállapot'), '') + winOnly(); return; }
  const H = S.health, J = S.healthJob;
  const scoreCls = H ? (H.score >= 85 ? 'ok' : H.score >= 60 ? 'warn' : 'bad') : '';
  const counts = H ? ['bad', 'warn', 'ok'].map(l => H.findings.filter(f => f.level === l).length) : [];
  $('#page-health').innerHTML = `
    ${head(t('Gépállapot'), t('Lemezek egészsége, szabad hely, vírusvédelem, frissítések, akkumulátor és indítópult egy felmérésben — javaslatokkal.'),
      `${H ? `<button class="btn" id="hOpen">${icon('file-text')}${tt('Riport (nyomtatás / PDF)')}</button>` : ''}<button class="btn primary" id="hRun">${icon('heart-pulse')}${tt(H ? 'Újramérés' : 'Felmérés indítása')}</button>`)}
    ${J ? `<div class="card"><div class="card-head"><div class="tile-ic">${icon('heart-pulse')}</div><div><h3>${tt('Felmérés folyamatban…')}</h3><p class="sub">${esc(J.log.slice(-1)[0] || '')}</p></div></div><div class="skeleton"></div></div>` : ''}
    ${H ? `<div class="card hero" style="grid-template-columns:auto minmax(0,1fr)">
        <div class="score-ring ${scoreCls}"><b>${H.score}</b><span>/ 100</span></div>
        <div><h2 style="margin:0 0 4px">${tt(H.score >= 85 ? 'A gép jó állapotban van' : H.score >= 60 ? 'Van néhány tennivaló' : 'Beavatkozás szükséges')}</h2>
          <p class="muted" style="margin:0 0 10px">${tt('Felmérve: {d}', { d: fmtDT(H.generated) })}</p>
          <div class="row"><span class="chip bad">${tt('{n} sürgős', { n: counts[0] })}</span><span class="chip warn">${tt('{n} figyelmeztetés', { n: counts[1] })}</span><span class="chip ok">${tt('{n} rendben', { n: counts[2] })}</span></div></div>
      </div>
      <div class="card">${H.findings.map(f => `<div class="finding ${f.level}"><div class="tile-ic ${LVL[f.level][1]}">${icon(LVL[f.level][2])}</div>
        <div><div class="t">${esc(f.title)}</div>${f.detail ? `<div class="d">${esc(f.detail)}</div>` : ''}${f.advice ? `<div class="a">${esc(f.advice)}</div>` : ''}</div>
        <span class="chip">${esc(f.area)}</span></div>`).join('')}</div>
      <p class="faint" style="font-size:12.5px;margin-top:12px">${tt('A riport fejlécében a szervizadataid jelennek meg — ezeket a Beállításokban adhatod meg.')} <a href="#settings" data-go="settings">${tt('Beállítások')}</a></p>`
      : (J ? '' : `<div class="card">${empty('heart-pulse', t('Még nem volt felmérés'), t('Egy-két perc, csak olvas — semmit nem módosít a gépen.'))}</div>`)}`;
  $('#hRun').onclick = e => busy(e.currentTarget, runHealth);
  const o = $('#hOpen');
  if (o) o.onclick = e => busy(e.currentTarget, async () => { const r = await api('health/open', {}); if (r.ok) toast(t('A riport megnyílt a böngészőben.'), 'ok'); else toast(r.msg, 'warn'); });
}
async function runHealth() {
  const { job } = await api('health/run', {});
  const j = await pollJob(job, jj => { S.healthJob = jj; if (isActive('health')) renderHealth(); });
  S.healthJob = null;
  if (j.status === 'done') { S.health = j.result; sideState(); toast(t('Felmérés kész: {n} pont', { n: j.result.score }), 'ok'); }
  else toast(j.error || t('A felmérés nem sikerült.'), 'err');
  if (isActive('health')) renderHealth();
  if (isActive('overview')) renderOverview();
}

/* ── INDÍTÓPULT ──────────────────────────────────────────────────────────── */
async function renderStartup() {
  const pg = $('#page-startup');
  if (!S.boot.system.is_windows) { pg.innerHTML = head(t('Indítópult'), '') + winOnly(); return; }
  const draw = () => {
    const D = S.startup;
    const on = D ? D.items.filter(i => i.enabled).length : 0;
    pg.innerHTML = `
      ${head(t('Indítópult'), t('A bejelentkezéskor induló programok. A kikapcsolás ugyanaz, mint a Feladatkezelőben: semmi nem törlődik, bármikor visszakapcsolható.'),
        `<button class="btn" id="suRe">${icon('refresh-cw')}${tt('Frissítés')}</button>`)}
      ${D ? `<div class="card"><div class="card-head"><div class="tile-ic ${on > 15 ? 'warn' : ''}">${icon('rocket')}</div><div><h3>${tt('{on} bekapcsolva / {n} bejegyzés', { on, n: D.items.length })}</h3><p class="sub">${tt('Ami nem kell rögtön bejelentkezéskor (frissítők, segédprogramok), azt nyugodtan kapcsold ki — a program maga megmarad.')}</p></div></div>
        ${D.items.length ? D.items.map(i => `<div class="list-item su">
          <input type="checkbox" class="switch" data-su="${i.id}" ${i.enabled ? 'checked' : ''} ${i.locked ? 'disabled' : ''} title="${tt(i.enabled ? 'Kikapcsolás' : 'Bekapcsolás')}">
          <div style="min-width:0"><div class="t">${esc(i.name)} ${i.missing ? `<span class="chip warn">${tt('hiányzó program')}</span>` : ''}${i.locked ? `<span class="chip">${icon('shield-check', 'sm')}${tt('Rendszergazda')}</span>` : ''}</div>
            <div class="d" title="${esc(i.command)}">${esc(i.publisher || '')}${i.publisher ? ' · ' : ''}<span class="mono">${esc(i.command)}</span></div></div>
          <span class="chip">${esc(i.kind)}</span></div>`).join('') : empty('circle-check', t('Üres'), t('Semmi nem indul automatikusan.'), 'ok')}
        ${D.items.some(i => i.locked) ? `<p class="faint" style="font-size:12.5px;margin:12px 0 0">${tt('A gépszintű bejegyzések módosításához indítsd újra a PyCleanert rendszergazdaként.')}</p>` : ''}</div>`
        : `<div class="card"><div class="skeleton" style="margin:8px 0"></div><div class="skeleton" style="width:75%;margin:14px 0"></div><div class="skeleton" style="width:60%"></div></div>`}`;
    $('#suRe').onclick = e => busy(e.currentTarget, async () => { S.startup = await api('startup'); draw(); });
    $$('[data-su]').forEach(sw => sw.onchange = async () => {
      sw.disabled = true;
      try {
        const r = await api('startup/toggle', { id: Number(sw.dataset.su), enabled: sw.checked });
        if (!r.ok) { sw.checked = !sw.checked; toast(r.msg, 'err'); }
        else { const it = S.startup.items.find(i => i.id === r.item.id); it.enabled = r.item.enabled; toast(`${r.item.name}: ${r.msg}`, 'ok', 2200); }
      } catch (e) { sw.checked = !sw.checked; toast(e.message, 'err'); }
      draw();
    });
  };
  draw();
  if (!S.startup) { try { S.startup = await api('startup'); } catch (e) { toast(e.message, 'err'); } if (isActive('startup')) draw(); }
}

/* ── PROGRAMFRISSÍTŐ (winget) ────────────────────────────────────────────── */
async function loadUpdates(btn) {
  await busy(btn, async () => { S.upd = await api('winget'); S.updSel = new Set(); sideState(); });
  if (isActive('updates')) renderUpdates();
}
function renderUpdates() {
  const pg = $('#page-updates');
  if (!S.boot.system.is_windows) { pg.innerHTML = head(t('Programfrissítő'), '') + winOnly(); return; }
  const U = S.upd, J = S.updJob;
  const pk = U?.packages || [];
  pg.innerHTML = `
    ${head(t('Programfrissítő'), t('A telepített programok frissítése a Windows beépített csomagkezelőjével (winget) — egy kattintással, csendben.'),
      `<button class="btn" id="upRe" ${J ? 'disabled' : ''}>${icon('refresh-cw')}${tt('Keresés')}</button>`)}
    ${J ? `<div class="card"><div class="card-head"><div class="tile-ic">${icon('circle-arrow-up')}</div><div><h3>${tt(J.status === 'running' ? 'Frissítés folyamatban…' : 'Frissítés kész')}</h3><p class="sub">${tt('A programok a háttérben frissülnek; egyes telepítők rövid időre ablakot nyithatnak.')}</p></div>
      ${J.status !== 'running' ? `<div class="right"><button class="icon-btn" id="upJobX">${icon('x')}</button></div>` : ''}</div><pre class="logbox">${esc(J.log.join('\n'))}</pre></div>` : ''}
    ${!U ? `<div class="card"><div class="skeleton" style="margin:8px 0"></div><div class="skeleton" style="width:70%;margin:14px 0"></div><p class="faint" style="margin:0">${tt('Frissítések keresése… (10–30 másodperc)')}</p></div>`
      : !U.available ? `<div class="card">${empty('circle-alert', t('A winget nem érhető el'), U.error || '', 'warn')}</div>`
      : !pk.length ? `<div class="card">${empty('circle-check', t('Minden program naprakész'), t('Nincs elérhető frissítés.'), 'ok')}</div>`
      : `<div class="card"><div class="card-head"><div class="tile-ic warn">${icon('circle-arrow-up')}</div><div><h3>${tt('{n} programhoz érhető el frissítés', { n: pk.length })}</h3><p class="sub">${tt('Frissítés előtt érdemes bezárni az érintett programokat.')}</p></div>
        <div class="right"><button class="btn sm" id="upAll" ${J?.status === 'running' ? 'disabled' : ''}>${tt('Mind kijelölése')}</button><button class="btn primary sm" id="upGo" ${S.updSel.size && J?.status !== 'running' ? '' : 'disabled'}>${icon('download', 'sm')}${tt('Frissítés ({n})', { n: S.updSel.size })}</button></div></div>
        <div class="table-wrap"><table class="tbl"><thead><tr><th></th><th>${tt('Program')}</th><th>${tt('Jelenlegi')}</th><th>${tt('Új')}</th></tr></thead><tbody>
        ${pk.map(p => `<tr><td class="w"><input type="checkbox" class="check" data-up="${esc(p.id)}" ${S.updSel.has(p.id) ? 'checked' : ''} ${p.truncated ? 'disabled' : ''}></td>
          <td class="file-cell grow-cell"><b>${esc(p.name)}</b><span class="mono" style="direction:ltr">${esc(p.id)}</span></td>
          <td class="num faint w">${esc(p.version)}</td><td class="num w"><b>${esc(p.available)}</b></td></tr>`).join('')}
        </tbody></table></div></div>`}`;
  $('#upRe').onclick = e => loadUpdates(e.currentTarget);
  const x = $('#upJobX'); if (x) x.onclick = () => { S.updJob = null; renderUpdates(); };
  $$('[data-up]').forEach(cb => cb.onchange = () => { cb.checked ? S.updSel.add(cb.dataset.up) : S.updSel.delete(cb.dataset.up); renderUpdates(); });
  const all = $('#upAll'); if (all) all.onclick = () => { pk.filter(p => !p.truncated).forEach(p => S.updSel.add(p.id)); renderUpdates(); };
  const go = $('#upGo');
  if (go) go.onclick = async e => {
    const ids = [...S.updSel];
    await busy(e.currentTarget, async () => {
      const { job } = await api('winget/upgrade', { ids });
      const j = await pollJob(job, jj => { S.updJob = jj; if (isActive('updates')) renderUpdates(); });
      const ok = (j.result || []).filter(r => r.ok).length;
      toast(t('{ok} / {n} program frissítve', { ok, n: ids.length }), ok === ids.length ? 'ok' : 'warn', 6000);
      S.upd = null; renderUpdates(); await loadUpdates();
    });
  };
  if (!U && !J) loadUpdates();
}

/* ── PROGRAMOK ───────────────────────────────────────────────────────────── */
function renderPrograms() {
  const pg = $('#page-programs');
  if (!S.boot.system.is_windows) { pg.innerHTML = head(t('Programok'), '') + winOnly(); return; }
  const P = S.progs, U = S.uninst;
  const q = S.progQ.trim().toLowerCase();
  let list = P ? P.programs.filter(p => !q || (p.name + ' ' + p.publisher).toLowerCase().includes(q)) : [];
  const sorters = { name: (a, b) => a.name.localeCompare(b.name, LOC()), size: (a, b) => b.size - a.size, date: (a, b) => (b.installed || '').localeCompare(a.installed || '') };
  list = list.sort(sorters[S.progSort]);
  const total = P ? P.programs.reduce((a, p) => a + p.size, 0) : 0;
  pg.innerHTML = `
    ${head(t('Programok'), t('Telepített programok eltávolítása a saját eltávolítójukkal, utána a maradékok (üres mappák) felkínálásával.'),
      `<button class="btn" id="prRe">${icon('refresh-cw')}${tt('Frissítés')}</button>`)}
    ${U ? `<div class="card"><div class="card-head"><div class="tile-ic ${U.status === 'running' ? '' : U.result?.ok ? 'ok' : 'warn'}">${icon('package')}</div><div>
        <h3>${U.status === 'running' ? tt('Eltávolítás: {n}', { n: U.title }) : U.result?.ok ? tt('Eltávolítva: {n}', { n: U.title }) : tt('Nem lett eltávolítva: {n}', { n: U.title })}</h3>
        <p class="sub">${tt(U.status === 'running' ? 'Az eltávolító saját ablakában kövesd a lépéseket. (Ha nem látod, nézd meg a tálcán.)' : U.result?.ok ? (U.result.leftovers.length ? 'Ezek a mappák maradtak utána. Csak azt jelöld ki, amire biztosan nincs szükség — a Lomtárba kerülnek.' : 'Nem maradt utána mappa.') : 'Az eltávolítás megszakadt, vagy a program bejegyzése megmaradt.')}</p></div>
        ${U.status !== 'running' ? `<div class="right"><button class="icon-btn" id="prUx">${icon('x')}</button></div>` : ''}</div>
      ${U.status === 'running' ? '<div class="skeleton"></div>' : ''}
      ${U.result?.leftovers?.length ? U.result.leftovers.map(l => `<label class="list-item"><input type="checkbox" class="check" data-lo="${esc(l.path)}"><div style="min-width:0"><div class="t mono" style="font-size:12.5px">${esc(l.path)}</div><div class="d">${tt('{n} fájl', { n: fmtNum(l.files) })} · ${esc(l.size_fmt)}</div></div><button class="icon-btn" data-reveal="${esc(l.path)}">${icon('folder-open')}</button></label>`).join('') + `<div class="row end" style="margin-top:12px"><button class="btn danger sm" id="prLo">${icon('trash-2', 'sm')}${tt('Kijelöltek Lomtárba')}</button></div>` : ''}
    </div>` : ''}
    <div class="card">
      <div class="row" style="margin-bottom:12px"><input type="text" id="prQ" class="grow" placeholder="${tt('Keresés név vagy kiadó szerint…')}" value="${esc(S.progQ)}">
        <select id="prSort"><option value="name">${tt('Név szerint')}</option><option value="size">${tt('Méret szerint')}</option><option value="date">${tt('Telepítés szerint')}</option></select></div>
      ${!P ? '<div class="skeleton" style="margin:8px 0"></div><div class="skeleton" style="width:80%;margin:14px 0"></div>' : `
      <p class="faint" style="margin:0 0 8px;font-size:12.5px">${tt('{n} program · összesen kb. {s}', { n: fmtNum(P.programs.length), s: fmtB(total) })}</p>
      <div class="table-wrap"><table class="tbl"><thead><tr><th>${tt('Program')}</th><th>${tt('Verzió')}</th><th class="r">${tt('Méret')}</th><th>${tt('Telepítve')}</th><th></th></tr></thead><tbody>
      ${list.map(p => `<tr><td class="file-cell grow-cell"><b title="${esc(p.name)}">${esc(p.name)}</b><span style="direction:ltr">${esc(p.publisher)}</span></td><td class="faint num w">${esc(p.version)}</td>
        <td class="r num w">${esc(p.size_fmt || '—')}</td><td class="faint num w">${esc(p.installed || '—')}</td>
        <td class="w"><button class="btn sm" data-un="${p.id}" ${U?.status === 'running' ? 'disabled' : ''}>${tt('Eltávolítás')}</button></td></tr>`).join('')}
      </tbody></table></div>`}
    </div>`;
  $('#prSort').value = S.progSort;
  $('#prSort').onchange = e => { S.progSort = e.target.value; renderPrograms(); };
  $('#prQ').oninput = e => { S.progQ = e.target.value; const pos = e.target.selectionStart; renderPrograms(); const i = $('#prQ'); i.focus(); i.setSelectionRange(pos, pos); };
  $('#prRe').onclick = e => busy(e.currentTarget, async () => { S.progs = await api('programs'); renderPrograms(); });
  const ux = $('#prUx'); if (ux) ux.onclick = () => { S.uninst = null; renderPrograms(); };
  $$('[data-un]').forEach(b => b.onclick = async () => {
    const p = S.progs.programs.find(x => x.id === Number(b.dataset.un));
    if (!await dialog({ title: t('{n} eltávolítása', { n: p.name }), ok: t('Eltávolítás'), danger: true,
      text: tt('Elindul a program saját eltávolítója. Ha kérdez, kövesd a lépéseit. Utána a PyCleaner felkínálja a megmaradt mappákat.') })) return;
    try {
      const { job } = await api('programs/uninstall', { id: p.id });
      const j = await pollJob(job, jj => { S.uninst = jj; if (isActive('programs')) renderPrograms(); });
      S.uninst = j;
      if (j.result?.ok) { toast(t('Eltávolítva: {n}', { n: p.name }), 'ok'); S.progs = await api('programs'); }
    } catch (e) { toast(e.message, 'err'); }
    if (isActive('programs')) renderPrograms();
  });
  const lo = $('#prLo');
  if (lo) lo.onclick = async e => {
    const paths = $$('[data-lo]').filter(c => c.checked).map(c => c.dataset.lo);
    if (!paths.length) return toast(t('Nincs kijelölt mappa.'), 'warn');
    await busy(e.currentTarget, async () => {
      const r = await api('programs/leftovers', { paths });
      const ok = r.results.filter(x => x.ok).length, bad = r.results.filter(x => !x.ok);
      if (ok) toast(t('{n} mappa a Lomtárba került', { n: ok }), 'ok');
      if (bad.length) toast(bad[0].error, 'err', 6000);
      S.uninst.result.leftovers = S.uninst.result.leftovers.filter(l => !r.results.some(x => x.ok && x.path === l.path));
    });
    renderPrograms();
  };
  if (!P) api('programs').then(r => { S.progs = r; if (isActive('programs')) renderPrograms(); }).catch(e => toast(e.message, 'err'));
}

/* ── REGISTRY ────────────────────────────────────────────────────────────── */
function renderRegistry() {
  if (!S.boot.system.is_windows) { $('#page-registry').innerHTML = head(t('Registry'), '') + winOnly(); return; }
  const R = S.reg;
  const admin = S.boot.system.is_admin;
  const items = R?.issues?.map(i => {
    const lock = i.admin && !admin;
    return `<div class="list-item"><input type="checkbox" class="check" data-reg="${i.id}" ${S.regSel.has(i.id) ? 'checked' : ''} ${lock ? 'disabled' : ''}>
      <div style="min-width:0"><div class="t">${esc(i.title)} ${i.admin ? `<span class="chip ${lock ? 'warn' : ''}">${i.hive}</span>` : ''}</div><div class="d" title="${esc(i.detail)}">${esc(i.detail)}</div></div>
      <span class="faint mono" title="${esc(i.hive + '\\' + i.key)}" style="font-size:11px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(i.key.split('\\').slice(-2).join('\\'))}</span></div>`;
  }).join('');
  $('#page-registry').innerHTML = `
    ${head(t('Registry'), t('Óvatos keresés: csak egyértelműen elavult bejegyzéseket jelez (törölt programok maradványai). Minden javítás előtt automatikus .reg mentés készül.'),
      `<button class="btn ghost" id="rgBk">${icon('archive')}${tt('Mentések mappája')}</button><button class="btn primary" id="rgScan">${icon('search')}${tt('Keresés')}</button>`)}
    ${R ? (R.issues.length ? `<div class="card"><div class="card-head"><div class="tile-ic warn">${icon('list-tree')}</div><div><h3>${tt('{n} elavult bejegyzés', { n: R.issues.length })}</h3><p class="sub">${admin ? '' : tt('A HKLM-bejegyzésekhez rendszergazdai jog kell.') + ' '}${tt('A javítás visszavonható: a mentett .reg fájlra duplán kattintva.')}</p></div>
      <div class="right"><button class="btn sm" id="rgAll">${tt('Mind kijelölése')}</button><button class="btn primary sm" id="rgFix" ${S.regSel.size ? '' : 'disabled'}>${icon('wrench', 'sm')}${tt('Javítás ({n})', { n: S.regSel.size })}</button></div></div>${items}</div>`
      : `<div class="card">${empty('shield-check', t('Rendben van'), t('Nem találtam elavult bejegyzést.'), 'ok')}</div>`)
      : `<div class="card">${empty('list-tree', t('Még nem kerestél'), t('A keresés csak olvas, semmit nem módosít.'))}</div>`}`;
  $('#rgScan').onclick = e => busy(e.currentTarget, async () => { S.reg = await api('registry/scan'); S.regSel.clear(); renderRegistry(); });
  $('#rgBk').onclick = () => api('registry/backups/open', {});
  $$('[data-reg]').forEach(cb => cb.onchange = () => { const id = Number(cb.dataset.reg); cb.checked ? S.regSel.add(id) : S.regSel.delete(id); renderRegistry(); });
  const all = $('#rgAll'); if (all) all.onclick = () => { R.issues.filter(i => !(i.admin && !admin)).forEach(i => S.regSel.add(i.id)); renderRegistry(); };
  const fix = $('#rgFix');
  if (fix) fix.onclick = async e => {
    if (!await dialog({ title: t('{n} registry-bejegyzés javítása', { n: S.regSel.size }), ok: t('Javítás'), danger: true,
      text: tt('A kijelölt bejegyzések törlődnek a rendszerleíró adatbázisból. Előtte automatikus .reg mentés készül, amelyre duplán kattintva visszaállíthatók.') })) return;
    busy(e.currentTarget, async () => {
      const r = await api('registry/fix', { ids: [...S.regSel] });
      const ok = r.results.filter(x => x.ok).length, bad = r.results.filter(x => !x.ok);
      if (ok) toast(t('{n} bejegyzés javítva, mentés: registry-backups', { n: ok }), 'ok');
      if (bad.length) toast(bad[0].msg, 'err', 6000);
      S.reg = await api('registry/scan'); S.regSel.clear(); renderRegistry();
    });
  };
}

/* ── WINDOWS-FINOMHANGOLÁS ───────────────────────────────────────────────── */
async function elevate(btn) {
  await busy(btn, async () => {
    const r = await api('admin/relaunch', {});
    if (r.ok) { toast(t('Újraindítás rendszergazdaként…'), 'ok'); setTimeout(showGoodbye, 600); }
    else toast(r.msg, 'warn');
  });
}
function renderTweaks() {
  if (!S.boot.system.is_windows) { $('#page-tweaks').innerHTML = head(t('Windows-finomhangolás'), '') + winOnly(); return; }
  const admin = S.boot.system.is_admin;
  const apps = S.apps;
  const appRows = apps ? [...apps].sort((a, b) => b.installed - a.installed).map(a => `<label class="list-item" style="cursor:${a.installed ? 'pointer' : 'default'}">
      <input type="checkbox" class="check" data-app="${esc(a.id)}" ${S.appSel.has(a.id) ? 'checked' : ''} ${a.installed ? '' : 'disabled'}>
      <div><div class="t">${esc(a.name)}</div><div class="d mono">${esc(a.id)}</div></div>
      <span class="chip ${a.installed ? 'ac' : ''}">${tt(a.installed ? 'Telepítve' : 'Nincs fent')}</span></label>`).join('')
    : '<div class="skeleton" style="margin:10px 0"></div><div class="skeleton" style="width:80%;margin:16px 0"></div><div class="skeleton" style="width:60%"></div>';
  $('#page-tweaks').innerHTML = `
    ${head(t('Windows-finomhangolás'), t('Előtelepített alkalmazások és a OneDrive eltávolítása. Nagyobb módosítás előtt érdemes visszaállítási pontot készíteni.'))}
    <div class="grid g2">
      <div class="card"><div class="card-head"><div class="tile-ic ${admin ? 'ok' : 'warn'}">${icon(admin ? 'shield-check' : 'shield-alert')}</div><div><h3>${tt(admin ? 'Rendszergazdaként fut' : 'Normál jogokkal fut')}</h3><p class="sub">${tt(admin ? 'Minden funkció elérhető.' : 'A visszaállítási ponthoz és a rendszermappákhoz emelt jog kell.')}</p></div></div>
        ${admin ? '' : `<button class="btn" id="twElev">${icon('shield-check')}${tt('Újraindítás rendszergazdaként')}</button>`}</div>
      <div class="card"><div class="card-head"><div class="tile-ic">${icon('rotate-ccw')}</div><div><h3>${tt('Visszaállítási pont')}</h3><p class="sub">${tt('A Windows saját biztonsági pontja; ha valami gond lenne, ide vissza lehet állni.')}</p></div></div>
        <button class="btn" id="twRp" ${admin ? '' : 'disabled'}>${icon('rotate-ccw')}${tt('Visszaállítási pont létrehozása')}</button></div>
    </div>
    <div class="card"><div class="card-head"><div class="tile-ic">${icon('package-x')}</div><div><h3>${tt('Előtelepített alkalmazások')}</h3><p class="sub">${tt('Csak az aktuális felhasználónál távolítja el őket; a Microsoft Store-ból bármikor visszatelepíthetők. Az Xbox-fiókhoz és a játékokhoz szükséges részeket szándékosan nem listázzuk.')}</p></div>
      <div class="right"><button class="btn sm" id="twDef" ${apps ? '' : 'disabled'}>${tt('Ajánlottak')}</button><button class="btn danger sm" id="twRm" ${S.appSel.size ? '' : 'disabled'}>${icon('trash-2', 'sm')}${tt('Eltávolítás ({n})', { n: S.appSel.size })}</button></div></div>
      <div>${appRows}</div></div>
    <div class="card"><div class="card-head"><div class="tile-ic warn">${icon('cloud-off')}</div><div><h3>${tt('OneDrive eltávolítása')}</h3><p class="sub">${tt('Leállítja és eltávolítja a OneDrive-ot. A felhőben tárolt fájlok a fiókodban megmaradnak; a csak felhőben lévő („online”) fájlok helyben nem lesznek elérhetők.')}</p></div>
      <div class="right"><button class="btn danger" id="twOd">${icon('cloud-off')}${tt('Eltávolítás')}</button></div></div></div>`;
  const el = $('#twElev'); if (el) el.onclick = e => elevate(e.currentTarget);
  $('#twRp').onclick = e => busy(e.currentTarget, async () => { const r = await api('tweaks/restore_point', {}); toast(r.msg, r.ok ? 'ok' : 'err', 6000); });
  $('#twOd').onclick = async e => {
    if (!await dialog({ title: t('OneDrive eltávolítása'), danger: true, ok: t('Eltávolítás'), text: tt('Biztosan eltávolítod a OneDrive-ot? Előtte érdemes ellenőrizni, hogy minden fontos fájl szinkronizálva van-e.') })) return;
    busy(e.currentTarget, async () => { const r = await api('tweaks/onedrive', {}); toast(r.msg, r.ok ? 'ok' : 'err', 7000); });
  };
  $$('[data-app]').forEach(cb => cb.onchange = () => { cb.checked ? S.appSel.add(cb.dataset.app) : S.appSel.delete(cb.dataset.app); renderTweaks(); });
  const def = $('#twDef'); if (def) def.onclick = () => { S.appSel = new Set(S.apps.filter(a => a.installed && a.default).map(a => a.id)); renderTweaks(); };
  $('#twRm').onclick = async e => {
    const names = S.apps.filter(a => S.appSel.has(a.id)).map(a => a.name);
    if (!await dialog({ title: t('{n} alkalmazás eltávolítása', { n: names.length }), danger: true, ok: t('Eltávolítás'), text: esc(names.join(', ')) })) return;
    await busy(e.currentTarget, async () => {
      const r = await api('tweaks/apps/remove', { ids: [...S.appSel] });
      const ok = r.results.filter(x => x.status === 'removed').length, bad = r.results.filter(x => !x.ok);
      toast(t('{n} alkalmazás eltávolítva', { n: ok }), ok ? 'ok' : 'info');
      if (bad.length) toast(t('Nem sikerült: {l}', { l: bad.map(b => b.id).join(', ') }), 'err', 7000);
      S.appSel.clear(); S.apps = (await api('tweaks/apps')).apps;
    });
    renderTweaks();
  };
  if (!apps) api('tweaks/apps').then(r => { S.apps = r.apps; if (isActive('tweaks')) renderTweaks(); }).catch(err => toast(err.message, 'err'));
}

/* ── ÜTEMEZŐ ─────────────────────────────────────────────────────────────── */
function renderSchedule() {
  const s = S.schedule, win = S.boot.system.is_windows, task = S.task;
  const allowed = S.cats.filter(c => !['trash', 'custom'].includes(c.id) && !c.admin);
  const next = s.enabled && s.last_run ? new Date(new Date(s.last_run).getTime() + s.interval_hours * 3600e3) : null;
  const intervals = [[6, '6 óránként'], [12, '12 óránként'], [24, 'naponta'], [72, '3 naponta'], [168, 'hetente']];
  $('#page-schedule').innerHTML = `
    ${head(t('Ütemező'), t('Automatikus háttértisztítás a választott időközönként.'))}
    <div class="card">
      <div class="setting"><div><div class="t">${tt('Automatikus tisztítás')}</div><div class="d">${s.enabled ? tt('Utoljára: {l}', { l: s.last_run ? fmtDT(s.last_run) : t('még nem futott') }) + (next ? ' · ' + tt('következő: {n}', { n: next.toLocaleString(LOC()) }) : '') : tt('Kikapcsolva')}</div></div><input type="checkbox" class="switch" id="scOn" ${s.enabled ? 'checked' : ''}></div>
      ${win ? `<div class="setting"><div><div class="t">${tt('Akkor is fusson, ha a PyCleaner be van zárva')}</div><div class="d">${tt('A Windows Feladatütemezője indítja el ablak nélkül, a háttérben.')}${task?.exists ? ' ' + tt('Feladat: {s}, következő futás: {n}', { s: task.state, n: task.next ? fmtDT(task.next) : '—' }) : ''}${task?.stale ? ' ' + tt('(A feladat egy korábbi telepítési helyre mutat — kapcsold ki és be.)') : ''}</div></div><input type="checkbox" class="switch" id="scTask" ${s.use_task ? 'checked' : ''} ${s.enabled ? '' : 'disabled'}></div>` : ''}
      <div class="setting"><div><div class="t">${tt('Gyakoriság')}</div></div>
        <select id="scInt">${intervals.map(([v, l]) => `<option value="${v}">${tt(l)}</option>`).join('')}</select></div>
      <div class="setting" style="align-items:start"><div><div class="t">${tt('Kategóriák')}</div><div class="d">${tt('Az ütemező csak biztonságos, nem végleges kategóriákat takaríthat.')}</div></div>
        <div style="display:grid;gap:10px">${allowed.map(c => `<label class="row" style="gap:10px;flex-wrap:nowrap"><input type="checkbox" class="check" data-sc="${c.id}" ${s.categories.includes(c.id) ? 'checked' : ''}>${esc(c.label)}</label>`).join('')}</div></div>
    </div>
    ${win ? '' : `<div class="banner" style="margin-top:14px">${icon('info', 'lg')}<div class="grow"><b>${tt('Tipp')}</b><span>${tt('Linuxon és macOS-en az ütemező csak a program futása alatt működik.')}</span></div></div>`}`;
  $('#scInt').value = String(s.interval_hours);
  const save = async () => {
    const r = await api('schedule', { enabled: $('#scOn').checked, use_task: win ? $('#scTask').checked : false,
      interval_hours: Number($('#scInt').value), categories: $$('[data-sc]').filter(x => x.checked).map(x => x.dataset.sc) });
    S.schedule = r;
    if (r.task && !r.task.ok) toast(r.task.msg, 'err', 6000);
    else toast(r.task?.msg || t('Ütemezés mentve'), 'ok', 2200);
    if (win) S.task = await api('schedule/task');
    sideState(); renderSchedule();
  };
  $('#scOn').onchange = save; $('#scInt').onchange = save; $$('[data-sc]').forEach(x => x.onchange = save);
  const tk = $('#scTask'); if (tk) tk.onchange = save;
  if (win && !task) api('schedule/task').then(r => { S.task = r; if (isActive('schedule')) renderSchedule(); }).catch(() => {});
}

/* ── ELŐZMÉNYEK + MENTÉSEK ───────────────────────────────────────────────── */
async function renderHistory() {
  const tab = S.histTab;
  $('#page-history').innerHTML = `
    ${head(t('Előzmények'), t('A korábbi tisztítások és a törlés előtt készült mentések.'),
      `<a class="btn" href="${dl('export/html')}" download>${icon('file-text')}${tt('HTML-riport')}</a><a class="btn" href="${dl('export/json')}" download>${icon('download')}JSON</a>`)}
    <div class="tabs"><button data-htab="history" class="${tab === 'history' ? 'on' : ''}">${tt('Tisztítások')}</button><button data-htab="backups" class="${tab === 'backups' ? 'on' : ''}">${tt('Mentések')}</button></div>
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
      <div class="card stat"><span class="k">${tt('Összesen felszabadítva')}</span><span class="v num">${esc(fmtB(total))}</span></div>
      <div class="card stat"><span class="k">${tt('Tisztítások')}</span><span class="v num">${fmtNum(h.length)}</span></div>
      <div class="card stat"><span class="k">${tt('Törölt fájlok')}</span><span class="v num">${fmtNum(files)}</span></div>
    </div>
    <div class="card">${h.length ? `<div class="card-head"><h3>${tt('Napló')}</h3><div class="right"><button class="btn ghost sm" id="hClr">${icon('trash', 'sm')}${tt('Előzmények törlése')}</button></div></div>
      <div class="table-wrap"><table class="tbl"><thead><tr><th>${tt('Időpont')}</th><th>${tt('Kategóriák')}</th><th class="r">${tt('Felszabadítva')}</th><th class="r">${tt('Fájl')}</th><th>${tt('Mód')}</th></tr></thead><tbody>
      ${h.map(e => `<tr><td class="num w">${esc(e.timestamp)}</td><td class="muted">${esc((e.categories || []).map(label).join(', '))}</td><td class="r num"><b>${esc(e.total_freed)}</b></td><td class="r num">${fmtNum(e.total_files)}</td><td class="w"><span class="chip ${e.auto ? 'ac' : ''}">${tt(e.auto ? 'Ütemezett' : 'Kézi')}</span></td></tr>`).join('')}
      </tbody></table></div>` : empty('history', t('Még nincs előzmény'), t('Az első tisztítás után itt jelenik meg.'))}</div>`;
  const c = $('#hClr');
  if (c) c.onclick = async () => { if (await dialog({ title: t('Előzmények törlése'), text: tt('Az összes korábbi tisztítás naplója törlődik.'), ok: t('Törlés'), danger: true })) { await api('history/clear', {}); S.lastClean = null; renderHistory(); } };
}
async function drawBackups() {
  const r = await api('backups');
  const prof = S.config.profiles[S.config.active_profile];
  $('#histBody').innerHTML = `<div class="card">
    <div class="card-head"><div class="tile-ic">${icon('archive')}</div><div><h3>${tt('Törlés előtti mentések')}</h3><p class="sub">${prof.auto_backup ? tt('Bekapcsolva · legfeljebb {mb} MB / mentés, az utolsó {k} marad meg', { mb: prof.backup_max_mb, k: prof.backup_keep }) : tt('Kikapcsolva — a Beállításokban kapcsolható be')}</p></div>
      <div class="right"><button class="btn sm" id="bkOpen">${icon('folder-open', 'sm')}${tt('Mappa megnyitása')}</button></div></div>
    ${r.backups.length ? r.backups.map(b => `<div class="list-item">${icon('archive')}<div><div class="t mono">${esc(b.name)}</div><div class="d">${esc(b.date)} · ${esc(fmtB(b.size))}</div></div>
      <div class="row"><a class="btn sm" href="${dl('backups/file/' + encodeURIComponent(b.name))}" download>${icon('download', 'sm')}${tt('Letöltés')}</a><button class="icon-btn danger" data-bkdel="${esc(b.name)}" title="${tt('Törlés')}">${icon('trash-2')}</button></div></div>`).join('')
      : empty('archive', t('Nincs mentés'), t('Bekapcsolt mentésnél minden tisztítás előtt egy ZIP készül a törlendő fájlokból.'))}</div>`;
  $('#bkOpen').onclick = () => api('backups/open', {});
  $$('[data-bkdel]').forEach(b => b.onclick = async () => { await api('backups/delete', { name: b.dataset.bkdel }); drawBackups(); });
}

/* ── BEÁLLÍTÁSOK ─────────────────────────────────────────────────────────── */
const ACCENTS = ['#2bb8e8', '#4f8cff', '#8b6cff', '#3ccf8a', '#ff8a3d', '#f2557a'];
function renderSettings() {
  const cfg = S.config, pid = cfg.active_profile, prof = cfg.profiles[pid];
  const profiles = Object.entries(cfg.profiles);
  const u = S.update, svc = cfg.service || {};
  const win = S.boot.system.is_windows;
  $('#page-settings').innerHTML = `
    ${head(t('Beállítások'), t('Megjelenés, nyelv, profilok, mentések, riport és frissítések.'))}
    <div class="card"><h3>${tt('Megjelenés')}</h3><p class="sub">${tt('A kiemelőszín profilonként tárolódik.')}</p>
      <div class="setting"><div class="t">${tt('Nyelv')}</div><select id="stLang"><option value="auto">${tt('Automatikus (a Windows nyelve)')}</option><option value="hu">Magyar</option><option value="en">English</option></select></div>
      <div class="setting"><div class="t">${tt('Téma')}</div><div class="seg" id="stTheme">${[['system', 'Rendszer'], ['dark', 'Sötét'], ['light', 'Világos']].map(([v, l]) => `<button data-v="${v}" class="${cfg.theme === v ? 'on' : ''}">${tt(l)}</button>`).join('')}</div></div>
      <div class="setting"><div class="t">${tt('Kiemelőszín')}</div><div class="swatches">${ACCENTS.map(a => `<button data-ac="${a}" class="${prof.accent === a ? 'on' : ''}" style="background:${a}" title="${a}"></button>`).join('')}</div></div>
      ${win && S.boot.native ? `<div class="setting"><div><div class="t">${tt('Bezáráskor a tálcára kerüljön')}</div><div class="d">${tt('Az ablak bezárása után a PyCleaner a tálcán fut tovább (gyors tisztítás, ütemező). Kilépés: jobb klikk a tálcaikonon.')}</div></div><input type="checkbox" class="switch" id="stTray" ${cfg.close_to_tray ? 'checked' : ''}></div>` : ''}
    </div>
    <div class="card"><div class="card-head"><div><h3>${tt('Profil: {n}', { n: profName(prof) })}</h3><p class="sub">${tt('Külön profil tartozhat például a saját és a családi géphez, saját mappákkal.')}</p></div>
      <div class="right"><select id="stProf">${profiles.map(([id, p]) => `<option value="${esc(id)}" ${id === pid ? 'selected' : ''}>${esc(profName(p))}${p.has_password ? ' 🔒' : ''}</option>`).join('')}</select>
      <button class="btn sm" id="stNew">${icon('user', 'sm')}${tt('Új profil')}</button>${pid !== 'default' ? `<button class="btn danger sm" id="stDel" title="${tt('Profil törlése')}">${icon('trash-2', 'sm')}</button>` : ''}</div></div>
      <div class="setting"><div><div class="t">${tt('Profil neve')}</div></div><input type="text" id="stName" value="${esc(profName(prof))}" maxlength="40" style="width:260px"></div>
      <div class="setting"><div><div class="t">${tt('Profiljelszó')}</div><div class="d">${tt(prof.has_password ? 'Be van állítva. Üresen mentve törlődik.' : 'Váltáskor kéri. Csak a profilváltást védi, nem titkosít.')}</div></div>
        <div class="row"><input type="password" id="stPw" placeholder="${tt(prof.has_password ? 'új jelszó' : 'nincs jelszó')}" style="width:180px" autocomplete="new-password"><button class="btn sm" id="stPwSave">${tt('Mentés')}</button></div></div>
      <div class="setting"><div><div class="t">${tt('Mentés törlés előtt')}</div><div class="d">${tt('Tisztítás előtt ZIP-be menti a törlendő fájlokat. Gyorsítótáraknál ritkán kell, de biztonságot ad.')}</div></div><input type="checkbox" class="switch" id="stBk" ${prof.auto_backup ? 'checked' : ''}></div>
      <div class="setting"><div><div class="t">${tt('Mentés mérete és száma')}</div><div class="d">${tt('Ennél nagyobb mentés nem készül; a régebbiek automatikusan törlődnek.')}</div></div>
        <div class="row"><input type="number" id="stBkMb" value="${prof.backup_max_mb}" min="10" max="10000" style="width:96px"><span class="muted">${tt('MB, utolsó')}</span><input type="number" id="stBkKeep" value="${prof.backup_keep}" min="1" max="100" style="width:72px"><span class="muted">${tt('db')}</span></div></div>
      <div class="setting" style="align-items:start"><div><div class="t">${tt('Egyéni mappák')}</div><div class="d">${tt('Ezek teljes tartalmát üríti az „Egyéni mappák” kategória. Rendszer- és személyes mappát nem fogad el.')}</div></div>
        <div style="min-width:min(420px,100%)"><div class="tags">${prof.custom_dirs.map((d, i) => `<span class="tag">${esc(d)}<button data-rmdir="${i}" title="${tt('Eltávolítás')}">${icon('x', 'sm')}</button></span>`).join('') || `<span class="faint">${tt('Nincs megadva')}</span>`}</div>
          <div class="row">${pathPicker('stDir', '')}<button class="btn" id="stDirAdd">${tt('Hozzáadás')}</button></div></div></div>
    </div>
    ${win ? `<div class="card"><div class="card-head"><div class="tile-ic">${icon('file-text')}</div><div><h3>${tt('Gépállapot-riport fejléce')}</h3><p class="sub">${tt('Szervizeléshez: a nyomtatható riport tetején és alján ezek jelennek meg. Üresen hagyva nincs fejléc.')}</p></div></div>
      <div class="setting"><div class="t">${tt('Szerviz / cég neve')}</div><input type="text" id="svName" value="${esc(svc.name || '')}" maxlength="80" style="width:360px;max-width:100%"></div>
      <div class="setting" style="align-items:start"><div class="t">${tt('Elérhetőség')}</div><textarea id="svContact" rows="2" maxlength="300" style="width:360px;max-width:100%">${esc(svc.contact || '')}</textarea></div>
      <div class="setting" style="align-items:start"><div><div class="t">${tt('Megjegyzés a riport alján')}</div><div class="d">${tt('Például garancia, következő karbantartás, ajánlott szolgáltatás.')}</div></div><textarea id="svNote" rows="3" maxlength="1000" style="width:360px;max-width:100%">${esc(svc.note || '')}</textarea></div>
    </div>` : ''}
    <div class="card"><div class="card-head"><div class="tile-ic">${icon('download')}</div><div><h3>${tt('Frissítések')}</h3><p class="sub">${u ? (u.ok ? (u.newer ? tt('Új verzió érhető el: {v}', { v: u.latest }) : tt('A legfrissebb verziót használod ({v}).', { v: u.current })) : tt('A legutóbbi ellenőrzés nem sikerült (nincs internet?).')) : tt('Telepített verzió: {v}', { v: S.boot.version })}</p></div>
      <div class="right">${u?.newer ? `<button class="btn primary sm" data-open-release>${tt('Letöltés')}</button>` : ''}<button class="btn sm" id="stUpd">${icon('refresh-cw', 'sm')}${tt('Ellenőrzés')}</button></div></div>
      <div class="setting"><div><div class="t">${tt('Indításkor ellenőrizze')}</div><div class="d">${tt('Csak a GitHubon közzétett legújabb verziószámot kérdezi le, adatot nem küld.')}</div></div><input type="checkbox" class="switch" id="stUpdAuto" ${cfg.check_updates ? 'checked' : ''}></div>
    </div>
    <div class="card"><div class="card-head"><img src="/static/logo.svg" width="38" height="38" alt=""><div><h3>PyCleaner ${esc(S.boot.version)}</h3><p class="sub">${tt('Nyílt forráskódú (MIT)')} · <a href="#" data-open-release>GitHub</a></p></div></div>
      <dl class="kv"><dt>${tt('Adatok helye')}</dt><dd class="mono" title="${esc(S.boot.data_dir)}">${esc(S.boot.data_dir)}</dd><dt>Python</dt><dd>${esc(S.boot.system.python)}</dd><dt>${tt('Ablak')}</dt><dd>${tt(S.boot.native ? 'natív (WebView2)' : 'böngésző')}</dd></dl></div>`;

  const saveProf = async (changes, msg) => { S.config = await api('config/profile', changes); applyTheme(); sideState(); renderSettings(); toast(msg || t('Mentve'), 'ok', 1800); };
  const setOpt = async (key, value) => { S.config = await api('config/option', { key, value }); };
  $('#stLang').value = cfg.language || 'auto';
  $('#stLang').onchange = async e => {
    await setOpt('language', e.target.value);
    location.reload();   /* a szerveroldali szövegek (kategóriák stb.) is az új nyelven jöjjenek */
  };
  $$('#stTheme button').forEach(b => b.onclick = async () => { await setOpt('theme', b.dataset.v); applyTheme(); renderSettings(); });
  $$('[data-ac]').forEach(b => b.onclick = () => saveProf({ accent: b.dataset.ac }, t('Kiemelőszín mentve')));
  const tray = $('#stTray'); if (tray) tray.onchange = async e => { await setOpt('close_to_tray', e.target.checked); toast(t('Mentve'), 'ok', 1500); };
  $('#stName').onchange = e => saveProf({ name: e.target.value });
  $('#stPwSave').onclick = () => saveProf({ password: $('#stPw').value }, $('#stPw').value ? t('Jelszó beállítva') : t('Jelszó törölve'));
  $('#stBk').onchange = e => saveProf({ auto_backup: e.target.checked });
  $('#stBkMb').onchange = e => saveProf({ backup_max_mb: Number(e.target.value) });
  $('#stBkKeep').onchange = e => saveProf({ backup_keep: Number(e.target.value) });
  $$('[data-rmdir]').forEach(b => b.onclick = () => { const d = [...prof.custom_dirs]; d.splice(Number(b.dataset.rmdir), 1); saveProf({ custom_dirs: d }); });
  $('#stDirAdd').onclick = async () => {
    const r = await api('config/validate_dir', { path: $('#stDir').value });
    if (!r.ok) return toast(r.msg, 'err');
    await saveProf({ custom_dirs: [...prof.custom_dirs, r.path] }, t('Mappa hozzáadva'));
    refreshCats();
  };
  if (win) {
    const saveSvc = async () => { await setOpt('service', { name: $('#svName').value, contact: $('#svContact').value, note: $('#svNote').value }); toast(t('Mentve'), 'ok', 1500); };
    ['#svName', '#svContact', '#svNote'].forEach(id => { $(id).onchange = saveSvc; });
  }
  $('#stProf').onchange = e => switchProfile(e.target.value);
  $('#stNew').onclick = async () => {
    const name = await dialog({ title: t('Új profil'), text: tt('Add meg az új profil nevét.'), ok: t('Létrehozás'), input: { placeholder: t('pl. Családi gép') } });
    if (name) { S.config = await api('config/profile/new', { name }); applyTheme(); sideState(); renderSettings(); refreshCats(); }
  };
  const del = $('#stDel');
  if (del) del.onclick = async () => {
    if (!await dialog({ title: t('Profil törlése'), text: tt('Törlöd a(z) „{n}” profilt?', { n: prof.name }), ok: t('Törlés'), danger: true })) return;
    const r = await api('config/profile/delete', { id: pid }); S.config = r.config; applyTheme(); sideState(); renderSettings(); refreshCats();
  };
  $('#stUpd').onclick = e => busy(e.currentTarget, async () => { S.update = await api('update'); sideState(); renderSettings(); });
  $('#stUpdAuto').onchange = e => setOpt('check_updates', e.target.checked);
}

async function switchProfile(id) {
  const p = S.config.profiles[id];
  let password = '';
  if (p.has_password) {
    password = await dialog({ title: t('Profil: {n}', { n: p.name }), text: tt('Ez a profil jelszóval védett.'), ok: t('Váltás'), input: { type: 'password', placeholder: t('Jelszó') } });
    if (password === null) { if ($('#stProf')) $('#stProf').value = S.config.active_profile; return; }
  }
  const r = await api('config/profile/switch', { id, password });
  if (!r.ok) { toast(t('Hibás jelszó'), 'err'); if ($('#stProf')) $('#stProf').value = S.config.active_profile; return; }
  S.config = r.config; applyTheme(); sideState(); refreshCats();
  toast(t('Aktív profil: {n}', { n: p.name }), 'ok', 2000);
  if (isActive('settings')) renderSettings();
}
$('#profileBtn').addEventListener('click', async () => {
  const ids = Object.keys(S.config.profiles);
  if (ids.length < 2) return go('settings');
  switchProfile(ids[(ids.indexOf(S.config.active_profile) + 1) % ids.length]);
});
async function refreshCats() {
  S.cats = (await api('bootstrap')).categories;
  S.selected = new Set([...S.selected].filter(id => S.cats.some(c => c.id === id && !c.locked)));
}

/* ── kilépés ─────────────────────────────────────────────────────────────── */
function showGoodbye() { $('#goodbye').hidden = false; }
$('#exitBtn').addEventListener('click', async () => {
  if (!await dialog({ title: t('Kilépés'), text: tt('Leállítod a PyCleanert? A programon belüli ütemező is leáll.'), ok: t('Kilépés') })) return;
  try { await api('exit', {}); } catch { /* a szerver már leállhatott */ }
  showGoodbye();
});

/* ── indulás ─────────────────────────────────────────────────────────────── */
(async function init() {
  try {
    S.boot = await api('bootstrap');
  } catch (e) {
    document.body.innerHTML = `<div class="goodbye"><h2>Nem érem el a PyCleaner szolgáltatást / Cannot reach PyCleaner</h2><p>${esc(e.message)}</p></div>`;
    return;
  }
  await setLanguage(S.boot.lang);
  S.cats = S.boot.categories; S.config = S.boot.config; S.schedule = S.boot.schedule;
  S.selected = new Set(S.cats.filter(c => c.default && !c.locked).map(c => c.id));
  applyTheme(); sideState();
  api('history').then(h => { S.lastClean = h[0] || null; if (isActive('overview')) renderOverview(); }).catch(() => {});
  api('health/last').then(h => { if (h) { S.health = h; sideState(); if (isActive('overview')) renderOverview(); } }).catch(() => {});
  go(location.hash.slice(1) || 'overview');
  startMonitor();
  if (S.config.check_updates) api('update').then(u => { S.update = u; sideState(); if (isActive('overview')) renderOverview(); }).catch(() => {});
})();
