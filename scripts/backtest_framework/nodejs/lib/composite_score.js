/**
 * Composite Score Calculator
 * Combines all 7 per-symbol signals into a final score (0-100) and recommendation.
 *
 * FIX CP1: Weights are now read from config.COMPOSITE_SCORE (previously hardcoded —
 *   editing config.json had no effect). Falls back to defaults if config missing.
 * FIX CP2: diversification is NOT a per-symbol signal — it's a portfolio-selection
 *   concern handled in backtest_engine.js (EG2: enforce sector spread in top-N).
 *   The config.COMPOSITE_SCORE.diversification entry is ignored here on purpose.
 *
 * CYCLE 7: added quiet_accumulation as the 7th per-symbol signal. It detects the
 *   'hold'-bucket pattern explicitly (year-low + maxed legal capita + quiet volume +
 *   not-pumped) which cycle 6 calibration showed achieves 52.5% success / PF=4.01.
 *
 * CYCLE 8: 3 targeted fixes based on cycle 7 calibration diagnostics:
 *   C8.1 (data-error guard) — |runup_10d_pct| > 100% is a data error.
 *   C8.2 (saturating ceiling) — clip scores above 75 down to 75.
 *   C8.3 (sweet-spot action bands) — 'buy' means 'score in 50-75 + qa>=13'.
 *
 * CYCLE 9: 4 changes based on cycle 8 calibration diagnostics. The key cycle 8
 *   finding was a PARADOX: the 'reduce' bucket (qa=11, base=45) hit 40% success
 *   with PF=1.93, while the 'strong_buy' bucket (qa=18, base=73) collapsed to
 *   22% with PF=0.53. This proves: qa_score matters MORE than composite_base —
 *   high qa in the ABSENCE of other signals = early-stage accumulation (good);
 *   high qa WITH all signals maxed = late-stage pump (bad).
 *
 *   C9.1 (demote strong_buy) — the cycle 8 strong_buy path (score==75 + qa>=13 +
 *        runup<=0) selected 86 'already-dropped' bounce-play recs that failed
 *        (22% succ, PF=0.53). We DEMOTE strong_buy back to 'buy'. No special
 *        promotion based on qa — qa is treated as a multiplier (C9.4) instead.
 *   C9.2 (new qa_buy action) — promote 'reduce'/'hold' recs to a NEW action
 *        'qa_buy' when qa_score >= 11 AND base_score in 35-55 (the early-stage
 *        accumulation zone that cycle 8's reduce bucket proved profitable).
 *        This captures the surprise winner of cycle 8 (40% succ, PF=1.93).
 *   C9.3 (lower ceiling to 65) — cycle 8's ceiling at 75 only triggered on
 *        93/1176 recs (7.9%). Lowering to 65 makes Q3 (63-69) and Q4 (69-81)
 *        collapse together, improving monotonicity. The sweet spot Q2 (50-65)
 *        becomes the new 'top' of the curve.
 *   C9.4 (qa multiplier) — instead of qa being just one of 7 weights in
 *        composite_base, qa now ALSO multiplies the final score:
 *          qaMultiplier = 0.7 + 0.06 * qa_score  (qa=0 → 0.7x, qa=20 → 1.9x)
 *        This directly encodes the cycle 8 finding: qa matters more than
 *        composite. A low-composite stock with high qa gets boosted; a
 *        high-composite stock with low qa gets dampened.
 */

const {
  smartMoneySignal,
  technicalSignal,
  fundamentalSignal,
  baseVolumeSignal,
  buyerCapitaSignal,
  pricePositionSignal,
  quietAccumulationSignal,
} = require('./signals');

// Default weights (used when config doesn't provide them) — match the signal maxes.
// CYCLE 7: added quiet_accumulation (weight 25). Other weights are reduced
// pro-rata to keep total = 100. price_position is reduced most because
// quiet_accumulation partly overlaps with it (year-low detection).
const DEFAULT_WEIGHTS = {
  smart_money: 18,         // was 22 (cycle 6)
  technical: 18,           // was 24
  fundamental: 17,         // was 22
  base_volume: 5,          // was 6
  buyer_capita: 8,         // was 10
  price_position: 9,      // was 22 — reduced (overlap with quiet_accumulation)
  quiet_accumulation: 25, // NEW (cycle 7)
  // diversification intentionally absent here — handled at selection (EG2)
};

const SIGNAL_MAX = {
  smart_money: 35,
  technical: 30,
  fundamental: 20,
  base_volume: 8,
  buyer_capita: 8,
  price_position: 7,
  quiet_accumulation: 20,
};

// CYCLE 8 constants
const RUNUP_DATA_ERROR_PCT = 100;    // C8.1: |runup| > 100% = data error
const SWEET_SPOT_MIN      = 50;      // C8.3: 'buy' starts at 50 (was 60)
const QA_CONFIRM_THRESHOLD = 13;     // C8.3: qa >= 13 confirms true quiet accumulation

// CYCLE 9 constants
const COMPOSITE_CEILING   = 65;      // C9.3: was 75 (cycle 8) — lowered for monotonicity
const QA_BUY_MIN          = 11;      // C9.2: qa >= 11 promotes reduce/hold to qa_buy
const QA_BUY_BASE_MIN     = 35;      // C9.2: base_score lower bound for qa_buy
const QA_BUY_BASE_MAX     = 55;      // C9.2: base_score upper bound for qa_buy (early stage)
// C9.4: qa multiplier — qa=0 → 0.7x (dampen), qa=20 → 1.9x (boost)
function qaMultiplier(qaScore) {
  return 0.7 + 0.06 * qaScore;
}

function calculateCompositeScore(insCode, onDate, dataLoader, scoreConfig) {
  // Run all 7 per-symbol signals
  const sm = smartMoneySignal(insCode, onDate, dataLoader);
  const tech = technicalSignal(insCode, onDate, dataLoader);
  const fund = fundamentalSignal(insCode, onDate, dataLoader);
  const bv = baseVolumeSignal(insCode, onDate, dataLoader);
  const bc = buyerCapitaSignal(insCode, onDate, dataLoader);
  const pp = pricePositionSignal(insCode, onDate, dataLoader);
  const qa = quietAccumulationSignal(insCode, onDate, dataLoader);

  const signalResults = {
    smart_money: sm,
    technical: tech,
    fundamental: fund,
    base_volume: bv,
    buyer_capita: bc,
    price_position: pp,
    quiet_accumulation: qa,
  };

  // FIX CP1: Read weights from config; each signal contributes
  //   (signal.score / signal.max) × weight
  // Then normalize so the total is on a 0-100 scale (sum of active weights → 100).
  const weights = {};
  let weightSum = 0;
  for (const key of Object.keys(DEFAULT_WEIGHTS)) {
    const w = (scoreConfig && scoreConfig[key] && scoreConfig[key].weight != null)
      ? Number(scoreConfig[key].weight)
      : DEFAULT_WEIGHTS[key];
    weights[key] = w;
    weightSum += w;
  }
  // Guard against zero sum
  if (weightSum <= 0) weightSum = 100;

  let rawScore = 0;
  for (const key of Object.keys(signalResults)) {
    const sig = signalResults[key];
    const max = SIGNAL_MAX[key] || sig.max || 1;
    const normalized = max > 0 ? (sig.score / max) : 0;  // 0..1
    rawScore += normalized * weights[key];
  }
  // Scale to 0-100
  const baseScore = Math.min(100, Math.max(0, (rawScore / weightSum) * 100));

  // FIX SG5 (cycle 5 aggressive retune): runup_10d is the STRONGEST inverted signal
  // in real data (-12.5pp edge — bigger than any positive signal). Stocks that
  // DROPPED in last 10 days (Q1) have 38.2% success; stocks that PUMPED (Q4) only
  // 25.7%. The v4 thresholds (6/12/20) were too conservative — only 69/1176 recs
  // got any penalty, and composite_base stayed non-monotonic (Q4=25% < Q2=39%).
  // v5 lowers the entry threshold to >3% and doubles penalty magnitudes so the
  // inverted edge actually flows into the composite. Bonus for drops raised to +5.
  //
  // CYCLE 8 C8.1: |runup| > 100% is a DATA ERROR (cycle 7 had 44 such recs, all from
  // one symbol 57233073645766428, with runup up to +1,941,900%). These corrupted
  // Q1 calibration. We now detect this and flag the rec as a data error so the
  // caller can short-circuit scoring.
  const candles10 = dataLoader.getCandlesUpTo(insCode, onDate, 12);
  let runup10dPct = 0;
  let runupPenalty = 0;
  let runupReason = '';
  let isDataError = false;
  if (candles10.length >= 11) {
    const closeNow = candles10[candles10.length - 1].close;
    const close10ago = candles10[candles10.length - 11].close;
    if (close10ago > 0) {
      runup10dPct = (closeNow - close10ago) / close10ago * 100;
      // C8.1 — guard against data errors (impossible 10-day moves in TSE)
      if (Math.abs(runup10dPct) > RUNUP_DATA_ERROR_PCT) {
        isDataError = true;
        runupPenalty = -50;  // force the score to near-zero
        runupReason = `runup 10d = ${runup10dPct.toFixed(0)}% (داده‌ی خراب — جریمه‌ی سنگین)`;
      } else if (runup10dPct > 15) {
        runupPenalty = -20;
        runupReason = `runup 10d = +${runup10dPct.toFixed(0)}% (پامپ سنگین — جریمه سنگین)`;
      } else if (runup10dPct > 10) {
        runupPenalty = -14;
        runupReason = `runup 10d = +${runup10dPct.toFixed(0)}% (گرم بیش از حد)`;
      } else if (runup10dPct > 6) {
        runupPenalty = -8;
        runupReason = `runup 10d = +${runup10dPct.toFixed(0)}% (گرم)`;
      } else if (runup10dPct > 3) {
        runupPenalty = -4;
        runupReason = `runup 10d = +${runup10dPct.toFixed(0)}%`;
      } else if (runup10dPct < -8) {
        runupPenalty = 5;
        runupReason = `runup 10d = ${runup10dPct.toFixed(0)}% (کاندید برگشت)`;
      }
    }
  }
  let totalScore = Math.min(100, Math.max(0, baseScore + runupPenalty));

  // C8.1 — short-circuit on data error: force score to 0 + action 'sell'.
  // This keeps the rec in the data (so we can count it) but makes it inert.
  if (isDataError) {
    totalScore = 0;
  } else {
    // C9.4 — qa multiplier: qa now also multiplies the score (not just weights it).
    // Rationale (cycle 8): the reduce bucket (qa=11, base=45) outperformed the
    // strong_buy bucket (qa=18, base=73). qa matters MORE than composite. So
    // qa=0 dampens the score to 0.7x, qa=20 boosts it to 1.9x. We apply the
    // multiplier to the post-penalty score, then re-clamp to [0,100].
    totalScore = totalScore * qaMultiplier(qa.score);
    totalScore = Math.min(100, Math.max(0, totalScore));
  }

  // C9.3 — saturating ceiling: clip scores above 65 down to 65.
  // Rationale (cycle 8 calibration): ceiling at 75 only triggered on 93/1176 recs
  // (7.9%), so Q3 (63-69) and Q4 (69-81) stayed separate — composite_base remained
  // non-monotonic (Q4=29.3% < Q3=36.8%). Lowering the ceiling to 65 collapses both
  // into a single top band. The sweet spot Q2 (50-65) becomes the new 'top'.
  if (totalScore > COMPOSITE_CEILING) {
    totalScore = COMPOSITE_CEILING;
  }

  // Weighted confidence
  const confidences = {
    smart_money: sm.confidence,
    technical: tech.confidence,
    fundamental: fund.confidence,
    base_volume: bv.confidence,
    buyer_capita: bc.confidence,
    price_position: pp.confidence,
    quiet_accumulation: qa.confidence,
  };
  let weightedConf = 0;
  for (const key of Object.keys(confidences)) {
    weightedConf += weights[key] * confidences[key];
  }
  weightedConf /= weightSum;

  // C9.1 + C9.2 — cycle 9 action bands.
  //
  // Cycle 8 calibration showed a paradox:
  //   - strong_buy bucket (qa=18, base=73) collapsed to 22% succ, PF=0.53
  //   - reduce bucket (qa=11, base=45) hit 40% succ, PF=1.93 (the surprise winner)
  //
  // The lesson: 'qa matters MORE than composite_base'. High qa in the absence
  // of other strong signals = early-stage accumulation (good). High qa WITH all
  // signals maxed = late-stage pump (bad).
  //
  // CYCLE 9 BANDS:
  //   sell:        score < 30
  //   reduce:      30 <= score < 50  (NOT promoted to qa_buy — qa insufficient)
  //   hold:        50 <= score < 65  (sweet spot, qa < 13 — good but unconfirmed)
  //   buy:         50 <= score < 65  AND qa_score >= 13  (qa-confirmed sweet spot)
  //   qa_buy:      base_score in [35,55] AND qa_score >= 11  (C9.2 NEW — captures
  //                the cycle 8 reduce-bucket winner, the early-stage accumulation
  //                pattern. Promoted from reduce/hold to a distinct 'qa_buy'.)
  //
  // C9.1: strong_buy is REMOVED. The cycle 8 strong_buy path (score==75 + qa>=13
  //        + runup<=0) selected 'already-dropped bounce plays' that failed. We
  //        demote those recs to 'buy' instead (they'll catch the qa>=13 buy path
  //        if applicable, otherwise fall to hold).
  //
  // Note on data errors: isDataError forces score=0, which lands in 'sell'.
  // Note: qa_buy is checked BEFORE the score bands, because qa_buy is a
  // composite-INDEPENDENT promotion based on qa alone.
  let action, actionLabelFa;
  if (isDataError) {
    action = 'sell';
    actionLabelFa = 'فروش (داده‌ی خراب)';
  } else if (qa.score >= QA_BUY_MIN
             && baseScore >= QA_BUY_BASE_MIN
             && baseScore <= QA_BUY_BASE_MAX) {
    // C9.2 — qa_buy: early-stage accumulation (high qa, moderate composite).
    // This is the cycle 8 'reduce' bucket pattern, now promoted to a buy action.
    action = 'qa_buy';
    actionLabelFa = 'خرید (جمع‌آوری اولیه)';
  } else if (totalScore >= 65) {
    // Score hit the ceiling (C9.3 = 65). This means pre-multiplier raw was high.
    // C9.1: NO strong_buy promotion. Just check qa to split buy vs hold.
    if (qa.score >= QA_CONFIRM_THRESHOLD) {
      action = 'buy';
      actionLabelFa = 'خرید (تأیید qa + سقف امتیاز)';
    } else {
      action = 'hold';
      actionLabelFa = 'نگه‌داری (گرم بیش از حد)';
    }
  } else if (totalScore >= SWEET_SPOT_MIN) {
    // 50 <= score < 65 — the sweet spot
    if (qa.score >= QA_CONFIRM_THRESHOLD) {
      action = 'buy';
      actionLabelFa = 'خرید (تأیید quiet accumulation)';
    } else {
      action = 'hold';
      actionLabelFa = 'نگه‌داری (sweet spot)';
    }
  } else if (totalScore >= 30) {
    action = 'reduce';
    actionLabelFa = 'کاهش وزن';
  } else {
    action = 'sell';
    actionLabelFa = 'فروش';
  }

  // Expected success rate — recalibrated to cycle 9 bands.
  // qa_buy is the highest (cycle 8 reduce bucket had 40% succ, PF=1.93).
  // These are placeholders; calibrate.js will produce the real values.
  let expectedSuccess;
  if (action === 'qa_buy') expectedSuccess = 0.55;
  else if (action === 'buy') expectedSuccess = 0.50;
  else if (action === 'hold') expectedSuccess = 0.45;
  else if (action === 'reduce') expectedSuccess = 0.40;
  else expectedSuccess = 0.38;

  // Collect all reasons
  const allReasons = [
    ...sm.reasons, ...tech.reasons, ...fund.reasons,
    ...bv.reasons, ...bc.reasons, ...pp.reasons,
    ...qa.reasons,
    runupReason,
  ].filter(r => r);

  // Position size suggestion — recalibrated to cycle 9 action bands.
  // qa_buy gets 0.08 (between buy's 0.07 and strong_buy's old 0.10) since it
  // captures the highest-edge pattern from cycle 8 (40% succ, PF=1.93).
  let suggestedSize = 0;
  if (action === 'qa_buy') suggestedSize = 0.08;
  else if (action === 'buy') suggestedSize = 0.07;
  else if (action === 'hold') suggestedSize = 0.04;

  return {
    ins_code: insCode,
    on_date: onDate,
    total_score: totalScore,
    action,
    action_label_fa: actionLabelFa,
    is_data_error: isDataError,   // C8.1 diagnostic
    breakdown: {
      smart_money: sm.score,
      technical: tech.score,
      fundamental: fund.score,
      base_volume: bv.score,
      buyer_capita: bc.score,
      price_position: pp.score,
      quiet_accumulation: qa.score,
    },
    // Runup penalty diagnostics (FIX SG5)
    runup_10d_pct: runup10dPct,
    runup_penalty: runupPenalty,
    base_score: baseScore,
    // C8.2 ceiling diagnostic: did the score get clipped? (C9.3 ceiling is now 65)
    ceiling_applied: !isDataError && (baseScore + runupPenalty) * qaMultiplier(qa.score) > COMPOSITE_CEILING,
    // C9.4 qa multiplier diagnostic
    qa_multiplier: isDataError ? 1.0 : qaMultiplier(qa.score),
    // Normalized 0..1 per-signal contributions (for diagnostics / calibration)
    normalized: {
      smart_money: SIGNAL_MAX.smart_money > 0 ? sm.score / SIGNAL_MAX.smart_money : 0,
      technical: SIGNAL_MAX.technical > 0 ? tech.score / SIGNAL_MAX.technical : 0,
      fundamental: SIGNAL_MAX.fundamental > 0 ? fund.score / SIGNAL_MAX.fundamental : 0,
      base_volume: SIGNAL_MAX.base_volume > 0 ? bv.score / SIGNAL_MAX.base_volume : 0,
      buyer_capita: SIGNAL_MAX.buyer_capita > 0 ? bc.score / SIGNAL_MAX.buyer_capita : 0,
      price_position: SIGNAL_MAX.price_position > 0 ? pp.score / SIGNAL_MAX.price_position : 0,
      quiet_accumulation: SIGNAL_MAX.quiet_accumulation > 0 ? qa.score / SIGNAL_MAX.quiet_accumulation : 0,
    },
    confidence: weightedConf,
    expected_success_rate: expectedSuccess,
    confidence_interval_low: Math.max(0, expectedSuccess - 0.15),
    confidence_interval_high: Math.min(1, expectedSuccess + 0.15),
    stop_loss_pct: 0.12,  // 12%
    target_pct: 0.17,     // 17%
    suggested_position_size_pct: suggestedSize,
    reasons: allReasons,
  };
}

module.exports = { calculateCompositeScore, DEFAULT_WEIGHTS, SIGNAL_MAX, qaMultiplier };
