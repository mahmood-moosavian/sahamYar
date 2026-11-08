"""
Report Generator
Creates a comprehensive HTML report from backtest results.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False


class ReportGenerator:
    """Generate HTML report from backtest results"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.charts_dir = self.output_dir / "charts"
        self.charts_dir.mkdir(exist_ok=True, parents=True)
    
    def generate(self, results: Dict, config: Dict = None) -> Path:
        """Generate complete HTML report"""
        
        # Generate charts
        charts = self._generate_charts(results)
        
        # Build HTML
        html = self._build_html(results, charts, config)
        
        # Save
        report_path = self.output_dir / "backtest_report.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return report_path
    
    def _generate_charts(self, results: Dict) -> Dict:
        """Generate all charts and return paths"""
        charts = {}
        
        if 'summary' not in results or 'error' in results.get('summary', {}):
            return charts
        
        summary = results['summary']
        evaluated = pd.DataFrame(results.get('evaluated_results', []))
        
        if evaluated.empty:
            return charts
        
        # Chart 1: Success rate by score range
        if 'by_score_range' in summary:
            charts['success_by_score'] = self._chart_success_by_score(summary['by_score_range'])
        
        # Chart 2: Return distribution
        results_30d = evaluated[evaluated['horizon_days'] == 30]
        if not results_30d.empty:
            charts['return_distribution'] = self._chart_return_distribution(results_30d)
        
        # Chart 3: Success rate by horizon
        if 'by_horizon' in summary:
            charts['success_by_horizon'] = self._chart_success_by_horizon(summary['by_horizon'])
        
        # Chart 4: Cumulative returns over time
        if not results_30d.empty:
            charts['cumulative_returns'] = self._chart_cumulative_returns(results_30d)
        
        # Chart 5: Calibration
        if 'calibration' in summary and summary['calibration']:
            charts['calibration'] = self._chart_calibration(summary['calibration'])
        
        return charts
    
    def _chart_success_by_score(self, by_score: Dict) -> str:
        """Bar chart of success rate by score range"""
        fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
        
        labels = list(by_score.keys())
        success_rates = [by_score[l].get('success_rate', 0) for l in labels]
        n_samples = [by_score[l].get('n', 0) for l in labels]
        
        # Persian labels
        persian_labels = {
            'strong_buy': 'خرید قوی\n(75-100)',
            'buy': 'خرید\n(60-75)',
            'hold': 'نگه‌داری\n(45-60)',
            'reduce': 'کاهش\n(30-45)',
            'sell': 'فروش\n(0-30)',
        }
        display_labels = [persian_labels.get(l, l) for l in labels]
        
        colors = ['#4caf50', '#81c784', '#ffeb3b', '#ff9800', '#f44336']
        bars = ax.bar(display_labels, success_rates, color=colors[:len(labels)], 
                      edgecolor='#24231f', linewidth=0.8)
        ax.axhline(y=50, color='#999', linestyle='--', alpha=0.5, label='Random (50%)')
        ax.set_ylabel('Success Rate (%)', fontsize=11)
        ax.set_title('Success Rate by Score Range (30-day horizon)', fontsize=12, pad=12)
        ax.set_ylim(0, max(success_rates + [60]) + 10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.yaxis.grid(True, alpha=0.25, linestyle='--')
        ax.set_axisbelow(True)
        
        for bar, sr, n in zip(bars, success_rates, n_samples):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                    f'{sr:.1f}%\n(n={n})', ha='center', va='bottom', fontsize=9)
        
        ax.legend(loc='upper right', fontsize=9)
        
        path = self.charts_dir / "success_by_score.png"
        fig.savefig(path, dpi=160, facecolor='white')
        plt.close(fig)
        return str(path)
    
    def _chart_return_distribution(self, df: pd.DataFrame) -> str:
        """Histogram of returns"""
        fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
        
        returns = df['return_pct'].values
        ax.hist(returns, bins=40, color='#2196f3', alpha=0.7, edgecolor='#24231f')
        ax.axvline(x=0, color='#666', linestyle='--', alpha=0.7)
        ax.axvline(x=df['return_pct'].mean(), color='#f44336', linestyle='-', 
                   linewidth=2, label=f"Mean: {df['return_pct'].mean():.2f}%")
        
        ax.set_xlabel('Return (%)', fontsize=11)
        ax.set_ylabel('Frequency', fontsize=11)
        ax.set_title('Distribution of Returns (30-day horizon)', fontsize=12, pad=12)
        ax.legend(fontsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.xaxis.grid(True, alpha=0.25, linestyle='--')
        ax.set_axisbelow(True)
        
        path = self.charts_dir / "return_distribution.png"
        fig.savefig(path, dpi=160, facecolor='white')
        plt.close(fig)
        return str(path)
    
    def _chart_success_by_horizon(self, by_horizon: Dict) -> str:
        """Success rate by evaluation horizon"""
        fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
        
        horizons = sorted([int(h) for h in by_horizon.keys()])
        success_rates = [by_horizon[h]['success_rate'] for h in horizons]
        benchmark_rates = [by_horizon[h].get('beats_benchmark_rate', 0) for h in horizons]
        
        x = np.arange(len(horizons))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, success_rates, width, label='Success Rate', 
                       color='#4caf50', edgecolor='#24231f', linewidth=0.8)
        bars2 = ax.bar(x + width/2, benchmark_rates, width, label='Beats Benchmark', 
                       color='#2196f3', edgecolor='#24231f', linewidth=0.8)
        
        ax.set_xlabel('Evaluation Horizon (days)', fontsize=11)
        ax.set_ylabel('Rate (%)', fontsize=11)
        ax.set_title('Performance by Evaluation Horizon', fontsize=12, pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels([f'{h}d' for h in horizons])
        ax.legend(fontsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.yaxis.grid(True, alpha=0.25, linestyle='--')
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(success_rates + benchmark_rates + [60]) + 10)
        
        path = self.charts_dir / "success_by_horizon.png"
        fig.savefig(path, dpi=160, facecolor='white')
        plt.close(fig)
        return str(path)
    
    def _chart_cumulative_returns(self, df: pd.DataFrame) -> str:
        """Cumulative returns over time"""
        fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
        
        df_sorted = df.sort_values('on_date')
        df_sorted['cum_return'] = (1 + df_sorted['return_pct'] / 100).cumprod()
        df_sorted['cum_benchmark'] = (1 + df_sorted['benchmark_return_pct'] / 100).cumprod()
        
        ax.plot(range(len(df_sorted)), df_sorted['cum_return'] * 100 - 100, 
                color='#4caf50', linewidth=2, label='Strategy')
        ax.plot(range(len(df_sorted)), df_sorted['cum_benchmark'] * 100 - 100, 
                color='#666', linewidth=2, linestyle='--', label='Benchmark')
        
        ax.set_xlabel('Recommendation Number (chronological)', fontsize=11)
        ax.set_ylabel('Cumulative Return (%)', fontsize=11)
        ax.set_title('Cumulative Returns: Strategy vs Benchmark', fontsize=12, pad=12)
        ax.legend(fontsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.yaxis.grid(True, alpha=0.25, linestyle='--')
        ax.set_axisbelow(True)
        
        path = self.charts_dir / "cumulative_returns.png"
        fig.savefig(path, dpi=160, facecolor='white')
        plt.close(fig)
        return str(path)
    
    def _chart_calibration(self, calibration: Dict) -> str:
        """Predicted vs actual success rate"""
        fig, ax = plt.subplots(figsize=(6, 6), constrained_layout=True)
        
        labels = list(calibration.keys())
        actual = [calibration[l]['actual_success_rate'] for l in labels]
        predicted = [calibration[l]['predicted_success_rate'] for l in labels]
        
        # Perfect calibration line
        ax.plot([0, 100], [0, 100], 'k--', alpha=0.3, label='Perfect calibration')
        
        # Scatter
        ax.scatter(predicted, actual, s=100, c='#2196f3', edgecolor='#24231f', zorder=5)
        
        for i, label in enumerate(labels):
            ax.annotate(f"n={calibration[label]['n']}", 
                       (predicted[i] + 1, actual[i] + 1), fontsize=8)
        
        ax.set_xlabel('Predicted Success Rate (%)', fontsize=11)
        ax.set_ylabel('Actual Success Rate (%)', fontsize=11)
        ax.set_title('Calibration: Predicted vs Actual', fontsize=12, pad=12)
        ax.legend(fontsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.25, linestyle='--')
        ax.set_axisbelow(True)
        
        path = self.charts_dir / "calibration.png"
        fig.savefig(path, dpi=160, facecolor='white')
        plt.close(fig)
        return str(path)
    
    def _build_html(self, results: Dict, charts: Dict, config: Dict) -> str:
        """Build complete HTML report"""
        summary = results.get('summary', {})
        bias_report = results.get('bias_report', {})
        
        # Format metrics
        overall = summary.get('overall', {})
        by_horizon = summary.get('by_horizon', {})
        by_action = summary.get('by_action', {})
        by_score = summary.get('by_score_range', {})
        calibration = summary.get('calibration', {})
        
        # Decision: PASS or FAIL based on key metrics
        success_rate = overall.get('success_rate', 0)
        beats_benchmark = overall.get('beats_benchmark_rate', 0)
        sharpe = overall.get('sharpe_annualized', 0)
        
        decision = 'PASS' if (success_rate >= 55 and beats_benchmark >= 55 and sharpe >= 0.5) else 'FAIL'
        decision_color = '#4caf50' if decision == 'PASS' else '#f44336'
        decision_msg = {
            'PASS': 'الگوریتم آماده‌ی انتشار است (با رعایت محدودیت‌های ذکر شده)',
            'FAIL': 'الگوریتم هنوز آماده‌ی انتشار نیست — نیاز به بهبود دارد',
        }[decision]
        
        # Bias summary
        bias_summary = bias_report.get('summary', {})
        bias_issues = bias_report.get('issues', [])
        bias_warnings = bias_report.get('warnings', [])
        bias_passed = bias_report.get('passed', [])
        
        html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>گزارش Backtest — سهام‌یار</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap">
<style>
  body {{ font-family: 'Vazirmatn', sans-serif; background: #f5f7fa; color: #24231f; 
         margin: 0; padding: 20px; line-height: 1.7; }}
  .container {{ max-width: 1100px; margin: 0 auto; background: white; 
                padding: 40px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
  h1 {{ color: #142a4d; border-bottom: 3px solid #4caf50; padding-bottom: 10px; }}
  h2 {{ color: #1e3a6d; margin-top: 32px; padding-right: 12px; 
        border-right: 4px solid #4caf50; }}
  h3 {{ color: #2e7d32; margin-top: 24px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
  th {{ background: #142a4d; color: white; padding: 10px 12px; text-align: right; }}
  td {{ padding: 8px 12px; border: 1px solid #e0e4ea; }}
  tr:nth-child(even) {{ background: #f8fbfc; }}
  .decision {{ padding: 20px; border-radius: 8px; margin: 20px 0; 
               background: {decision_color}22; border-right: 4px solid {decision_color}; }}
  .decision h2 {{ color: {decision_color}; border: none; padding: 0; margin: 0 0 8px 0; }}
  .chart {{ margin: 24px 0; text-align: center; }}
  .chart img {{ max-width: 100%; border: 1px solid #e0e4ea; border-radius: 6px; }}
  .chart-caption {{ color: #666; font-size: 13px; margin-top: 6px; }}
  .alert {{ padding: 12px 16px; border-radius: 6px; margin: 12px 0; }}
  .alert-warn {{ background: #fff3e0; border-right: 4px solid #ff9800; }}
  .alert-error {{ background: #ffebee; border-right: 4px solid #f44336; }}
  .alert-success {{ background: #e8f5e9; border-right: 4px solid #4caf50; }}
  .alert-info {{ background: #e3f2fd; border-right: 4px solid #2196f3; }}
  .alert-title {{ font-weight: 700; margin-bottom: 6px; }}
  .metric-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }}
  .metric-card {{ background: #f8fbfc; padding: 16px; border-radius: 6px; text-align: center; 
                  border: 1px solid #e0e4ea; }}
  .metric-value {{ font-size: 24px; font-weight: 700; color: #142a4d; }}
  .metric-label {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .good {{ color: #4caf50; }}
  .bad {{ color: #f44336; }}
  .neutral {{ color: #ff9800; }}
  code {{ background: #f0f7f0; color: #2e7d32; padding: 1px 5px; border-radius: 3px; 
          font-family: monospace; }}
</style>
</head>
<body>
<div class="container">
  <h1>گزارش Backtest الگوریتم Composite Score</h1>
  <p style="color:#666;">
    تولید شده در: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
    دوره‌ی بررسی: {summary.get('date_range', {}).get('start', '?')} تا {summary.get('date_range', {}).get('end', '?')}<br>
    تعداد کل توصیه‌ها: {results.get('total_recommendations', 0):,}
  </p>
  
  <div class="decision">
    <h2>تصمیم: {decision}</h2>
    <p style="margin:0;">{decision_msg}</p>
  </div>
  
  <h2>خلاصه‌ی عملکرد کلی (افق ۳۰ روزه)</h2>
  <div class="metric-grid">
    <div class="metric-card">
      <div class="metric-value {'good' if success_rate >= 55 else 'bad'}">{success_rate}%</div>
      <div class="metric-label">نرخ موفقیت</div>
    </div>
    <div class="metric-card">
      <div class="metric-value {'good' if beats_benchmark >= 55 else 'bad'}">{beats_benchmark}%</div>
      <div class="metric-label">بهتر از شاخص</div>
    </div>
    <div class="metric-card">
      <div class="metric-value {'good' if sharpe >= 0.5 else 'bad'}">{sharpe}</div>
      <div class="metric-label">Sharpe Ratio (سالانه)</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{overall.get('avg_return_pct', 0)}%</div>
      <div class="metric-label">میانگین بازده</div>
    </div>
  </div>
  
  <table>
    <tr><th>معیار</th><th>مقدار</th><th>وضعیت</th></tr>
    <tr><td>تعداد نمونه</td><td>{overall.get('n', 0)}</td><td>{'کافی' if overall.get('n', 0) >= 200 else 'ناکافی'}</td></tr>
    <tr><td>نرخ موفقیت</td><td>{success_rate}%</td><td class="{'good' if success_rate >= 55 else 'bad'}">هدف: 55%+</td></tr>
    <tr><td>بهتر از شاخص</td><td>{beats_benchmark}%</td><td class="{'good' if beats_benchmark >= 55 else 'bad'}">هدف: 55%+</td></tr>
    <tr><td>میانگین بازده</td><td>{overall.get('avg_return_pct', 0)}%</td><td>—</td></tr>
    <tr><td>میانگین بازده مازاد بر شاخص</td><td>{overall.get('avg_excess_return_pct', 0)}%</td><td>{'مثبت' if overall.get('avg_excess_return_pct', 0) > 0 else 'منفی'}</td></tr>
    <tr><td>Sharpe Ratio (سالانه)</td><td>{sharpe}</td><td class="{'good' if sharpe >= 0.5 else 'bad'}">هدف: 0.5+</td></tr>
    <tr><td>Sortino Ratio</td><td>{overall.get('sortino_ratio', 0)}</td><td>—</td></tr>
    <tr><td>حداکثر Drawdown</td><td>{overall.get('max_drawdown_pct', 0)}%</td><td class="{'good' if overall.get('max_drawdown_pct', 0) > -10 else 'bad'}">هدف: کمتر از -10%</td></tr>
    <tr><td>میانگین سود (برد)</td><td>{overall.get('avg_win_pct', 0)}%</td><td>—</td></tr>
    <tr><td>میانگین زیان (باخت)</td><td>{overall.get('avg_loss_pct', 0)}%</td><td>—</td></tr>
    <tr><td>Profit Factor</td><td>{overall.get('profit_factor', 0)}</td><td class="{'good' if overall.get('profit_factor', 0) > 1.5 else 'bad'}">هدف: 1.5+</td></tr>
    <tr><td>نرخ فعال شدن Stop Loss</td><td>{overall.get('stop_loss_hit_rate', 0)}%</td><td>—</td></tr>
    <tr><td>فاصله‌ی اطمینان 95٪</td><td>[{overall.get('ci_95_low', '?')}, {overall.get('ci_95_high', '?')}]%</td><td>—</td></tr>
  </table>
  
  <h2>عملکرد بر اساس افق زمانی</h2>
  <table>
    <tr><th>افق</th><th>n</th><th>موفقیت</th><th>بهتر از شاخص</th><th>میانگین بازده</th><th>Sharpe</th></tr>
"""
        for h in sorted(by_horizon.keys(), key=int):
            m = by_horizon[h]
            html += f"""    <tr><td>{h} روز</td><td>{m.get('n', 0)}</td><td>{m.get('success_rate', 0)}%</td>
                <td>{m.get('beats_benchmark_rate', 0)}%</td><td>{m.get('avg_return_pct', 0)}%</td>
                <td>{m.get('sharpe_annualized', 0)}</td></tr>
"""
        
        html += """  </table>
"""
        
        if 'success_by_horizon' in charts:
            html += f"""
  <div class="chart">
    <img src="charts/success_by_horizon.png" alt="Success by horizon">
    <div class="chart-caption">نمودار ۱: نرخ موفقیت و بهتر از شاخص بر اساس افق زمانی</div>
  </div>
"""
        
        html += """  <h2>عملکرد بر اساس محدوده‌ی Score</h2>
  <table>
    <tr><th>محدوده</th><th>n</th><th>موفقیت</th><th>میانگین بازده</th><th>Sharpe</th><th>حداکثر Drawdown</th></tr>
"""
        persian_labels = {
            'strong_buy': 'خرید قوی (75-100)',
            'buy': 'خرید (60-75)',
            'hold': 'نگه‌داری (45-60)',
            'reduce': 'کاهش (30-45)',
            'sell': 'فروش (0-30)',
        }
        for label in ['strong_buy', 'buy', 'hold', 'reduce', 'sell']:
            if label in by_score:
                m = by_score[label]
                html += f"""    <tr><td>{persian_labels.get(label, label)}</td><td>{m.get('n', 0)}</td>
                    <td>{m.get('success_rate', 0)}%</td><td>{m.get('avg_return_pct', 0)}%</td>
                    <td>{m.get('sharpe_annualized', 0)}</td><td>{m.get('max_drawdown_pct', 0)}%</td></tr>
"""
        
        html += """  </table>
"""
        
        if 'success_by_score' in charts:
            html += f"""
  <div class="chart">
    <img src="charts/success_by_score.png" alt="Success by score">
    <div class="chart-caption">نمودار ۲: نرخ موفقیت بر اساس محدوده‌ی Score (هدف: س cores بالاتر باید موفقیت بالاتر داشته باشند)</div>
  </div>
"""
        
        if 'return_distribution' in charts:
            html += f"""
  <div class="chart">
    <img src="charts/return_distribution.png" alt="Return distribution">
    <div class="chart-caption">نمودار ۳: توزیع بازده توصیه‌ها (خط قرمز: میانگین)</div>
  </div>
"""
        
        if 'cumulative_returns' in charts:
            html += f"""
  <div class="chart">
    <img src="charts/cumulative_returns.png" alt="Cumulative returns">
    <div class="chart-caption">نمودار ۴: بازده انباشتی استراتژی در مقایسه با شاخص</div>
  </div>
"""
        
        # Calibration section
        if calibration:
            html += """  <h2>کالیبراسیون: پیش‌بینی در برابر واقعیت</h2>
  <p>این بخش بررسی می‌کند که آیا نرخ موفقیت پیش‌بینی‌شده با واقعیت مطابقت دارد یا خیر.</p>
  <table>
    <tr><th>محدوده‌ی Score</th><th>n</th><th>پیش‌بینی شده</th><th>واقعی</th><th>خطای کالیبراسیون</th></tr>
"""
            for label, cal in calibration.items():
                html += f"""    <tr><td>{label}</td><td>{cal.get('n', 0)}</td>
                    <td>{cal.get('predicted_success_rate', 0)}%</td>
                    <td>{cal.get('actual_success_rate', 0)}%</td>
                    <td class="{'good' if cal.get('calibration_error', 100) < 5 else ('neutral' if cal.get('calibration_error', 100) < 10 else 'bad')}">{cal.get('calibration_error', 0)}%</td></tr>
"""
            
            html += """  </table>
"""
            
            if 'calibration' in charts:
                html += f"""
  <div class="chart">
    <img src="charts/calibration.png" alt="Calibration" style="max-width: 500px;">
    <div class="chart-caption">نمودار ۵: کالیبراسیون — نقاط نزدیک به خط چین نشان‌دهنده‌ی پیش‌بینی دقیق است</div>
  </div>
"""
        
        # Bias checks
        html += f"""  <h2>بررسی خطاهای متداول (Bias Checks)</h2>
"""
        if bias_issues:
            html += f"""  <div class="alert alert-error">
    <div class="alert-title">❌ مشکلات جدی ({len(bias_issues)})</div>
    <ul>
"""
            for issue in bias_issues:
                html += f"      <li><strong>{issue.get('check', '')}</strong>: {issue.get('message', '')}</li>\n"
            html += "    </ul>\n  </div>\n"
        
        if bias_warnings:
            html += f"""  <div class="alert alert-warn">
    <div class="alert-title">⚠️ هشدارها ({len(bias_warnings)})</div>
    <ul>
"""
            for warn in bias_warnings:
                html += f"      <li><strong>{warn.get('check', '')}</strong>: {warn.get('message', '')}</li>\n"
            html += "    </ul>\n  </div>\n"
        
        if bias_passed:
            html += f"""  <div class="alert alert-success">
    <div class="alert-title">✅ بررسی‌های موفق ({len(bias_passed)})</div>
    <ul>
"""
            for p in bias_passed:
                html += f"      <li><strong>{p.get('check', '')}</strong>: {p.get('message', '')}</li>\n"
            html += "    </ul>\n  </div>\n"
        
        # Recommendations
        html += f"""  <h2>توصیه‌های نهایی</h2>
"""
        if decision == 'PASS':
            html += """  <div class="alert alert-success">
    <div class="alert-title">✅ الگوریتم آماده‌ی انتشار</div>
    <ul>
      <li>نرخ موفقیت در محدوده‌ی قابل‌قبول است (55%+)</li>
      <li>Sharpe Ratio مثبت و بالاتر از حد نصاب است</li>
      <li>هیچ مشکل Bias جدی شناسایی نشده</li>
      <li><strong>توصیه:</strong> با نمایش شفاف نتایج به کاربران، انتشار را شروع کنید</li>
    </ul>
  </div>
"""
        else:
            html += f"""  <div class="alert alert-error">
    <div class="alert-title">❌ الگوریتم نیاز به بهبود دارد</div>
    <ul>
      <li>نرخ موفقیت: {success_rate}% (هدف: 55%+)</li>
      <li>Sharpe: {sharpe} (هدف: 0.5+)</li>
      <li><strong>اقدامات پیشنهادی:</strong></li>
      <li>۱. وزن‌های Composite Score را روی داده‌ی train بهینه کنید</li>
      <li>۲. سیگنال‌های جدید اضافه کنید (مثلاً حجم مبنا، سرانه خریدار)</li>
      <li>۳. افق‌های مختلف را امتحان کنید (شاید ۷ روز بهتر از ۳۰ روز عمل کند)</li>
      <li>۴. در صورت وجود Bias جدی، ابتدا آن را برطرف کنید</li>
    </ul>
  </div>
"""
        
        html += f"""
  <div class="alert alert-info">
    <div class="alert-title">📝 یادآوری مهم</div>
    <p style="margin:0;">
    حتی اگر الگوریتم PASS شود، در گزارش به کاربران همیشه:
    </p>
    <ul>
      <li>نرخ موفقیت واقعی را نشان دهید (نه ادعای 70%+ مثل bifilter)</li>
      <li>Confidence Interval همراه هر توصیه ارائه دهید</li>
      <li>Stop Loss همراه هر توصیه پیشنهاد دهید</li>
      <li>Disclaimer حقوقی «عملکرد گذشته ضامن آینده نیست» را برجسته کنید</li>
    </ul>
  </div>
  
  <hr style="margin-top: 40px; border: none; border-top: 1px solid #e0e4ea;">
  <p style="color: #666; font-size: 12px; text-align: center;">
    Generated by سهام‌یار Backtest Framework · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
  </p>
</div>
</body>
</html>"""
        
        return html
