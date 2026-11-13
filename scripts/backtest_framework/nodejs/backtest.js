#!/usr/bin/env node
/**
 * سهام‌یار Backtest Framework — Node.js Version
 *
 * Equivalent to Python's main.py. Does NOT require Python or pip.
 *
 * Usage:
 *   node backtest.js                  # Run full backtest
 *   node backtest.js --mode quick     # Quick test (fewer symbols)
 *   node backtest.js --mode full      # Full run (all symbols)
 *
 * Requirements:
 *   - Node.js 14+
 *   - CSV data files in data/csv/ (from TSETMC crawler)
 *
 * No external npm packages needed — uses only built-in modules.
 */

const fs = require('fs');
const path = require('path');
const DataLoader = require('./lib/data_loader');
const BacktestEngine = require('./lib/backtest_engine');
const { computeFullSummary } = require('./lib/metrics');
const { generateReport } = require('./lib/report');

// Load config (JSON — no PyYAML needed)
function loadConfig() {
  const configPath = path.join(__dirname, 'config.json');
  const yamlPath = path.join(__dirname, 'config.yaml');

  if (fs.existsSync(configPath)) {
    return JSON.parse(fs.readFileSync(configPath, 'utf8'));
  }

  // Fallback: try YAML (would need js-yaml package)
  if (fs.existsSync(yamlPath)) {
    try {
      const yaml = require('js-yaml');
      return yaml.load(fs.readFileSync(yamlPath, 'utf8'));
    } catch (e) {
      console.error('✗ config.json not found and js-yaml not installed');
      console.error('  Solution: Ensure config.json exists (it should be in the framework)');
      process.exit(1);
    }
  }

  console.error('✗ No config file found (config.json or config.yaml)');
  process.exit(1);
}

// ============================================================
// Main
// ============================================================

async function main() {
  const args = process.argv.slice(2);
  let mode = 'normal';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--mode') {
      mode = args[++i];
    } else if (args[i] === '--help' || args[i] === '-h') {
      console.log(`
سهام‌یار Backtest Framework (Node.js)

Usage:
  node backtest.js [options]

Options:
  --mode <quick|normal|full>   Run mode
                               quick=fewer symbols (fast test)
                               normal=default settings
                               full=all symbols (slow)
  -h, --help                   Show this help

No external dependencies required.
Data must be in data/csv/ (from TSETMC crawler).
`);
      process.exit(0);
    }
  }

  console.log('='.repeat(60));
  console.log('سهام‌یار Backtest Framework (Node.js)');
  console.log('='.repeat(60));
  console.log(`Mode: ${mode}\n`);

  // Load config
  const config = loadConfig();

  // Adjust config based on mode
  if (mode === 'quick') {
    config.BACKTEST.sample_symbols_per_day = 10;
    config.BACKTEST.daily_buy_recommendations = 1;
    config.BACKTEST.daily_sell_recommendations = 1;
  } else if (mode === 'full') {
    config.BACKTEST.sample_symbols_per_day = 100;
    config.BACKTEST.daily_buy_recommendations = 5;
    config.BACKTEST.daily_sell_recommendations = 3;
  }

  // Step 1: Load data
  console.log('STEP 1: Loading data...');
  const dataLoader = new DataLoader(config);

  try {
    const summary = dataLoader.summary();
    console.log(`  ✓ Symbols:        ${summary.symbols}`);
    console.log(`  ✓ Active:         ${summary.activeSymbols}`);
    console.log(`  ✓ Candles:        ${summary.candles.toLocaleString()}`);
    console.log(`  ✓ Client types:   ${summary.clientTypes.toLocaleString()}`);
    console.log(`  ✓ Fundamentals:   ${summary.fundamentals}`);
    console.log(`  ✓ Market index:   ${summary.marketIndexRecords}`);
  } catch (err) {
    console.error(`\n✗ Error loading data: ${err.message}`);
    console.error('\nMake sure you have run the TSETMC crawler first:');
    console.error('  cd tsetmc_crawler');
    console.error('  node crawler_v2.js --mode medium');
    process.exit(1);
  }

  // Step 2: Run backtest
  console.log('\nSTEP 2: Running backtest...');
  const engine = new BacktestEngine(dataLoader, config);

  let lastProgress = '';
  const results = await engine.run((current, total, date) => {
    const pct = (current / total * 100).toFixed(1);
    const progress = `[${current}/${total}] ${pct}% | date: ${date}`;
    if (progress !== lastProgress) {
      process.stdout.write(`\r  ${progress.padEnd(60)}`);
      lastProgress = progress;
    }
  });
  console.log('\n');

  // Step 3: Compute metrics
  console.log('STEP 3: Computing metrics...');
  const summary = computeFullSummary(results.evaluated);

  const overall = summary.overall || {};
  console.log(`\n  Overall metrics (30-day horizon):`);
  console.log(`    Total recommendations:  ${(overall.n || 0).toLocaleString()}`);
  console.log(`    Success rate:          ${overall.success_rate || 0}%`);
  console.log(`    Beats benchmark:       ${overall.beats_benchmark_rate || 0}%`);
  console.log(`    Avg return:            ${overall.avg_return_pct || 0}%`);
  console.log(`    Avg excess return:     ${overall.avg_excess_return_pct || 0}%`);
  console.log(`    Sharpe (annualized):   ${overall.sharpe_annualized || 0}`);
  console.log(`    Max drawdown:          ${overall.max_drawdown_pct || 0}%`);
  console.log(`    Profit factor:         ${overall.profit_factor || 0}`);
  console.log(`    Stop loss hit rate:    ${overall.stop_loss_hit_rate || 0}%`);

  const decision = overall.decision || 'FAIL';
  const decisionIcon = decision === 'PASS' ? '✓' : '✗';
  console.log(`\n  ${decisionIcon} Decision: ${decision}`);

  // Step 4: Generate report
  console.log('\nSTEP 4: Generating report...');
  const outputDir = path.join(__dirname, '..', 'output');
  fs.mkdirSync(outputDir, { recursive: true });

  const reportPath = generateReport(results, summary, outputDir);
  console.log(`  ✓ Report saved: ${reportPath}`);

  // Save raw results as JSON
  const resultsPath = path.join(outputDir, 'backtest_results.json');
  fs.writeFileSync(resultsPath, JSON.stringify({
    summary,
    total_recommendations: results.recommendations.length,
    total_evaluated: results.evaluated.length,
  }, null, 2), 'utf8');
  console.log(`  ✓ Raw results: ${resultsPath}`);

  // Save recommendations as CSV
  // FIX MR3: Previously only 5 columns (ins_code, on_date, total_score, action, confidence).
  // Now includes the full per-signal breakdown + normalized values so calibrate.js
  // can regress sub-signal values against outcomes and tune weights with evidence.
  const recsPath = path.join(outputDir, 'all_recommendations.csv');
  if (results.recommendations.length > 0) {
    const headers = [
      'ins_code', 'on_date', 'total_score', 'action', 'confidence',
      'sm_score', 'tech_score', 'fund_score', 'bv_score', 'bc_score', 'pp_score',
      'sm_norm', 'tech_norm', 'fund_norm', 'bv_norm', 'bc_norm', 'pp_norm',
      'base_score', 'runup_10d_pct', 'runup_penalty',
      'hard_filter_passed', 'hard_filter_used',
      'expected_success', 'stop_loss_pct',
    ];
    const lines = [headers.join(',')];
    for (const r of results.recommendations) {
      const b = r.breakdown || {};
      const n = r.normalized || {};
      const row = [
        r.ins_code, r.on_date, r.total_score.toFixed(2), r.action, r.confidence.toFixed(3),
        (b.smart_money ?? 0).toFixed(2), (b.technical ?? 0).toFixed(2), (b.fundamental ?? 0).toFixed(2),
        (b.base_volume ?? 0).toFixed(2), (b.buyer_capita ?? 0).toFixed(2), (b.price_position ?? 0).toFixed(2),
        (n.smart_money ?? 0).toFixed(3), (n.technical ?? 0).toFixed(3), (n.fundamental ?? 0).toFixed(3),
        (n.base_volume ?? 0).toFixed(3), (n.buyer_capita ?? 0).toFixed(3), (n.price_position ?? 0).toFixed(3),
        (r.base_score ?? 0).toFixed(2), (r.runup_10d_pct ?? 0).toFixed(1), (r.runup_penalty ?? 0).toFixed(0),
        r.hard_filter_passed ? 1 : 0, r.hard_filter_used ? 1 : 0,
        (r.expected_success_rate ?? 0).toFixed(3), (r.stop_loss_pct ?? 0).toFixed(3),
      ];
      lines.push(row.join(','));
    }
    fs.writeFileSync(recsPath, lines.join('\n'), 'utf8');
    console.log(`  ✓ Recommendations (with breakdown): ${recsPath}`);
  }

  console.log('\n' + '='.repeat(60));
  console.log('DONE!');
  console.log('='.repeat(60));
  console.log(`\nOpen the report:`);
  console.log(`  ${reportPath}`);
  console.log(`\nOr in browser:`);
  console.log(`  file:///${reportPath.replace(/\\/g, '/')}`);
}

main().catch(err => {
  console.error('\n✗ Fatal error:', err.message);
  console.error(err.stack);
  process.exit(1);
});
