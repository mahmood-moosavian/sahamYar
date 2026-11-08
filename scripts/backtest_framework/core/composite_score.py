"""
Composite Score Calculator
Combines all signal results into a final score and recommendation.

The composite score is a weighted combination of:
1. Smart Money Signal (35 points max)
2. Technical Signal (30 points max)
3. Fundamental Signal (20 points max)
4. Diversification Signal (15 points max)

Total: 100 points

Output includes confidence intervals based on backtest performance.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import pandas as pd
import numpy as np

from .signals import (
    Signal, SignalResult,
    SmartMoneySignal, TechnicalSignal,
    FundamentalSignal, DiversificationSignal
)


@dataclass
class Recommendation:
    """Final recommendation for a symbol"""
    ins_code: str
    on_date: int
    total_score: float              # 0-100
    action: str                     # strong_buy, buy, hold, reduce, sell
    action_label_fa: str            # خرید قوی، خرید، نگه‌داری، کاهش وزن، فروش
    
    # Score breakdown by layer
    breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Confidence and intervals
    confidence: float = 0.5         # 0-1
    expected_success_rate: float = 0.5   # Based on backtest
    confidence_interval_low: float = 0.0
    confidence_interval_high: float = 0.0
    
    # Risk management
    stop_loss_pct: float = 0.08     # -8%
    target_pct: float = 0.17        # +17%
    suggested_position_size_pct: float = 0.05  # 5% of portfolio
    
    # Explanations
    reasons: List[str] = field(default_factory=list)
    
    # Backtest basis
    backtest_sample_size: int = 0
    backtest_success_rate: float = 0.0
    
    def __post_init__(self):
        self._set_action()
    
    def _set_action(self):
        """Determine action based on score"""
        if self.total_score >= 75:
            self.action = "strong_buy"
            self.action_label_fa = "خرید قوی"
        elif self.total_score >= 60:
            self.action = "buy"
            self.action_label_fa = "خرید"
        elif self.total_score >= 45:
            self.action = "hold"
            self.action_label_fa = "نگه‌داری"
        elif self.total_score >= 30:
            self.action = "reduce"
            self.action_label_fa = "کاهش وزن"
        else:
            self.action = "sell"
            self.action_label_fa = "فروش"


class CompositeScoreCalculator:
    """Combine all signal results into a final recommendation"""
    
    # Action thresholds
    SCORE_THRESHOLDS = {
        'strong_buy': 75,
        'buy': 60,
        'hold': 45,
        'reduce': 30,
        'sell': 0,
    }
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # Initialize signal generators
        sm_config = self.config.get('COMPOSITE_SCORE', {}).get('smart_money', {})
        tech_config = self.config.get('COMPOSITE_SCORE', {}).get('technical', {})
        fund_config = self.config.get('COMPOSITE_SCORE', {}).get('fundamental', {})
        div_config = self.config.get('COMPOSITE_SCORE', {}).get('diversification', {})
        
        self.smart_money_signal = SmartMoneySignal(sm_config)
        self.technical_signal = TechnicalSignal(tech_config)
        self.fundamental_signal = FundamentalSignal(fund_config)
        self.diversification_signal = DiversificationSignal(div_config)
        
        # Risk config
        risk_cfg = self.config.get('RISK', {})
        self.default_stop_loss = risk_cfg.get('default_stop_loss_pct', 8.0) / 100
        self.default_target = risk_cfg.get('default_target_pct', 17.0) / 100
        self.max_position_size = risk_cfg.get('max_position_size_pct', 10.0) / 100
    
    def calculate(self,
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> Recommendation:
        """Calculate composite score for a symbol"""
        
        # Run each signal
        sm_result = self.smart_money_signal.calculate(ins_code, on_date, data_loader, portfolio)
        tech_result = self.technical_signal.calculate(ins_code, on_date, data_loader, portfolio)
        fund_result = self.fundamental_signal.calculate(ins_code, on_date, data_loader, portfolio)
        div_result = self.diversification_signal.calculate(ins_code, on_date, data_loader, portfolio)
        
        # Combine scores
        total_score = (
            sm_result.score +
            tech_result.score +
            fund_result.score +
            div_result.score
        )
        total_score = max(0, min(100, total_score))
        
        # Weighted confidence
        weights = [35, 30, 20, 15]
        confidences = [sm_result.confidence, tech_result.confidence, 
                       fund_result.confidence, div_result.confidence]
        weighted_conf = sum(w * c for w, c in zip(weights, confidences)) / sum(weights)
        
        # Collect all reasons
        all_reasons = []
        all_reasons.extend(sm_result.reasons)
        all_reasons.extend(tech_result.reasons)
        all_reasons.extend(fund_result.reasons)
        all_reasons.extend(div_result.reasons)
        
        # Calculate expected success rate based on score
        # This will be calibrated from actual backtest results
        expected_success_rate = self._estimate_success_rate(total_score)
        
        # Confidence interval (will be tightened with real backtest data)
        ci_low = max(0, expected_success_rate - 0.15)
        ci_high = min(1, expected_success_rate + 0.15)
        
        # Position size based on score and confidence
        if total_score >= 75:
            suggested_size = self.max_position_size  # 10%
        elif total_score >= 60:
            suggested_size = self.max_position_size * 0.7  # 7%
        elif total_score >= 45:
            suggested_size = self.max_position_size * 0.4  # 4%
        else:
            suggested_size = 0
        
        return Recommendation(
            ins_code=ins_code,
            on_date=on_date,
            total_score=total_score,
            action="",
            action_label_fa="",
            breakdown={
                'smart_money': sm_result.score,
                'technical': tech_result.score,
                'fundamental': fund_result.score,
                'diversification': div_result.score,
            },
            confidence=weighted_conf,
            expected_success_rate=expected_success_rate,
            confidence_interval_low=ci_low,
            confidence_interval_high=ci_high,
            stop_loss_pct=self.default_stop_loss,
            target_pct=self.default_target,
            suggested_position_size_pct=suggested_size,
            reasons=all_reasons,
        )
    
    def _estimate_success_rate(self, score: float) -> float:
        """Estimate expected success rate based on score.
        
        This is a placeholder. In production, this should be calibrated
        from actual backtest results — map score ranges to observed success rates.
        
        Conservative estimates based on literature:
        - High score (75+) → ~60-65% success
        - Medium score (60-75) → ~55-60% success
        - Low score (<60) → ~50-55% success (random)
        """
        if score >= 75:
            return 0.62
        elif score >= 60:
            return 0.58
        elif score >= 45:
            return 0.54
        elif score >= 30:
            return 0.50
        else:
            return 0.48
    
    def get_signal_results(self,
                            ins_code: str,
                            on_date: int,
                            data_loader,
                            portfolio: Optional[pd.DataFrame] = None) -> Dict[str, SignalResult]:
        """Get individual signal results (for debugging and reporting)"""
        return {
            'smart_money': self.smart_money_signal.calculate(ins_code, on_date, data_loader, portfolio),
            'technical': self.technical_signal.calculate(ins_code, on_date, data_loader, portfolio),
            'fundamental': self.fundamental_signal.calculate(ins_code, on_date, data_loader, portfolio),
            'diversification': self.diversification_signal.calculate(ins_code, on_date, data_loader, portfolio),
        }
