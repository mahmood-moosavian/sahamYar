/**
 * Signals — All signal calculations for the Composite Score
 *
 * 7 signals across 4 layers:
 * 1. Smart Money (35 pts): net_legal_value, accumulation, consistency
 * 2. Technical (30 pts): RSI, MFI, MACD, trend alignment
 * 3. Fundamental (20 pts): P/E ratio, EPS growth
 * 4. Additional (23 pts): base volume, buyer capita, price position
 *
 * Total: 100 pts (scaled)
 */

// ============================================================
// Math helpers
// ============================================================

function computeEMA(values, period) {
  if (values.length < period) return [];
  const multiplier = 2 / (period + 1);
  const ema = [values[0]];
  for (let i = 1; i < values.length; i++) {
    ema.push(values[i] * multiplier + ema[ema.length - 1] * (1 - multiplier));
  }
  return ema;
}

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

function correlation(arr1, arr2) {
  const n = Math.min(arr1.length, arr2.length);
  if (n < 2) return 0;
  const m1 = mean(arr1.slice(0, n));
  const m2 = mean(arr2.slice(0, n));
  let num = 0, den1 = 0, den2 = 0;
  for (let i = 0; i < n; i++) {
    const d1 = arr1[i] - m1;
    const d2 = arr2[i] - m2;
    num += d1 * d2;
    den1 += d1 * d1;
    den2 += d2 * d2;
  }
  if (den1 === 0 || den2 === 0) return 0;
  return num / Math.sqrt(den1 * den2);
}

// ============================================================
// Smart Money Signal (35 pts max)
// ============================================================

function smartMoneySignal(insCode, onDate, dataLoader) {
  const lookback = 5;
  const ctData = dataLoader.getClientTypesUpTo(insCode, onDate, lookback + 2);

  if (ctData.length < 3) {
    return { score: 0, max: 35, reasons: ['داده‌ی حقوقی/حقیقی کافی نیست'], confidence: 0.1 };
  }

  const recent = ctData.slice(-lookback);

  // Sub-signal 1: Net legal value over lookback (15 pts)
  const netLegalValue = recent.reduce((sum, ct) =>
    sum + (ct.buy_legal_value - ct.sell_legal_value), 0);
  const avgDailyLegal = mean(recent.map(ct =>
    ct.buy_legal_value + ct.sell_legal_value));
  let netLegalRatio = avgDailyLegal > 0 ? netLegalValue / avgDailyLegal : 0;
  netLegalRatio = Math.max(-1, Math.min(1, netLegalRatio));
  const netLegalScore = (netLegalRatio + 1) / 2 * 15;

  // Sub-signal 2: Accumulation pattern (12 pts)
  const latest = recent[recent.length - 1];
  const legalBuySellRatio = latest.sell_legal_volume > 0
    ? latest.buy_legal_volume / latest.sell_legal_volume : 2;
  const realSellBuyRatio = latest.buy_real_volume > 0
    ? latest.sell_real_volume / latest.buy_real_volume : 1;

  let accScore = 0;
  let accReason = '';
  if (legalBuySellRatio > 2 && realSellBuyRatio > 1.5) {
    accScore = 12;
    accReason = 'الگوی جمع‌آوری قوی (حقوقی خریدار، حقیقی فروشنده)';
  } else if (legalBuySellRatio > 1.5) {
    accScore = 7;
    accReason = 'حقوقی خریدار نسبی';
  } else if (legalBuySellRatio < 0.5 && realSellBuyRatio < 0.67) {
    accScore = -6;
    accReason = 'الگوی توزیع (حقوقی فروشنده)';
  }

  // Sub-signal 3: Consistency (8 pts)
  const positiveDays = recent.filter(ct =>
    ct.buy_legal_value > ct.sell_legal_value).length;
  let consistencyScore = 0;
  let consistencyReason = '';
  if (positiveDays >= 3) {
    consistencyScore = 8;
    consistencyReason = `ورود پول حقوقی در ${positiveDays} روز از ${recent.length}`;
  } else if (positiveDays >= 2) {
    consistencyScore = 4;
    consistencyReason = `ورود پول حقوقی در ${positiveDays} روز`;
  }

  const totalScore = Math.max(0, Math.min(35, netLegalScore + accScore + consistencyScore));
  const confidence = Math.min(1, ctData.length / lookback * 0.5 + (accScore > 0 ? 0.5 : 0.2));

  return {
    score: totalScore,
    max: 35,
    confidence,
    reasons: [accReason, consistencyReason].filter(r => r),
  };
}

// ============================================================
// Technical Signal (30 pts max)
// ============================================================

function technicalSignal(insCode, onDate, dataLoader) {
  const candles = dataLoader.getCandlesUpTo(insCode, onDate, 250);

  if (candles.length < 30) {
    return { score: 0, max: 30, reasons: ['داده‌ی کندل کافی نیست'], confidence: 0.1 };
  }

  const closes = candles.map(c => c.close);
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  const volumes = candles.map(c => c.volume);

  // Sub-signal 1: RSI (8 pts)
  let rsiScore = 0, rsiValue = 0, rsiReason = '';
  if (closes.length >= 15) {
    const gains = [], losses = [];
    for (let i = 1; i < closes.length; i++) {
      const change = closes[i] - closes[i - 1];
      gains.push(change > 0 ? change : 0);
      losses.push(change < 0 ? -change : 0);
    }
    const period = 14;
    const avgGain = mean(gains.slice(-period));
    const avgLoss = mean(losses.slice(-period));
    rsiValue = avgLoss === 0 ? 100 : 100 - (100 / (1 + avgGain / avgLoss));

    if (rsiValue < 30) {
      rsiScore = 8;
      rsiReason = `RSI = ${rsiValue.toFixed(1)} (اشباع فروش)`;
    } else if (rsiValue > 70) {
      rsiScore = 0;
      rsiReason = `RSI = ${rsiValue.toFixed(1)} (اشباع خرید)`;
    } else {
      rsiScore = 8 * Math.max(0, (70 - rsiValue) / 40);
      rsiReason = `RSI = ${rsiValue.toFixed(1)}`;
    }
  }

  // Sub-signal 2: MFI (7 pts)
  let mfiScore = 0, mfiValue = 0, mfiReason = '';
  if (closes.length >= 15) {
    const typicalPrices = [];
    for (let i = 0; i < closes.length; i++) {
      typicalPrices.push((highs[i] + lows[i] + closes[i]) / 3);
    }
    const moneyFlows = typicalPrices.map((tp, i) => tp * volumes[i]);
    const rawFlows = [];
    for (let i = 1; i < closes.length; i++) {
      if (closes[i] > closes[i - 1]) rawFlows.push(moneyFlows[i]);
      else if (closes[i] < closes[i - 1]) rawFlows.push(-moneyFlows[i]);
      else rawFlows.push(0);
    }
    const period = 14;
    const recent = rawFlows.slice(-period);
    const posFlow = recent.filter(f => f > 0).reduce((a, b) => a + b, 0);
    const negFlow = Math.abs(recent.filter(f => f < 0).reduce((a, b) => a + b, 0));
    mfiValue = negFlow === 0 ? 100 : 100 - (100 / (1 + posFlow / negFlow));

    if (mfiValue < 20) {
      mfiScore = 7;
      mfiReason = `MFI = ${mfiValue.toFixed(1)} (اشباع فروش حجمی)`;
    } else if (mfiValue > 80) {
      mfiScore = 0;
      mfiReason = `MFI = ${mfiValue.toFixed(1)} (اشباع خرید حجمی)`;
    } else {
      mfiScore = 7 * Math.max(0, (80 - mfiValue) / 60);
      mfiReason = `MFI = ${mfiValue.toFixed(1)}`;
    }
  }

  // Sub-signal 3: MACD (8 pts)
  let macdScore = 0, macdReason = '';
  if (closes.length >= 35) {
    const ema12 = computeEMA(closes, 12);
    const ema26 = computeEMA(closes, 26);
    const macdLine = [];
    for (let i = 0; i < Math.min(ema12.length, ema26.length); i++) {
      macdLine.push(ema12[i] - ema26[i]);
    }
    const signalLine = computeEMA(macdLine, 9);
    if (macdLine.length > 0 && signalLine.length > 0) {
      const histogram = macdLine[macdLine.length - 1] - signalLine[signalLine.length - 1];
      if (histogram > 0) {
        macdScore = 8;
        macdReason = `MACD مثبت (${histogram.toFixed(2)})`;
      } else {
        macdScore = 0;
        macdReason = `MACD منفی (${histogram.toFixed(2)})`;
      }
    }
  }

  // Sub-signal 4: Trend alignment (7 pts)
  let trendScore = 0, trendReason = '';
  if (closes.length >= 200) {
    const ema20 = computeEMA(closes, 20);
    const ema50 = computeEMA(closes, 50);
    const ema200 = computeEMA(closes, 200);
    const e20 = ema20[ema20.length - 1];
    const e50 = ema50[ema50.length - 1];
    const e200 = ema200[ema200.length - 1];

    if (e20 > e50 && e50 > e200) {
      trendScore = 7;
      trendReason = 'روند صعودی (EMA20 > EMA50 > EMA200)';
    } else if (e20 > e50) {
      trendScore = 3.5;
      trendReason = 'روند صعودی کوتاه‌مدت';
    } else if (e20 < e50 && e50 < e200) {
      trendScore = 0;
      trendReason = 'روند نزولی قوی';
    } else {
      trendScore = 1.75;
      trendReason = 'روند نامشخص';
    }
  }

  const totalScore = Math.max(0, Math.min(30, rsiScore + mfiScore + macdScore + trendScore));
  const confidence = Math.min(1, closes.length / 200 * 0.4 + 0.4);

  return {
    score: totalScore,
    max: 30,
    confidence,
    reasons: [rsiReason, mfiReason, macdReason, trendReason].filter(r => r),
  };
}

// ============================================================
// Fundamental Signal (20 pts max)
// ============================================================

function fundamentalSignal(insCode, onDate, dataLoader) {
  const fundamentals = dataLoader.getFundamentalsFor(insCode);

  if (!fundamentals || fundamentals.length === 0) {
    return { score: 0, max: 20, reasons: ['داده‌ی بنیادی موجود نیست'], confidence: 0.1 };
  }

  const latest = fundamentals[fundamentals.length - 1];
  const candles = dataLoader.getCandlesUpTo(insCode, onDate, 5);

  if (candles.length === 0) {
    return { score: 0, max: 20, reasons: ['قیمت اخیر موجود نیست'], confidence: 0.1 };
  }

  const currentPrice = candles[candles.length - 1].close;
  const eps = parseFloat(latest.eps || latest.estimated_eps || 0);
  const sectorPe = parseFloat(latest.sector_pe || 0);

  // Sub-signal 1: P/E relative to sector (12 pts)
  let peScore = 0, peReason = '';
  if (eps > 0 && sectorPe > 0) {
    const pe = currentPrice / eps;
    if (pe < sectorPe * 0.85) {
      peScore = 12;
      peReason = `P/E = ${pe.toFixed(1)} (زیر P/E گروه ${sectorPe.toFixed(1)})`;
    } else if (pe < sectorPe) {
      peScore = 8.4;
      peReason = `P/E = ${pe.toFixed(1)} (کمی زیر گروه)`;
    } else if (pe < sectorPe * 1.15) {
      peScore = 3.6;
      peReason = `P/E = ${pe.toFixed(1)} (نزدیک گروه)`;
    } else {
      peScore = 0;
      peReason = `P/E = ${pe.toFixed(1)} (گران)`;
    }
  } else {
    peReason = 'EPS منفی یا صفر';
  }

  // Sub-signal 2: EPS growth (8 pts)
  let epsScore = 0, epsReason = '';
  if (fundamentals.length >= 2) {
    const prev = fundamentals[fundamentals.length - 2];
    const prevEps = parseFloat(prev.eps || 0);
    const latestEps = parseFloat(latest.eps || 0);

    if (prevEps <= 0 && latestEps > 0) {
      epsScore = 8;
      epsReason = 'سودآور شدن';
    } else if (prevEps > 0) {
      const growth = (latestEps - prevEps) / Math.abs(prevEps) * 100;
      if (growth > 20) {
        epsScore = 8;
        epsReason = `رشد EPS: +${growth.toFixed(0)}%`;
      } else if (growth > 0) {
        epsScore = 4;
        epsReason = `رشد EPS: +${growth.toFixed(0)}%`;
      } else if (growth > -20) {
        epsScore = 1.6;
        epsReason = `کاهش EPS: ${growth.toFixed(0)}%`;
      } else {
        epsReason = `کاهش شدید EPS: ${growth.toFixed(0)}%`;
      }
    }
  }

  const totalScore = Math.max(0, Math.min(20, peScore + epsScore));
  return {
    score: totalScore,
    max: 20,
    confidence: 0.6,
    reasons: [peReason, epsReason].filter(r => r),
  };
}

// ============================================================
// Base Volume Signal (8 pts max)
// ============================================================

function baseVolumeSignal(insCode, onDate, dataLoader) {
  const candles = dataLoader.getCandlesUpTo(insCode, onDate, 30);

  if (candles.length < 5) {
    return { score: 0, max: 8, reasons: ['داده‌ی کافی نیست'], confidence: 0.1 };
  }

  const latest = candles[candles.length - 1];
  const recent = candles.slice(-20);
  const recentVolumes = recent.map(c => c.volume);
  const medianVol = recentVolumes.sort((a, b) => a - b)[Math.floor(recentVolumes.length / 2)];
  const estimatedBaseVol = medianVol * 0.3;

  if (estimatedBaseVol === 0) {
    return { score: 0, max: 8, reasons: ['حجم مبنا قابل محاسبه نیست'], confidence: 0.1 };
  }

  const ratio = latest.volume / estimatedBaseVol;
  let score = 0, reason = '';

  if (ratio >= 2) {
    score = 8;
    reason = `حجم امروز ${ratio.toFixed(1)}× حجم مبنا (تقاضای قوی)`;
  } else if (ratio >= 1.5) {
    score = 5.6;
    reason = `حجم امروز ${ratio.toFixed(1)}× حجم مبنا`;
  } else if (ratio >= 1) {
    score = 3.2;
    reason = `حجم امروز ${ratio.toFixed(1)}× حجم مبنا`;
  } else if (ratio >= 0.7) {
    score = 1.6;
    reason = `حجم امروز ${ratio.toFixed(1)}× حجم مبنا (ضعیف)`;
  } else {
    score = 0;
    reason = `حجم امروز فقط ${ratio.toFixed(1)}× حجم مبنا (نامعتبر)`;
  }

  return { score, max: 8, confidence: Math.min(1, candles.length / 20), reasons: [reason] };
}

// ============================================================
// Buyer Capita Signal (8 pts max)
// ============================================================

function buyerCapitaSignal(insCode, onDate, dataLoader) {
  const ctData = dataLoader.getClientTypesUpTo(insCode, onDate, 5);

  if (ctData.length < 3) {
    return { score: 0, max: 8, reasons: ['داده‌ی حقوقی/حقیقی کافی نیست'], confidence: 0.1 };
  }

  const latest = ctData[ctData.length - 1];
  const legalCapita = latest.buy_legal_count > 0
    ? latest.buy_legal_volume / latest.buy_legal_count : 0;
  const realCapita = latest.buy_real_count > 0
    ? latest.buy_real_volume / latest.buy_real_count : 0;

  const ratio = realCapita > 0 ? legalCapita / realCapita : 1;
  let score = 0, reason = '';

  if (ratio >= 10) {
    score = 8;
    reason = `سرانه خریدار حقوقی ${ratio.toFixed(0)}× حقیقی (حقوقی بزرگ)`;
  } else if (ratio >= 5) {
    score = 5.6;
    reason = `سرانه حقوقی ${ratio.toFixed(1)}× حقیقی`;
  } else if (ratio >= 2) {
    score = 3.2;
    reason = `سرانه حقوقی ${ratio.toFixed(1)}× حقیقی`;
  } else if (ratio >= 1) {
    score = 1.6;
    reason = `سرانه حقوقی ${ratio.toFixed(1)}× حقیقی`;
  } else {
    reason = `سرانه حقوقی ${ratio.toFixed(1)}× حقیقی (حقیقی غالب)`;
  }

  return { score, max: 8, confidence: Math.min(1, ctData.length / 5 * 0.5 + 0.3), reasons: [reason] };
}

// ============================================================
// Price Position Signal (7 pts max)
// ============================================================

function pricePositionSignal(insCode, onDate, dataLoader) {
  const candles = dataLoader.getCandlesUpTo(insCode, onDate, 252);

  if (candles.length < 100) {
    return { score: 0, max: 7, reasons: ['داده‌ی کافی برای کف/سقف سال نیست'], confidence: 0.2 };
  }

  const yearHigh = Math.max(...candles.map(c => c.high));
  const yearLow = Math.min(...candles.map(c => c.low));
  const currentClose = candles[candles.length - 1].close;

  if (yearHigh === yearLow) {
    return { score: 0, max: 7, reasons: ['بازه‌ی قیمتی صفر'], confidence: 0.3 };
  }

  const position = (currentClose - yearLow) / (yearHigh - yearLow);
  let score = 0, reason = '';

  if (position < 0.2) {
    score = 7;
    reason = `قیمت نزدیک کف سال (${(position * 100).toFixed(0)}%) — فرصت خرید`;
  } else if (position < 0.4) {
    score = 4.9;
    reason = `قیمت در محدوده‌ی پایین (${(position * 100).toFixed(0)}%)`;
  } else if (position < 0.6) {
    score = 2.8;
    reason = `قیمت در میانه‌ی سال (${(position * 100).toFixed(0)}%)`;
  } else if (position < 0.8) {
    score = 1.4;
    reason = `قیمت در محدوده‌ی بالا (${(position * 100).toFixed(0)}%)`;
  } else {
    score = 0;
    reason = `قیمت نزدیک سقف سال (${(position * 100).toFixed(0)}%)`;
  }

  return { score, max: 7, confidence: Math.min(1, candles.length / 252 * 0.7 + 0.3), reasons: [reason] };
}

module.exports = {
  smartMoneySignal,
  technicalSignal,
  fundamentalSignal,
  baseVolumeSignal,
  buyerCapitaSignal,
  pricePositionSignal,
};
