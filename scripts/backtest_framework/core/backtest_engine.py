"""
Backtest Engine
Replays history day-by-day, generates recommendations, tracks outcomes.

Key features:
1. Walk-forward validation: train/test with rolling windows
2. Look-ahead bias prevention: only uses data available on decision date
3. Multiple evaluation horizons (7, 14, 30, 60, 90 days)
4. Benchmark comparison (TEDPIX or equal-weight)
5. Detailed recommendations tracking for reporting
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

from .data_loader import DataLoader
from .composite_score import CompositeScoreCalculator, Recommendation
from .metrics import PerformanceMetrics, BiasChecker

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    start_date: int = 14010101
    end_date: int = 14040830
    train_window_days: int = 504
    test_window_days: int = 252
    step_days: int = 126
    evaluation_horizons: List[int] = None
    success_threshold_pct: float = 5.0
    benchmark: str = "tedpix"
    daily_buy_recommendations: int = 5
    daily_sell_recommendations: int = 3
    sample_symbols_per_day: int = 50  # for performance: sample subset of all symbols
    
    def __post_init__(self):
        if self.evaluation_horizons is None:
            self.evaluation_horizons = [7, 14, 30, 60, 90]


class BacktestEngine:
    """Main backtest orchestrator"""
    
    def __init__(self, 
                 data_loader: DataLoader,
                 composite_calculator: CompositeScoreCalculator,
                 config: BacktestConfig = None):
        self.data_loader = data_loader
        self.calculator = composite_calculator
        self.config = config or BacktestConfig()
        
        # Results storage
        self.all_recommendations: List[Recommendation] = []
        self.evaluated_results: List[Dict] = []
        self.walk_forward_splits: List[Dict] = []
        
        # Bias checker
        self.bias_checker = BiasChecker()
    
    def run_full_backtest(self, 
                          walk_forward: bool = True,
                          progress_callback=None) -> Dict:
        """
        Run complete backtest.
        
        Args:
            walk_forward: If True, split data into train/test windows
            progress_callback: Optional callback(day_index, total_days) for progress
            
        Returns:
            Dict with summary metrics and raw results
        """
        logger.info("Starting full backtest...")
        
        # Get all trading dates in range
        candles = self.data_loader.load_candles()
        trading_dates = sorted(candles[
            (candles['date_jalali'] >= self.config.start_date) &
            (candles['date_jalali'] <= self.config.end_date)
        ]['date_jalali'].unique())
        
        logger.info(f"Backtest period: {trading_dates[0]} to {trading_dates[-1]}")
        logger.info(f"Total trading days: {len(trading_dates)}")
        
        if walk_forward:
            # Split into windows
            self.walk_forward_splits = self._generate_walk_forward_splits(trading_dates)
            logger.info(f"Walk-forward splits: {len(self.walk_forward_splits)}")
        else:
            # Single split: all data is test
            self.walk_forward_splits = [{
                'train_start': trading_dates[0],
                'train_end': trading_dates[0],  # no training needed
                'test_start': trading_dates[0],
                'test_end': trading_dates[-1],
                'test_dates': trading_dates,
            }]
        
        # Run each window
        for split_idx, split in enumerate(self.walk_forward_splits):
            logger.info(f"\n--- Split {split_idx + 1}/{len(self.walk_forward_splits)} ---")
            logger.info(f"Train: {split['train_start']} - {split['train_end']}")
            logger.info(f"Test:  {split['test_start']} - {split['test_end']}")
            
            self._run_split(split, progress_callback, split_idx)
        
        # Evaluate all recommendations
        logger.info("\nEvaluating recommendations...")
        self._evaluate_recommendations()
        
        # Compute metrics
        metrics = PerformanceMetrics(self.evaluated_results, self.data_loader)
        summary = metrics.compute_summary()
        
        # Run bias checks
        bias_report = self.bias_checker.check(self.all_recommendations, self.data_loader)
        
        return {
            'summary': summary,
            'walk_forward_splits': self.walk_forward_splits,
            'total_recommendations': len(self.all_recommendations),
            'evaluated_recommendations': len(self.evaluated_results),
            'bias_report': bias_report,
            'raw_recommendations': [asdict(r) for r in self.all_recommendations],
            'evaluated_results': self.evaluated_results,
        }
    
    def _generate_walk_forward_splits(self, trading_dates: List[int]) -> List[Dict]:
        """Generate walk-forward train/test splits"""
        splits = []
        n = len(trading_dates)
        train_size = self.config.train_window_days
        test_size = self.config.test_window_days
        step = self.config.step_days
        
        i = 0
        while i + train_size + test_size <= n:
            train_start = trading_dates[i]
            train_end = trading_dates[i + train_size - 1]
            test_start = trading_dates[i + train_size]
            test_end = trading_dates[min(i + train_size + test_size - 1, n - 1)]
            test_dates = trading_dates[i + train_size : i + train_size + test_size]
            
            splits.append({
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'test_dates': test_dates,
            })
            
            i += step
        
        return splits
    
    def _run_split(self, split: Dict, progress_callback, split_idx: int):
        """Run backtest on a single train/test split"""
        test_dates = split['test_dates']
        total_days = len(test_dates)
        
        # Sample symbols to evaluate (for performance)
        active_symbols = self.data_loader.get_active_symbols()
        if len(active_symbols) > self.config.sample_symbols_per_day:
            # Use the same sample across all days for consistency
            sampled = active_symbols.sample(
                self.config.sample_symbols_per_day, 
                random_state=42 + split_idx
            )
        else:
            sampled = active_symbols
        
        logger.info(f"Evaluating {len(sampled)} symbols per day for {total_days} days")
        
        for day_idx, decision_date in enumerate(test_dates):
            if progress_callback:
                progress_callback(day_idx, total_days)
            
            # Skip if not enough history (need at least 200 days for EMA200)
            candles = self.data_loader.load_candles()
            min_date = candles['date_jalali'].min()
            if decision_date - min_date < 200:
                continue
            
            daily_recommendations = []
            
            for _, sym in sampled.iterrows():
                ins_code = sym['ins_code']
                
                try:
                    recommendation = self.calculator.calculate(
                        ins_code=ins_code,
                        on_date=decision_date,
                        data_loader=self.data_loader,
                        portfolio=None  # No portfolio in backtest (use equal weight)
                    )
                    daily_recommendations.append(recommendation)
                except Exception as e:
                    logger.debug(f"Error calculating {ins_code} on {decision_date}: {e}")
                    continue
            
            # Sort by score, take top N buy recommendations
            daily_recommendations.sort(key=lambda r: -r.total_score)
            top_buy = daily_recommendations[:self.config.daily_buy_recommendations]
            
            # Take bottom N for sell recommendations
            bottom_sell = daily_recommendations[-self.config.daily_sell_recommendations:]
            
            self.all_recommendations.extend(top_buy)
            self.all_recommendations.extend(bottom_sell)
        
        logger.info(f"Generated {len(self.all_recommendations)} total recommendations so far")
    
    def _evaluate_recommendations(self):
        """Evaluate each recommendation against actual future performance"""
        candles = self.data_loader.load_candles()
        
        for rec in self.all_recommendations:
            # Get future candles for evaluation
            future = candles[
                (candles['ins_code'] == rec.ins_code) &
                (candles['date_jalali'] >= rec.on_date)
            ].sort_values('date_jalali')
            
            if future.empty:
                continue
            
            entry_price = future.iloc[0]['close']  # price on decision date
            
            for horizon in self.config.evaluation_horizons:
                if len(future) <= horizon:
                    continue  # not enough future data
                
                exit_price = future.iloc[horizon]['close']
                return_pct = (exit_price - entry_price) / entry_price * 100
                
                # Check if hit stop loss first
                future_window = future.iloc[1:horizon + 1]
                if not future_window.empty:
                    min_low = future_window['low'].min()
                    stop_loss_hit = min_low <= entry_price * (1 - rec.stop_loss_pct)
                else:
                    stop_loss_hit = False
                
                # Benchmark return
                benchmark_return = self._get_benchmark_return(rec.on_date, horizon)
                
                # Success: return >= threshold OR beat benchmark by threshold
                is_success = (return_pct >= self.config.success_threshold_pct and 
                              not stop_loss_hit)
                beats_benchmark = (return_pct - benchmark_return) >= self.config.success_threshold_pct
                
                self.evaluated_results.append({
                    'ins_code': rec.ins_code,
                    'on_date': rec.on_date,
                    'score': rec.total_score,
                    'action': rec.action,
                    'horizon_days': horizon,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'return_pct': return_pct,
                    'benchmark_return_pct': benchmark_return,
                    'excess_return_pct': return_pct - benchmark_return,
                    'stop_loss_hit': stop_loss_hit,
                    'is_success': is_success,
                    'beats_benchmark': beats_benchmark,
                    'confidence_interval_low': rec.confidence_interval_low,
                    'confidence_interval_high': rec.confidence_interval_high,
                    'breakdown': rec.breakdown,
                })
    
    def _get_benchmark_return(self, on_date: int, horizon: int) -> float:
        """Get benchmark return for comparison"""
        try:
            market_index = self.data_loader.load_market_index()
            future_idx = market_index[market_index['date_jalali'] >= on_date].sort_values('date_jalali')
            
            if len(future_idx) <= horizon:
                return 0.0
            
            start_val = future_idx.iloc[0]['index_value']
            end_val = future_idx.iloc[horizon]['index_value']
            
            return (end_val - start_val) / start_val * 100
        except Exception:
            return 0.0
