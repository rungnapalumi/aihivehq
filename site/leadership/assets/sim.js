/*
 * AIHive Leadership Expedition — simulation engine
 * ------------------------------------------------
 * Pure, deterministic logic (no randomness, no clock, no network).
 * The same choices always produce the same state and the same report.
 * Loaded in the browser as window.AIHiveSim and in Node (tests) via require().
 *
 * IMPORTANT: every score produced here is an ILLUSTRATIVE SIMULATION INDICATOR
 * computed from a transparent rubric. It is not a validated measure of
 * leadership competency, personality, psychological traits or real-world
 * leadership effectiveness.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(); }
  else { root.AIHiveSim = factory(); }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var DIMENSIONS = [
    { id: 'strategic', label: 'Strategic Thinking' },
    { id: 'decision', label: 'Decision Making' },
    { id: 'adaptability', label: 'Adaptability' },
    { id: 'delegation', label: 'Delegation' },
    { id: 'communication', label: 'Communication' },
    { id: 'execution', label: 'Execution' }
  ];
  var BASELINE = 50;
  var RATIONALE_MIN_CHARS = 20;

  var START = { timeRemaining: 125, energy: 100, supplies: 3 };

  // Illustrative terrain (SVG coordinates 0..800 x 0..520). Fictional.
  var MAP = {
    start: { x: 80, y: 450, label: 'Start' },
    finish: { x: 720, y: 70, label: 'Finish' },
    checkpoints: {
      CP1: { x: 210, y: 380, points: 10, label: 'CP1', zone: 'Valley edge' },
      CP2: { x: 300, y: 180, points: 20, label: 'CP2', zone: 'North ridge' },
      CP3: { x: 420, y: 400, points: 15, label: 'CP3', zone: 'Footbridge' },
      CP4: { x: 520, y: 250, points: 25, label: 'CP4', zone: 'Lake shore' },
      CP5: { x: 650, y: 170, points: 40, label: 'CP5', zone: 'Summit plateau' }
    },
    routes: {
      ridge: ['start', 'CP2', 'CP4'],
      valley: ['start', 'CP1', 'CP3'],
      scout: ['start', 'CP1', 'CP4']
    }
  };

  var TEAM = [
    { name: 'Mai', note: 'strongest map reader' },
    { name: 'Ken', note: 'fastest over rough ground' },
    { name: 'Priya', note: 'calm under pressure, good with timings' },
    { name: 'Leo', note: 'new to the team, keen to contribute' }
  ];

  var EVENT_IMPACT = { ridge: 28, valley: 12, scout: 8 }; // minutes lost to the D3 event if unmitigated

  var DECISIONS = [
    {
      id: 'd1', number: 1, title: 'Select an initial route and strategy',
      prompt: 'You have 125 minutes, a team of four and five checkpoints worth different points. Which opening strategy do you choose?',
      options: [
        { id: 'ridge', label: 'Ridge Direct', summary: 'Climb the north ridge for a fast line to CP2 (20 pts) and then CP4 (25 pts).',
          tradeoff: 'Fastest route to high-value checkpoints, but steep, tiring and exposed if the weather turns.',
          tags: ['speed', 'risk'], indicators: { strategic: 10, decision: 10, execution: 5 } },
        { id: 'valley', label: 'Valley Trail', summary: 'Follow the valley trail to CP1 (10 pts) and CP3 (15 pts) at a sustainable pace.',
          tradeoff: 'Lower energy cost and predictable, but collects fewer points early and depends on the footbridge.',
          tags: ['safety'], indicators: { strategic: 5, decision: 5, execution: 10 } },
        { id: 'scout', label: 'Scout First', summary: 'Take CP1 (10 pts) and send two teammates ahead to check the lake crossing before committing to CP4.',
          tradeoff: 'Costs time up front, but the team gains information that reduces later surprises.',
          tags: ['information', 'people'], indicators: { strategic: 15, delegation: 10, communication: 5, execution: -5 } }
      ]
    },
    {
      id: 'd2', number: 2, title: 'Allocate responsibilities among team members',
      prompt: 'Mai reads maps well, Ken is fast, Priya is calm with timings and Leo is new. How do you organise the team for the next leg?',
      options: [
        { id: 'command', label: 'Lead from the front', summary: 'You navigate and make every call yourself; the team follows your pace.',
          tradeoff: 'Quick, clear decisions, but you carry the load and the team’s knowledge stays untapped.',
          tags: ['speed', 'control'], indicators: { decision: 10, execution: 10, delegation: -10, communication: -5 } },
        { id: 'specialists', label: 'Specialist roles', summary: 'Mai navigates, Ken scouts ahead, Priya keeps time, Leo manages supplies.',
          tradeoff: 'Uses strengths and builds resilience, but takes a few minutes to set up and coordinate.',
          tags: ['people', 'structure'], indicators: { delegation: 15, communication: 10, strategic: 5 } },
        { id: 'rotate', label: 'Rotate leadership', summary: 'Each teammate, including Leo, leads one section; you coach rather than direct.',
          tradeoff: 'Builds trust and shares the load, but is slower and a small navigation slip is likely.',
          tags: ['people', 'development'], indicators: { delegation: 20, communication: 10, adaptability: 5, execution: -5 } }
      ]
    },
    {
      id: 'd3', number: 3, title: 'Respond to an unexpected change in mission conditions',
      prompt: 'Fog rolls over the ridge and the marshal radios that the footbridge is closed. Leo reports a minor ankle strain. What now?',
      options: [
        { id: 'push', label: 'Push on with the plan', summary: 'Keep the original plan and increase the pace to absorb the delay.',
          tradeoff: 'Protects the plan and momentum, but drains energy and absorbs the full impact of the change.',
          tags: ['speed', 'risk'], indicators: { execution: 10, decision: 5, adaptability: -10 } },
        { id: 'replan', label: 'Re-plan on a safer line', summary: 'Strap Leo’s ankle (uses one supply kit) and re-route on a lower, safer line.',
          tradeoff: 'Reduces risk and protects the team, but costs a supply kit and some time.',
          tags: ['safety', 'adaptability'], indicators: { adaptability: 15, strategic: 5, decision: 5 } },
        { id: 'huddle', label: 'Team huddle', summary: 'Stop for a short huddle so everyone shares what they know before deciding.',
          tradeoff: 'Surfaces information and rests the team, but only pays off if roles or prior scouting give the team something to share.',
          tags: ['people', 'communication'], indicators: { communication: 15, adaptability: 10, delegation: 5, decision: -5 } }
      ]
    },
    {
      id: 'd4', number: 4, title: 'Prioritise objectives under time pressure',
      prompt: 'Time is running down. CP5 on the summit plateau is worth 40 points but is far. What is your priority for the final leg?',
      options: [
        { id: 'summit', label: 'Go for CP5', summary: 'Commit to the 40-point summit checkpoint before the finish (about 45 minutes).',
          tradeoff: 'Highest reward, but a late finish costs 3 points per minute and a tired team (energy below 40%) moves slower.',
          tags: ['ambition', 'risk'], indicators: { strategic: 5, decision: 10 } },
        { id: 'nearest', label: 'Collect the nearest checkpoint', summary: 'Pick up the closest checkpoint you have not visited, then finish (about 30 minutes).',
          tradeoff: 'Balanced gain with moderate time use; leaves the biggest prize on the table.',
          tags: ['balance'], indicators: { strategic: 10, execution: 5 } },
        { id: 'finish', label: 'Head to the finish', summary: 'Go straight to the finish (about 15 minutes) and bank an early-finish bonus.',
          tradeoff: 'Secures the result and protects the team, but forgoes further checkpoints.',
          tags: ['safety', 'execution'], indicators: { decision: 5, execution: 5 } }
      ]
    }
  ];

  var SUMMIT_ENERGY = 40;      // below this energy, CP5 takes 15 min longer
  var LATE_PENALTY_PER_MIN = 3;
  var NEAREST = { ridge: 'CP1', valley: 'CP4', scout: 'CP2' };

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function findDecision(id) { for (var i = 0; i < DECISIONS.length; i++) if (DECISIONS[i].id === id) return DECISIONS[i]; return null; }
  function findOption(dec, id) { for (var i = 0; i < dec.options.length; i++) if (dec.options[i].id === id) return dec.options[i]; return null; }

  function createState() {
    return {
      step: 0, // index of the next decision (0..4); 4 = finished
      timeRemaining: START.timeRemaining,
      energy: START.energy,
      supplies: START.supplies,
      checkpoints: [],
      points: 0,
      flags: {},
      decisions: [],
      finished: false,
      late: false,
      lateMinutes: 0,
      finishBonus: 0
    };
  }

  function addCheckpoint(s, id, notes) {
    if (s.checkpoints.indexOf(id) !== -1) return;
    s.checkpoints.push(id);
    s.points += MAP.checkpoints[id].points;
    notes.push('Reached ' + id + ' (' + MAP.checkpoints[id].zone + ', +' + MAP.checkpoints[id].points + ' pts).');
  }

  // Returns the outcome numbers for an option given the current state (no mutation).
  function previewOutcome(state, decisionId, optionId) {
    var s = clone(state);
    var notes = [];
    var route = s.flags.route;
    var t = 0, e = 0, sup = 0, cps = [];
    var extraInd = {};
    if (decisionId === 'd1') {
      if (optionId === 'ridge') { t = 35; e = 35; cps = ['CP2']; notes.push('The climb is hard work, but the team is first onto the ridge.'); }
      if (optionId === 'valley') { t = 30; e = 10; cps = ['CP1']; notes.push('A steady pace on good paths keeps the team fresh.'); }
      if (optionId === 'scout') { t = 40; e = 15; cps = ['CP1']; notes.push('Ken and Mai confirm the lake crossing is passable and spot where the fog usually settles.'); }
    } else if (decisionId === 'd2') {
      var legCp = route === 'valley' ? 'CP3' : 'CP4';
      cps = [legCp];
      if (optionId === 'command') { t = 20; e = 15; notes.push('You set a quick pace. Decisions are fast, and you are carrying most of the mental load.'); }
      if (optionId === 'specialists') { t = 25; e = 10; notes.push('Setting up roles takes a few minutes; Mai’s navigation and Priya’s timing keep the leg clean.'); }
      if (optionId === 'rotate') { t = 32; e = 5; notes.push('Leo leads a section and takes a slightly long line (about 5 minutes lost). Shared effort keeps energy high.'); }
    } else if (decisionId === 'd3') {
      var impact = EVENT_IMPACT[route] || 0;
      if (optionId === 'push') { t = 8 + impact; e = 20; notes.push('Pushing through the change costs ' + impact + ' minutes and a lot of energy.'); }
      if (optionId === 'replan') {
        t = 12 + Math.round(impact / 2); e = 5; sup = 1;
        notes.push('Leo’s ankle is strapped (one supply kit used) and the safer line halves the delay.');
      }
      if (optionId === 'huddle') {
        var informed = !!(s.flags.roles || s.flags.rotation || s.flags.info);
        if (informed) { t = 10; e = -5; notes.push('Because the team already shares information, Mai proposes a bypass in minutes. The pause also lets everyone recover.'); }
        else { t = 10 + impact; e = -5; notes.push('The team has little extra information to share, so the huddle adds time on top of the full delay.'); }
      }
    } else if (decisionId === 'd4') {
      if (optionId === 'summit') {
        var tired = s.energy < SUMMIT_ENERGY;
        t = 45 + (tired ? 15 : 0); e = 15; cps = ['CP5'];
        if (tired) notes.push('With team energy below ' + SUMMIT_ENERGY + '%, the climb to CP5 takes 15 minutes longer.');
        notes.push('The team commits to the summit plateau.');
      }
      if (optionId === 'nearest') {
        // Nearest unvisited checkpoint from where each route ends (CP3 is closed after the event).
        var pick = NEAREST[route];
        t = 30; e = 10; cps = [pick];
        notes.push('The team detours to ' + pick + ' (' + MAP.checkpoints[pick].zone + ') on the way to the finish.');
      }
      if (optionId === 'finish') { t = 15; e = 5; notes.push('The team heads straight for the finish.'); }
    }
    return { time: t, energy: e, supplies: sup, checkpoints: cps, notes: notes, extraIndicators: extraInd };
  }

  function applyDecision(state, decisionId, optionId, rationale) {
    var dec = findDecision(decisionId);
    if (!dec) throw new Error('Unknown decision ' + decisionId);
    if (DECISIONS[state.step] !== dec) throw new Error('Decision ' + decisionId + ' is out of order');
    var opt = findOption(dec, optionId);
    if (!opt) throw new Error('Unknown option ' + optionId + ' for ' + decisionId);
    var s = clone(state);
    var before = { timeRemaining: s.timeRemaining, energy: s.energy, supplies: s.supplies, points: s.points, checkpoints: s.checkpoints.length };
    var o = previewOutcome(s, decisionId, optionId);
    var notes = o.notes.slice();

    s.timeRemaining -= o.time;
    s.energy = Math.max(0, Math.min(100, s.energy - o.energy));
    s.supplies = Math.max(0, s.supplies - o.supplies);
    for (var i = 0; i < o.checkpoints.length; i++) addCheckpoint(s, o.checkpoints[i], notes);

    if (decisionId === 'd1') { s.flags.route = optionId; if (optionId === 'scout') s.flags.info = true; }
    if (decisionId === 'd2') { if (optionId === 'specialists') s.flags.roles = true; if (optionId === 'rotate') s.flags.rotation = true; }

    if (decisionId === 'd4') {
      s.finished = true;
      if (s.timeRemaining < 0) {
        s.late = true; s.lateMinutes = -s.timeRemaining;
        var penalty = Math.min(s.points, LATE_PENALTY_PER_MIN * s.lateMinutes);
        s.points -= penalty;
        notes.push('The team finishes ' + s.lateMinutes + ' minutes late: −' + penalty + ' pts penalty.');
      } else {
        var bonus = 15;
        if (optionId === 'finish') bonus += Math.min(20, s.timeRemaining);
        s.finishBonus = bonus;
        s.points += bonus;
        notes.push('On-time finish with ' + s.timeRemaining + ' minutes to spare: +' + bonus + ' pts finish bonus.');
      }
    }

    var cleanRationale = (typeof rationale === 'string') ? rationale.trim().slice(0, 500) : '';
    s.decisions.push({
      decisionId: decisionId, number: dec.number, title: dec.title,
      optionId: optionId, label: opt.label, summary: opt.summary, tags: opt.tags.slice(),
      rationale: cleanRationale,
      consequence: notes,
      delta: {
        time: s.timeRemaining - before.timeRemaining,
        energy: s.energy - before.energy,
        supplies: s.supplies - before.supplies,
        points: s.points - before.points,
        checkpoints: s.checkpoints.length - before.checkpoints
      },
      after: { timeRemaining: s.timeRemaining, energy: s.energy, supplies: s.supplies, points: s.points, checkpoints: s.checkpoints.slice() }
    });
    s.step += 1;
    return s;
  }

  function run(choices, rationales) {
    var s = createState();
    for (var i = 0; i < choices.length; i++) s = applyDecision(s, DECISIONS[i].id, choices[i], rationales ? rationales[i] : '');
    return s;
  }

  // ---------- Report ----------
  var DIM_LABEL = {}; DIMENSIONS.forEach(function (d) { DIM_LABEL[d.id] = d.label; });

  var TAG_TEXT = {
    speed: 'prioritised pace and momentum',
    risk: 'accepted higher exposure for a higher potential reward',
    safety: 'prioritised safety and predictability',
    information: 'invested time in gathering information before committing',
    people: 'involved teammates in the work or the decision',
    control: 'kept decisions centralised with the leader',
    structure: 'set up clear roles',
    development: 'used the task to develop a teammate',
    adaptability: 'changed the plan in response to new conditions',
    communication: 'paused to share information as a team',
    ambition: 'aimed for the highest-value objective',
    balance: 'chose a middle path between reward and time',
    execution: 'protected a secure finish'
  };

  var REFLECTIONS = {
    d1: {
      ridge: 'You chose speed and exposure at the start. In your work, when do you commit early to an aggressive plan, and how do you check the downside first?',
      valley: 'You chose a predictable opening. When has a cautious start helped you, and when might it have cost you an opportunity?',
      scout: 'You invested time in information before committing. How do you decide how much information is “enough” before you act?'
    },
    d2: {
      command: 'You kept the decisions with yourself. Which decisions on your team could someone else make well, if you let them?',
      specialists: 'You assigned roles by strength. How do you discover your team’s strengths, and who might be under-used?',
      rotate: 'You shared leadership, accepting a slower leg. What would make you comfortable trading short-term speed for team capability?'
    },
    d3: {
      push: 'You held the plan when conditions changed. What signals would tell you a plan should be changed rather than pushed?',
      replan: 'You re-planned and protected a teammate. How do you balance people’s wellbeing against delivery pressure?',
      huddle: 'You stopped to hear the team. In fast-moving situations, how do you make space for others’ information without losing momentum?'
    },
    d4: {
      summit: 'You went for the biggest prize under time pressure. How do you judge when ambition becomes over-commitment?',
      nearest: 'You took a balanced final objective. How do you explain trade-offs like this to stakeholders who wanted more?',
      finish: 'You secured the result. When is “banking the win” the right call, and when is it leaving value on the table?'
    }
  };

  var ACTIONS = {
    strategic: ['Before your next significant decision, write down three alternative options with their cost, time and risk, then choose.', 'Hold a 20-minute “pre-mortem” with your team on one current project: assume it failed and list why.'],
    decision: ['For one week, note each important decision, the information you had, and how long you took. Review the pattern on Friday.', 'Agree a clear decision rule (who decides, by when, using what criteria) for one recurring team decision.'],
    adaptability: ['Pick one plan in flight and define in advance the signals that would make you change it.', 'After a disruption this month, run a 15-minute “what did we learn” review with the people affected.'],
    delegation: ['Delegate one decision (not just a task) to a team member this week, and agree how you will support rather than override.', 'Map each team member’s strengths and one area they want to grow; match one upcoming assignment to it.'],
    communication: ['Open your next team meeting by asking each person for one piece of information you might not have.', 'When you make a call, share the “why” in two sentences with everyone affected.'],
    execution: ['Choose one priority for the month, set a visible milestone each week, and review progress with your team.', 'Identify one task you regularly over-commit on; agree a realistic buffer and test it for two weeks.']
  };

  function computeIndicators(state) {
    var scores = {}; DIMENSIONS.forEach(function (d) { scores[d.id] = BASELINE; });
    var contributions = []; // {source, dimension, delta, reason}
    state.decisions.forEach(function (rec) {
      var dec = findDecision(rec.decisionId);
      var opt = findOption(dec, rec.optionId);
      Object.keys(opt.indicators).forEach(function (dim) {
        contributions.push({ source: 'Decision ' + rec.number + ' · ' + opt.label, dimension: dim, delta: opt.indicators[dim], reason: 'Rubric value for choosing “' + opt.label + '”' });
      });
      if (rec.rationale && rec.rationale.length >= RATIONALE_MIN_CHARS) {
        contributions.push({ source: 'Decision ' + rec.number + ' · rationale', dimension: 'communication', delta: 3, reason: 'A written rationale (≥' + RATIONALE_MIN_CHARS + ' characters) was recorded' });
        contributions.push({ source: 'Decision ' + rec.number + ' · rationale', dimension: 'decision', delta: 2, reason: 'A written rationale (≥' + RATIONALE_MIN_CHARS + ' characters) was recorded' });
      }
    });
    if (state.finished) {
      if (state.late) contributions.push({ source: 'Mission outcome', dimension: 'execution', delta: -10, reason: 'Finished ' + state.lateMinutes + ' min after the time limit' });
      else contributions.push({ source: 'Mission outcome', dimension: 'execution', delta: 5, reason: 'Finished within the time limit' });
      if (state.energy < 20) contributions.push({ source: 'Mission outcome', dimension: 'execution', delta: -5, reason: 'Team energy ended below 20%' });
      var d4 = state.decisions[3];
      var timeBeforeD4 = state.decisions[2] ? state.decisions[2].after.timeRemaining : 0;
      if (d4 && d4.optionId === 'finish') {
        if (timeBeforeD4 < 45) contributions.push({ source: 'Decision 4 · context', dimension: 'strategic', delta: 10, reason: 'Chose a secure finish when fewer than 45 minutes remained' });
        else contributions.push({ source: 'Decision 4 · context', dimension: 'strategic', delta: -5, reason: 'Chose to finish early with 45+ minutes still available' });
      }
      if (d4 && d4.optionId === 'summit') {
        contributions.push(state.late
          ? { source: 'Decision 4 · context', dimension: 'execution', delta: -5, reason: 'Committed to CP5 without enough time to finish on time' }
          : { source: 'Decision 4 · context', dimension: 'execution', delta: 10, reason: 'Committed to CP5 and still finished on time' });
      }
    }
    contributions.forEach(function (c) { scores[c.dimension] += c.delta; });
    Object.keys(scores).forEach(function (k) { scores[k] = Math.max(0, Math.min(100, scores[k])); });
    return { scores: scores, contributions: contributions };
  }

  function rankDims(scores, desc) {
    var order = DIMENSIONS.map(function (d, i) { return { id: d.id, i: i, v: scores[d.id] }; });
    order.sort(function (a, b) { return desc ? (b.v - a.v) || (a.i - b.i) : (a.v - b.v) || (a.i - b.i); });
    return order.map(function (o) { return o.id; });
  }

  function driversFor(contributions, dim, positive) {
    return contributions.filter(function (c) { return c.dimension === dim && (positive ? c.delta > 0 : c.delta < 0); })
      .sort(function (a, b) { return positive ? b.delta - a.delta : a.delta - b.delta; });
  }

  function buildReport(state) {
    if (!state.finished || state.decisions.length !== DECISIONS.length) throw new Error('Simulation not finished');
    var ind = computeIndicators(state);
    var scores = ind.scores;

    // Observed decision patterns — derived only from the tags of recorded choices.
    var tagCount = {}, tagWhere = {};
    state.decisions.forEach(function (d) {
      d.tags.forEach(function (t) { tagCount[t] = (tagCount[t] || 0) + 1; (tagWhere[t] = tagWhere[t] || []).push('D' + d.number + ' ' + d.label); });
    });
    var patterns = Object.keys(tagCount).filter(function (t) { return tagCount[t] >= 2; })
      .sort(function (a, b) { return tagCount[b] - tagCount[a] || (a < b ? -1 : 1); })
      .map(function (t) { return 'In ' + tagCount[t] + ' of 4 decisions you ' + TAG_TEXT[t] + ' (' + tagWhere[t].join('; ') + ').'; });
    var withRationale = state.decisions.filter(function (d) { return d.rationale && d.rationale.length >= RATIONALE_MIN_CHARS; }).length;
    patterns.push('You recorded a written rationale for ' + withRationale + ' of 4 decisions.');
    if (patterns.length === 1) patterns.unshift('Your choices did not repeat a single theme: each decision drew on a different approach (' + state.decisions.map(function (d) { return d.label; }).join(', ') + ').');

    var top = rankDims(scores, true).slice(0, 2);
    var bottom = rankDims(scores, false).slice(0, 2);
    var strengths = top.map(function (dim) {
      var dr = driversFor(ind.contributions, dim, true).slice(0, 2).map(function (c) { return c.source; });
      return { dimension: DIM_LABEL[dim], score: scores[dim], evidence: dr.length ? 'Driven in this simulation by: ' + dr.join('; ') + '.' : 'No choice added to this indicator; it stayed at the baseline.' };
    });
    var development = bottom.map(function (dim) {
      var neg = driversFor(ind.contributions, dim, false).slice(0, 2).map(function (c) { return c.source + ' (' + c.delta + ')'; });
      var pos = driversFor(ind.contributions, dim, true).map(function (c) { return c.source + ' (+' + c.delta + ')'; });
      var ev = neg.length ? 'Lowered in this simulation by: ' + neg.join('; ') + '.'
        : (pos.length ? 'Rose less than your other indicators in this run; only ' + pos.join('; ') + ' added to it.' : 'None of your choices added to this indicator in this run; it stayed at the baseline.');
      return { dimension: DIM_LABEL[dim], score: scores[dim], evidence: ev };
    });

    var alternatives = state.decisions.map(function (d) {
      var dec = findDecision(d.decisionId);
      return {
        decision: 'Decision ' + d.number + ' — ' + dec.title, chosen: d.label,
        others: dec.options.filter(function (o) { return o.id !== d.optionId; }).map(function (o) { return { label: o.label, tradeoff: o.tradeoff }; })
      };
    });

    var reflections = state.decisions.map(function (d) { return REFLECTIONS[d.decisionId][d.optionId]; });

    var actions = [];
    bottom.forEach(function (dim) { ACTIONS[dim].forEach(function (a) { actions.push({ dimension: DIM_LABEL[dim], action: a }); }); });
    var plan = actions.slice(0, 4).map(function (a, i) { return { week: i + 1, dimension: a.dimension, action: a.action }; });

    return {
      title: 'Leadership Intelligence Report — Illustrative',
      disclaimer: 'All scores are illustrative simulation indicators produced by a transparent, deterministic rubric from the four decisions recorded in this simulated training environment. They are not a validated assessment of leadership competencies, personality, psychological traits or real-world leadership effectiveness.',
      summary: {
        points: state.points, checkpoints: state.checkpoints.slice(), checkpointCount: state.checkpoints.length,
        timeRemaining: state.timeRemaining, energy: state.energy, supplies: state.supplies,
        onTime: !state.late, lateMinutes: state.lateMinutes, finishBonus: state.finishBonus
      },
      dimensions: DIMENSIONS.map(function (d) { return { id: d.id, label: d.label, score: scores[d.id] }; }),
      contributions: ind.contributions.map(function (c) { return { source: c.source, dimension: DIM_LABEL[c.dimension], delta: c.delta, reason: c.reason }; }),
      baseline: BASELINE,
      history: state.decisions.map(function (d) { return { number: d.number, title: d.title, choice: d.label, summary: d.summary, rationale: d.rationale, consequence: d.consequence, delta: d.delta }; }),
      patterns: patterns,
      strengths: strengths,
      development: development,
      alternatives: alternatives,
      reflections: reflections,
      plan: plan
    };
  }

  return {
    DIMENSIONS: DIMENSIONS, DECISIONS: DECISIONS, MAP: MAP, TEAM: TEAM, START: START, BASELINE: BASELINE,
    RATIONALE_MIN_CHARS: RATIONALE_MIN_CHARS, EVENT_IMPACT: EVENT_IMPACT,
    createState: createState, previewOutcome: previewOutcome, applyDecision: applyDecision, run: run,
    computeIndicators: computeIndicators, buildReport: buildReport
  };
}));
