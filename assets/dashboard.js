/* Exact public aggregate snapshot. Synced with data/metrics.json. */
const EMBEDDED_METRICS = {
  "schema": "trackguard-public-aggregates-v1",
  "product": "TrackGuard",
  "recorded_at": "2026-10-22",
  "target": {
    "position_rmse_m": 0.2,
    "lateral_rmse_m": 0.2,
    "coverage_percent": 90
  },
  "windows": [
    {
      "id": "later_laps",
      "label": "Development laps 6 + 7",
      "kind": "same-session development",
      "coverage_percent": 94.8,
      "planned": 460,
      "published": 411,
      "unavailable": 49,
      "seed_count": 1,
      "qualified": true,
      "note": "One continuous run. One initial truth seed. No reset between laps. Consumed development data, not untouched validation.",
      "position_rmse_m": 0.1747753326636938,
      "lateral_rmse_m": 0.11421952782837566,
      "position_median_m": 0.13351518078480298,
      "position_p95_m": 0.31945388599089014,
      "position_max_m": 0.5874495693389843,
      "within20cm_all_planned_percent": 71.24183006535948,
      "within20cm_count": 327,
      "scored_planned_excluding_seed": 459,
      "paired_scored_frames": 410,
      "longitudinal_rmse_m": 0.13228876131541847,
      "yaw_rmse_deg": 0.10694967979624358,
      "absolute_lateral_p95_m": 0.25184152755336653,
      "absolute_lateral_max_m": 0.5706257251895852,
      "absolute_longitudinal_p95_m": 0.2595835414358725,
      "absolute_longitudinal_max_m": 0.39985447463360063,
      "absolute_yaw_p95_deg": 0.21044725023463787,
      "absolute_yaw_max_deg": 0.41764192530648103
    },
    {
      "id": "lap6",
      "label": "Development lap 6",
      "kind": "same-session development",
      "position_rmse_m": 0.1533886102612008,
      "lateral_rmse_m": 0.08593158317855984,
      "coverage_percent": 95.0,
      "planned": 241,
      "published": 217,
      "unavailable": 24,
      "seed_count": 1,
      "qualified": true,
      "note": "First slice of the same continuous run.",
      "paired_scored_frames": 216,
      "longitudinal_rmse_m": 0.12705836757289463,
      "yaw_rmse_deg": 0.1029982072922213,
      "position_median_m": 0.1265178343356524,
      "position_p95_m": 0.27155499693744534,
      "position_max_m": 0.4094843904783589,
      "absolute_lateral_p95_m": 0.1684383489139666,
      "absolute_lateral_max_m": 0.4009659950046245,
      "absolute_longitudinal_p95_m": 0.24847089962561614,
      "absolute_longitudinal_max_m": 0.37244033839961094,
      "absolute_yaw_p95_deg": 0.1955197070459805,
      "absolute_yaw_max_deg": 0.41764192530648103
    },
    {
      "id": "lap7",
      "label": "Development lap 7",
      "kind": "same-session development",
      "position_rmse_m": 0.1958587847117569,
      "lateral_rmse_m": 0.13910438917442194,
      "coverage_percent": 95.5,
      "planned": 219,
      "published": 194,
      "unavailable": 25,
      "seed_count": 0,
      "qualified": true,
      "note": "Continues lap 6 state. No lap 7 reseed.",
      "paired_scored_frames": 194,
      "longitudinal_rmse_m": 0.1378790501170403,
      "yaw_rmse_deg": 0.11118415371230454,
      "position_median_m": 0.1433511986053615,
      "position_p95_m": 0.3540013045793492,
      "position_max_m": 0.5874495693389843,
      "absolute_lateral_p95_m": 0.3148103524111429,
      "absolute_lateral_max_m": 0.5706257251895852,
      "absolute_longitudinal_p95_m": 0.2966079463838835,
      "absolute_longitudinal_max_m": 0.39985447463360063,
      "absolute_yaw_p95_deg": 0.22418593375853907,
      "absolute_yaw_max_deg": 0.41586262109084154
    },
    {
      "id": "stress",
      "label": "131-second stress window",
      "kind": "same-session development stress",
      "position_rmse_m": 0.1847964735,
      "lateral_rmse_m": 0.099534224,
      "coverage_percent": 72.0,
      "planned": 263,
      "published": 179,
      "unavailable": 84,
      "seed_count": 1,
      "qualified": false,
      "note": "Separate seeded window. Accuracy passes on published poses, but one-second coverage fails the 90% target. Not ranked."
    },
    {
      "id": "day",
      "label": "Day-session blind replay",
      "kind": "different-session visual initialization",
      "position_rmse_m": null,
      "lateral_rmse_m": null,
      "coverage_percent": 0.0,
      "planned": 148,
      "published": 0,
      "unavailable": 148,
      "seed_count": 0,
      "qualified": false,
      "note": "73.9-second recording, 148 complete groups at 2 Hz. No supplied initial pose or truth labels. 145 geometry rejects and 3 single-camera results; no approved three-camera fix. Fusion never initialized. RMSE unavailable. Different initialization condition from the night benchmark."
    }
  ],
  "runtime": {
    "source": "Earlier R14 raw geometry profile, not R16 end-to-end latency",
    "mean_ms": 379.491,
    "p95_ms": 484.995,
    "offline_setup_s": 162.451,
    "hardware": "AMD Ryzen AI 7 350 CPU",
    "numerical_threads": 2,
    "sampling_hz": 2,
    "live_performance_demonstrated": false,
    "gpu_performance_measured": false
  },
  "methodology": [
    "Position RMSE = sqrt(mean(dx^2 + dy^2)) over finite published estimates; the single initial truth seed is excluded from local RMSE.",
    "Lateral RMSE projects the error across the ground-truth vehicle heading.",
    "One-second coverage is the percentage of evaluated one-second bins containing at least one pose. It differs from the fraction of published frames.",
    "The combined publication fraction is 411/460, or 89.35%. Its occupied one-second coverage is 94.8%.",
    "Unavailable outputs remain in coverage accounting. No later-lap reset or future observation is permitted.",
    "The nominal 0.20 m uncertainty publication threshold is uncalibrated. It is not a bound on actual position error.",
    "Day coverage uses 74 camera-time bins because no ground-truth interval is available. It is not an organizer RMSE or ranking score.",
    "The track-replay graphics show the real sealed R16 development run as derived display pixels and errors. The reference is evaluator-only. All 460 rows and 49 unavailable estimates remain represented; raw world poses and labels stay local.",
    "No measured hardware cost saving, safety certification, customer deployment, 4090 latency, live 10 Hz performance or independent-session 20 cm result is claimed."
  ],
  "measured_replay": {
    "schema": "trackguard-measured-replay-v1",
    "path": "data/replay.json",
    "reference_scope": "Evaluation-only reference after sealed inference",
    "accuracy_scope": "Published eligible non-seed observations; no lap 7 reseed",
    "supersedes_synthetic_graphics_note_for": "assets/track-replay* only",
    "yaw_definition": "Wrapped signed estimate minus reference degrees",
    "longitudinal_definition": "Signed error along reference heading",
    "tail_definition": "Linear-interpolated 95th percentile of absolute errors",
    "new_aggregates_computed_before_rounding": true
  }
};

(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const labels = {later_laps:'Laps 6 + 7',lap6:'Lap 6',lap7:'Lap 7',stress:'Stress window',day:'Day blind replay'};
  const state = {data:EMBEDDED_METRICS,selected:'later_laps',playing:false};
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const cm = value => finite(value) ? `${(value*100).toFixed(2)} cm` : 'Unavailable';
  const percent = (value,digits=1) => finite(value) ? `${value.toFixed(digits)}%` : 'Unavailable';
  const publication = w => w.planned ? w.published/w.planned*100 : null;
  const escape = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const result = w => w.id==='day' ? 'No initialization' : w.qualified ? 'Local targets met' : 'Coverage fails';
  const setText = (id,value) => { $(id).textContent=value; };
  function validate(data) {
    if (!data || data.schema!=='trackguard-public-aggregates-v1' || !data.target || !Array.isArray(data.windows) || !data.runtime || !Array.isArray(data.methodology)) throw Error('Unsupported aggregate contract');
    if (data.windows.length!==5 || new Set(data.windows.map(w=>w.id)).size!==5) throw Error('Incomplete windows');
    for (const w of data.windows) {
      if (!Object.hasOwn(labels,w.id) || !finite(w.coverage_percent) || w.coverage_percent<0 || w.coverage_percent>100 || w.published+w.unavailable!==w.planned || !Number.isInteger(w.planned) || w.planned<=0) throw Error('Invalid window aggregates');
      for (const key of ['position_rmse_m','lateral_rmse_m']) if (w[key]!==null && (!finite(w[key]) || w[key]<0)) throw Error('Invalid RMSE');
    }
    return data;
  }
  function metric(id,value,unit) {
    const el=$(id);
    el.classList.toggle('missing',!finite(value));
    el.innerHTML=finite(value) ? `${value.toFixed(2)}<span class="unit">${unit}</span>` : 'Unavailable';
  }
  function drawAccuracy(w) {
    if (!finite(w.position_rmse_m) || !finite(w.lateral_rmse_m)) {
      $('accuracy-chart').innerHTML='<div class="empty-chart" role="img" aria-label="RMSE unavailable: fusion never initialized"><strong>No initialized pose</strong><span>RMSE unavailable, not zero.</span></div>';
      return;
    }
    const max=25, start=92, length=390, y0=40, target=state.data.target.position_rmse_m*100;
    const x=value=>start+value/max*length;
    const rows=[['Position',w.position_rmse_m*100,40],['Lateral',w.lateral_rmse_m*100,96]];
    const grid=[0,5,10,15,20,25].map(t=>`<line x1="${x(t)}" y1="25" x2="${x(t)}" y2="136" stroke="#e4ebea"/><text x="${x(t)}" y="158" text-anchor="middle" fill="#4d626b" font-size="10">${t}</text>`).join('');
    $('accuracy-chart').innerHTML=`<svg viewBox="0 0 550 180" role="img" aria-label="Position RMSE ${cm(w.position_rmse_m)}, lateral RMSE ${cm(w.lateral_rmse_m)}. Target ${target} centimetres." xmlns="http://www.w3.org/2000/svg"><g font-family="system-ui,sans-serif">${grid}<line x1="${x(target)}" y1="20" x2="${x(target)}" y2="136" stroke="#a45b00" stroke-width="1.5" stroke-dasharray="4 4"/><text x="${x(target)}" y="13" text-anchor="middle" fill="#a45b00" font-size="10">${target} cm target</text>${rows.map(([name,v,y])=>`<text x="0" y="${y+16}" fill="#4d626b" font-size="12">${name}</text><rect x="${start}" y="${y}" width="${Math.min(v,max)/max*length}" height="25" rx="2" fill="${name==='Position'?'#007d7d':'#759b9e'}"/><text x="${Math.min(x(v)+8,502)}" y="${y+17}" fill="#102c3a" font-family="Consolas,monospace" font-size="12">${v.toFixed(2)}</text>`).join('')}</g></svg>`;
  }
  function drawAvailability(w) {
    const left=0, width=500, target=state.data.target.coverage_percent, pub=publication(w);
    $('availability-chart').innerHTML=`<svg viewBox="0 0 550 180" role="img" aria-label="Occupied one-second coverage ${percent(w.coverage_percent)} against ${target} percent target. Frame publication fraction ${percent(pub,2)}, ${w.published} published and ${w.unavailable} unavailable out of ${w.planned} planned." xmlns="http://www.w3.org/2000/svg"><g font-family="system-ui,sans-serif"><text x="0" y="18" fill="#4d626b" font-size="11">Occupied one-second bins</text><text x="500" y="18" text-anchor="end" fill="#102c3a" font-family="Consolas,monospace" font-size="13">${percent(w.coverage_percent)}</text><rect x="0" y="30" width="500" height="23" rx="2" fill="#e8eeec"/><rect x="0" y="30" width="${w.coverage_percent/100*width}" height="23" rx="2" fill="${w.coverage_percent>=target?'#007d7d':'#a45b00'}"/><line x1="${target/100*width}" y1="25" x2="${target/100*width}" y2="59" stroke="#a45b00" stroke-width="1.5" stroke-dasharray="3 3"/><text x="${target/100*width}" y="74" text-anchor="middle" fill="#a45b00" font-size="9">${target}% target</text><text x="0" y="103" fill="#4d626b" font-size="11">Published frames / planned frames</text><text x="500" y="103" text-anchor="end" fill="#102c3a" font-family="Consolas,monospace" font-size="13">${percent(pub,2)}</text><rect x="0" y="116" width="500" height="23" rx="2" fill="#f2dfc1"/><rect x="0" y="116" width="${pub/100*width}" height="23" rx="2" fill="#007d7d"/><rect x="0" y="155" width="7" height="7" fill="#007d7d"/><text x="14" y="162" fill="#4d626b" font-size="10">${w.published} published</text><rect x="200" y="155" width="7" height="7" fill="#a45b00"/><text x="214" y="162" fill="#4d626b" font-size="10">${w.unavailable} unavailable</text></g></svg>`;
  }
  function drawComparison() {
    $('comparison-body').innerHTML=state.data.windows.map(w=>`<tr class="${w.id===state.selected?'is-selected':''}" ${w.id===state.selected?'aria-current="true"':''}><td><button type="button" data-window="${w.id}" aria-label="Inspect ${escape(w.label)}">${escape(w.label)}</button><span class="row-kind">${escape(w.kind)}</span></td><td>${cm(w.position_rmse_m)}</td><td>${cm(w.lateral_rmse_m)}</td><td><span class="coverage-cell">${percent(w.coverage_percent)}<span class="mini-bar" aria-hidden="true"><i class="${w.coverage_percent<state.data.target.coverage_percent?'fail':''}" style="width:${w.coverage_percent}%"></i></span></span></td><td>${w.published} / ${w.planned}<span class="row-kind">${percent(publication(w),2)} publication</span></td><td>${w.seed_count}</td><td class="${w.qualified?'result-pass':'result-fail'}">${result(w)}</td></tr>`).join('');
    $('comparison-body').querySelectorAll('[data-window]').forEach(button=>button.addEventListener('click',()=>{select(button.dataset.window);$('window-buttons').querySelector(`[data-window="${button.dataset.window}"]`).focus();}));
  }
  function select(id) {
    const w=state.data.windows.find(w=>w.id===id);
    if (!w) return;
    state.selected=id;
    $('window-buttons').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.window===id)));
    setText('selected-title',w.label);setText('selected-kind',w.kind);setText('selected-status',result(w));$('selected-status').classList.toggle('warn',!w.qualified);setText('window-note',w.note);
    metric('position-value',finite(w.position_rmse_m)?w.position_rmse_m*100:null,'cm');metric('lateral-value',finite(w.lateral_rmse_m)?w.lateral_rmse_m*100:null,'cm');metric('coverage-value',w.coverage_percent,'%');metric('publication-value',publication(w),'%');
    metric('longitudinal-value',finite(w.longitudinal_rmse_m)?w.longitudinal_rmse_m*100:null,'cm');metric('yaw-value',w.yaw_rmse_deg,'°');
    setText('longitudinal-caption',finite(w.longitudinal_rmse_m)?`Along reference heading · absolute p95 ${cm(w.absolute_longitudinal_p95_m)}`:id==='day'?'No initialized pose':'No aggregate supplied for this window');
    setText('yaw-caption',finite(w.yaw_rmse_deg)?`${finite(w.absolute_yaw_p95_deg)?`Absolute p95 ${w.absolute_yaw_p95_deg.toFixed(3)}° · `:''}published non-seed poses`:id==='day'?'No initialized pose':'No aggregate supplied for this window');
    setText('position-caption',finite(w.position_rmse_m)?`Target ≤ ${state.data.target.position_rmse_m*100} cm · published poses`:'Fusion never initialized');setText('lateral-caption',finite(w.lateral_rmse_m)?`Target ≤ ${state.data.target.lateral_rmse_m*100} cm · across heading`:'No approved geometric fix');setText('coverage-caption',`${w.coverage_percent>=state.data.target.coverage_percent?'Meets':'Below'} ${state.data.target.coverage_percent}% occupied-bin target`);$('coverage-caption').classList.toggle('fail',w.coverage_percent<state.data.target.coverage_percent);setText('publication-caption',`${w.published} / ${w.planned} planned · ${w.unavailable} unavailable`);
    setText('p95-value',finite(w.position_p95_m)?cm(w.position_p95_m):'Not reported');setText('distribution-caption',finite(w.position_median_m)?`Median ${cm(w.position_median_m)} · max ${cm(w.position_max_m)}`:id==='day'?'No initialization; no error distribution':'No distribution supplied for this window');setText('within-value',finite(w.within20cm_all_planned_percent)?percent(w.within20cm_all_planned_percent,2):'Not reported');setText('within-caption',finite(w.within20cm_all_planned_percent)?`${w.within20cm_count} / ${w.scored_planned_excluding_seed} planned, excluding seed`:id==='day'?'No ground-truth scoring interval':'No within-20-cm aggregate supplied');
    setText('accuracy-footnote',id==='day'?'No ground-truth labels or initialized pose. No RMSE can be computed.':'Only finite published estimates contribute to RMSE. The single initial truth seed is excluded from local error scoring.');
    setText('availability-note',id==='day'?'Day: 74 camera-time bins, without a ground-truth interval. Zero coverage; no initialized output.':'Coverage counts occupied one-second bins. Frame publication counts every planned output, including unavailable outputs.');
    setText('exact-values',JSON.stringify(w,null,2));drawAccuracy(w);drawAvailability(w);drawComparison();
  }
  function render(data) {
    state.data=validate(data);
    $('window-buttons').innerHTML=data.windows.map(w=>`<button class="window-button" data-window="${w.id}" type="button" aria-pressed="false">${labels[w.id]}</button>`).join('');
    $('window-buttons').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>select(b.dataset.window)));
    const stress=data.windows.find(w=>w.id==='stress');setText('stress-summary',`Stress: ${percent(stress.coverage_percent)} coverage`);
    const methods=data.methodology.map(m=>data.measured_replay && m.startsWith('All graphics showing a course')?'The measured replay uses real recorded development data and rendered track bounds. Reference markers are evaluation-only, after sealed inference. Public replay coordinates are rounded display pixels. No future reference enters inference.':m);
    if(data.measured_replay)methods.push('Yaw error is signed estimate minus reference, wrapped to ±180 degrees. Longitudinal error is signed along reference heading. The initial seed is excluded from all replay accuracy measures.');
    $('method-list').innerHTML=methods.map(m=>`<li>${escape(m)}</li>`).join('');
    const runtime=data.runtime;setText('runtime-source',runtime.source);setText('runtime-hardware',`${runtime.hardware} · ${runtime.numerical_threads} numerical threads · ${runtime.sampling_hz} Hz sampling`);$('runtime-mean').innerHTML=`${runtime.mean_ms.toFixed(3)}<small>ms</small>`;$('runtime-p95').innerHTML=`${runtime.p95_ms.toFixed(3)}<small>ms</small>`;setText('runtime-boundary',`${runtime.offline_setup_s.toFixed(3)} s offline setup. This is not R16 end-to-end latency. No measured GPU or live performance.`);
    setText('recorded-date',`Aggregate snapshot · ${data.recorded_at}`);select(state.selected);
  }
  render(EMBEDDED_METRICS);
  // file:// uses the exact embedded snapshot; HTTP refreshes from the approved sibling JSON.
  if (window.location.protocol!=='file:') {
    fetch('data/metrics.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw Error('Aggregate JSON unavailable');return response.json();}).then(data=>{
      validate(data);const parity=JSON.stringify(data)===JSON.stringify(EMBEDDED_METRICS);render(data);setText('source-status',parity?'Local aggregate JSON · embedded snapshot verified':'Local aggregate JSON loaded · embedded snapshot differs');
    }).catch(()=>setText('source-status','Approved embedded snapshot · local JSON could not be loaded'));
  }
})();
