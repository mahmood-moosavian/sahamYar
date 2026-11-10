#!/usr/bin/env python3
"""
Experiment Runner — runs multiple backtest configurations
and aggregates results for comparison.

Does NOT modify the framework. Only loads config, runs backtest, collects metrics.
"""
import sys
import os
import json
import copy
import yaml
import logging
import shutil
from pathlib import Path
from datetime import datetime
import pandas as pd

# Suppress verbose logging
logging.basicConfig(level=logging.WARNING)

# Setup paths
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from core.data_loader import DataLoader
from core.composite_score import CompositeScoreCalculator
from core.backtest_engine import BacktestEngine, BacktestConfig

BASE_CONFIG_PATH = SCRIPT_DIR / "config.yaml"
RESULTS_FILE = SCRIPT_DIR / "output" / "experiments_results.json"
SUMMARY_CSV = SCRIPT_DIR / "output" / "experiments_summary.csv"


def load_base_config():
    with open(BASE_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_single_experiment(experiment_name: str, 
                          config_overrides: dict,
                          data_loader: DataLoader) -> dict:
    """Run a single backtest experiment with given config overrides"""
    base_config = load_base_config()
    
    # Deep merge config overrides
    def deep_merge(base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    config = deep_merge(base_config, config_overrides)
    
    # Initialize calculator with overridden config
    calculator = CompositeScoreCalculator(config)
    
    # Initialize backtest config
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
        daily_buy_recommendations=bt_cfg.get('daily_buy_recommendations', 3),
        daily_sell_recommendations=bt_cfg.get('daily_sell_recommendations', 2),
        sample_symbols_per_day=bt_cfg.get('sample_symbols_per_day', 30),
    )
    
    engine = BacktestEngine(data_loader, calculator, backtest_config)
    
    # Run backtest (suppress progress callback)
    results = engine.run_full_backtest(walk_forward=True, progress_callback=None)
    
    # Extract key metrics
    summary = results.get('summary', {})
    overall = summary.get('overall', {})
    by_horizon = summary.get('by_horizon', {})
    by_score = summary.get('by_score_range', {})
    bias_summary = results.get('bias_report', {}).get('summary', {})
    
    # Determine decision
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
        'experiment': experiment_name,
        'config_overrides': config_overrides,
        'timestamp': datetime.now().isoformat(),
        'metrics': {
            'n': overall.get('n', 0),
            'success_rate': success_rate,
            'beats_benchmark_rate': beats_benchmark,
            'avg_return_pct': overall.get('avg_return_pct', 0),
            'avg_excess_return_pct': overall.get('avg_excess_return_pct', 0),
            'sharpe': sharpe,
            'sortino': overall.get('sortino_ratio', 0),
            'max_drawdown_pct': max_dd,
            'avg_win_pct': overall.get('avg_win_pct', 0),
            'avg_loss_pct': overall.get('avg_loss_pct', 0),
            'profit_factor': profit_factor,
            'stop_loss_hit_rate': overall.get('stop_loss_hit_rate', 0),
            'ci_95_low': overall.get('ci_95_low', None),
            'ci_95_high': overall.get('ci_95_high', None),
        },
        'by_horizon': {
            str(h): {
                'n': m.get('n', 0),
                'success_rate': m.get('success_rate', 0),
                'beats_benchmark': m.get('beats_benchmark_rate', 0),
                'avg_return': m.get('avg_return_pct', 0),
                'sharpe': m.get('sharpe_annualized', 0),
            } for h, m in by_horizon.items()
        },
        'bias': {
            'issues': bias_summary.get('issues_count', 0),
            'warnings': bias_summary.get('warnings_count', 0),
            'passed': bias_summary.get('passed_count', 0),
        },
        'decision': decision,
        'total_recommendations': results.get('total_recommendations', 0),
    }


def main():
    print("=" * 80)
    print("EXPERIMENT RUNNER — Multiple Backtest Configurations")
    print("=" * 80)
    
    # Initialize data loader once (shared across experiments)
    data_loader = DataLoader(str(BASE_CONFIG_PATH))
    
    # Verify data is loaded
    try:
        summary = data_loader.summary()
        print(f"\n✓ Data loaded: {summary['symbols']} symbols, {summary['candles']:,} candles")
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        print("Run: python main.py --generate-sample-data")
        sys.exit(1)
    
    # ============================================================
    # EXPERIMENT SET A: Weight Combinations
    # ============================================================
    experiments_A = [
        ("A1_baseline_35_30_20_15", {}),
        ("A2_smart_heavy_50_20_20_10", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 50, 'sub_signals': {'net_legal_value_5d': 22, 'accumulation_pattern': 18, 'smart_money_consistency': 10}},
                'technical': {'weight': 20, 'sub_signals': {'rsi_14': 6, 'mfi_14': 5, 'macd_crossover': 5, 'trend_alignment': 4}},
                'fundamental': {'weight': 20, 'sub_signals': {'pe_below_sector': 12, 'eps_growth': 8}},
                'diversification': {'weight': 10, 'sub_signals': {'low_correlation': 7, 'new_sector': 3}},
            }
        }),
        ("A3_tech_heavy_20_50_15_15", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 20, 'sub_signals': {'net_legal_value_5d': 9, 'accumulation_pattern': 7, 'smart_money_consistency': 4}},
                'technical': {'weight': 50, 'sub_signals': {'rsi_14': 13, 'mfi_14': 12, 'macd_crossover': 13, 'trend_alignment': 12}},
                'fundamental': {'weight': 15, 'sub_signals': {'pe_below_sector': 9, 'eps_growth': 6}},
                'diversification': {'weight': 15, 'sub_signals': {'low_correlation': 10, 'new_sector': 5}},
            }
        }),
        ("A4_fund_heavy_25_20_35_20", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 25, 'sub_signals': {'net_legal_value_5d': 11, 'accumulation_pattern': 9, 'smart_money_consistency': 5}},
                'technical': {'weight': 20, 'sub_signals': {'rsi_14': 5, 'mfi_14': 5, 'macd_crossover': 5, 'trend_alignment': 5}},
                'fundamental': {'weight': 35, 'sub_signals': {'pe_below_sector': 20, 'eps_growth': 15}},
                'diversification': {'weight': 20, 'sub_signals': {'low_correlation': 13, 'new_sector': 7}},
            }
        }),
        ("A5_equal_25_25_25_25", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 25, 'sub_signals': {'net_legal_value_5d': 11, 'accumulation_pattern': 9, 'smart_money_consistency': 5}},
                'technical': {'weight': 25, 'sub_signals': {'rsi_14': 6, 'mfi_14': 6, 'macd_crossover': 7, 'trend_alignment': 6}},
                'fundamental': {'weight': 25, 'sub_signals': {'pe_below_sector': 15, 'eps_growth': 10}},
                'diversification': {'weight': 25, 'sub_signals': {'low_correlation': 17, 'new_sector': 8}},
            }
        }),
        ("A6_div_heavy_20_20_20_40", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 20, 'sub_signals': {'net_legal_value_5d': 9, 'accumulation_pattern': 7, 'smart_money_consistency': 4}},
                'technical': {'weight': 20, 'sub_signals': {'rsi_14': 5, 'mfi_14': 5, 'macd_crossover': 5, 'trend_alignment': 5}},
                'fundamental': {'weight': 20, 'sub_signals': {'pe_below_sector': 12, 'eps_growth': 8}},
                'diversification': {'weight': 40, 'sub_signals': {'low_correlation': 27, 'new_sector': 13}},
            }
        }),
    ]
    
    # ============================================================
    # EXPERIMENT SET B: Stop Loss Variations
    # ============================================================
    experiments_B = [
        ("B1_no_stop_loss", {
            'RISK': {'default_stop_loss_pct': 100.0, 'default_target_pct': 17.0}
        }),
        ("B2_stop_loss_5", {
            'RISK': {'default_stop_loss_pct': 5.0, 'default_target_pct': 17.0}
        }),
        ("B3_stop_loss_8_baseline", {
            'RISK': {'default_stop_loss_pct': 8.0, 'default_target_pct': 17.0}
        }),
        ("B4_stop_loss_12", {
            'RISK': {'default_stop_loss_pct': 12.0, 'default_target_pct': 17.0}
        }),
        ("B5_stop_loss_15", {
            'RISK': {'default_stop_loss_pct': 15.0, 'default_target_pct': 17.0}
        }),
    ]
    
    # ============================================================
    # EXPERIMENT SET C: Success Threshold Tuning
    # ============================================================
    experiments_C = [
        ("C1_threshold_3", {
            'BACKTEST': {'success_threshold_pct': 3.0}
        }),
        ("C2_threshold_5_baseline", {
            'BACKTEST': {'success_threshold_pct': 5.0}
        }),
        ("C3_threshold_7", {
            'BACKTEST': {'success_threshold_pct': 7.0}
        }),
        ("C4_threshold_10", {
            'BACKTEST': {'success_threshold_pct': 10.0}
        }),
    ]
    
    # ============================================================
    # EXPERIMENT SET D: Signal Ablation (disable each layer)
    # ============================================================
    experiments_D = [
        ("D1_disable_smart_money", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 0, 'sub_signals': {'net_legal_value_5d': 0, 'accumulation_pattern': 0, 'smart_money_consistency': 0}},
                'technical': {'weight': 50, 'sub_signals': {'rsi_14': 13, 'mfi_14': 12, 'macd_crossover': 13, 'trend_alignment': 12}},
                'fundamental': {'weight': 30, 'sub_signals': {'pe_below_sector': 18, 'eps_growth': 12}},
                'diversification': {'weight': 20, 'sub_signals': {'low_correlation': 13, 'new_sector': 7}},
            }
        }),
        ("D2_disable_technical", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 50, 'sub_signals': {'net_legal_value_5d': 22, 'accumulation_pattern': 18, 'smart_money_consistency': 10}},
                'technical': {'weight': 0, 'sub_signals': {'rsi_14': 0, 'mfi_14': 0, 'macd_crossover': 0, 'trend_alignment': 0}},
                'fundamental': {'weight': 30, 'sub_signals': {'pe_below_sector': 18, 'eps_growth': 12}},
                'diversification': {'weight': 20, 'sub_signals': {'low_correlation': 13, 'new_sector': 7}},
            }
        }),
        ("D3_disable_fundamental", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 50, 'sub_signals': {'net_legal_value_5d': 22, 'accumulation_pattern': 18, 'smart_money_consistency': 10}},
                'technical': {'weight': 30, 'sub_signals': {'rsi_14': 8, 'mfi_14': 7, 'macd_crossover': 8, 'trend_alignment': 7}},
                'fundamental': {'weight': 0, 'sub_signals': {'pe_below_sector': 0, 'eps_growth': 0}},
                'diversification': {'weight': 20, 'sub_signals': {'low_correlation': 13, 'new_sector': 7}},
            }
        }),
        ("D4_disable_diversification", {
            'COMPOSITE_SCORE': {
                'smart_money': {'weight': 45, 'sub_signals': {'net_legal_value_5d': 20, 'accumulation_pattern': 17, 'smart_money_consistency': 8}},
                'technical': {'weight': 35, 'sub_signals': {'rsi_14': 9, 'mfi_14': 8, 'macd_crossover': 10, 'trend_alignment': 8}},
                'fundamental': {'weight': 20, 'sub_signals': {'pe_below_sector': 12, 'eps_growth': 8}},
                'diversification': {'weight': 0, 'sub_signals': {'low_correlation': 0, 'new_sector': 0}},
            }
        }),
    ]
    
    # ============================================================
    # EXPERIMENT SET E: Sample Size / Recommendation Count
    # ============================================================
    experiments_E = [
        ("E1_few_recs_2_1", {
            'BACKTEST': {'daily_buy_recommendations': 2, 'daily_sell_recommendations': 1}
        }),
        ("E2_baseline_3_2", {
            'BACKTEST': {'daily_buy_recommendations': 3, 'daily_sell_recommendations': 2}
        }),
        ("E3_more_recs_5_3", {
            'BACKTEST': {'daily_buy_recommendations': 5, 'daily_sell_recommendations': 3}
        }),
    ]
    
    all_experiments = (
        [("A", exp) for exp in experiments_A] +
        [("B", exp) for exp in experiments_B] +
        [("C", exp) for exp in experiments_C] +
        [("D", exp) for exp in experiments_D] +
        [("E", exp) for exp in experiments_E]
    )
    
    print(f"\nTotal experiments to run: {len(all_experiments)}")
    print(f"Estimated time: {len(all_experiments) * 25} seconds\n")
    
    # Run all experiments
    all_results = []
    for i, (set_id, (name, overrides)) in enumerate(all_experiments, 1):
        print(f"[{i:02d}/{len(all_experiments)}] Running {name}...", end=" ", flush=True)
        try:
            result = run_single_experiment(name, overrides, data_loader)
            all_results.append(result)
            
            m = result['metrics']
            print(f"✓ success={m['success_rate']}% beats={m['beats_benchmark_rate']}% "
                  f"sharpe={m['sharpe']} decision={result['decision']}")
        except Exception as e:
            print(f"✗ Error: {e}")
            all_results.append({
                'experiment': name,
                'error': str(e),
                'decision': 'ERROR',
            })
    
    # Save results
    RESULTS_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    
    # Create summary CSV
    rows = []
    for r in all_results:
        if 'error' in r:
            rows.append({'experiment': r['experiment'], 'decision': 'ERROR'})
            continue
        m = r['metrics']
        rows.append({
            'experiment': r['experiment'],
            'decision': r['decision'],
            'n': m['n'],
            'success_rate': m['success_rate'],
            'beats_benchmark': m['beats_benchmark_rate'],
            'avg_return': m['avg_return_pct'],
            'excess_return': m['avg_excess_return_pct'],
            'sharpe': m['sharpe'],
            'sortino': m['sortino'],
            'max_drawdown': m['max_drawdown_pct'],
            'profit_factor': m['profit_factor'],
            'stop_loss_hit_rate': m['stop_loss_hit_rate'],
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(SUMMARY_CSV, index=False, encoding='utf-8-sig')
    
    print(f"\n{'=' * 80}")
    print(f"RESULTS SAVED")
    print(f"{'=' * 80}")
    print(f"  JSON: {RESULTS_FILE}")
    print(f"  CSV:  {SUMMARY_CSV}")
    
    # Print summary table sorted by success rate
    print(f"\n{'=' * 80}")
    print("SUMMARY TABLE (sorted by success_rate)")
    print(f"{'=' * 80}")
    
    df_valid = df[df['decision'] != 'ERROR'].copy()
    df_valid = df_valid.sort_values('success_rate', ascending=False)
    
    print(f"\n{'Experiment':<32} {'Decision':<8} {'Success':>8} {'Beats':>8} {'Sharpe':>8} {'DD':>8} {'PF':>6}")
    print("-" * 88)
    for _, row in df_valid.iterrows():
        print(f"{row['experiment']:<32} {row['decision']:<8} "
              f"{row['success_rate']:>7.1f}% {row['beats_benchmark']:>7.1f}% "
              f"{row['sharpe']:>8.3f} {row['max_drawdown']:>7.1f}% {row['profit_factor']:>6.2f}")
    
    # Find best
    if not df_valid.empty:
        best = df_valid.iloc[0]
        print(f"\n{'=' * 80}")
        print(f"BEST EXPERIMENT: {best['experiment']}")
        print(f"{'=' * 80}")
        print(f"  Decision:       {best['decision']}")
        print(f"  Success rate:   {best['success_rate']}%")
        print(f"  Beats bench:    {best['beats_benchmark']}%")
        print(f"  Sharpe:         {best['sharpe']}")
        print(f"  Max drawdown:   {best['max_drawdown']}%")
        print(f"  Profit factor:  {best['profit_factor']}")
    
    # Count PASS vs FAIL
    pass_count = (df_valid['decision'] == 'PASS').sum()
    fail_count = (df_valid['decision'] == 'FAIL').sum()
    print(f"\nDecision summary: {pass_count} PASS, {fail_count} FAIL out of {len(df_valid)} experiments")


if __name__ == "__main__":
    main()
