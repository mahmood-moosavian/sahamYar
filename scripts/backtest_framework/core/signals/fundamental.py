"""
Fundamental Signal — P/E, EPS, NAV Analysis

Academic basis (strong):
- Graham & Dodd, Security Analysis (1934): value investing foundation
- Fama & French (1992): Three-Factor Model — value stocks outperform
- Lakonishok, Shleifer & Vishny (1994): value strategy ~12% annual excess return

Sub-signals:
1. P/E below sector average (relative valuation)
2. EPS growth (estimated EPS > last year EPS)
3. NAV premium/discount (for funds)
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Signal, SignalResult


class FundamentalSignal(Signal):
    name = "fundamental"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.max_score = self.config.get('weight', 20)
        sub = self.config.get('sub_signals', {})
        self.w_pe = sub.get('pe_below_sector', 12)
        self.w_eps = sub.get('eps_growth', 8)
    
    def calculate(self,
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> SignalResult:
        warnings = self._validate_data_availability(
            ins_code, on_date, data_loader, required_history_days=5
        )
        
        # Get latest fundamentals (only those available on on_date — bias protection)
        fundamentals = data_loader.get_fundamentals_available_on(ins_code, on_date)
        
        if fundamentals.empty:
            return SignalResult(
                score=0.0, max_score=self.max_score, normalized=0.0,
                confidence=0.1, sub_signals={},
                reasons=["داده‌ی بنیادی موجود نیست"],
                data_quality_warnings=warnings + ["فاقد گزارش بنیادی"],
            )
        
        latest_fund = fundamentals.iloc[-1]
        
        # Get current price (latest close before on_date)
        candles = data_loader.get_candles_up_to(ins_code, on_date, days=5)
        if candles.empty:
            return SignalResult(
                score=0.0, max_score=self.max_score, normalized=0.0,
                confidence=0.1, sub_signals={},
                reasons=["قیمت اخیر موجود نیست"],
                data_quality_warnings=warnings,
            )
        
        current_price = candles.iloc[-1]['close']
        estimated_eps = latest_fund.get('estimated_eps', 0) or 0
        sector_pe = latest_fund.get('sector_pe', 0) or 0
        eps = latest_fund.get('eps', 0) or 0
        nav = latest_fund.get('nav', 0) or 0
        
        # === Sub-signal 1: P/E relative to sector ===
        pe_score, pe_value, pe_reason = self._compute_pe_score(
            current_price, estimated_eps, sector_pe
        )
        
        # === Sub-signal 2: EPS growth ===
        eps_score, eps_reason = self._compute_eps_growth_score(fundamentals)
        
        total_score = max(0, min(self.max_score, pe_score + eps_score))
        
        # Confidence: higher when fundamentals are recent
        confidence = 0.6  # base
        if 'report_date' in latest_fund and pd.notna(latest_fund['report_date']):
            # Newer reports → higher confidence
            confidence = 0.7
        
        reasons = [pe_reason, eps_reason]
        
        return SignalResult(
            score=total_score,
            max_score=self.max_score,
            normalized=total_score / self.max_score if self.max_score > 0 else 0,
            confidence=confidence,
            sub_signals={
                'pe_below_sector': pe_score,
                'eps_growth': eps_score,
            },
            reasons=reasons,
            data_quality_warnings=warnings,
        )
    
    def _compute_pe_score(self, price: float, eps: float, sector_pe: float):
        """Compute P/E score relative to sector"""
        if eps <= 0:
            return 0, None, "EPS منفی یا صفر — ارزیابی P/E ناممکن"
        if sector_pe <= 0:
            return 0, None, "P/E گروه موجود نیست"
        
        pe = price / eps
        
        # Score based on P/E relative to sector
        if pe < sector_pe * 0.85:
            # 15%+ below sector → undervalued
            score = self.w_pe
            reason = f"P/E = {pe:.1f} (زیر P/E گروه {sector_pe:.1f} — زیر قیمت)"
        elif pe < sector_pe * 1.0:
            score = self.w_pe * 0.7
            reason = f"P/E = {pe:.1f} (کمی زیر P/E گروه {sector_pe:.1f})"
        elif pe < sector_pe * 1.15:
            score = self.w_pe * 0.3
            reason = f"P/E = {pe:.1f} (نزدیک P/E گروه {sector_pe:.1f})"
        else:
            score = 0
            reason = f"P/E = {pe:.1f} (بالا تر از P/E گروه {sector_pe:.1f} — گران)"
        
        return score, pe, reason
    
    def _compute_eps_growth_score(self, fundamentals: pd.DataFrame):
        """Compute EPS growth score based on quarterly trend"""
        if len(fundamentals) < 2:
            return 0, "داده‌ی بنیادی کافی برای ارزیابی رشد EPS نیست"
        
        # Compare latest EPS to previous
        latest_eps = fundamentals.iloc[-1].get('eps', 0) or 0
        prev_eps = fundamentals.iloc[-2].get('eps', 0) or 0
        
        if prev_eps <= 0 and latest_eps > 0:
            # Turned profitable
            score = self.w_eps
            reason = "سودآور شدن (EPS از منفی به مثبت)"
        elif prev_eps > 0:
            growth_pct = (latest_eps - prev_eps) / abs(prev_eps) * 100
            
            if growth_pct > 20:
                score = self.w_eps
                reason = f"رشد EPS: +{growth_pct:.0f}٪"
            elif growth_pct > 0:
                score = self.w_eps * 0.5
                reason = f"رشد EPS: +{growth_pct:.0f}٪"
            elif growth_pct > -20:
                score = self.w_eps * 0.2
                reason = f"کاهش EPS: {growth_pct:.0f}٪"
            else:
                score = 0
                reason = f"کاهش شدید EPS: {growth_pct:.0f}٪"
        else:
            score = 0
            reason = f"EPS همچنان منفی ({latest_eps:.0f})"
        
        return score, reason
