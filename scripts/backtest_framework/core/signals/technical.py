"""
Technical Signal — RSI, MFI, MACD, EMA Trend

Academic basis:
- Wilder (1978): RSI developed (heuristic, no strong academic backing)
- Brock, Lakonishok, LeBaron (1992): MA crossovers have predictive power
- Neely et al. (2014): Technical analysis has ~52-55% accuracy out-of-sample

Sub-signals:
1. RSI(14) — oversold < 30, overbought > 70
2. MFI(14) — money flow with volume
3. MACD crossover — histogram > 0 = bullish
4. Trend alignment — EMA20 > EMA50 > EMA200
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Signal, SignalResult


class TechnicalSignal(Signal):
    name = "technical"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.max_score = self.config.get('weight', 30)
        sub = self.config.get('sub_signals', {})
        self.w_rsi = sub.get('rsi_14', 8)
        self.w_mfi = sub.get('mfi_14', 7)
        self.w_macd = sub.get('macd_crossover', 8)
        self.w_trend = sub.get('trend_alignment', 7)
        
        # Indicator parameters
        self.rsi_period = 14
        self.mfi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.ema_short = 20
        self.ema_mid = 50
        self.ema_long = 200
    
    def calculate(self,
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> SignalResult:
        # Need at least 200+ days for EMA200
        warnings = self._validate_data_availability(
            ins_code, on_date, data_loader, required_history_days=210
        )
        
        candles = data_loader.get_candles_up_to(ins_code, on_date, days=250)
        if len(candles) < 30:
            return SignalResult(
                score=0.0, max_score=self.max_score, normalized=0.0,
                confidence=0.1, sub_signals={},
                reasons=["داده‌ی کندل کافی برای تحلیل تکنیکال نیست"],
                data_quality_warnings=warnings,
            )
        
        closes = candles['close'].values
        highs = candles['high'].values
        lows = candles['low'].values
        volumes = candles['volume'].values.astype(float)
        
        # === Sub-signal 1: RSI ===
        rsi_score, rsi_value, rsi_reason = self._compute_rsi(closes)
        
        # === Sub-signal 2: MFI ===
        mfi_score, mfi_value, mfi_reason = self._compute_mfi(highs, lows, closes, volumes)
        
        # === Sub-signal 3: MACD ===
        macd_score, macd_value, macd_reason = self._compute_macd(closes)
        
        # === Sub-signal 4: Trend alignment ===
        trend_score, trend_reason = self._compute_trend(closes)
        
        total_score = max(0, min(self.max_score, rsi_score + mfi_score + macd_score + trend_score))
        confidence = min(1.0, len(candles) / 200 * 0.4 + 0.4)  # higher confidence with more data
        
        reasons = [rsi_reason, mfi_reason, macd_reason, trend_reason]
        
        return SignalResult(
            score=total_score,
            max_score=self.max_score,
            normalized=total_score / self.max_score if self.max_score > 0 else 0,
            confidence=confidence,
            sub_signals={
                'rsi_14': rsi_score,
                'mfi_14': mfi_score,
                'macd_crossover': macd_score,
                'trend_alignment': trend_score,
            },
            reasons=reasons,
            data_quality_warnings=warnings,
        )
    
    def _compute_rsi(self, closes: np.ndarray):
        """Compute RSI and return (score, value, reason)"""
        if len(closes) < self.rsi_period + 1:
            return 0, None, "داده‌ی کافی برای RSI نیست"
        
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Wilder's smoothing
        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Score: oversold (RSI < 30) = high score
        if rsi < 30:
            score = self.w_rsi
            reason = f"RSI = {rsi:.1f} (اشباع فروش — فرصت خرید)"
        elif rsi > 70:
            score = 0
            reason = f"RSI = {rsi:.1f} (اشباع خرید — احتیاط)"
        else:
            # Linear scale: 30 → 8 points, 70 → 0 points
            score = self.w_rsi * max(0, (70 - rsi) / 40)
            reason = f"RSI = {rsi:.1f} (نوتری)"
        
        return score, rsi, reason
    
    def _compute_mfi(self, highs, lows, closes, volumes):
        """Compute Money Flow Index"""
        if len(closes) < self.mfi_period + 1:
            return 0, None, "داده‌ی کافی برای MFI نیست"
        
        typical_prices = (highs + lows + closes) / 3
        money_flows = typical_prices * volumes
        
        # Money flow ratio
        raw_money_flow = np.where(
            np.diff(closes) > 0, money_flows[1:],
            np.where(np.diff(closes) < 0, -money_flows[1:], 0)
        )
        
        pos_flow = np.sum(np.where(raw_money_flow[-self.mfi_period:] > 0, 
                                    raw_money_flow[-self.mfi_period:], 0))
        neg_flow = np.abs(np.sum(np.where(raw_money_flow[-self.mfi_period:] < 0, 
                                           raw_money_flow[-self.mfi_period:], 0)))
        
        if neg_flow == 0:
            mfi = 100.0
        else:
            money_ratio = pos_flow / neg_flow
            mfi = 100 - (100 / (1 + money_ratio))
        
        # Score: MFI < 20 = high score
        if mfi < 20:
            score = self.w_mfi
            reason = f"MFI = {mfi:.1f} (اشباع فروش حجمی)"
        elif mfi > 80:
            score = 0
            reason = f"MFI = {mfi:.1f} (اشباع خرید حجمی)"
        else:
            score = self.w_mfi * max(0, (80 - mfi) / 60)
            reason = f"MFI = {mfi:.1f} (نوتری)"
        
        return score, mfi, reason
    
    def _compute_macd(self, closes: np.ndarray):
        """Compute MACD and score crossover"""
        if len(closes) < self.macd_slow + self.macd_signal:
            return 0, None, "داده‌ی کافی برای MACD نیست"
        
        # Compute EMAs
        ema_fast = self._compute_ema(closes, self.macd_fast)
        ema_slow = self._compute_ema(closes, self.macd_slow)
        
        # MACD line
        macd_line = np.array(ema_fast) - np.array(ema_slow)
        
        # Signal line (EMA of MACD)
        signal_line = self._compute_ema(macd_line, self.macd_signal)
        
        # Histogram
        if len(macd_line) == 0 or len(signal_line) == 0:
            return 0, None, "محاسبه‌ی MACD ناموفق"
        
        histogram = macd_line[-1] - signal_line[-1]
        
        if histogram > 0:
            # Check if it's a fresh crossover (was negative yesterday)
            if len(macd_line) >= 2 and len(signal_line) >= 2:
                prev_hist = macd_line[-2] - signal_line[-2]
                if prev_hist <= 0:
                    score = self.w_macd  # Fresh bullish crossover
                    reason = "کراس صعودی MACD (سیگنال خرید تازه)"
                else:
                    score = self.w_macd * 0.6
                    reason = f"MACD مثبت ({histogram:.2f})"
            else:
                score = self.w_macd * 0.6
                reason = f"MACD مثبت ({histogram:.2f})"
        else:
            score = 0
            reason = f"MACD منفی ({histogram:.2f})"
        
        return score, histogram, reason
    
    def _compute_trend(self, closes: np.ndarray):
        """Compute trend alignment based on EMA stacking"""
        if len(closes) < self.ema_long:
            return 0, "داده‌ی کافی برای EMA200 نیست"
        
        ema20 = self._compute_ema(closes, self.ema_short)[-1]
        ema50 = self._compute_ema(closes, self.ema_mid)[-1]
        ema200 = self._compute_ema(closes, self.ema_long)[-1]
        
        # Bullish trend: EMA20 > EMA50 > EMA200
        if ema20 > ema50 > ema200:
            score = self.w_trend
            reason = "روند صعودی (EMA20 > EMA50 > EMA200)"
        elif ema20 > ema50:
            score = self.w_trend * 0.5
            reason = "روند صعودی کوتاه‌مدت"
        elif ema20 < ema50 < ema200:
            score = 0
            reason = "روند نزولی قوی"
        else:
            score = self.w_trend * 0.25
            reason = "روند نامشخص"
        
        return score, reason
    
    def _compute_ema(self, values: np.ndarray, period: int) -> np.ndarray:
        """Compute Exponential Moving Average"""
        if len(values) < period:
            return np.array([])
        multiplier = 2 / (period + 1)
        ema = [values[0]]
        for v in values[1:]:
            ema.append(v * multiplier + ema[-1] * (1 - multiplier))
        return np.array(ema)
