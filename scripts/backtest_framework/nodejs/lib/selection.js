/**
 * Two-Stage Hard Filter + Composite Selection (cycle 6).
 *
 * Cycle 5 calibration on REAL data showed:
 *   - runup_10d Q1 (drop <= -3.1%) -> 38.9% success, Q4 (pump >= +0.8%) -> 27.7%
 *     edge = -11.2pp (INVERTED). Strongest inverted signal in the system.
 *   - price_position Q1 (pp_score=0, near year HIGH) -> 8.5% success,
 *     Q4 (pp_score=7, near year LOW) -> 40.5%. edge = +32.0pp. Strongest positive.
 *
 * The linear weighted composite cannot exploit these: composite_base has been
 * NON-MONOTONIC in every cycle (Q2 > Q4). Penalizing only softens the dip; it
 * cannot make Q4 > Q2 because Q4 selects stocks where ALL signals max
 * simultaneously = overheated pump.
 *
 * Two-stage approach:
 *   Stage 1 — HARD GATE: keep only stocks passing BOTH criteria:
 *       runup_10d_pct <= max_runup_pct      (NOT recently pumped)
 *       pp_score      >= min_pp_score       (in lower half of year range)
 *   Stage 2 — among passing stocks, take top-N by composite total_score,
 *     with the existing sector diversification.
 *
 * If a day has fewer than N stocks passing the gate, fall back to the unfiltered
 * top-N for that day (with a flag in the rec) so the backtest still produces
 * recommendations and we can measure the gate's selectivity.
 *
 * Config (BACKTEST block):
 *   enable_hard_filter: true
 *   max_runup_pct:   3.0   (reject stocks that rose > 3% in 10 days)
 *   min_pp_score:    2.8   (reject stocks in upper half of year range)
 *   min_passers:    10    (if fewer pass, fall back to unfiltered selection)
 *
 * A recommendation object gains:
 *   hard_filter_passed: bool  (whether it passed stage-1)
 *   hard_filter_used: bool    (whether stage-1 was actually used that day)
 */

'use strict';

/**
 * Apply stage-1 hard filter to a list of recommendations.
 * Returns { passers: [...], fallback: boolean }.
 * `passers` are recs that meet BOTH criteria; `fallback` indicates whether
 * too few passed (caller should use unfiltered list instead).
 */
function hardFilter(dailyScores, opts) {
  const maxRunup = opts.max_runup_pct;   // e.g. 3.0
  const minPp = opts.min_pp_score;       // e.g. 2.8
  const minPassers = opts.min_passers;   // e.g. 10

  if (maxRunup == null || minPp == null) {
    return { passers: dailyScores, fallback: true, rejected: [] };
  }

  const passers = [];
  const rejected = [];
  for (const rec of dailyScores) {
    const runup = rec.runup_10d_pct != null ? rec.runup_10d_pct : 0;
    const pp = rec.breakdown ? rec.breakdown.price_position : 0;
    const ok = (runup <= maxRunup) && (pp >= minPp);
    rec.hard_filter_passed = ok;
    if (ok) {
      passers.push(rec);
    } else {
      rejected.push(rec);
    }
  }

  const fallback = passers.length < minPassers;
  return { passers, fallback, rejected };
}

/**
 * Select top-N buys with sector diversification.
 * If `pool` has at least minPassers entries, pick from pool; otherwise pick from
 * the full dailyScores (and mark recs with hard_filter_used=false).
 */
function selectTopBuys(pool, dailyScores, dailyBuy, sectorMap, opts) {
  const usedFiltered = pool.length >= (opts.min_passers || 0);
  const source = usedFiltered ? pool : dailyScores;

  // Sort source descending by total_score
  source.sort((a, b) => b.total_score - a.total_score);

  const top = [];
  if (opts.diversify_top_picks !== false) {
    const usedSectors = new Set();
    const remaining = [];
    for (const rec of source) {
      const sector = sectorMap[rec.ins_code] || '';
      if (!usedSectors.has(sector)) {
        top.push(rec);
        usedSectors.add(sector);
      } else {
        remaining.push(rec);
      }
      if (top.length >= dailyBuy) break;
    }
    for (const rec of remaining) {
      if (top.length >= dailyBuy) break;
      top.push(rec);
    }
  } else {
    for (let i = 0; i < Math.min(dailyBuy, source.length); i++) {
      top.push(source[i]);
    }
  }

  // Annotate whether the hard filter was actually used to pick these
  for (const rec of top) rec.hard_filter_used = usedFiltered;
  return top;
}

module.exports = { hardFilter, selectTopBuys };
