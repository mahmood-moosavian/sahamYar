"""
Core package initialization
"""
from .data_loader import DataLoader
from .composite_score import CompositeScoreCalculator, Recommendation
from .backtest_engine import BacktestEngine, BacktestConfig
from .metrics import PerformanceMetrics, BiasChecker
from .signals import (
    Signal, SignalResult,
    SmartMoneySignal, TechnicalSignal,
    FundamentalSignal, DiversificationSignal,
)

__all__ = [
    'DataLoader',
    'CompositeScoreCalculator', 'Recommendation',
    'BacktestEngine', 'BacktestConfig',
    'PerformanceMetrics', 'BiasChecker',
    'Signal', 'SignalResult',
    'SmartMoneySignal', 'TechnicalSignal',
    'FundamentalSignal', 'DiversificationSignal',
]
