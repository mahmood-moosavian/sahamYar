#!/usr/bin/env python3
"""Focused experiment runner - subset of key experiments only."""
import sys
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.WARNING)

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from core.data_loader import DataLoader
from core.composite_score import CompositeScoreCalculator
from core.backtest_engine import BacktestEngine, BacktestConfig

BASE_CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_base_config():
    with open(BASE_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_experiment(name, config_overrides, data_loader):
    base_config = load_base_config()
    
    def deep_merge(base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    config = deep_merge(base_config, config_overrides)
    calculator = CompositeScoreCalculator(config)
    
    bt_cfg = config.get('BACKTEST', {})
    backtest_config = BacktestConfig(
        start_date=bt_cfg.get('start_date', 14030101),
        end_date=bt_cfg.get('end_date', 14040331),
        train_window_days=bt_cfg.get('train_window_days', 252),
        test_window_days=bt_cfg.get('test_window_days', 126),
        step_days=bt_cfg.get('step_days', 63),
        evaluation_horizons=bt_cfg.get('evaluation_horizons', [7, 14, 30, 60, 90]),
        success_threshold_pct=bt_cfg.get('success_threshold_pct', 5.0),
        benchmark=bt_cfg.get('benchmark', 'tedpix'),
        daily_buy_recommendations=bt_cfg.get('daily_buy_recommendations', 2),
        daily_sell_recommendations=bt_cfg.get('daily_sell_recommendations', 1),
        sample_symbols_per_day=bt_cfg.get('sample_symbols_per_day', 30),
    )
    
    engine = BacktestEngine(data_loader, calculator, backtest_config)
    results = engine.run_full_backtest(walk_forward=True, progress_callback=None)
    
    summary = results.get('summary', {})
    overall = summary.get('overall', {})
    bias_summary = results.get('bias_report', {}).get('summary', {})
    
    success_rate = overall.get('success_rate', 0)
    beats_benchmark = overall.get('beats_benchmark_rate', 0)
    sharpe = overall.get('sharpe_annualized', 0)
    max_dd = overall.get('max_drawdown_pct', -100)
    profit_factor = overall.get('profit_factor', 0) if overall.get('profit_factor', 0) != 'inf' else 99
    
    decision = 'PASS' if (
        success_rate >= 55 and 
        beats_benchmark >= 55 and 
        sharpe >= 0.5 and
        max_dd > -10 and
        profit_factor >= 1.5
    ) else 'FAIL'
    
    return {
        'experiment': name,
        'metrics': {
            'n': overall.get('n', 0),
            'success_rate': success_rate,
            'beats_benchmark_rate': beats_benchmark,
            'avg_return_pct': overall.get('avg_return_pct', 0),
            'avg_excess_return_pct': overall.get('avg_excess_return_pct', 0),
            'sharpe': sharpe,
            'sortino': overall.get('sortino_ratio', 0),
            'max_drawdown_pct': max_dd,
            'profit_factor': profit_factor,
            'stop_loss_hit_rate': overall.get('stop_loss_hit_rate', 0),
        },
        'decision': decision,
        'total_recommendations': results.get('total_recommendations', 0),
    }


def main():
    print("=" * 80)
    print("FOCUSED EXPERIMENTS — After Improvements (3 new signals + better data)")
    print("=" * 80)
    
    data_loader = DataLoader(str(BASE_CONFIG_PATH))
    summary = data_loader.summary()
    print(f"\n✓ Data loaded: {summary['symbols']} symbols, {summary['candles']:,} candles")
    
    # Focused experiments - only the most important ones
    experiments = [
        # Baseline: current improved config
        ("NEW1_baseline_improved", {}),
        
        # Stop Loss variations (key finding)
        ("NEW2_sl_8", {'RISK': {'default_stop_loss_pct': 8.0}}),
        ("NEW3_sl_12_baseline", {'RISK': {'default_stop_loss_pct': 12.0}}),
        ("NEW4_sl_15", {'RISK': {'default_stop_loss_pct': 15.0}}),
        ("NEW5_no_sl", {'RISK': {'default_stop_loss_pct': 100.0}}),
        
        # Recommendation count (key finding)
        ("NEW6_recs_3_2", {'BACKTEST': {'daily_buy_recommendations': 3, 'daily_sell_recommendations': 2}}),
        ("NEW7_recs_2_1_baseline", {'BACKTEST': {'daily_buy_recommendations': 2, 'daily_sell_recommendations': 1}}),
        ("NEW8_recs_1_0", {'BACKTEST': {'daily_buy_recommendations': 1, 'daily_sell_recommendations': 0}}),
        
        # Threshold (key finding)
        ("NEW9_thresh_3", {'BACKTEST': {'success_threshold_pct': 3.0}}),
        ("NEW10_thresh_5_baseline", {'BACKTEST': {'success_threshold_pct': 5.0}}),
        ("NEW11_thresh_7", {'BACKTEST': {'success_threshold_pct': 7.0}}),
    ]
    
    print(f"\nTotal experiments: {len(experiments)}")
    print(f"Estimated time: {len(experiments) * 30} seconds\n")
    
    all_results = []
    for i, (name, overrides) in enumerate(experiments, 1):
        print(f"[{i:02d}/{len(experiments)}] {name}...", end=" ", flush=True)
        try:
            result = run_experiment(name, overrides, data_loader)
            all_results.append(result)
            m = result['metrics']
            print(f"✓ succ={m['success_rate']}% beats={m['beats_benchmark_rate']}% "
                  f"sharpe={m['sharpe']} ret={m['avg_return_pct']}% PF={m['profit_factor']} "
                  f"DD={m['max_drawdown_pct']}% → {result['decision']}")
        except Exception as e:
            print(f"✗ Error: {e}")
            all_results.append({'experiment': name, 'decision': 'ERROR', 'error': str(e)})
    
    # Save
    OUTPUT_DIR = SCRIPT_DIR / "output"
    with open(OUTPUT_DIR / "experiments_v2_results.json", 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    
    # Summary table
    print(f"\n{'=' * 100}")
    print("SUMMARY TABLE (sorted by success_rate)")
    print(f"{'=' * 100}")
    
    valid = [r for r in all_results if 'error' not in r]
    valid.sort(key=lambda x: -x['metrics']['success_rate'])
    
    print(f"\n{'Experiment':<30} {'Decision':<8} {'Succ%':>7} {'Beats%':>7} {'Sharpe':>7} {'Ret%':>7} {'PF':>5} {'DD%':>8}")
    print("-" * 100)
    for r in valid:
        m = r['metrics']
        print(f"{r['experiment']:<30} {r['decision']:<8} "
              f"{m['success_rate']:>6.1f}% {m['beats_benchmark_rate']:>6.1f}% "
              f"{m['sharpe']:>7.3f} {m['avg_return_pct']:>6.1f}% "
              f"{m['profit_factor']:>5.2f} {m['max_drawdown_pct']:>7.1f}%")
    
    pass_count = sum(1 for r in valid if r['decision'] == 'PASS')
    fail_count = sum(1 for r in valid if r['decision'] == 'FAIL')
    print(f"\nDecision: {pass_count} PASS, {fail_count} FAIL out of {len(valid)}")
    
    if valid:
        best = max(valid, key=lambda x: x['metrics']['success_rate'])
        print(f"\nBEST: {best['experiment']}")
        m = best['metrics']
        print(f"  Success: {m['success_rate']}%, Sharpe: {m['sharpe']}, "
              f"PF: {m['profit_factor']}, Return: {m['avg_return_pct']}%")


if __name__ == "__main__":
    main()
