/**
 * Backtest Engine — Walks through history, generates recommendations, evaluates outcomes
 */

const { calculateCompositeScore } = require('./composite_score');
const { hardFilter, selectTopBuys } = require('./selection');

// FIX EG1: Seeded PRNG (LCG) — deterministic shuffle for reproducible sampling.
// Replaces the old `sort by ins_code, slice(0, N)` which always picked the SAME
// lowest-ins_code symbols every day, biasing the entire backtest.
function seededShuffle(arr, seed) {
  const a = arr.slice();
  let s = seed || 42;
  for (let i = a.length - 1; i > 0; i--) {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    const j = s % (i + 1);
    const tmp = a[i]; a[i] = a[j]; a[j] = tmp;
  }
  return a;
}

class BacktestEngine {
  constructor(dataLoader, config) {
    this.dataLoader = dataLoader;
    this.config = config;
    this.allRecommendations = [];
    this.evaluatedResults = [];
  }

  async run(progressCallback) {
    const btConfig = this.config.BACKTEST || {};
    let startDate = btConfig.start_date || 14030101;
    let endDate = btConfig.end_date || 14040331;
    const dailyBuy = btConfig.daily_buy_recommendations || 2;
    const dailySell = btConfig.daily_sell_recommendations || 1;
    const sampleSize = btConfig.sample_symbols_per_day || 30;
    const horizons = btConfig.evaluation_horizons || [7, 14, 30, 60, 90];
    const successThreshold = btConfig.success_threshold_pct || 5.0;

    // Get all candles
    const candles = this.dataLoader.loadCandles();

    // AUTO-DETECT date range from actual data
    if (candles.length > 0) {
      const allDates = candles.map(c => c.date_jalali).filter(d => d > 0).sort((a, b) => a - b);
      if (allDates.length > 0) {
        const dataMinDate = allDates[0];
        const dataMaxDate = allDates[allDates.length - 1];
        console.log(`Data date range: ${dataMinDate} to ${dataMaxDate}`);

        // If config range doesn't overlap with data, auto-adjust
        if (startDate > dataMaxDate || endDate < dataMinDate) {
          console.log(`⚠ Config range (${startDate}-${endDate}) doesn't match data!`);
          console.log(`  Auto-adjusting to data range...`);
          // Use the data's date range, but leave 90 days at the end for evaluation
          startDate = dataMinDate;
          endDate = dataMaxDate - 90;  // Need 90 days for evaluation horizon
          if (endDate < startDate) {
            endDate = dataMaxDate;  // fallback
          }
          console.log(`  New range: ${startDate} to ${endDate}`);
        }
      }
    }

    // Get all trading dates in range
    let tradingDates = [...new Set(candles
      .filter(c => c.date_jalali >= startDate && c.date_jalali <= endDate)
      .map(c => c.date_jalali))]
      .sort((a, b) => a - b);

    // Need at least 200 days of history before first decision date
    // Use reduce instead of Math.min(...spread) to avoid stack overflow on large arrays
    let minDate = Infinity;
    for (const c of candles) {
      if (c.date_jalali > 0 && c.date_jalali < minDate) minDate = c.date_jalali;
    }
    if (minDate === Infinity) minDate = 0;
    tradingDates = tradingDates.filter(d => d - minDate >= 200);

    console.log(`Backtest period: ${tradingDates[0] || 'N/A'} to ${tradingDates[tradingDates.length - 1] || 'N/A'}`);
    console.log(`Trading days: ${tradingDates.length}`);

    if (tradingDates.length === 0) {
      console.log(`\n⚠ No trading days found in the date range.`);
      console.log(`  Possible issues:`);
      console.log(`  1. Not enough historical data (need 200+ days before backtest start)`);
      console.log(`  2. Date format mismatch (expected Jalali integer like 14050816)`);
      console.log(`  3. Crawler didn't fetch enough data`);
      console.log(`\n  Data summary:`);
      const allDates = candles.map(c => c.date_jalali).filter(d => d > 0).sort((a, b) => a - b);
      if (allDates.length > 0) {
        console.log(`    Candles date range: ${allDates[0]} to ${allDates[allDates.length - 1]}`);
        console.log(`    Unique dates: ${new Set(allDates).size}`);
        console.log(`    Total candles: ${candles.length}`);
        // Count candles per symbol
        const bySymbol = {};
        for (const c of candles) {
          bySymbol[c.ins_code] = (bySymbol[c.ins_code] || 0) + 1;
        }
        const counts = Object.values(bySymbol).sort((a, b) => b - a);
        console.log(`    Candles per symbol: max=${counts[0]}, median=${counts[Math.floor(counts.length / 2)]}, min=${counts[counts.length - 1]}`);
      }
      return { recommendations: [], evaluated: [] };
    }

    // Get active symbols and sample
    const activeSymbols = this.dataLoader.getActiveSymbols();
    console.log(`Active symbols: ${activeSymbols.length}`);

    // NEW: Filter to only symbols that HAVE candle data
    // Build a set of ins_codes that have candles
    const symbolsWithCandles = new Set(candles.map(c => c.ins_code));
    const symbolsWithData = activeSymbols.filter(s => symbolsWithCandles.has(s.ins_code));
    console.log(`Symbols with candle data: ${symbolsWithData.length}`);

    if (symbolsWithData.length === 0) {
      console.log(`\n⚠ No symbols have candle data! Run the crawler first.`);
      return { recommendations: [], evaluated: [] };
    }

    // FIX EG1: Seeded RANDOM sampling (was sort-by-ins_code → biased to same N symbols).
    // sampleSize = 0 means use ALL active symbols with data (no sampling).
    const seed = btConfig.sample_seed || 42;
    const sampledSymbols = (sampleSize > 0)
      ? seededShuffle(symbolsWithData, seed).slice(0, Math.min(sampleSize, symbolsWithData.length))
      : symbolsWithData;

    console.log(`Sampling ${sampledSymbols.length} symbols per day (seed=${seed})\n`);

    // FIX EG2: Build ins_code → sector_code map for sector diversification at selection.
    // The config.COMPOSITE_SCORE.diversification weight is honored HERE at selection time,
    // not as a per-symbol score (diversification is a portfolio-level property).
    const sectorMap = {};
    for (const s of symbolsWithData) {
      sectorMap[s.ins_code] = s.sector_code || s.sector_name || '';
    }
    const diversifyTopPicks = btConfig.diversify_top_picks !== false;  // default true

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
          // FIX CP1: pass config.COMPOSITE_SCORE so signal weights are honored
          const rec = calculateCompositeScore(sym.ins_code, decisionDate, this.dataLoader, this.config.COMPOSITE_SCORE);
          dailyScores.push(rec);
        } catch (e) {
          // Skip errors
        }
      }

      if (dailyScores.length === 0) continue;

      // Sort by score
      dailyScores.sort((a, b) => b.total_score - a.total_score);

      // CYCLE 6: Two-stage hard filter + composite selection.
      // Stage 1 — keep only stocks NOT recently pumped (runup <= max_runup_pct)
      // AND in the lower half of the year range (pp_score >= min_pp_score).
      // Stage 2 — among passers, take top-N by composite score, sector-diversified.
      // Fallback: if fewer than min_passers pass, use unfiltered top-N.
      const filterOpts = btConfig.enable_hard_filter
        ? {
            max_runup_pct: btConfig.max_runup_pct,
            min_pp_score: btConfig.min_pp_score,
            min_passers: btConfig.min_passers,
            diversify_top_picks: btConfig.diversify_top_picks,
          }
        : { diversify_top_picks: btConfig.diversify_top_picks };

      let topBuys;
      if (btConfig.enable_hard_filter) {
        const { passers } = hardFilter(dailyScores, filterOpts);
        topBuys = selectTopBuys(passers, dailyScores, dailyBuy, sectorMap, filterOpts);
      } else {
        // Original behavior — no gate
        topBuys = [];
        if (diversifyTopPicks) {
          const usedSectors = new Set();
          const remaining = [];
          for (const rec of dailyScores) {
            const sector = sectorMap[rec.ins_code] || '';
            if (!usedSectors.has(sector)) {
              topBuys.push(rec);
              usedSectors.add(sector);
            } else {
              remaining.push(rec);
            }
            if (topBuys.length >= dailyBuy) break;
          }
          for (const rec of remaining) {
            if (topBuys.length >= dailyBuy) break;
            topBuys.push(rec);
          }
        } else {
          topBuys = dailyScores.slice(0, dailyBuy);
        }
      }
      // Take bottom N for sell (unchanged)
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
        
        // Skip if prices are invalid (zero, negative, or NaN)
        if (!entryPrice || entryPrice <= 0 || !exitPrice || exitPrice <= 0) continue;
        
        const returnPct = (exitPrice - entryPrice) / entryPrice * 100;

        // FILTER: Skip extreme returns — these are data errors (stock splits, 
        // capital increases, or price corrections that TSETMC didn't adjust)
        // Real daily returns in Iranian market are capped at ±7% per day
        // Over 30 days, max realistic return is ~200% (rare IPOs)
        // Anything beyond ±300% is almost certainly a data error
        const MAX_REALISTIC_RETURN = 300;  // +300%
        const MIN_REALISTIC_RETURN = -90;  // -90%
        if (returnPct > MAX_REALISTIC_RETURN || returnPct < MIN_REALISTIC_RETURN) {
          continue;  // Skip this evaluation — data error
        }

        // Check stop loss — use loop instead of Math.min(...spread) for safety
        const futureWindow = futureCandles.slice(1, horizon + 1);
        let minLow = entryPrice;
        for (const c of futureWindow) {
          if (c.low < minLow) minLow = c.low;
        }
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
