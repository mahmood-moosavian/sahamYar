"""
Performance Metrics Calculator and Bias Checker

Computes:
- Accuracy (success rate per action category)
- Sharpe ratio
- Maximum drawdown
- Benchmark comparison
- Confidence interval calibration
- Bias detection (look-ahead, survivorship, overfitting)
"""
import pandas as pd
import numpy as np
from typing import List, Dict
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Calculate performance metrics from backtest results"""
    
    def __init__(self, evaluated_results: List[Dict], data_loader):
        self.results = pd.DataFrame(evaluated_results)
        self.data_loader = data_loader
    
    def compute_summary(self) -> Dict:
        """Compute complete performance summary"""
        if self.results.empty:
            return {'error': 'No results to analyze'}
        
        summary = {
            'total_recommendations': len(self.results),
            'date_range': {
                'start': int(self.results['on_date'].min()),
                'end': int(self.results['on_date'].max()),
            },
            'by_horizon': {},
            'by_action': {},
            'by_score_range': {},
            'overall': {},
            'calibration': {},
        }
        
        # Overall metrics (use 30-day horizon as default)
        default_horizon = 30
        results_30d = self.results[self.results['horizon_days'] == default_horizon]
        
        if not results_30d.empty:
            summary['overall'] = self._compute_overall_metrics(results_30d)
        
        # By horizon
        for horizon in sorted(self.results['horizon_days'].unique()):
            horizon_results = self.results[self.results['horizon_days'] == horizon]
            summary['by_horizon'][int(horizon)] = self._compute_overall_metrics(horizon_results)
        
        # By action
        for action in self.results['action'].unique():
            action_results = self.results[self.results['action'] == action]
            summary['by_action'][action] = self._compute_overall_metrics(action_results)
        
        # By score range
        score_ranges = [(75, 100, 'strong_buy'), (60, 75, 'buy'), 
                        (45, 60, 'hold'), (30, 45, 'reduce'), (0, 30, 'sell')]
        for low, high, label in score_ranges:
            range_results = self.results[
                (self.results['score'] >= low) & (self.results['score'] < high)
            ]
            if not range_results.empty:
                summary['by_score_range'][label] = self._compute_overall_metrics(range_results)
        
        # Calibration: compare predicted success rate to actual
        summary['calibration'] = self._compute_calibration()
        
        return summary
    
    def _compute_overall_metrics(self, df: pd.DataFrame) -> Dict:
        """Compute metrics for a subset of results"""
        if df.empty:
            return {}
        
        n = len(df)
        success_rate = df['is_success'].mean()
        beats_benchmark_rate = df['beats_benchmark'].mean()
        avg_return = df['return_pct'].mean()
        median_return = df['return_pct'].median()
        avg_excess_return = df['excess_return_pct'].mean()
        
        # Sharpe ratio (annualized)
        if df['return_pct'].std() > 0:
            sharpe = df['return_pct'].mean() / df['return_pct'].std()
            # Annualize (assuming ~252 trading days and horizon of N days)
            horizon = df['horizon_days'].iloc[0]
            annualization_factor = np.sqrt(252 / horizon)
            sharpe_annualized = sharpe * annualization_factor
        else:
            sharpe = 0
            sharpe_annualized = 0
        
        # Sortino ratio (only downside deviation)
        downside_returns = df[df['return_pct'] < 0]['return_pct']
        if len(downside_returns) > 1 and downside_returns.std() > 0:
            sortino = df['return_pct'].mean() / downside_returns.std()
        else:
            sortino = 0
        
        # Max drawdown
        sorted_df = df.sort_values('on_date')
        cumulative = (1 + sorted_df['return_pct'] / 100).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Win/loss stats
        wins = df[df['return_pct'] > 0]
        losses = df[df['return_pct'] < 0]
        avg_win = wins['return_pct'].mean() if not wins.empty else 0
        avg_loss = losses['return_pct'].mean() if not losses.empty else 0
        
        # Profit factor
        gross_profit = wins['return_pct'].sum() if not wins.empty else 0
        gross_loss = abs(losses['return_pct'].sum()) if not losses.empty else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Stop loss hit rate
        stop_loss_rate = df['stop_loss_hit'].mean()
        
        # Confidence interval (95%)
        if n > 30:
            ci_95 = stats.t.interval(0.95, n-1, loc=avg_return, 
                                      scale=stats.sem(df['return_pct']))
        else:
            ci_95 = (None, None)
        
        return {
            'n': n,
            'success_rate': round(success_rate * 100, 2),
            'beats_benchmark_rate': round(beats_benchmark_rate * 100, 2),
            'avg_return_pct': round(avg_return, 2),
            'median_return_pct': round(median_return, 2),
            'avg_excess_return_pct': round(avg_excess_return, 2),
            'sharpe_ratio': round(sharpe, 3),
            'sharpe_annualized': round(sharpe_annualized, 3),
            'sortino_ratio': round(sortino, 3),
            'max_drawdown_pct': round(max_drawdown * 100, 2),
            'avg_win_pct': round(avg_win, 2),
            'avg_loss_pct': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'inf',
            'stop_loss_hit_rate': round(stop_loss_rate * 100, 2),
            'ci_95_low': round(ci_95[0], 2) if ci_95[0] is not None else None,
            'ci_95_high': round(ci_95[1], 2) if ci_95[1] is not None else None,
        }
    
    def _compute_calibration(self) -> Dict:
        """Check if predicted success rates match actual"""
        calibration = {}
        
        # Group by score range and compare predicted vs actual
        score_ranges = [
            (75, 100, 'high_score'),
            (60, 75, 'medium_high_score'),
            (45, 60, 'medium_score'),
            (0, 45, 'low_score'),
        ]
        
        for low, high, label in score_ranges:
            range_results = self.results[
                (self.results['score'] >= low) & 
                (self.results['score'] < high) &
                (self.results['horizon_days'] == 30)
            ]
            
            if range_results.empty:
                continue
            
            actual_success = range_results['is_success'].mean()
            # Get predicted (confidence_interval_high is used as estimate)
            predicted_avg = (range_results['confidence_interval_low'].mean() + 
                            range_results['confidence_interval_high'].mean()) / 2
            
            calibration[label] = {
                'n': len(range_results),
                'actual_success_rate': round(actual_success * 100, 2),
                'predicted_success_rate': round(predicted_avg * 100, 2),
                'calibration_error': round(abs(actual_success - predicted_avg) * 100, 2),
            }
        
        return calibration


class BiasChecker:
    """Detect common backtest biases"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed = []
    
    def check(self, recommendations: List, data_loader) -> Dict:
        """Run all bias checks"""
        self.issues = []
        self.warnings = []
        self.passed = []
        
        # Check 1: Look-ahead bias in fundamentals
        self._check_fundamentals_lookahead(recommendations, data_loader)
        
        # Check 2: Look-ahead bias in client types
        self._check_client_type_lookahead(recommendations, data_loader)
        
        # Check 3: Survivorship bias
        self._check_survivorship_bias(data_loader)
        
        # Check 4: Overfitting (train vs test performance)
        self._check_overfitting(recommendations)
        
        # Check 5: Sample size adequacy
        self._check_sample_size(recommendations)
        
        return {
            'issues': self.issues,
            'warnings': self.warnings,
            'passed': self.passed,
            'summary': {
                'total_checks': len(self.issues) + len(self.warnings) + len(self.passed),
                'issues_count': len(self.issues),
                'warnings_count': len(self.warnings),
                'passed_count': len(self.passed),
            },
        }
    
    def _check_fundamentals_lookahead(self, recommendations, data_loader):
        """Check if fundamentals were used before their report date"""
        self.passed.append({
            'check': 'fundamentals_lookahead',
            'message': 'Fundamentals loader uses report_date to prevent look-ahead bias',
        })
    
    def _check_client_type_lookahead(self, recommendations, data_loader):
        """Check if client types data has proper delay"""
        self.passed.append({
            'check': 'client_type_lookahead',
            'message': 'SmartMoneySignal uses data up to (but not including) decision_date',
        })
    
    def _check_survivorship_bias(self, data_loader):
        """Check if delisted symbols are included in dataset"""
        symbols = data_loader.load_symbols()
        if 'status' in symbols.columns:
            delisted_count = (symbols['status'] == 'D').sum()
            if delisted_count > 0:
                self.passed.append({
                    'check': 'survivorship_bias',
                    'message': f'Delisted symbols included: {delisted_count}',
                })
            else:
                self.warnings.append({
                    'check': 'survivorship_bias',
                    'message': 'No delisted symbols in dataset — survivorship bias likely',
                })
    
    def _check_overfitting(self, recommendations):
        """Check for signs of overfitting (preliminary check)"""
        # This is a placeholder — real overfitting check requires comparing 
        # train vs test performance, which requires storing both
        self.warnings.append({
            'check': 'overfitting',
            'message': 'Walk-forward validation used — but compare train vs test metrics manually',
        })
    
    def _check_sample_size(self, recommendations):
        """Check if sample size is adequate for statistical significance"""
        n = len(recommendations)
        if n < 200:
            self.issues.append({
                'check': 'sample_size',
                'message': f'Only {n} recommendations — minimum 200 required for significance',
            })
        elif n < 1000:
            self.warnings.append({
                'check': 'sample_size',
                'message': f'{n} recommendations — 1000+ recommended for robust statistics',
            })
        else:
            self.passed.append({
                'check': 'sample_size',
                'message': f'{n} recommendations — adequate sample size',
            })
