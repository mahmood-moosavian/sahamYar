/**
 * Metrics Calculator — Compute performance metrics from backtest results
 */

function mean(arr) {
  if (arr.length === 0) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function std(arr) {
  if (arr.length < 2) return 0;
  const m = mean(arr);
  const variance = arr.reduce((sum, val) => sum + Math.pow(val - m, 2), 0) / (arr.length - 1);
  return Math.sqrt(variance);
}

function computeMetrics(results) {
  if (results.length === 0) return {};

  const n = results.length;
  const successRate = results.filter(r => r.is_success).length / n * 100;
  const beatsBenchmark = results.filter(r => r.beats_benchmark).length / n * 100;
  const avgReturn = mean(results.map(r => r.return_pct));
  const avgExcessReturn = mean(results.map(r => r.excess_return_pct));
  const stopLossRate = results.filter(r => r.stop_loss_hit).length / n * 100;

  // Sharpe ratio
  const returns = results.map(r => r.return_pct);
  const stdReturns = std(returns);
  const horizon = results[0].horizon_days;
  const sharpe = stdReturns > 0 ? mean(returns) / stdReturns : 0;
  const sharpeAnnualized = sharpe * Math.sqrt(252 / horizon);

  // Sortino ratio
  const downsideReturns = returns.filter(r => r < 0);
  const sortino = downsideReturns.length > 1 && std(downsideReturns) > 0
    ? mean(returns) / std(downsideReturns) : 0;

  // Max drawdown
  const sortedResults = [...results].sort((a, b) => a.on_date - b.on_date);
  let cumulative = 1;
  let runningMax = 1;
  let maxDrawdown = 0;
  for (const r of sortedResults) {
    cumulative *= (1 + r.return_pct / 100);
    runningMax = Math.max(runningMax, cumulative);
    const drawdown = (cumulative - runningMax) / runningMax;
    maxDrawdown = Math.min(maxDrawdown, drawdown);
  }

  // Win/loss stats
  const wins = results.filter(r => r.return_pct > 0);
  const losses = results.filter(r => r.return_pct < 0);
  const avgWin = wins.length > 0 ? mean(wins.map(r => r.return_pct)) : 0;
  const avgLoss = losses.length > 0 ? mean(losses.map(r => r.return_pct)) : 0;

  // Profit factor
  const grossProfit = wins.reduce((sum, r) => sum + r.return_pct, 0);
  const grossLoss = Math.abs(losses.reduce((sum, r) => sum + r.return_pct, 0));
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 999 : 0;

  // Decision
  const decision = (successRate >= 55 && beatsBenchmark >= 55 && sharpeAnnualized >= 0.5 && maxDrawdown > -0.10 && profitFactor >= 1.5) ? 'PASS' : 'FAIL';

  return {
    n,
    success_rate: parseFloat(successRate.toFixed(2)),
    beats_benchmark_rate: parseFloat(beatsBenchmark.toFixed(2)),
    avg_return_pct: parseFloat(avgReturn.toFixed(2)),
    avg_excess_return_pct: parseFloat(avgExcessReturn.toFixed(2)),
    sharpe: parseFloat(sharpe.toFixed(3)),
    sharpe_annualized: parseFloat(sharpeAnnualized.toFixed(3)),
    sortino: parseFloat(sortino.toFixed(3)),
    max_drawdown_pct: parseFloat((maxDrawdown * 100).toFixed(2)),
    avg_win_pct: parseFloat(avgWin.toFixed(2)),
    avg_loss_pct: parseFloat(avgLoss.toFixed(2)),
    profit_factor: profitFactor === 999 ? 'inf' : parseFloat(profitFactor.toFixed(2)),
    stop_loss_hit_rate: parseFloat(stopLossRate.toFixed(2)),
    decision,
  };
}

function computeFullSummary(evaluatedResults) {
  const summary = {
    total_recommendations: evaluatedResults.length,
    overall: {},
    by_horizon: {},
    by_action: {},
    by_score_range: {},
  };

  // Overall (30-day horizon as default)
  const results30d = evaluatedResults.filter(r => r.horizon_days === 30);
  if (results30d.length > 0) {
    summary.overall = computeMetrics(results30d);
  }

  // By horizon
  const horizons = [...new Set(evaluatedResults.map(r => r.horizon_days))].sort((a, b) => a - b);
  for (const h of horizons) {
    const hResults = evaluatedResults.filter(r => r.horizon_days === h);
    summary.by_horizon[h] = computeMetrics(hResults);
  }

  // By action
  const actions = [...new Set(evaluatedResults.map(r => r.action))];
  for (const a of actions) {
    const aResults = evaluatedResults.filter(r => r.action === a);
    summary.by_action[a] = computeMetrics(aResults);
  }

  // By score range
  const ranges = [
    { min: 75, max: 100, label: 'strong_buy' },
    { min: 60, max: 75, label: 'buy' },
    { min: 45, max: 60, label: 'hold' },
    { min: 30, max: 45, label: 'reduce' },
    { min: 0, max: 30, label: 'sell' },
  ];
  for (const range of ranges) {
    const rResults = evaluatedResults.filter(r =>
      r.score >= range.min && r.score < range.max && r.horizon_days === 30);
    if (rResults.length > 0) {
      summary.by_score_range[range.label] = computeMetrics(rResults);
    }
  }

  return summary;
}

module.exports = { computeMetrics, computeFullSummary };
