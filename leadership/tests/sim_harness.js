// Runs the simulation engine for pytest. Usage: node sim_harness.js '<json command>'
const path = require('path');
const Sim = require(path.join(__dirname, '..', '..', 'site', 'leadership', 'assets', 'sim.js'));
const cmd = JSON.parse(process.argv[2] || '{}');
const out = {};
function all() {
  const opts = Sim.DECISIONS.map(d => d.options.map(o => o.id));
  const res = [];
  for (const a of opts[0]) for (const b of opts[1]) for (const c of opts[2]) for (const d of opts[3]) {
    const s = Sim.run([a, b, c, d]);
    res.push({ choices: [a, b, c, d], state: s, report: Sim.buildReport(s) });
  }
  return res;
}
try {
  if (cmd.op === 'run') { const s = Sim.run(cmd.choices, cmd.rationales); out.state = s; out.report = Sim.buildReport(s); }
  else if (cmd.op === 'all') { out.runs = all(); }
  else if (cmd.op === 'meta') { out.decisions = Sim.DECISIONS; out.dimensions = Sim.DIMENSIONS; out.start = Sim.START; out.map = Sim.MAP; }
  else if (cmd.op === 'apply') {
    let s = Sim.createState();
    for (const [d, o] of cmd.steps) s = Sim.applyDecision(s, d, o, '');
    out.state = s;
  }
  else if (cmd.op === 'unfinished') { out.report = Sim.buildReport(Sim.createState()); }
} catch (e) { out.error = String(e.message || e); }
process.stdout.write(JSON.stringify(out));
