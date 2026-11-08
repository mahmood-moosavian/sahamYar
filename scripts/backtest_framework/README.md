# سهام‌یار Backtest Framework

**Framework اعتبارسنجی الگوریتم پیشنهاد خرید/فروش قبل از انتشار به کاربران واقعی**

این framework قبل از الگوریتم Composite Score اصلی اجرا می‌شود تا مطمئن شوید سیگنال‌های شما واقعاً کار می‌کنند و دقت ادعا شده را دارند.

## نصب و راه‌اندازی

```bash
# نصب dependencies
pip install -r requirements.txt

# تولید داده‌ی نمونه (synthetic TSETMC-like data)
python main.py --generate-sample-data

# اجرای backtest کامل با walk-forward validation
python main.py

# اجرای سریع‌تر بدون walk-forward (single split)
python main.py --no-walk-forward
```

## ساختار پروژه

```
backtest_framework/
├── config.yaml                        # تنظیمات (وزن‌ها، تاریخ‌ها، thresholds)
├── requirements.txt                   # Python dependencies
├── main.py                            # Entry point
│
├── data/
│   ├── schema.sql                     # PostgreSQL schema
│   ├── sample_data_generator.py       # تولید داده‌ی synthetic
│   └── csv/                           # CSV data files (auto-generated)
│       ├── symbols.csv
│       ├── daily_candles.csv
│       ├── client_types.csv
│       ├── fundamentals.csv
│       └── market_index.csv
│
├── core/
│   ├── data_loader.py                 # بارگذاری داده از CSV یا PostgreSQL
│   ├── composite_score.py             # محاسبه‌ی Composite Score نهایی
│   ├── backtest_engine.py             # موتور اصلی backtest با walk-forward
│   ├── metrics.py                     # محاسبه‌ی metrics + bias detection
│   └── signals/                       # سیگنال‌های تحلیلی
│       ├── base.py                    # کلاس پایه‌ی Signal
│       ├── smart_money.py             # سیگنال حقوقی/حقیقی (قوی‌ترین)
│       ├── technical.py               # RSI, MFI, MACD, EMA
│       ├── fundamental.py             # P/E, EPS, NAV
│       └── diversification.py         # هم‌بستگی و تنوع پورتفو
│
├── reports/
│   └── report_generator.py            # تولید HTML report با نمودارها
│
└── output/                            # خروجی‌ها (auto-created)
    ├── backtest_report.html           # گزارش کامل
    ├── backtest_results.json          # نتایج خام
    ├── all_recommendations.csv        # همه‌ی توصیه‌ها
    ├── backtest.log                   # لاگ اجرا
    └── charts/                        # نمودارهای PNG
```

## Workflow کلی

```
۱. تولید داده‌ی نمونه (یا بارگذاری داده‌ی واقعی TSETMC)
        ↓
۲. Split داده به train/test windows (walk-forward)
        ↓
۳. برای هر روز در test window:
   - برای هر نماد: محاسبه‌ی Composite Score
   - انتخاب ۵ سهم برتر برای BUY و ۳ سهم پایین برای SELL
        ↓
۴. ارزیابی هر توصیه با قیمت واقعی آینده (۷، ۱۴، ۳۰، ۶۰، ۹۰ روز)
        ↓
۵. محاسبه‌ی metrics:
   - نرخ موفقیت، Sharpe Ratio، Sortino، Max Drawdown
   - مقایسه با شاخص (TEDPIX)
   - Calibration: پیش‌بینی در برابر واقعیت
        ↓
۶. بررسی Bias ها:
   - Look-ahead bias (با report_date)
   - Survivorship bias (نمادهای حذف‌شده)
   - Sample size adequacy
        ↓
۷. تولید گزارش HTML با تصمیم نهایی: PASS یا FAIL
```

## معیارهای تصمیم‌گیری (PASS/FAIL)

الگوریتم **PASS** می‌شود اگر همه‌ی این موارد برآورده شوند:

| معیار | حد نصاب | توضیح |
|---|---|---|
| نرخ موفقیت | ≥ ۵۵٪ | توصیه‌های با بازده ۵٪+ در ۳۰ روز |
| بهتر از شاخص | ≥ ۵۵٪ | توصیه‌ها بازده بالاتر از TEDPIX داشته باشند |
| Sharpe Ratio (سالانه) | ≥ ۰.۵ | بازده تنظیم‌شده برای ریسک |
| Max Drawdown | ≥ -۱۰٪ | حداکثر افت تجمعی |
| Profit Factor | ≥ ۱.۵ | نسبت سود به زیان |
| Sample Size | ≥ ۲۰۰ | تعداد توصیه‌ها برای معناداری آماری |
| Bias Issues | ۰ | بدون خطای look-ahead یا survivorship |

## تنظیم وزن‌های Composite Score

در `config.yaml` می‌توانید وزن‌های هر لایه را تنظیم کنید:

```yaml
COMPOSITE_SCORE:
  smart_money:
    weight: 35        # max points (0-35)
    sub_signals:
      net_legal_value_5d: 15
      accumulation_pattern: 12
      smart_money_consistency: 8
      
  technical:
    weight: 30        # max points (0-30)
    sub_signals:
      rsi_14: 8
      mfi_14: 7
      macd_crossover: 8
      trend_alignment: 7
      
  fundamental:
    weight: 20        # max points (0-20)
    sub_signals:
      pe_below_sector: 12
      eps_growth: 8
      
  diversification:
    weight: 15        # max points (0-15)
    sub_signals:
      low_correlation: 10
      new_sector: 5
```

برای بهینه‌سازی وزن‌ها:
۱. وزن‌های اولیه را تنظیم کنید
۲. backtest را اجرا کنید
۳. اگر PASS نشد، وزن‌ها را تغییر دهید و دوباره اجرا کنید
۴. وقتی PASS شد، وزن‌ها را ثابت نگه دارید و روی داده‌ی واقعی تست کنید

## استفاده با داده‌ی واقعی TSETMC

### حالت CSV
فایل‌های CSV خود را در `data/csv/` قرار دهید با ساختار زیر:

**symbols.csv:**
```csv
ins_code,ticker,fullname,sector_code,sector_name,flow,status,listed_at,delisted_at,updated_at
46348559193224090,فولاد,فولاد مبارکه اصفهان,27,فلزات اساسی,1,A,2000-03-21,,2026-11-07
```

**daily_candles.csv:**
```csv
ins_code,date_jalali,open,high,low,close,last_price,yesterday,volume,trade_count,value,max_allowed,min_allowed
46348559193224090,14050816,4410,4480,4380,4410,4410,4290,8502279,500,37502324190,4505,4077
```

**client_types.csv:**
```csv
ins_code,date_jalali,buy_real_count,sell_real_count,buy_legal_count,sell_legal_count,buy_real_volume,sell_real_volume,buy_legal_volume,sell_legal_volume,buy_real_value,sell_real_value,buy_legal_value,sell_legal_value
```

**fundamentals.csv:**
```csv
ins_code,fiscal_period,eps,estimated_eps,sector_pe,nav,report_date
```

### حالت PostgreSQL
۱. schema.sql را در دیتابیس خود اجرا کنید
۲. در config.yaml، `DATA_SOURCE: "postgres"` را تنظیم کنید
۳. تنظیمات اتصال را در بخش POSTGRES وارد کنید

## تفسیر گزارش

گزارش HTML شامل این بخش‌هاست:

۱. **تصمیم PASS/FAIL** — آیا الگوریتم آماده‌ی انتشار است؟
۲. **خلاصه‌ی عملکرد کلی** — ۴ metric کلیدی (موفقیت، بهتر از شاخص، Sharpe، میانگین بازده)
۳. **جدول کامل metrics** — همه‌ی ۱۳ شاخص عملکرد
۴. **عملکرد بر اساس افق زمانی** — ۷، ۱۴، ۳۰، ۶۰، ۹۰ روز
۵. **عملکرد بر اساس محدوده‌ی Score** — آیا Score بالاتر واقعاً موفقیت بالاتر می‌دهد؟
۶. **توزیع بازده‌ها** — نمودار histogram
۷. **بازده انباشتی** — استراتژی در برابر شاخص
۸. **کالیبراسیون** — آیا پیش‌بینی‌ها با واقعیت مطابقت دارند؟
۹. **بررسی Bias ها** — مشکلات احتمالی و راهکارها
۱۰. **توصیه‌های نهایی** — گام‌های بعدی

## نکات مهم

### Bias Detection
framework به‌صورت خودکار این bias ها را بررسی می‌کند:
- **Look-ahead bias**: فقط داده‌ی موجود در زمان تصمیم استفاده می‌شود
- **Survivorship bias**: نمادهای حذف‌شده باید در داده باشند
- **Sample size**: حداقل ۲۰۰ توصیه لازم است

### Walk-Forward Validation
به جای یک train/test split ثابت، داده به چند پنجره تقسیم می‌شود:
- Train: ۲ سال (~۵۰۴ روز)
- Test: ۱ سال (~۲۵۲ روز)
- Step: ۶ ماه (~۱۲۶ روز)

این کار اطمینان می‌دهد که الگوریتم در دوره‌های مختلف بازار کار می‌کند.

### Performance Optimization
برای اجرای سریع‌تر:
- `sample_symbols_per_day` را در config کاهش دهید (پیش‌فرض: ۵۰)
- `--no-walk-forward` برای single split استفاده کنید
- `evaluation_horizons` را محدود کنید به `[30]`

## عیب‌یابی

### "FileNotFoundError: symbols.csv not found"
داده نمونه تولید نشده. اجرا کنید:
```bash
python main.py --generate-sample-data
```

### خطای نصب dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### اجرای بسیار کند
- `sample_symbols_per_day` را در config.yaml کاهش دهید
- یا `--no-walk-forward` را امتحان کنید

## تماس و پشتیبانی

این framework بخشی از پروژه‌ی سهام‌یار است.
گزارش باگ‌ها و درخواست feature در GitHub repository پروژه.

---

**یادآوری مهم:** حتی اگر الگوریتم PASS شود، هیچ‌گاه به کاربران «نرخ موفقیت ۱۰۰٪» یا «سیگنال قطعی» اعلام نکنید. همیشه:
- Confidence Interval نشان دهید
- Stop Loss همراه هر توصیه ارائه دهید
- Disclaimer «عملکرد گذشته ضامن آینده نیست» را برجسته کنید
