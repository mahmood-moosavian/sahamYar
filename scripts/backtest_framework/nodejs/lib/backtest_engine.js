/**
 * Backtest Engine — Walks through history, generates recommendations, evaluates outcomes
 */

const { calculateCompositeScore } = require('./composite_score');

class BacktestEngine {
  constructor(dataLoader, config) {
    this.dataLoader = dataLoader;
    this.config = config;
    this.allRecommendations = [];
    this.evaluatedResults = [];
  }

  async run(progressCallback) {
    const btConfig = this.config.BACKTEST || {};
    const startDate = btConfig.start_date || 14030101;
    const endDate = btConfig.end_date || 14040331;
    const dailyBuy = btConfig.daily_buy_recommendations || 2;
    const dailySell = btConfig.daily_sell_recommendations || 1;
    const sampleSize = btConfig.sample_symbols_per_day || 30;
    const horizons = btConfig.evaluation_horizons || [7, 14, 30, 60, 90];
    const successThreshold = btConfig.success_threshold_pct || 5.0;

    // Get all trading dates in range
    const candles = this.dataLoader.loadCandles();
    let tradingDates = [...new Set(candles
      .filter(c => c.date_jalali >= startDate && c.date_jalali <= endDate)
      .map(c => c.date_jalali))]
      .sort((a, b) => a - b);

    console.log(`Backtest period: ${tradingDates[0]} to ${tradingDates[tradingDates.length - 1]}`);
    console.log(`Trading days: ${tradingDates.length}`);

    // Get active symbols and sample
    const activeSymbols = this.dataLoader.getActiveSymbols();
    console.log(`Active symbols: ${activeSymbols.length}`);

    // Sample symbols (deterministic for reproducibility)
    const sampledSymbols = activeSymbols
      .sort((a, b) => a.ins_code.localeCompare(b.ins_code))
      .slice(0, Math.min(sampleSize, activeSymbols.length));

    console.log(`Sampling ${sampledSymbols.length} symbols per day\n`);

    // Need at least 200 days of history before first decision
    const minDate = Math.min(...candles.map(c => c.date_jalali));
    tradingDates = tradingDates.filter(d => d - minDate >= 200);

    let processedDays = 0;
    const totalDays = tradingDates.length;

    for (const decisionDate of tradingDates) {
      processedDays++;

      if (progressCallback) {
        progressCallback(processedDays, totalDays, decisionDate);
      }

      // Calculate scores for all sampled symbols
      const dailyScores = [];

      for (const sym of sampledSymbols) {
        try {
          const rec = calculateCompositeScore(sym.ins_code, decisionDate, this.dataLoader);
          dailyScores.push(rec);
        } catch (e) {
          // Skip errors
        }
      }

      if (dailyScores.length === 0) continue;

      // Sort by score
      dailyScores.sort((a, b) => b.total_score - a.total_score);

      // Take top N for buy
      const topBuys = dailyScores.slice(0, dailyBuy);
      // Take bottom N for sell
      const bottomSells = dailyScores.slice(-dailySell);

      this.allRecommendations.push(...topBuys, ...bottomSells);
    }

    console.log(`\nGenerated ${this.allRecommendations.length} recommendations`);

    // Evaluate recommendations
    console.log('Evaluating recommendations...');
    this.evaluateRecommendations(horizons, successThreshold);

    console.log(`Evaluated ${this.evaluatedResults.length} outcomes`);

    return this.getResults();
  }

  evaluateRecommendations(horizons, successThreshold) {
    const candles = this.dataLoader.loadCandles();

    // Group candles by ins_code for faster lookup
    const candlesBySymbol = {};
    for (const c of candles) {
      if (!candlesBySymbol[c.ins_code]) candlesBySymbol[c.ins_code] = [];
      candlesBySymbol[c.ins_code].push(c);
    }

    for (const rec of this.allRecommendations) {
      const symCandles = candlesBySymbol[rec.ins_code];
      if (!symCandles) continue;

      // Find candles on or after decision date
      const futureCandles = symCandles
        .filter(c => c.date_jalali >= rec.on_date)
        .sort((a, b) => a.date_jalali - b.date_jalali);

      if (futureCandles.length === 0) continue;

      const entryPrice = futureCandles[0].close;

      for (const horizon of horizons) {
        if (futureCandles.length <= horizon) continue;

        const exitCandle = futureCandles[horizon];
        const exitPrice = exitCandle.close;
        const returnPct = (exitPrice - entryPrice) / entryPrice * 100;

        // Check stop loss
        const futureWindow = futureCandles.slice(1, horizon + 1);
        const minLow = futureWindow.length > 0
          ? Math.min(...futureWindow.map(c => c.low)) : entryPrice;
        const stopLossHit = minLow <= entryPrice * (1 - rec.stop_loss_pct);

        // Benchmark return
        const benchmarkReturn = this.dataLoader.getBenchmarkReturn(rec.on_date, horizon);

        // Success: return >= threshold AND not stopped out
        const isSuccess = returnPct >= successThreshold && !stopLossHit;
        const beatsBenchmark = (returnPct - benchmarkReturn) >= successThreshold;

        this.evaluatedResults.push({
          ins_code: rec.ins_code,
          on_date: rec.on_date,
          score: rec.total_score,
          action: rec.action,
          horizon_days: horizon,
          entry_price: entryPrice,
          exit_price: exitPrice,
          return_pct: returnPct,
          benchmark_return_pct: benchmarkReturn,
          excess_return_pct: returnPct - benchmarkReturn,
          stop_loss_hit: stopLossHit,
          is_success: isSuccess,
          beats_benchmark: beatsBenchmark,
          confidence_interval_low: rec.confidence_interval_low,
          confidence_interval_high: rec.confidence_interval_high,
        });
      }
    }
  }

  getResults() {
    return {
      recommendations: this.allRecommendations,
      evaluated: this.evaluatedResults,
    };
  }
}

module.exports = BacktestEngine;
