/* AIHive Leadership Expedition — demo UI controller. All logic lives in sim.js. */
(function () {
  'use strict';
  var Sim = window.AIHiveSim;
  var $ = function (id) { return document.getElementById(id); };
  var mapEl = $('sim-map'), statsEl = $('sim-stats'), logEl = $('sim-log'), stageEl = $('sim-stage');
  var reportSec = $('report'), reportBody = $('report-body');
  var ui = { view: 'intro', state: Sim.createState(), selected: null, rationale: '', last: null };

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function signed(n, unit) { return (n > 0 ? '+' : n < 0 ? '−' : '±') + Math.abs(n) + (unit || ''); }

  // ---------- Map ----------
  function pt(id) { return id === 'start' ? Sim.MAP.start : id === 'finish' ? Sim.MAP.finish : Sim.MAP.checkpoints[id]; }
  function pathD(ids) { return ids.map(function (id, i) { var p = pt(id); return (i ? 'L' : 'M') + p.x + ' ' + p.y; }).join(' '); }
  function visited(state) {
    var seq = ['start'];
    state.decisions.forEach(function (d) {
      d.after.checkpoints.forEach(function (c) { if (seq.indexOf(c) === -1) seq.push(c); });
    });
    if (state.finished) seq.push('finish');
    return seq;
  }
  var ROUTE_STYLE = { ridge: ['#fbbf24', 'Ridge · 35 min · CP2'], valley: ['#34d399', 'Valley · 30 min · CP1'], scout: ['#60a5fa', 'Scout · 40 min · CP1'] };

  function renderMap(state) {
    var route = state.flags.route;
    var afterEvent = state.step >= 3;
    var s = [];
    s.push('<svg viewBox="0 0 800 520" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Illustrative terrain map of a simulated training environment with start, finish, five checkpoints and three alternative routes">');
    s.push('<defs><linearGradient id="g1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2563eb"/><stop offset="1" stop-color="#7c3aed"/></linearGradient>' +
      '<radialGradient id="bg" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="#13243a"/><stop offset="1" stop-color="#0a1220"/></radialGradient>' +
      '<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="rgba(148,163,184,.07)"/></pattern>' +
      '<filter id="blur"><feGaussianBlur stdDeviation="14"/></filter></defs>');
    s.push('<rect width="800" height="520" fill="url(#bg)"/><rect width="800" height="520" fill="url(#grid)"/>');
    // forest patches
    s.push('<g fill="rgba(52,211,153,.07)"><path d="M120 300c60-40 140-20 170 30s-40 110-110 100-120-90-60-130z"/><path d="M480 420c50-30 150-20 190 20s-30 80-110 70-120-60-80-90z"/><path d="M380 90c40-30 120-20 140 20s-40 70-90 60-80-50-50-80z"/></g>');
    // contours: ridge & summit
    s.push('<g fill="none" stroke="rgba(167,139,250,.28)" stroke-width="1.3">');
    [70, 52, 36, 20].forEach(function (r) { s.push('<ellipse cx="300" cy="185" rx="' + (r * 1.9) + '" ry="' + r + '" transform="rotate(-18 300 185)"/>'); });
    [62, 44, 28, 14].forEach(function (r) { s.push('<ellipse cx="650" cy="170" rx="' + (r * 1.5) + '" ry="' + r + '" transform="rotate(12 650 170)"/>'); });
    s.push('</g>');
    // lake and river
    s.push('<ellipse cx="560" cy="320" rx="88" ry="42" fill="rgba(59,130,246,.32)" stroke="rgba(96,165,250,.6)"/>');
    s.push('<text x="560" y="325" text-anchor="middle" fill="rgba(191,219,254,.75)" font-size="12" font-style="italic">Lake</text>');
    s.push('<path d="M330 520C360 470 400 450 420 412S455 340 486 330" fill="none" stroke="rgba(96,165,250,.55)" stroke-width="5" stroke-linecap="round"/>');
    // footbridge
    s.push('<g transform="translate(404 424) rotate(-35)"><rect x="-16" y="-5" width="32" height="10" rx="2" fill="#a16207" opacity=".85"/></g>');
    if (afterEvent) s.push('<g transform="translate(404 424)"><circle r="13" fill="rgba(251,113,133,.25)" stroke="#fb7185"/><path d="M-6-6L6 6M6-6L-6 6" stroke="#fb7185" stroke-width="2.5"/></g><text x="404" y="458" text-anchor="middle" fill="#fda4af" font-size="11" font-weight="700">BRIDGE CLOSED</text>');
    // candidate routes (before D1) or chosen route
    Object.keys(Sim.MAP.routes).forEach(function (k) {
      var chosen = route === k;
      if (route && !chosen) return;
      var st = ROUTE_STYLE[k];
      s.push('<path d="' + pathD(Sim.MAP.routes[k]) + '" fill="none" stroke="' + st[0] + '" stroke-width="' + (chosen ? 2 : 2.2) + '" stroke-dasharray="7 6" opacity="' + (chosen ? .55 : .85) + '"/>');
    });
    if (!route) {
      s.push('<g font-size="11.5" font-weight="600">' +
        '<text x="150" y="250" fill="#fbbf24">' + ROUTE_STYLE.ridge[1] + '</text>' +
        '<text x="250" y="470" fill="#34d399">' + ROUTE_STYLE.valley[1] + '</text>' +
        '<text x="300" y="330" fill="#60a5fa">' + ROUTE_STYLE.scout[1] + '</text></g>');
    }
    // D4 option previews
    if (ui.view === 'decide' && state.step === 3) {
      s.push('<path d="' + pathD([lastPoint(state), 'CP5', 'finish']) + '" fill="none" stroke="#c084fc" stroke-width="2" stroke-dasharray="3 6"/>');
    }
    // travelled path
    var seq = visited(state);
    if (seq.length > 1) s.push('<path d="' + pathD(seq) + '" fill="none" stroke="url(#g1)" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>');
    // fog
    if (afterEvent) s.push('<g filter="url(#blur)" opacity=".55"><ellipse cx="300" cy="170" rx="150" ry="70" fill="#e2e8f0"/></g><text x="300" y="120" text-anchor="middle" fill="#e2e8f0" font-size="12" font-weight="700" letter-spacing="2">FOG</text>');
    // checkpoints
    Object.keys(Sim.MAP.checkpoints).forEach(function (id) {
      var c = Sim.MAP.checkpoints[id], got = state.checkpoints.indexOf(id) !== -1;
      s.push('<g transform="translate(' + c.x + ' ' + c.y + ')">' +
        '<circle r="17" fill="' + (got ? 'url(#g1)' : 'rgba(10,14,26,.8)') + '" stroke="#c084fc" stroke-width="2.5"/>' +
        '<text y="4.5" text-anchor="middle" fill="#fff" font-size="12" font-weight="700">' + (got ? '✓' : id.slice(2)) + '</text>' +
        '<text y="34" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="600">' + id + ' · ' + c.points + ' pts</text></g>');
    });
    var st0 = Sim.MAP.start, fin = Sim.MAP.finish;
    s.push('<g transform="translate(' + st0.x + ' ' + st0.y + ')"><path d="M0-18L16 10H-16Z" fill="none" stroke="#f472b6" stroke-width="3"/><text y="30" text-anchor="middle" fill="#fbcfe8" font-size="11" font-weight="700">START</text></g>');
    s.push('<g transform="translate(' + fin.x + ' ' + fin.y + ')"><circle r="16" fill="' + (state.finished ? 'rgba(244,114,182,.35)' : 'none') + '" stroke="#f472b6" stroke-width="3"/><circle r="9" fill="none" stroke="#f472b6" stroke-width="3"/><text y="34" text-anchor="middle" fill="#fbcfe8" font-size="11" font-weight="700">FINISH</text></g>');
    // north arrow and banner
    s.push('<g transform="translate(760 470)"><path d="M0-22L7 4 0-2-7 4Z" fill="#cbd5e1"/><text y="18" text-anchor="middle" fill="#cbd5e1" font-size="11" font-weight="700">N</text></g>');
    s.push('<rect x="10" y="10" width="420" height="24" rx="6" fill="rgba(10,14,26,.8)" stroke="rgba(251,191,36,.5)"/><text x="20" y="26" fill="#fbbf24" font-size="11" font-weight="700" letter-spacing=".5">SIMULATED TRAINING ENVIRONMENT · NOT A REAL MAP</text>');
    s.push('</svg>');
    mapEl.innerHTML = s.join('');
  }
  function lastPoint(state) { var v = visited(state); return v[v.length - 1]; }

  // ---------- Stats ----------
  function renderStats(state) {
    var t = state.timeRemaining, e = state.energy;
    var tClass = t < 0 ? 'bad' : t < 30 ? 'warn' : '';
    var eClass = e < 25 ? 'bad' : e < 40 ? 'warn' : '';
    statsEl.innerHTML =
      stat('Time remaining', '<span data-testid="stat-time">' + t + '</span> min', tClass, Math.max(0, t) / Sim.START.timeRemaining * 100) +
      stat('Team energy', '<span data-testid="stat-energy">' + e + '</span>%', eClass, e) +
      stat('Supply kits', '<span data-testid="stat-supplies">' + state.supplies + '</span> / ' + Sim.START.supplies, '', state.supplies / Sim.START.supplies * 100) +
      stat('Checkpoints', '<span data-testid="stat-cps">' + state.checkpoints.length + '</span> / 5', '', state.checkpoints.length / 5 * 100) +
      stat('Mission points', '<span data-testid="stat-points">' + state.points + '</span>', '', null) +
      stat('Decisions made', '<span data-testid="stat-decisions">' + state.decisions.length + '</span> / 4', '', state.decisions.length / 4 * 100);
    logEl.innerHTML = state.decisions.map(function (d) {
      return '<li><span class="k" style="color:#e2e8f0">D' + d.number + ':</span> ' + esc(d.label) + (d.rationale ? ' <span title="Rationale recorded">✎</span>' : '') + '</li>';
    }).join('');
  }
  function stat(label, value, cls, pct) {
    return '<div class="stat"><small>' + label + '</small><b class="' + cls + '">' + value + '</b>' + (pct === null ? '' : '<div class="meter"><i style="width:' + Math.max(0, Math.min(100, pct)) + '%"></i></div>') + '</div>';
  }
  function progress(state, current) {
    var h = '<div class="progress" aria-hidden="true">';
    for (var i = 0; i < 4; i++) h += '<span class="' + (i < state.step ? 'done' : i === current ? 'now' : '') + '"></span>';
    return h + '</div>';
  }

  // ---------- Stage ----------
  function renderStage() {
    var st = ui.state, h = '';
    if (ui.view === 'intro') {
      h += '<span class="kicker">Mission briefing</span><h2>Lead your team through Kestrel Forest</h2>';
      h += '<p class="prompt">You have <b>' + Sim.START.timeRemaining + ' minutes</b>, <b>' + Sim.START.supplies + ' supply kits</b> and a team at full energy. Five checkpoints are worth different points. Finish on time for a bonus; finishing late costs 3 points per minute.</p>';
      h += '<div class="team">' + Sim.TEAM.map(function (m) { return '<div><b>' + m.name + '</b> — ' + m.note + '</div>'; }).join('') + '</div>';
      h += '<p class="note" style="margin:1rem 0">There is no single right answer. Each option trades time, energy, information and people differently. Your report is built only from the choices you make here.</p>';
      h += '<button class="btn btn-primary" type="button" id="sim-start" data-testid="sim-start">Start the expedition</button>';
    } else if (ui.view === 'decide') {
      var dec = Sim.DECISIONS[st.step];
      h += progress(st, st.step);
      h += '<span class="kicker">Decision ' + dec.number + ' of 4</span><h2>' + esc(dec.title) + '</h2><p class="prompt">' + esc(dec.prompt) + '</p>';
      if (dec.id === 'd4') h += '<p class="note note-amber" style="margin-top:.8rem">You have <b>' + st.timeRemaining + ' minutes</b> left and team energy is <b>' + st.energy + '%</b>.</p>';
      h += '<div class="opts" role="group" aria-label="Options">';
      dec.options.forEach(function (o) {
        h += '<button type="button" class="opt" data-opt="' + o.id + '" data-testid="opt-' + o.id + '" aria-pressed="' + (ui.selected === o.id) + '"><b>' + esc(o.label) + '</b><span>' + esc(o.summary) + '</span><em>Trade-off: ' + esc(o.tradeoff) + '</em></button>';
      });
      h += '</div>';
      h += '<div class="field"><label for="sim-why">Why this choice? <span class="hint">(optional — shown in your report)</span></label><textarea id="sim-why" data-testid="sim-why" maxlength="500" placeholder="A sentence on your reasoning…">' + esc(ui.rationale) + '</textarea></div>';
      h += '<div class="actions" style="margin-top:1rem"><span style="font-size:.85rem;color:var(--slate-400)">' + (ui.selected ? 'Ready to commit.' : 'Select an option to continue.') + '</span><button class="btn btn-primary" type="button" id="sim-confirm" data-testid="sim-confirm"' + (ui.selected ? '' : ' disabled') + '>Confirm decision</button></div>';
    } else if (ui.view === 'result') {
      var d = st.decisions[st.decisions.length - 1];
      h += progress(st, -1);
      h += '<span class="kicker">Decision ' + d.number + ' · consequences</span><h2>You chose: ' + esc(d.label) + '</h2>';
      h += '<div class="consequence" data-testid="consequence"><ul>' + d.consequence.map(function (c) { return '<li>' + esc(c) + '</li>'; }).join('') + '</ul>';
      h += '<div class="deltas">' + delta(d.delta.time, ' min time', true) + delta(d.delta.energy, '% energy', true) + (d.delta.supplies ? delta(d.delta.supplies, ' supply kit', true) : '') + delta(d.delta.points, ' pts', true) + (d.delta.checkpoints ? delta(d.delta.checkpoints, ' checkpoint', true) : '') + '</div></div>';
      if (d.rationale) h += '<p style="font-size:.88rem;color:var(--slate-400)">Your rationale: “' + esc(d.rationale) + '”</p>';
      h += '<div class="actions" style="margin-top:1rem"><span></span>' + (st.finished
        ? '<button class="btn btn-primary" type="button" id="sim-report" data-testid="sim-report">View your Leadership Intelligence Report</button>'
        : '<button class="btn btn-primary" type="button" id="sim-next" data-testid="sim-next">Next decision →</button>') + '</div>';
    } else if (ui.view === 'done') {
      h += progress(st, -1);
      h += '<span class="kicker">Mission complete</span><h2>' + (st.late ? 'Finished ' + st.lateMinutes + ' minutes late' : 'Finished on time') + ' with ' + st.points + ' points</h2>';
      h += '<p class="prompt">Your illustrative Leadership Intelligence Report is below. Try again with different choices to see how outcomes and indicators change.</p>';
      h += '<div class="actions" style="margin-top:1rem"><a class="btn btn-secondary" href="#report">Jump to report</a><button class="btn btn-primary" type="button" id="sim-restart2">↺ Restart simulation</button></div>';
    }
    stageEl.innerHTML = h;
    bindStage();
  }
  function delta(n, unit, show) { if (!show) return ''; var cls = n > 0 ? 'pos' : n < 0 ? 'neg' : ''; return '<span class="delta ' + cls + '">' + signed(n, unit) + '</span>'; }

  function bindStage() {
    var b;
    if ((b = $('sim-start'))) b.onclick = function () { ui.view = 'decide'; render(); focusStage(); };
    stageEl.querySelectorAll('.opt').forEach(function (btn) {
      btn.onclick = function () { ui.selected = btn.getAttribute('data-opt'); var w = $('sim-why'); ui.rationale = w ? w.value : ''; renderStage(); renderMap(ui.state); };
    });
    if ((b = $('sim-why'))) b.oninput = function (ev) { ui.rationale = ev.target.value; };
    if ((b = $('sim-confirm'))) b.onclick = function () {
      var dec = Sim.DECISIONS[ui.state.step];
      ui.state = Sim.applyDecision(ui.state, dec.id, ui.selected, ui.rationale);
      ui.selected = null; ui.rationale = ''; ui.view = 'result'; render(); focusStage();
    };
    if ((b = $('sim-next'))) b.onclick = function () { ui.view = 'decide'; render(); focusStage(); };
    if ((b = $('sim-report'))) b.onclick = function () { ui.view = 'done'; render(); renderReport(); reportSec.scrollIntoView({ behavior: 'smooth' }); };
    if ((b = $('sim-restart2'))) b.onclick = restart;
  }
  function focusStage() { if (window.innerWidth < 980) stageEl.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  function restart() {
    ui = { view: 'intro', state: Sim.createState(), selected: null, rationale: '' };
    reportSec.hidden = true; reportBody.innerHTML = '';
    render(); $('sim-app').scrollIntoView({ behavior: 'smooth' });
  }
  $('sim-restart').onclick = restart;

  // ---------- Report ----------
  function radar(dims) {
    var cx = 170, cy = 165, R = 115, n = dims.length, h = [];
    function p(i, v) { var a = -Math.PI / 2 + i * 2 * Math.PI / n; return [cx + Math.cos(a) * R * v / 100, cy + Math.sin(a) * R * v / 100]; }
    h.push('<svg class="radar" viewBox="-95 -5 530 340" role="img" aria-label="Radar chart of illustrative simulation indicators">');
    [25, 50, 75, 100].forEach(function (v) {
      h.push('<polygon points="' + dims.map(function (_, i) { return p(i, v).join(','); }).join(' ') + '" fill="none" stroke="rgba(148,163,184,' + (v === 50 ? .45 : .18) + ')"' + (v === 50 ? ' stroke-dasharray="4 4"' : '') + '/>');
    });
    dims.forEach(function (d, i) { var q = p(i, 100); h.push('<line x1="' + cx + '" y1="' + cy + '" x2="' + q[0] + '" y2="' + q[1] + '" stroke="rgba(148,163,184,.18)"/>'); });
    h.push('<polygon points="' + dims.map(function (d, i) { return p(i, d.score).join(','); }).join(' ') + '" fill="rgba(124,58,237,.35)" stroke="#a78bfa" stroke-width="2"/>');
    dims.forEach(function (d, i) {
      var q = p(i, d.score); h.push('<circle cx="' + q[0] + '" cy="' + q[1] + '" r="3.5" fill="#fff"/>');
      var l = p(i, 128), anchor = Math.abs(l[0] - cx) < 10 ? 'middle' : l[0] > cx ? 'start' : 'end';
      h.push('<text x="' + l[0] + '" y="' + (l[1] + 4) + '" text-anchor="' + anchor + '">' + esc(d.label) + ' (' + d.score + ')</text>');
    });
    h.push('</svg>');
    return h.join('');
  }

  function renderReport() {
    var r = Sim.buildReport(ui.state), s = r.summary, h = [];
    h.push('<div class="panel" style="border-color:rgba(124,58,237,.45)"><span class="badge badge-sim">Illustrative · Simulated training environment</span>');
    h.push('<h2 style="font-size:clamp(1.5rem,3vw,2.1rem);margin:.8rem 0 .4rem">Leadership Intelligence Report</h2>');
    h.push('<p style="color:var(--slate-400);font-size:.92rem" data-testid="report-disclaimer">' + esc(r.disclaimer) + '</p>');
    h.push('<div class="summary-stats" style="margin-top:1.2rem">' +
      stat('Mission points', '<span data-testid="report-points">' + s.points + '</span>', '', null) +
      stat('Checkpoints', s.checkpointCount + ' / 5', '', null) +
      stat('Finish', s.onTime ? 'On time (' + s.timeRemaining + ' min spare)' : s.lateMinutes + ' min late', s.onTime ? '' : 'bad', null) +
      stat('Team energy at finish', s.energy + '%', s.energy < 25 ? 'bad' : '', null) + '</div>');
    h.push('<div class="no-print" style="display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1.2rem"><button class="btn btn-secondary btn-sm" type="button" id="rep-print">Print / save as PDF</button><button class="btn btn-secondary btn-sm" type="button" id="rep-restart">↺ Restart simulation</button></div></div>');

    h.push('<div class="report-grid" style="margin-bottom:1.5rem"><div class="panel"><h3>Illustrative simulation indicators</h3>' + radar(r.dimensions) + '<p style="font-size:.8rem;color:var(--slate-500)">Dashed ring = baseline (' + r.baseline + '). Scale 0–100.</p></div>');
    h.push('<div class="panel"><h3>Indicator scores</h3><div class="bars" data-testid="report-bars">' + r.dimensions.map(function (d) {
      return '<div class="bar-row"><span>' + esc(d.label) + '</span><div class="meter"><i style="width:' + d.score + '%"></i></div><b>' + d.score + '</b></div>';
    }).join('') + '</div><p class="note" style="margin-top:1.2rem">Each indicator starts at ' + r.baseline + '. Fixed rubric values for each choice, plus written rationales and the mission outcome, move it up or down. The full calculation is listed below.</p></div></div>');

    h.push('<div class="panel"><h3>Decision history</h3><div class="tbl-wrap"><table class="tbl" data-testid="report-history"><thead><tr><th>#</th><th>Decision</th><th>Your choice</th><th>Rationale</th><th>Result</th></tr></thead><tbody>' +
      r.history.map(function (d) {
        return '<tr><td>' + d.number + '</td><td>' + esc(d.title) + '</td><td class="k">' + esc(d.choice) + '</td><td>' + (d.rationale ? '“' + esc(d.rationale) + '”' : '<span style="color:var(--slate-500)">—</span>') + '</td><td class="num">' + signed(d.delta.time, ' min') + ' · ' + signed(d.delta.energy, '% energy') + ' · ' + signed(d.delta.points, ' pts') + '</td></tr>';
      }).join('') + '</tbody></table></div></div>');

    h.push('<div class="report-grid" style="margin-bottom:1.5rem"><div class="panel"><h3>Observed decision patterns</h3><ul class="clean" data-testid="report-patterns">' + r.patterns.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ul><p style="font-size:.8rem;color:var(--slate-500);margin-top:.6rem">Patterns describe only the four choices recorded in this simulation.</p></div>');
    h.push('<div class="panel"><h3>Potential strengths</h3><ul class="clean">' + r.strengths.map(function (x) { return '<li><span class="k">' + esc(x.dimension) + ' · ' + x.score + '</span><br>' + esc(x.evidence) + '</li>'; }).join('') + '</ul>');
    h.push('<h3 style="margin-top:1.2rem">Development opportunities</h3><ul class="clean">' + r.development.map(function (x) { return '<li><span class="k">' + esc(x.dimension) + ' · ' + x.score + '</span><br>' + esc(x.evidence) + '</li>'; }).join('') + '</ul></div></div>');

    h.push('<div class="panel"><h3>Alternative strategies</h3><ul class="clean">' + r.alternatives.map(function (a) {
      return '<li><span class="k">' + esc(a.decision) + '</span> — you chose <b>' + esc(a.chosen) + '</b>.<br>' + a.others.map(function (o) { return '<b>' + esc(o.label) + ':</b> ' + esc(o.tradeoff); }).join('<br>') + '</li>';
    }).join('') + '</ul></div>');

    h.push('<div class="report-grid" style="margin-bottom:1.5rem"><div class="panel"><h3>Personalised reflection questions</h3><ol style="padding-left:1.2rem;color:var(--slate-300);font-size:.93rem">' + r.reflections.map(function (q) { return '<li style="margin:.5rem 0">' + esc(q) + '</li>'; }).join('') + '</ol></div>');
    h.push('<div class="panel"><h3>Suggested 30-day development actions</h3><ul class="clean" data-testid="report-plan">' + r.plan.map(function (p) { return '<li><span class="k">Week ' + p.week + ' · ' + esc(p.dimension) + '</span><br>' + esc(p.action) + '</li>'; }).join('') + '</ul>' +
      '<p class="note" style="margin-top:1rem">In the full program, a professional coach reviews this plan with you, and <a href="https://aihive-coach.onrender.com">AIHive Coach</a> can help you keep it going week by week.</p></div></div>');

    h.push('<div class="panel"><h3>How these indicators were calculated (transparent rubric)</h3><div class="tbl-wrap"><table class="tbl" data-testid="report-rubric"><thead><tr><th>Source</th><th>Indicator</th><th>Change</th><th>Reason</th></tr></thead><tbody>' +
      r.contributions.map(function (c) { return '<tr><td>' + esc(c.source) + '</td><td>' + esc(c.dimension) + '</td><td class="num">' + signed(c.delta) + '</td><td>' + esc(c.reason) + '</td></tr>'; }).join('') +
      '</tbody></table></div><p style="font-size:.8rem;color:var(--slate-500);margin-top:.8rem">No AI was used to generate this demo report. The same choices always produce the same report.</p></div>');

    reportBody.innerHTML = h.join('');
    reportSec.hidden = false;
    $("rep-restart").onclick = restart;
    $("rep-print").onclick = function () { window.print(); };
  }

  function render() { renderMap(ui.state); renderStats(ui.state); renderStage(); }
  render();
}());
