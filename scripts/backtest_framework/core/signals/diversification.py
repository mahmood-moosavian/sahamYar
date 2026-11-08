"""
Diversification Signal — Portfolio Correlation & Sector Concentration

Academic basis (strongest):
- Markowitz (1952): Modern Portfolio Theory — Nobel 1990
- Sharpe (1964): CAPM — Nobel 1990
- Diversification is the only "free lunch" in finance

This signal does NOT predict prices — it improves risk-adjusted return.
It's the most reliable layer because it's based on established theory.

Sub-signals:
1. Low correlation with existing portfolio
2. Adds new sector exposure (diversification benefit)
"""
import pandas as pd
import numpy as np
from typing import Optional
from .base import Signal, SignalResult


class DiversificationSignal(Signal):
    name = "diversification"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.max_score = self.config.get('weight', 15)
        sub = self.config.get('sub_signals', {})
        self.w_corr = sub.get('low_correlation', 10)
        self.w_sector = sub.get('new_sector', 5)
        self.correlation_window = 60  # days for correlation calculation
    
    def calculate(self,
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> SignalResult:
        warnings = self._validate_data_availability(
            ins_code, on_date, data_loader, required_history_days=70
        )
        
        # If user has no portfolio, give neutral score (we can't measure diversification)
        if portfolio is None or portfolio.empty:
            return SignalResult(
                score=self.max_score * 0.5,  # neutral
                max_score=self.max_score,
                normalized=0.5,
                confidence=0.3,
                sub_signals={'low_correlation': 0, 'new_sector': 0},
                reasons=["کاربر پورتفویی وارد نکرده — ارزیابی تنوع ممکن نیست"],
                data_quality_warnings=warnings,
            )
        
        # === Sub-signal 1: Correlation with portfolio ===
        corr_score, correlation_value, corr_reason = self._compute_correlation(
            ins_code, on_date, data_loader, portfolio
        )
        
        # === Sub-signal 2: Sector diversification ===
        sector_score, sector_reason = self._compute_sector_score(
            ins_code, on_date, data_loader, portfolio
        )
        
        total_score = max(0, min(self.max_score, corr_score + sector_score))
        confidence = 0.8  # High confidence in correlation calculation
        
        return SignalResult(
            score=total_score,
            max_score=self.max_score,
            normalized=total_score / self.max_score if self.max_score > 0 else 0,
            confidence=confidence,
            sub_signals={
                'low_correlation': corr_score,
                'new_sector': sector_score,
            },
            reasons=[corr_reason, sector_reason],
            data_quality_warnings=warnings,
        )
    
    def _compute_correlation(self, ins_code, on_date, data_loader, portfolio):
        """Compute correlation between target symbol and portfolio's weighted returns"""
        # Get target symbol's returns
        target_candles = data_loader.get_candles_up_to(ins_code, on_date, days=self.correlation_window + 10)
        if len(target_candles) < self.correlation_window:
            return 0, None, "داده‌ی تاریخی کافی برای محاسبه‌ی هم‌بستگی نیست"
        
        target_returns = target_candles['close'].pct_change().dropna().tail(self.correlation_window)
        
        # Compute portfolio weighted returns
        portfolio_returns_list = []
        weights = []
        
        symbols = data_loader.load_symbols()
        
        for _, holding in portfolio.iterrows():
            hold_ins_code = holding['ins_code']
            qty = holding.get('quantity', 0)
            buy_price = holding.get('buy_price', 0)
            value = qty * buy_price
            weights.append(value)
            
            hold_candles = data_loader.get_candles_up_to(hold_ins_code, on_date, days=self.correlation_window + 10)
            if len(hold_candles) < self.correlation_window:
                continue
            hold_returns = hold_candles['close'].pct_change().dropna().tail(self.correlation_window)
            portfolio_returns_list.append(hold_returns)
        
        if not portfolio_returns_list:
            return 0, None, "داده‌ی پورتفوی کاربر ناکافی"
        
        # Align indices
        min_len = min(len(r) for r in portfolio_returns_list)
        portfolio_returns_list = [r.tail(min_len) for r in portfolio_returns_list]
        target_returns = target_returns.tail(min_len)
        
        # Weighted portfolio returns
        total_weight = sum(weights[:len(portfolio_returns_list)])
        if total_weight == 0:
            return 0, None, "ارزش پورتفو صفر است"
        
        weights_normalized = [w / total_weight for w in weights[:len(portfolio_returns_list)]]
        
        portfolio_combined = pd.DataFrame(portfolio_returns_list).T.fillna(0)
        portfolio_weighted = (portfolio_combined * weights_normalized).sum(axis=1)
        
        # Compute correlation
        if len(target_returns) != len(portfolio_weighted):
            target_returns = target_returns.reset_index(drop=True)
            portfolio_weighted = portfolio_weighted.reset_index(drop=True)
        
        correlation = target_returns.corr(portfolio_weighted)
        
        if pd.isna(correlation):
            return 0, None, "محاسبه‌ی هم‌بستگی ناممکن"
        
        # Score: low correlation = high score
        if correlation < 0.3:
            score = self.w_corr
            reason = f"هم‌بستگی پایین با پورتفو: {correlation:.2f} (کمک به تنوع)"
        elif correlation < 0.6:
            score = self.w_corr * 0.5
            reason = f"هم‌بستگی متوسط: {correlation:.2f}"
        elif correlation < 0.8:
            score = self.w_corr * 0.2
            reason = f"هم‌بستگی بالا: {correlation:.2f}"
        else:
            score = 0
            reason = f"هم‌بستگی بسیار بالا: {correlation:.2f} (افزایش تمرکز)"
        
        return score, correlation, reason
    
    def _compute_sector_score(self, ins_code, on_date, data_loader, portfolio):
        """Check if symbol adds a new sector to portfolio"""
        symbols = data_loader.load_symbols()
        target_sym = symbols[symbols['ins_code'] == ins_code]
        if target_sym.empty:
            return 0, "نماد یافت نشد"
        
        target_sector = target_sym.iloc[0]['sector_code']
        
        # Get sectors in portfolio
        portfolio_sectors = []
        sector_weights = {}
        total_weight = 0
        
        for _, holding in portfolio.iterrows():
            hold_sym = symbols[symbols['ins_code'] == holding['ins_code']]
            if hold_sym.empty:
                continue
            hold_sector = hold_sym.iloc[0]['sector_code']
            qty = holding.get('quantity', 0)
            buy_price = holding.get('buy_price', 0)
            value = qty * buy_price
            
            portfolio_sectors.append(hold_sector)
            sector_weights[hold_sector] = sector_weights.get(hold_sector, 0) + value
            total_weight += value
        
        if total_weight == 0:
            return 0, "ارزش پورتفو صفر"
        
        # Sort sectors by weight
        sorted_sectors = sorted(sector_weights.items(), key=lambda x: -x[1])
        top_3_sectors = [s[0] for s in sorted_sectors[:3]]
        top_3_weight_pct = sum(s[1] for s in sorted_sectors[:3]) / total_weight * 100
        
        # Check if target sector is in top 3
        if target_sector not in top_3_sectors:
            score = self.w_sector
            reason = f"سهم در گروه صنعتی جدید است (نه در ۳ گروه پروزن پورتفو)"
        else:
            # Check concentration of this sector
            target_sector_weight = sector_weights[target_sector] / total_weight * 100
            if target_sector_weight > 30:
                score = 0
                reason = f"گروه صنعتی این سهم {target_sector_weight:.0f}٪ پورتفو را تشکیل می‌دهد — تمرکز خطرناک"
            elif target_sector_weight > 20:
                score = self.w_sector * 0.3
                reason = f"گروه صنعتی پروزن ({target_sector_weight:.0f}٪)"
            else:
                score = self.w_sector * 0.6
                reason = f"در گروه صنعتی موجود ({target_sector_weight:.0f}٪)"
        
        return score, reason
