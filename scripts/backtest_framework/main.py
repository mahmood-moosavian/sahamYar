#!/usr/bin/env python3
"""
Main Entry Point for Backtest Framework

Usage:
    python main.py [options]

Options:
    --generate-sample-data    Generate synthetic sample data first
    --no-walk-forward         Run single split (no walk-forward)
    --config PATH             Use custom config file
    --output-dir PATH         Custom output directory
"""
import sys
import os
import argparse
import logging
from pathlib import Path
import yaml
import json
import pandas as pd

# Setup paths
SCRIPT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(SCRIPT_DIR))

from core import (
    DataLoader, CompositeScoreCalculator, 
    BacktestEngine, BacktestConfig,
)
from reports.report_generator import ReportGenerator


def setup_logging(config: dict):
    """Setup logging based on config"""
    log_cfg = config.get('LOGGING', {})
    level = getattr(logging, log_cfg.get('level', 'INFO'))
    
    output_dir = SCRIPT_DIR / config.get('OUTPUT', {}).get('output_dir', 'output')
    output_dir.mkdir(exist_ok=True, parents=True)
    
    log_file = output_dir / log_cfg.get('file', 'backtest.log').split('/')[-1]
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ]
    )


def generate_sample_data():
    """Generate synthetic sample data for testing"""
    print("\n" + "=" * 60)
    print("STEP 1: Generate Sample Data")
    print("=" * 60)
    
    from data.sample_data_generator import main as gen_main
    gen_main()


def run_backtest(config_path: str = None, walk_forward: bool = True, 
                 output_dir: str = None):
    """Run the complete backtest"""
    
    # Load config
    if config_path is None:
        config_path = SCRIPT_DIR / "config.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if output_dir:
        config.setdefault('OUTPUT', {})['output_dir'] = output_dir
    
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    print("\n" + "=" * 60)
    print("STEP 2: Load Data")
    print("=" * 60)
    
    # Initialize data loader
    data_loader = DataLoader(config_path)
    
    try:
        summary = data_loader.summary()
        print(f"\n✓ Loaded data:")
        for k, v in summary.items():
            if isinstance(v, dict):
                print(f"  {k}:")
                for kk, vv in v.items():
                    print(f"    {kk}: {vv}")
            else:
                print(f"  {k}: {v:,}")
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nRun with --generate-sample-data first to create test data.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("STEP 3: Initialize Composite Score Calculator")
    print("=" * 60)
    
    calculator = CompositeScoreCalculator(config)
    
    print(f"\n✓ Initialized with weights:")
    cs = config.get('COMPOSITE_SCORE', {})
    for layer, lc in cs.items():
        if isinstance(lc, dict) and 'weight' in lc:
            print(f"  {layer}: {lc['weight']} points")
    
    print("\n" + "=" * 60)
    print("STEP 4: Run Backtest")
    print("=" * 60)
    
    # Configure backtest
    bt_cfg = config.get('BACKTEST', {})
    backtest_config = BacktestConfig(
        start_date=bt_cfg.get('start_date', 14010101),
        end_date=bt_cfg.get('end_date', 14040830),
        train_window_days=bt_cfg.get('train_window_days', 504),
        test_window_days=bt_cfg.get('test_window_days', 252),
        step_days=bt_cfg.get('step_days', 126),
        evaluation_horizons=bt_cfg.get('evaluation_horizons', [7, 14, 30, 60, 90]),
        success_threshold_pct=bt_cfg.get('success_threshold_pct', 5.0),
        benchmark=bt_cfg.get('benchmark', 'tedpix'),
        daily_buy_recommendations=bt_cfg.get('daily_buy_recommendations', 5),
        daily_sell_recommendations=bt_cfg.get('daily_sell_recommendations', 3),
        sample_symbols_per_day=bt_cfg.get('sample_symbols_per_day', 50),
    )
    
    engine = BacktestEngine(data_loader, calculator, backtest_config)
    
    # Progress callback
    def progress(day_idx, total_days):
        if day_idx % 50 == 0 or day_idx == total_days - 1:
            pct = day_idx / total_days * 100
            print(f"  Progress: {pct:.1f}% ({day_idx}/{total_days} days)", end='\r')
    
    print(f"\nRunning {'walk-forward' if walk_forward else 'single split'} backtest...")
    results = engine.run_full_backtest(walk_forward=walk_forward, 
                                        progress_callback=progress)
    print()  # newline after progress
    
    print(f"\n✓ Generated {results['total_recommendations']:,} recommendations")
    print(f"✓ Evaluated {results['evaluated_recommendations']:,} outcomes")
    
    print("\n" + "=" * 60)
    print("STEP 5: Generate Report")
    print("=" * 60)
    
    # Generate HTML report
    output_path = SCRIPT_DIR / config.get('OUTPUT', {}).get('output_dir', 'output')
    report_gen = ReportGenerator(output_dir=str(output_path))
    report_path = report_gen.generate(results, config)
    
    print(f"\n✓ Report saved to: {report_path}")
    
    # Save raw results as JSON
    if config.get('OUTPUT', {}).get('save_raw_results', True):
        raw_path = output_path / config.get('OUTPUT', {}).get('raw_results_filename', 'backtest_results.json')
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, default=str, ensure_ascii=False, indent=2)
        print(f"✓ Raw results saved to: {raw_path}")
    
    # Save recommendations as CSV
    if config.get('OUTPUT', {}).get('save_recommendations_csv', True):
        rec_path = output_path / config.get('OUTPUT', {}).get('recommendations_filename', 'all_recommendations.csv')
        recs_df = pd.DataFrame([r for r in results.get('raw_recommendations', [])])
        recs_df.to_csv(rec_path, index=False, encoding='utf-8-sig')
        print(f"✓ Recommendations saved to: {rec_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    summary = results.get('summary', {})
    overall = summary.get('overall', {})
    
    if overall:
        print(f"\nOverall metrics (30-day horizon):")
        print(f"  Total recommendations:     {overall.get('n', 0):,}")
        print(f"  Success rate:              {overall.get('success_rate', 0)}%")
        print(f"  Beats benchmark:           {overall.get('beats_benchmark_rate', 0)}%")
        print(f"  Avg return:                {overall.get('avg_return_pct', 0)}%")
        print(f"  Avg excess return:         {overall.get('avg_excess_return_pct', 0)}%")
        print(f"  Sharpe (annualized):       {overall.get('sharpe_annualized', 0)}")
        print(f"  Max drawdown:              {overall.get('max_drawdown_pct', 0)}%")
        print(f"  Profit factor:             {overall.get('profit_factor', 0)}")
        print(f"  Stop loss hit rate:        {overall.get('stop_loss_hit_rate', 0)}%")
    
    # Bias summary
    bias = results.get('bias_report', {}).get('summary', {})
    if bias:
        print(f"\nBias checks:")
        print(f"  Issues:    {bias.get('issues_count', 0)}")
        print(f"  Warnings:  {bias.get('warnings_count', 0)}")
        print(f"  Passed:    {bias.get('passed_count', 0)}")
    
    print(f"\n{'✓' if overall.get('success_rate', 0) >= 55 else '✗'} Decision: {'PASS' if overall.get('success_rate', 0) >= 55 else 'FAIL'}")
    print(f"\nFull report: {report_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='سهام‌یار Backtest Framework')
    parser.add_argument('--generate-sample-data', action='store_true',
                        help='Generate synthetic sample data first')
    parser.add_argument('--no-walk-forward', action='store_true',
                        help='Run single split (no walk-forward)')
    parser.add_argument('--config', type=str, default=None,
                        help='Path to config file')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Custom output directory')
    
    args = parser.parse_args()
    
    if args.generate_sample_data:
        generate_sample_data()
    
    run_backtest(
        config_path=args.config,
        walk_forward=not args.no_walk_forward,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
