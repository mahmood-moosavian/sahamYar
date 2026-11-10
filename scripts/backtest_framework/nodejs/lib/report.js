/**
 * Report Generator — Creates HTML report from backtest results
 */

const fs = require('fs');
const path = require('path');

function generateReport(results, summary, outputDir) {
  const overall = summary.overall || {};
  const byHorizon = summary.by_horizon || {};
  const byScore = summary.by_score_range || {};

  const decision = overall.decision || 'FAIL';
  const decisionColor = decision === 'PASS' ? '#4caf50' : '#f44336';
  const decisionMsg = decision === 'PASS'
    ? 'الگوریتم آماده‌ی انتشار است'
    : 'الگوریتم نیاز به بهبود دارد';

  const successRate = overall.success_rate || 0;
  const beatsBenchmark = overall.beats_benchmark_rate || 0;
  const sharpe = overall.sharpe_annualized || 0;
  const avgReturn = overall.avg_return_pct || 0;

  // Generate horizon table
  let horizonRows = '';
  for (const [h, m] of Object.entries(byHorizon)) {
    horizonRows += `
      <tr>
        <td>${h} روز</td>
        <td>${m.n || 0}</td>
        <td class="${m.success_rate >= 55 ? 'good' : 'bad'}">${m.success_rate || 0}%</td>
        <td>${m.beats_benchmark_rate || 0}%</td>
        <td>${m.avg_return_pct || 0}%</td>
        <td>${m.sharpe_annualized || 0}</td>
      </tr>`;
  }

  // Generate score range table
  const persianLabels = {
    strong_buy: 'خرید قوی (75-100)',
    buy: 'خرید (60-75)',
    hold: 'نگه‌داری (45-60)',
    reduce: 'کاهش (30-45)',
    sell: 'فروش (0-30)',
  };
  let scoreRows = '';
  for (const label of ['strong_buy', 'buy', 'hold', 'reduce', 'sell']) {
    if (byScore[label]) {
      const m = byScore[label];
      scoreRows += `
        <tr>
          <td>${persianLabels[label]}</td>
          <td>${m.n || 0}</td>
          <td class="${m.success_rate >= 55 ? 'good' : (m.success_rate >= 45 ? 'neutral' : 'bad')}">${m.success_rate || 0}%</td>
          <td>${m.avg_return_pct || 0}%</td>
          <td>${m.sharpe_annualized || 0}</td>
          <td>${m.profit_factor || 0}</td>
        </tr>`;
    }
  }

  const html = `<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>گزارش Backtest — سهام‌یار</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap">
<style>
  body { font-family: 'Vazirmatn', sans-serif; background: #f5f7fa; color: #24231f;
         margin: 0; padding: 20px; line-height: 1.7; }
  .container { max-width: 1100px; margin: 0 auto; background: white;
                padding: 40px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
  h1 { color: #142a4d; border-bottom: 3px solid #4caf50; padding-bottom: 10px; }
  h2 { color: #1e3a6d; margin-top: 32px; padding-right: 12px;
        border-right: 4px solid #4caf50; }
  table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }
  th { background: #142a4d; color: white; padding: 10px 12px; text-align: right; }
  td { padding: 8px 12px; border: 1px solid #e0e4ea; }
  tr:nth-child(even) { background: #f8fbfc; }
  .decision { padding: 20px; border-radius: 8px; margin: 20px 0;
               background: ${decisionColor}22; border-right: 4px solid ${decisionColor}; }
  .decision h2 { color: ${decisionColor}; border: none; padding: 0; margin: 0 0 8px 0; }
  .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }
  .metric-card { background: #f8fbfc; padding: 16px; border-radius: 6px; text-align: center;
                  border: 1px solid #e0e4ea; }
  .metric-value { font-size: 24px; font-weight: 700; color: #142a4d; }
  .metric-label { font-size: 12px; color: #666; margin-top: 4px; }
  .good { color: #4caf50; font-weight: 700; }
  .bad { color: #f44336; font-weight: 700; }
  .neutral { color: #ff9800; font-weight: 700; }
  .alert { padding: 12px 16px; border-radius: 6px; margin: 12px 0; }
  .alert-info { background: #e3f2fd; border-right: 4px solid #2196f3; }
  .alert-success { background: #e8f5e9; border-right: 4px solid #4caf50; }
  .alert-error { background: #ffebee; border-right: 4px solid #f44336; }
</style>
</head>
<body>
<div class="container">
  <h1>گزارش Backtest الگوریتم Composite Score</h1>
  <p style="color:#666;">
    تولید شده در: ${new Date().toLocaleString('fa-IR')}<br>
    تعداد کل توصیه‌ها: ${summary.total_recommendations || 0}
  </p>

  <div class="decision">
    <h2>تصمیم: ${decision}</h2>
    <p style="margin:0;">${decisionMsg}</p>
  </div>

  <h2>خلاصه‌ی عملکرد کلی (افق ۳۰ روزه)</h2>
  <div class="metric-grid">
    <div class="metric-card">
      <div class="metric-value ${successRate >= 55 ? 'good' : 'bad'}">${successRate}%</div>
      <div class="metric-label">نرخ موفقیت</div>
    </div>
    <div class="metric-card">
      <div class="metric-value ${beatsBenchmark >= 55 ? 'good' : 'bad'}">${beatsBenchmark}%</div>
      <div class="metric-label">بهتر از شاخص</div>
    </div>
    <div class="metric-card">
      <div class="metric-value ${sharpe >= 0.5 ? 'good' : 'bad'}">${sharpe}</div>
      <div class="metric-label">Sharpe Ratio</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">${avgReturn}%</div>
      <div class="metric-label">میانگین بازده</div>
    </div>
  </div>

  <table>
    <tr><th>معیار</th><th>مقدار</th><th>وضعیت</th></tr>
    <tr><td>تعداد نمونه</td><td>${overall.n || 0}</td><td>${(overall.n || 0) >= 200 ? 'کافی' : 'ناکافی'}</td></tr>
    <tr><td>نرخ موفقیت</td><td>${successRate}%</td><td class="${successRate >= 55 ? 'good' : 'bad'}">هدف: 55%+</td></tr>
    <tr><td>بهتر از شاخص</td><td>${beatsBenchmark}%</td><td class="${beatsBenchmark >= 55 ? 'good' : 'bad'}">هدف: 55%+</td></tr>
    <tr><td>میانگین بازده</td><td>${avgReturn}%</td><td>—</td></tr>
    <tr><td>میانگین بازده مازاد</td><td>${overall.avg_excess_return_pct || 0}%</td><td>${(overall.avg_excess_return_pct || 0) > 0 ? 'مثبت' : 'منفی'}</td></tr>
    <tr><td>Sharpe Ratio (سالانه)</td><td>${sharpe}</td><td class="${sharpe >= 0.5 ? 'good' : 'bad'}">هدف: 0.5+</td></tr>
    <tr><td>Sortino Ratio</td><td>${overall.sortino || 0}</td><td>—</td></tr>
    <tr><td>حداکثر Drawdown</td><td>${overall.max_drawdown_pct || 0}%</td><td class="${(overall.max_drawdown_pct || -100) > -10 ? 'good' : 'bad'}">هدف: کمتر از -10%</td></tr>
    <tr><td>میانگین سود (برد)</td><td>${overall.avg_win_pct || 0}%</td><td>—</td></tr>
    <tr><td>میانگین زیان (باخت)</td><td>${overall.avg_loss_pct || 0}%</td><td>—</td></tr>
    <tr><td>Profit Factor</td><td>${overall.profit_factor || 0}</td><td class="${(overall.profit_factor || 0) >= 1.5 ? 'good' : 'bad'}">هدف: 1.5+</td></tr>
    <tr><td>نرخ فعال شدن Stop Loss</td><td>${overall.stop_loss_hit_rate || 0}%</td><td>—</td></tr>
  </table>

  <h2>عملکرد بر اساس افق زمانی</h2>
  <table>
    <tr><th>افق</th><th>n</th><th>موفقیت</th><th>بهتر از شاخص</th><th>میانگین بازده</th><th>Sharpe</th></tr>
    ${horizonRows}
  </table>

  <h2>عملکرد بر اساس محدوده‌ی Score</h2>
  <table>
    <tr><th>محدوده</th><th>n</th><th>موفقیت</th><th>میانگین بازده</th><th>Sharpe</th><th>Profit Factor</th></tr>
    ${scoreRows}
  </table>

  ${decision === 'PASS' ? `
  <div class="alert alert-success">
    <strong>✅ الگوریتم آماده‌ی انتشار</strong>
    <ul>
      <li>نرخ موفقیت در محدوده‌ی قابل‌قبول</li>
      <li>Sharpe Ratio بالاتر از حد نصاب</li>
      <li>توصیه: با نمایش شفاف نتایج، انتشار را شروع کنید</li>
    </ul>
  </div>` : `
  <div class="alert alert-error">
    <strong>❌ الگوریتم نیاز به بهبود دارد</strong>
    <ul>
      <li>نرخ موفقیت: ${successRate}% (هدف: 55%+)</li>
      <li>Sharpe: ${sharpe} (هدف: 0.5+)</li>
      <li>اقدامات: وزن‌ها را بهینه کنید، سیگنال‌های جدید اضافه کنید</li>
    </ul>
  </div>`}

  <div class="alert alert-info">
    <strong>📝 یادآوری</strong>
    <ul>
      <li>نرخ موفقیت واقعی را به کاربران نشان دهید</li>
      <li>Confidence Interval همراه هر توصیه ارائه دهید</li>
      <li>Disclaimer «عملکرد گذشته ضامن آینده نیست» را برجسته کنید</li>
    </ul>
  </div>

  <hr style="margin-top: 40px; border: none; border-top: 1px solid #e0e4ea;">
  <p style="color: #666; font-size: 12px; text-align: center;">
    Generated by سهام‌یار Backtest Framework (Node.js) · ${new Date().toISOString()}
  </p>
</div>
</body>
</html>`;

  const reportPath = path.join(outputDir, 'backtest_report.html');
  fs.writeFileSync(reportPath, html, 'utf8');
  return reportPath;
}

module.exports = { generateReport };
