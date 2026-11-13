/**
 * Calibration Analyzer — computes per-signal edge from backtest recommendations.
 *
 * Reads output/all_recommendations.csv (with breakdown columns) + candle data,
 * computes 30-day return for each recommendation, then buckets each signal by
 * quartile and reports:
 *   - avg return per quartile
 *   - success rate (return >= 5%) per quartile
 *   - edge = top_quartile_success - bottom_quartile_success
 *
 * Positive edge = signal is predictive (higher value → more success).
 * Negative edge = signal is anti-predictive (inverted — reduce weight or invert).
 *
 * Output: output/calibration_report.json (small, pushable to git for analysis)
 *
 * Usage: node calibrate.js
 */

const fs = require('fs');
const path = require('path');
const DataLoader = require('./lib/data_loader');

const configPath = path.join(__dirname, 'config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const dataLoader = new DataLoader(config);

const recsPath = path.join(__dirname, '..', 'output', 'all_recommendations.csv');
const outPath = path.join(__dirname, '..', 'output', 'calibration_report.json');

console.log('============================================================');
console.log('Calibration Analyzer');
console.log('============================================================\n');

// Load recommendations
const recsText = fs.readFileSync(recsPath, 'utf8');
const recsLines = recsText.trim().split('\n');
const headers = recsLines[0].split(',');
const recs = [];
for (let i = 1; i < recsLines.length; i++) {
  if (!recsLines[i].trim()) continue;
  const vals = recsLines[i].split(',');
  const r = {};
  for (let j = 0; j < headers.length; j++) r[headers[j]] = vals[j] || '';
  recs.push(r);
}
console.log(`Loaded ${recs.length} recommendations`);

// Load candles and build index for fast lookup
console.log('Loading candle data...');
const candles = dataLoader.loadCandles();
const candlesBySymbol = {};
for (const c of candles) {
  if (!candlesBySymbol[c.ins_code]) candlesBySymbol[c.ins_code] = [];
  candlesBySymbol[c.ins_code].push(c);
}
for (const ic in candlesBySymbol) {
  candlesBySymbol[ic].sort((a, b) => a.date_jalali - b.date_jalali);
}
console.log(`Candles loaded: ${candles.length.toLocaleString()}`);

// Compute 30-day return for each recommendation
const HORIZON = 30;
const SUCCESS_THRESHOLD = 5.0;
let evaluated = 0;
let skipped = 0;

for (const r of recs) {
  const symCandles = candlesBySymbol[r.ins_code];
  if (!symCandles) { skipped++; continue; }
  const future = symCandles.filter(c => c.date_jalali >= parseInt(r.on_date, 10));
  if (future.length <= HORIZON) { skipped++; continue; }
  const entry = future[0].close;
  const exit = future[HORIZON].close;
  if (!entry || entry <= 0 || !exit || exit <= 0) { skipped++; continue; }
  const ret = (exit - entry) / entry * 100;
  if (ret > 300 || ret < -90) { skipped++; continue; } // outlier filter
  r._return_30d = ret;
  r._success = ret >= SUCCESS_THRESHOLD ? 1 : 0;
  evaluated++;
}
console.log(`Evaluated: ${evaluated}, skipped: ${skipped}\n`);

// Signals to analyze
const signals = [
  { key: 'sm_score', name: 'smart_money', max: 35 },
  { key: 'tech_score', name: 'technical', max: 30 },
  { key: 'fund_score', name: 'fundamental', max: 20 },
  { key: 'bv_score', name: 'base_volume', max: 8 },
  { key: 'bc_score', name: 'buyer_capita', max: 8 },
  { key: 'pp_score', name: 'price_position', max: 7 },
  { key: 'base_score', name: 'composite_base', max: 100 },
  { key: 'runup_10d_pct', name: 'runup_10d', max: null },
];

const report = {
  generated_at: new Date().toISOString(),
  horizon_days: HORIZON,
  success_threshold_pct: SUCCESS_THRESHOLD,
  total_recommendations: recs.length,
  evaluated: evaluated,
  skipped: skipped,
  overall: {
    success_rate: recs.filter(r => r._success != null).reduce((s, r) => s + r._success, 0) / evaluated * 100,
    avg_return: recs.filter(r => r._return_30d != null).reduce((s, r) => s + r._return_30d, 0) / evaluated,
  },
  by_signal: {},
};

console.log('='.repeat(70));
console.log('PER-SIGNAL EDGE ANALYSIS (30-day horizon)');
console.log('='.repeat(70));
console.log(`  Overall: success=${report.overall.success_rate.toFixed(1)}%  avg_ret=${report.overall.avg_return.toFixed(2)}%\n`);

const hdr = ['signal', 'Q1(low)', 'Q2', 'Q3', 'Q4(high)', 'edge'].map((s, i) =>
  s.padStart(i === 0 ? 14 : (i === 5 ? 8 : 16)).slice(-14)
);
console.log(`  ${'signal'.padStart(14)} | ${'Q1(low)'.padStart(28)} | ${'Q2'.padStart(28)} | ${'Q3'.padStart(28)} | ${'Q4(high)'.padStart(28)} | ${'edge'.padStart(8)}`);
console.log('  ' + '-'.repeat(130));

for (const sig of signals) {
  const vals = recs.filter(r => r._return_30d != null).map(r => ({
    v: parseFloat(r[sig.key]),
    ret: r._return_30d,
    succ: r._success,
  })).filter(x => !isNaN(x.v));

  if (vals.length < 20) continue;
  vals.sort((a, b) => a.v - b.v);

  const qSize = Math.floor(vals.length / 4);
  const quartiles = [];
  for (let q = 0; q < 4; q++) {
    const start = q * qSize;
    const end = q === 3 ? vals.length : (q + 1) * qSize;
    const slice = vals.slice(start, end);
    if (slice.length === 0) {
      quartiles.push({ n: 0, avg_ret: 0, succ: 0, v_range: 'n/a' });
      continue;
    }
    const avgRet = slice.reduce((s, x) => s + x.ret, 0) / slice.length;
    const succ = slice.filter(x => x.succ).length / slice.length * 100;
    quartiles.push({
      n: slice.length,
      avg_ret: avgRet,
      succ: succ,
      v_range: `${slice[0].v.toFixed(1)}-${slice[slice.length-1].v.toFixed(1)}`,
    });
  }

  const edge = quartiles[3].succ - quartiles[0].succ;
  const edgeRet = quartiles[3].avg_ret - quartiles[0].avg_ret;

  report.by_signal[sig.name] = {
    quartiles,
    edge_success_pp: edge,
    edge_return_pp: edgeRet,
    interpretation: edge > 5 ? 'predictive' : edge < -5 ? 'inverted' : 'weak',
  };

  const fmt = (q) => `n=${q.n} succ=${q.succ.toFixed(1)}% ret=${q.avg_ret.toFixed(2)}%`;
  const edgeStr = (edge > 0 ? '+' : '') + edge.toFixed(1) + 'pp';
  console.log(`  ${sig.name.padStart(14)} | ${fmt(quartiles[0]).padStart(28)} | ${fmt(quartiles[1]).padStart(28)} | ${fmt(quartiles[2]).padStart(28)} | ${fmt(quartiles[3]).padStart(28)} | ${edgeStr.padStart(8)}`);
}

// Save report
fs.writeFileSync(outPath, JSON.stringify(report, null, 2), 'utf8');
console.log(`\n✓ Calibration report saved: ${outPath}`);
console.log('  Push this file to git for cycle 4 weight tuning.');
