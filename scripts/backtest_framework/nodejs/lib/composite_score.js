/**
 * Composite Score Calculator
 * Combines all 7 signals into a final score (0-100) and recommendation.
 */

const {
  smartMoneySignal,
  technicalSignal,
  fundamentalSignal,
  baseVolumeSignal,
  buyerCapitaSignal,
  pricePositionSignal,
} = require('./signals');

function calculateCompositeScore(insCode, onDate, dataLoader) {
  // Run all 7 signals
  const sm = smartMoneySignal(insCode, onDate, dataLoader);
  const tech = technicalSignal(insCode, onDate, dataLoader);
  const fund = fundamentalSignal(insCode, onDate, dataLoader);
  const bv = baseVolumeSignal(insCode, onDate, dataLoader);
  const bc = buyerCapitaSignal(insCode, onDate, dataLoader);
  const pp = pricePositionSignal(insCode, onDate, dataLoader);

  // Combine scores (max raw = 35+30+20+8+8+7 = 108)
  const rawScore = sm.score + tech.score + fund.score + bv.score + bc.score + pp.score;
  // Scale to 0-100
  const totalScore = Math.min(100, rawScore * 100 / 108);

  // Weighted confidence
  const weights = [35, 30, 20, 8, 8, 7];
  const confidences = [sm.confidence, tech.confidence, fund.confidence, bv.confidence, bc.confidence, pp.confidence];
  const weightedConf = weights.reduce((sum, w, i) => sum + w * confidences[i], 0) / weights.reduce((a, b) => a + b, 0);

  // Determine action based on score
  // Adjusted: strong_buy threshold raised from 75 to 85
  // because backtest showed 75-84 performed WORSE than 60-74
  let action, actionLabelFa;
  if (totalScore >= 85) { action = 'strong_buy'; actionLabelFa = 'خرید قوی'; }
  else if (totalScore >= 60) { action = 'buy'; actionLabelFa = 'خرید'; }
  else if (totalScore >= 45) { action = 'hold'; actionLabelFa = 'نگه‌داری'; }
  else if (totalScore >= 30) { action = 'reduce'; actionLabelFa = 'کاهش وزن'; }
  else { action = 'sell'; actionLabelFa = 'فروش'; }

  // Expected success rate (placeholder, will be calibrated from backtest)
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

module.exports = { calculateCompositeScore };
