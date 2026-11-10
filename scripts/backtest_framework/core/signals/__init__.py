"""Signals package - all signal generators for the backtest framework."""
from .base import Signal, SignalResult
from .smart_money import SmartMoneySignal
from .technical import TechnicalSignal
from .fundamental import FundamentalSignal
from .diversification import DiversificationSignal

__all__ = [
    'Signal', 'SignalResult',
    'SmartMoneySignal', 'TechnicalSignal',
    'FundamentalSignal', 'DiversificationSignal',
]
