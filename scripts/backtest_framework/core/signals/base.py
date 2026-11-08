"""
Base Signal Class
Defines the interface that all signal generators must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import pandas as pd


@dataclass
class SignalResult:
    """Result of a signal calculation"""
    score: float                    # 0 to max_score
    max_score: float                # maximum possible score for this signal
    normalized: float               # score / max_score (0 to 1)
    confidence: float               # 0 to 1 — how confident we are in this signal
    sub_signals: Dict[str, float] = field(default_factory=dict)  # breakdown
    reasons: List[str] = field(default_factory=list)  # human-readable reasons
    data_quality_warnings: List[str] = field(default_factory=list)  # any data issues
    
    def __post_init__(self):
        if self.max_score > 0:
            self.normalized = self.score / self.max_score
        else:
            self.normalized = 0.0


class Signal(ABC):
    """Abstract base class for all signals"""
    
    name: str = "base"
    max_score: float = 100.0
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    @abstractmethod
    def calculate(self, 
                  ins_code: str,
                  on_date: int,
                  data_loader,
                  portfolio: Optional[pd.DataFrame] = None) -> SignalResult:
        """
        Calculate the signal for a given symbol on a given date.
        
        Args:
            ins_code: Symbol identifier (TSETMC InsCode)
            on_date: Decision date (Jalali integer, e.g., 14040815)
            data_loader: DataLoader instance for accessing historical data
            portfolio: Optional user portfolio (DataFrame with ins_code, quantity, buy_price)
            
        Returns:
            SignalResult with score, confidence, and breakdown
            
        IMPORTANT: This method MUST only use data available on or before on_date.
        Any future data access is a look-ahead bias violation.
        """
        pass
    
    def _validate_data_availability(self, 
                                     ins_code: str,
                                     on_date: int,
                                     data_loader,
                                     required_history_days: int = 30) -> List[str]:
        """Check that we have enough historical data"""
        warnings = []
        candles = data_loader.get_candles_up_to(ins_code, on_date, days=required_history_days)
        
        if len(candles) < required_history_days * 0.5:
            warnings.append(
                f"Insufficient history: {len(candles)}/{required_history_days} days for {ins_code}"
            )
        
        return warnings
