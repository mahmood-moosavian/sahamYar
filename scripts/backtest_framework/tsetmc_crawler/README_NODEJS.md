# TSETMC Crawler (Node.js)

نسخه‌ی Node.js از TSETMC Crawler — برای کاربرانی که Node.js راحت‌تر از Python دارند.

## نصب

```bash
cd tsetmc_crawler
npm install
```

این دستور `axios` و `cheerio` را نصب می‌کند (تنها dependencies).

## استفاده

### ۱. تست اتصال به TSETMC
```bash
node test_connection.js
```
بررسی می‌کند که آیا TSETMC از سیستم شما قابل دسترسی است (نیاز به IP ایرانی).

### ۲. تست parser با mock data
```bash
node test_parser.js
```
منطق parser را با داده‌ی شبیه‌سازی‌شده تست می‌کند (بدون نیاز به TSETMC).

### ۳. Debug — دیدن فرمت واقعی TSETMC
```bash
node debug_tsetmc.js
```
پاسخ خام TSETMC را در فایل‌های `.txt` ذخیره می‌کند تا parser را با فرمت واقعی تطبیق دهیم.

### ۴. اجرای crawl واقعی
```bash
# تست سریع (۱۰ نماد، ~۲ دقیقه)
node crawler.js --mode test

# متوسط (۱۰۰ نماد، ~۴۰ دقیقه) ⭐ توصیه‌شده
node crawler.js --mode medium

# کامل (همه‌ی ~۵۰۰۰ نماد، ۶-۱۲ ساعت)
node crawler.js --mode full

# ادامه‌ی crawl متوقف‌شده
node crawler.js --mode medium --resume

# فقط شاخص بازار (TEDPIX)
node crawler.js --market-index-only
```

### ۵. کمک
```bash
node crawler.js --help
```

## خروجی

پس از اجرای crawler، این فایل‌ها در `../data/csv/` ساخته می‌شوند:

```
data/csv/
├── symbols.csv          # لیست نمادها
├── daily_candles.csv    # کندل‌های روزانه (OHLCV)
├── client_types.csv     # تفکیک حقیقی/حقوقی
├── market_index.csv     # شاخص کل (TEDPIX)
└── crawl_state.json     # حالت برای resume
```

این فایل‌ها با فرمت Backtest Framework (Python) سازگار هستند.

## اجرای Backtest پس از crawl

پس از تکمیل crawl، به پوشه‌ی اصلی framework برگرد و backtest را اجرا کن:

```bash
cd ..
python main.py  # بدون --generate-sample-data
```

## پیش‌نیازها

- Node.js 16 یا بالاتر ([دانلود](https://nodejs.org/))
- npm (همراه Node.js نصب می‌شود)
- دسترسی به TSETMC (IP ایرانی یا VPN ایرانی)

## عیب‌یابی

### `Error: Cannot find module 'axios'`
```bash
npm install
```

### `TIMEOUT` در test_connection
- TSETMC از IP شما دسترسی نمی‌دهد
- از VPN ایرانی استفاده کنید

### `No candles returned` در test_connection
- Parser با فرمت واقعی تطابق ندارد
- `node debug_tsetmc.js` را اجرا کن و فایل‌های `.txt` را برایم بفرست

## مزایای نسخه‌ی Node.js

- ✅ نصب آسان‌تر روی ویندوز (بدون مشکل pip)
- ✅ مدیریت dependencies با npm
- ✅ اجرای async سریع‌تر
- ✅ خروجی CSV سازگار با Python framework
