/**
 * Composite Score Calculator
 * Combines all 6 per-symbol signals into a final score (0-100) and recommendation.
 *
 * FIX CP1: Weights are now read from config.COMPOSITE_SCORE (previously hardcoded —
 *   editing config.json had no effect). Falls back to defaults if config missing.
 * FIX CP2: diversification is NOT a per-symbol signal — it's a portfolio-selection
 *   concern handled in backtest_engine.js (EG2: enforce sector spread in top-N).
 *   The config.COMPOSITE_SCORE.diversification entry is ignored here on purpose.
 */

const {
  smartMoneySignal,
  technicalSignal,
  fundamentalSignal,
  baseVolumeSignal,
  buyerCapitaSignal,
  pricePositionSignal,
} = require('./signals');

// Default weights (used when config doesn't provide them) — match the signal maxes.
const DEFAULT_WEIGHTS = {
  smart_money: 20,
  technical: 30,
  fundamental: 25,
  base_volume: 8,
  buyer_capita: 8,
  price_position: 12,
  // diversification intentionally absent here — handled at selection (EG2)
};

const SIGNAL_MAX = {
  smart_money: 35,
  technical: 30,
  fundamental: 20,
  base_volume: 8,
  buyer_capita: 8,
  price_position: 7,
};

function calculateCompositeScore(insCode, onDate, dataLoader, scoreConfig) {
  // Run all 6 per-symbol signals
  const sm = smartMoneySignal(insCode, onDate, dataLoader);
  const tech = technicalSignal(insCode, onDate, dataLoader);
  const fund = fundamentalSignal(insCode, onDate, dataLoader);
  const bv = baseVolumeSignal(insCode, onDate, dataLoader);
  const bc = buyerCapitaSignal(insCode, onDate, dataLoader);
  const pp = pricePositionSignal(insCode, onDate, dataLoader);

  const signalResults = {
    smart_money: sm,
    technical: tech,
    fundamental: fund,
    base_volume: bv,
    buyer_capita: bc,
    price_position: pp,
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
  const candles10 = dataLoader.getCandlesUpTo(insCode, onDate, 12);
  let runup10dPct = 0;
  let runupPenalty = 0;
  let runupReason = '';
  if (candles10.length >= 11) {
    const closeNow = candles10[candles10.length - 1].close;
    const close10ago = candles10[candles10.length - 11].close;
    if (close10ago > 0) {
      runup10dPct = (closeNow - close10ago) / close10ago * 100;
      if (runup10dPct > 15) {
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
  const totalScore = Math.min(100, Math.max(0, baseScore + runupPenalty));

  // Weighted confidence
  const confidences = {
    smart_money: sm.confidence,
    technical: tech.confidence,
    fundamental: fund.confidence,
    base_volume: bv.confidence,
    buyer_capita: bc.confidence,
    price_position: pp.confidence,
  };
  let weightedConf = 0;
  for (const key of Object.keys(confidences)) {
    weightedConf += weights[key] * confidences[key];
  }
  weightedConf /= weightSum;

  // Determine action based on score.
  // Thresholds kept identical to previous behavior (strong_buy ≥ 85, etc.) so
  // historical comparison stays apples-to-apples. Strategy-bet retuning (raising
  // strong_buy, changing bands) belongs in cycle 2 once we have per-signal diagnostics.
  let action, actionLabelFa;
  if (totalScore >= 85) { action = 'strong_buy'; actionLabelFa = 'خرید قوی'; }
  else if (totalScore >= 60) { action = 'buy'; actionLabelFa = 'خرید'; }
  else if (totalScore >= 45) { action = 'hold'; actionLabelFa = 'نگه‌داری'; }
  else if (totalScore >= 30) { action = 'reduce'; actionLabelFa = 'کاهش وزن'; }
  else { action = 'sell'; actionLabelFa = 'فروش'; }

  // Expected success rate (placeholder until calibrate.js produces real values)
  let expectedSuccess;
  if (totalScore >= 75) expectedSuccess = 0.62;
  else if (totalScore >= 60) expectedSuccess = 0.58;
  else if (totalScore >= 45) expectedSuccess = 0.54;
  else if (totalScore >= 30) expectedSuccess = 0.50;
  else expectedSuccess = 0.48;

  // Collect all reasons
  const allReasons = [
    ...sm.reasons, ...tech.reasons, ...fund.reasons,
    ...bv.reasons, ...bc.reasons, ...pp.reasons,
    runupReason,
  ].filter(r => r);

  // Position size suggestion
  let suggestedSize = 0;
  if (totalScore >= 75) suggestedSize = 0.10;
  else if (totalScore >= 60) suggestedSize = 0.07;
  else if (totalScore >= 45) suggestedSize = 0.04;

  return {
    ins_code: insCode,
    on_date: onDate,
    total_score: totalScore,
    action,
    action_label_fa: actionLabelFa,
    breakdown: {
      smart_money: sm.score,
      technical: tech.score,
      fundamental: fund.score,
      base_volume: bv.score,
      buyer_capita: bc.score,
      price_position: pp.score,
    },
    // Runup penalty diagnostics (FIX SG5)
    runup_10d_pct: runup10dPct,
    runup_penalty: runupPenalty,
    base_score: baseScore,
    // Normalized 0..1 per-signal contributions (for diagnostics / calibration)
    normalized: {
      smart_money: SIGNAL_MAX.smart_money > 0 ? sm.score / SIGNAL_MAX.smart_money : 0,
      technical: SIGNAL_MAX.technical > 0 ? tech.score / SIGNAL_MAX.technical : 0,
      fundamental: SIGNAL_MAX.fundamental > 0 ? fund.score / SIGNAL_MAX.fundamental : 0,
      base_volume: SIGNAL_MAX.base_volume > 0 ? bv.score / SIGNAL_MAX.base_volume : 0,
      buyer_capita: SIGNAL_MAX.buyer_capita > 0 ? bc.score / SIGNAL_MAX.buyer_capita : 0,
      price_position: SIGNAL_MAX.price_position > 0 ? pp.score / SIGNAL_MAX.price_position : 0,
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

module.exports = { calculateCompositeScore, DEFAULT_WEIGHTS, SIGNAL_MAX };
