"""
Additional Signals — Volume-based and Price Position signals

Added based on backtest findings:
- BaseVolumeSignal: حجم مبنا (regulatory minimum volume)
- BuyerCapitaSignal: سرانه خریدار (buyer per capita)
- PricePositionSignal: موقعیت قیمت نسبت به کف/سقف سال
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Signal, SignalResult


class BaseVolumeSignal(Signal):
    """حجم مبنا — regulatory minimum volume check
    
    In Iranian market, if today's volume < base_vol, the closing price
    is not considered valid for next day's price limit calculation.
    Stocks that meet base volume are more reliable.
    
    Also, volume > 2x base_vol indicates strong interest.
    """
    name = "base_volume"
    max_score = 8.0
    
    def calculate(self,
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> SignalResult:
        warnings = self._validate_data_availability(
            ins_code, on_date, data_loader, required_history_days=30
        )
        
        # Get recent candles (need to compute base volume)
        candles = data_loader.get_candles_up_to(ins_code, on_date, days=30)
        
        if len(candles) < 5:
            return SignalResult(
                score=0.0, max_score=self.max_score, normalized=0.0,
                confidence=0.1, sub_signals={},
                reasons=["داده‌ی کافی برای بررسی حجم مبنا نیست"],
                data_quality_warnings=warnings,
            )
        
        latest = candles.iloc[-1]
        today_volume = latest['volume']
        
        # Estimate base volume from historical data
        # In real TSETMC data, base_vol is provided. For synthetic data,
        # we estimate as median of last 20 days volumes * 0.3
        recent_volumes = candles['volume'].tail(20).values
        estimated_base_vol = np.median(recent_volumes) * 0.3
        
        if estimated_base_vol == 0:
            return SignalResult(
                score=0.0, max_score=self.max_score, normalized=0.0,
                confidence=0.1, sub_signals={},
                reasons=["حجم مبنا قابل محاسبه نیست"],
                data_quality_warnings=warnings,
            )
        
        vol_ratio = today_volume / estimated_base_vol
        
        if vol_ratio >= 2.0:
            score = self.max_score
            reason = f"حجم امروز {vol_ratio:.1f}× حجم مبنا (تقاضای قوی)"
        elif vol_ratio >= 1.5:
            score = self.max_score * 0.7
            reason = f"حجم امروز {vol_ratio:.1f}× حجم مبنا (تقاضای خوب)"
        elif vol_ratio >= 1.0:
            score = self.max_score * 0.4
            reason = f"حجم امروز {vol_ratio:.1f}× حجم مبنا (متوسط)"
        elif vol_ratio >= 0.7:
            score = self.max_score * 0.2
            reason = f"حجم امروز {vol_ratio:.1f}× حجم مبنا (ضعیف)"
        else:
            score = -self.max_score * 0.3  # penalty for low volume
            reason = f"حجم امروز فقط {vol_ratio:.1f}× حجم مبنا (هشدار: قیمت پایانی نامعتبر)"
        
        confidence = min(1.0, len(candles) / 20)
        
        return SignalResult(
            score=max(0, score), max_score=self.max_score,
            normalized=max(0, score) / self.max_score,
            confidence=confidence,
            sub_signals={'volume_ratio': vol_ratio},
            reasons=[reason],
            data_quality_warnings=warnings,
        )


class BuyerCapitaSignal(Signal):
    """سرانه خریدار — buyer per capita analysis
    
    Measures average volume per buyer:
    - High capita = few large buyers (institutional accumulation)
    - Low capita = many small buyers (retail enthusiasm)
    
    For BUY signals, we prefer high legal buyer capita.
    """
    name = "buyer_capita"
    max_score = 8.0
    
    def calculate(self,
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> SignalResult:
        warnings = self._validate_data_availability(
            ins_code, on_date, data_loader, required_history_days=10
        )
        
        # Get latest client type data
        client_types = data_loader.load_client_types()
        sym_ct = client_types[
            (client_types['ins_code'] == ins_code) &
            (client_types['date_jalali'] < on_date)
        ].tail(5)
        
        if len(sym_ct) < 3:
            return SignalResult(
                score=0.0, max_score=self.max_score, normalized=0.0,
                confidence=0.1, sub_signals={},
                reasons=["داده‌ی حقوقی/حقیقی کافی برای سرانه نیست"],
                data_quality_warnings=warnings,
            )
        
        latest = sym_ct.iloc[-1]
        
        # Compute per-capita volumes
        if latest['buy_legal_count'] > 0:
            legal_capita = latest['buy_legal_volume'] / latest['buy_legal_count']
        else:
            legal_capita = 0
        
        if latest['buy_real_count'] > 0:
            real_capita = latest['buy_real_volume'] / latest['buy_real_count']
        else:
            real_capita = 0
        
        # Score based on ratio
        if real_capita > 0:
            ratio = legal_capita / real_capita
        else:
            ratio = 1.0 if legal_capita > 0 else 0
        
        if ratio >= 10:
            score = self.max_score
            reason = f"سرانه خریدار حقوقی {ratio:.0f}× حقیقی (حقوقی بزرگ در حال خرید)"
        elif ratio >= 5:
            score = self.max_score * 0.7
            reason = f"سرانه خریدار حقوقی {ratio:.1f}× حقیقی (حقوقی قوی)"
        elif ratio >= 2:
            score = self.max_score * 0.4
            reason = f"سرانه خریدار حقوقی {ratio:.1f}× حقیقی (حقوقی فعال)"
        elif ratio >= 1:
            score = self.max_score * 0.2
            reason = f"سرانه خریدار حقوقی {ratio:.1f}× حقیقی (متوسط)"
        else:
            score = 0
            reason = f"سرانه خریدار حقوقی {ratio:.1f}× حقیقی (حقیقی غالب)"
        
        confidence = min(1.0, len(sym_ct) / 5 * 0.5 + 0.3)
        
        return SignalResult(
            score=score, max_score=self.max_score,
            normalized=score / self.max_score,
            confidence=confidence,
            sub_signals={'legal_to_real_capita_ratio': ratio},
            reasons=[reason],
            data_quality_warnings=warnings,
        )


class PricePositionSignal(Signal):
    """موقعیت قیمت نسبت به کف/سقف سال
    
    Where is current price relative to 52-week range?
    - Near 52-week low (position < 0.2) = potential value
    - Near 52-week high (position > 0.8) = potential overbought
    
    Based on mean reversion theory.
    """
    name = "price_position"
    max_score = 7.0
    
    def calculate(self,
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> SignalResult:
        warnings = self._validate_data_availability(
            ins_code, on_date, data_loader, required_history_days=252
        )
        
        # Need ~1 year of data for 52-week high/low
        candles = data_loader.get_candles_up_to(ins_code, on_date, days=252)
        
        if len(candles) < 100:
            return SignalResult(
                score=0.0, max_score=self.max_score, normalized=0.0,
                confidence=0.2, sub_signals={},
                reasons=["داده‌ی کافی برای محاسبه‌ی کف/سقف سال نیست"],
                data_quality_warnings=warnings,
            )
        
        year_high = candles['high'].max()
        year_low = candles['low'].min()
        current_close = candles.iloc[-1]['close']
        
        if year_high == year_low:
            return SignalResult(
                score=0.0, max_score=self.max_score, normalized=0.0,
                confidence=0.3, sub_signals={},
                reasons=["بازه‌ی قیمتی سال صفر است"],
                data_quality_warnings=warnings,
            )
        
        # Position: 0 = at year low, 1 = at year high
        position = (current_close - year_low) / (year_high - year_low)
        
        # Score: low position = high score (value opportunity)
        if position < 0.2:
            score = self.max_score
            reason = f"قیمت نزدیک کف سال (موقعیت: {position*100:.0f}٪) — فرصت خرید"
        elif position < 0.4:
            score = self.max_score * 0.7
            reason = f"قیمت در محدوده‌ی پایین سال (موقعیت: {position*100:.0f}٪)"
        elif position < 0.6:
            score = self.max_score * 0.4
            reason = f"قیمت در میانه‌ی سال (موقعیت: {position*100:.0f}٪)"
        elif position < 0.8:
            score = self.max_score * 0.2
            reason = f"قیمت در محدوده‌ی بالا (موقعیت: {position*100:.0f}٪)"
        else:
            score = 0
            reason = f"قیمت نزدیک سقف سال (موقعیت: {position*100:.0f}٪) — احتیاط"
        
        confidence = min(1.0, len(candles) / 252 * 0.7 + 0.3)
        
        return SignalResult(
            score=score, max_score=self.max_score,
            normalized=score / self.max_score,
            confidence=confidence,
            sub_signals={'year_position': position},
            reasons=[reason],
            data_quality_warnings=warnings,
        )
