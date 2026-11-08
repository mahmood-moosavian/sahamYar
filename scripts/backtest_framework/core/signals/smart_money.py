"""
Smart Money Signal — حقوقی/حقیقی Analysis

This is the strongest signal layer for Iranian market.
Based on the observation that legal entities (banks, investment companies, funds)
often have material non-public information and trade ahead of major moves.

Academic basis:
- Seyhun (1986, 1992): Insiders predict returns at ~60% accuracy
- Jaffe (1974): Insiders profit consistently
- Lakonishok & Lee (2001): Legal entity trades predict short-term returns

Sub-signals:
1. Net legal value over 5 days (positive = inflow)
2. Accumulation pattern (legal buyer + real seller = strong buy)
3. Smart money consistency (3+ days of inflow)
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Signal, SignalResult


class SmartMoneySignal(Signal):
    name = "smart_money"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.max_score = self.config.get('weight', 35)
        sub = self.config.get('sub_signals', {})
        self.w_net_legal = sub.get('net_legal_value_5d', 15)
        self.w_accumulation = sub.get('accumulation_pattern', 12)
        self.w_consistency = sub.get('smart_money_consistency', 8)
        self.lookback_days = 5
        self.consistency_days = 3
    
    def calculate(self,
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> SignalResult:
        warnings = self._validate_data_availability(
            ins_code, on_date, data_loader, required_history_days=10
        )
        
        # Get client types data up to (but NOT including) on_date
        # NOTE: TSETMC publishes client_types with 1-day delay, so we use on_date - 1
        client_types = data_loader.load_client_types()
        sym_ct = client_types[
            (client_types['ins_code'] == ins_code) &
            (client_types['date_jalali'] < on_date)
        ].tail(self.lookback_days)
        
        if len(sym_ct) < 3:
            return SignalResult(
                score=0.0,
                max_score=self.max_score,
                normalized=0.0,
                confidence=0.1,
                sub_signals={},
                reasons=["داده‌ی حقوقی/حقیقی کافی نیست"],
                data_quality_warnings=warnings + [f"فقط {len(sym_ct)} روز داده‌ی حقوقی/حقیقی موجود"],
            )
        
        # Sub-signal 1: Net legal value over lookback period
        net_legal_value = (sym_ct['buy_legal_value'].sum() - 
                          sym_ct['sell_legal_value'].sum())
        avg_daily_legal_value = (
            sym_ct['buy_legal_value'].mean() + sym_ct['sell_legal_value'].mean()
        )
        
        if avg_daily_legal_value > 0:
            net_legal_ratio = net_legal_value / avg_daily_legal_value
            # Clamp to [-1, 1]
            net_legal_ratio = max(-1.0, min(1.0, net_legal_ratio))
            # Convert to score: 0 if -1, full if +1
            net_legal_score = (net_legal_ratio + 1) / 2 * self.w_net_legal
        else:
            net_legal_ratio = 0
            net_legal_score = 0
            warnings.append("No legal entity activity")
        
        # Sub-signal 2: Accumulation pattern
        # Pattern: Legal buying > 2x legal selling AND Real selling > 1.5x real buying
        latest = sym_ct.iloc[-1]
        accumulation_score = 0.0
        accumulation_reason = ""
        
        if latest['sell_legal_volume'] > 0:
            legal_buy_sell_ratio = latest['buy_legal_volume'] / latest['sell_legal_volume']
        else:
            legal_buy_sell_ratio = 2.0 if latest['buy_legal_volume'] > 0 else 1.0
        
        if latest['buy_real_volume'] > 0:
            real_sell_buy_ratio = latest['sell_real_volume'] / latest['buy_real_volume']
        else:
            real_sell_buy_ratio = 2.0 if latest['sell_real_volume'] > 0 else 1.0
        
        if legal_buy_sell_ratio > 2.0 and real_sell_buy_ratio > 1.5:
            accumulation_score = self.w_accumulation
            accumulation_reason = "الگوی جمع‌آوری قوی (حقوقی خریدار، حقیقی فروشنده)"
        elif legal_buy_sell_ratio > 1.5:
            accumulation_score = self.w_accumulation * 0.6
            accumulation_reason = "حقوقی خریدار نسبی"
        elif legal_buy_sell_ratio < 0.5 and real_sell_buy_ratio < 0.67:
            accumulation_score = -self.w_accumulation * 0.5  # penalty
            accumulation_reason = "الگوی توزیع (حقوقی فروشنده، حقیقی خریدار)"
        
        # Sub-signal 3: Consistency
        # Check if legal inflow has been consistent for N days
        net_daily = sym_ct['buy_legal_value'] - sym_ct['sell_legal_value']
        positive_days = (net_daily > 0).sum()
        
        if positive_days >= self.consistency_days:
            consistency_score = self.w_consistency
            consistency_reason = f"ورود پول حقوقی در {positive_days} روز از {len(sym_ct)}"
        elif positive_days >= 2:
            consistency_score = self.w_consistency * 0.5
            consistency_reason = f"ورود پول حقوقی در {positive_days} روز"
        else:
            consistency_score = 0
            consistency_reason = "عدم تداوم ورود پول حقوقی"
        
        # Total score
        total_score = max(0, min(self.max_score, net_legal_score + accumulation_score + consistency_score))
        
        # Confidence: higher when we have more data and clear pattern
        confidence = min(1.0, len(sym_ct) / self.lookback_days * 0.5 + 
                         (0.5 if accumulation_score > 0 else 0.2))
        
        reasons = [
            accumulation_reason,
            consistency_reason,
            f"خالص ورود پول حقوقی (۵ روز): {self._format_toman(net_legal_value)}",
        ]
        
        return SignalResult(
            score=total_score,
            max_score=self.max_score,
            normalized=total_score / self.max_score if self.max_score > 0 else 0,
            confidence=confidence,
            sub_signals={
                'net_legal_value_5d': net_legal_score,
                'accumulation_pattern': accumulation_score,
                'smart_money_consistency': consistency_score,
            },
            reasons=reasons,
            data_quality_warnings=warnings,
        )
    
    def _format_toman(self, value: float) -> str:
        """Format value as Toman string"""
        if value is None:
            return "نامشخص"
        abs_val = abs(value)
        sign = "+" if value >= 0 else "-"
        if abs_val >= 1e9:
            return f"{sign}{abs_val/1e9:.2f} میلیارد تومان"
        elif abs_val >= 1e6:
            return f"{sign}{abs_val/1e6:.2f} میلیون تومان"
        elif abs_val >= 1e3:
            return f"{sign}{abs_val/1e3:.0f} هزار تومان"
        else:
            return f"{sign}{abs_val:.0f} تومان"
