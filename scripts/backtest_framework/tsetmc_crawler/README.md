# TSETMC Crawler — راهنمای استفاده

این crawler داده‌های واقعی از سایت TSETMC (بورس تهران) دریافت و در قالب CSV ذخیره می‌کند تا با Backtest Framework قابل استفاده باشد.

## ⚠️ پیش‌نیاز مهم

TSETMC به IPهای خارج از ایران اجازه‌ی دسترسی نمی‌دهد. این crawler را باید از **سیستمی در ایران** اجرا کنید.

راه‌حل‌ها:
1. اجرا روی کامپیوتر شخصی در ایران
2. استفاده از VPN ایرانی
3. اجاره‌ی VPS ایرانی (ArvanCloud، ParsPack، ایران‌هاست و...)

## نصب

```bash
cd backtest_framework/tsetmc_crawler
pip install requests beautifulsoup4 jdatetime pandas
```

## تست اتصال (اولین قدم)

قبل از اجرای کامل، تست کنید که آیا به TSETMC دسترسی دارید:

```bash
python test_connection.py
```

اگر خروجی `✓ ALL TESTS PASSED` بود، آماده‌ی crawl هستید.

اگر خطای TIMEOUT گرفتید:
- احتمالاً IP شما خارج از ایران است
- از VPN ایرانی استفاده کنید

## اجرای Crawler

### حالت ۱: تست سریع (۱۰ نماد، ~۲ دقیقه)
```bash
python crawler.py --mode test
```
مناسب برای تأیید اینکه همه‌چیز کار می‌کند.

### حالت ۲: متوسط (۱۰۰ نماد، ~۳۰-۴۰ دقیقه) ⭐ توصیه‌شده
```bash
python crawler.py --mode medium
```
برای اولین backtest واقعی کافی است. شامل فعال‌ترین ۱۰۰ نماد بازار.

### حالت ۳: کامل (همه‌ی ~۵۰۰۰ نماد، ۶-۱۲ ساعت)
```bash
python crawler.py --mode full
```
برای backtest حرفه‌ای. می‌توانید در شب اجرا کنید و صبح داده‌ها آماده باشد.

### حالت ۴: ادامه‌ی crawl متوقف‌شده
```bash
python crawler.py --mode medium --resume
```
اگر crawl قطع شد (اینترنت، قطع برق و...)، با این گزینه از همانجا ادامه می‌یابد.

### حالت ۵: فقط شاخص بازار (TEDPIX)
```bash
python crawler.py --market-index-only
```
اگر فقط داده‌ی شاخص کل را لازم دارید.

## خروجی

پس از اجرا، این فایل‌ها در `data/csv/` ساخته می‌شوند:

```
data/csv/
├── symbols.csv          # لیست همه‌ی نمادها
├── daily_candles.csv    # کندل‌های روزانه (OHLCV)
├── client_types.csv     # تفکیک حقیقی/حقوقی
├── market_index.csv     # شاخص کل (TEDPIX)
└── crawl_state.json     #状態 برای resume
```

این فایل‌ها با فرمت مورد نیاز Backtest Framework سازگار هستند.

## اجرای Backtest با داده‌ی واقعی

پس از تکمیل crawl:

```bash
cd ..  # برگشت به backtest_framework/
python main.py  # بدون --generate-sample-data
```

Framework خودش داده‌های واقعی را از `data/csv/` می‌خواند و backtest را اجرا می‌کند.

## تنظیمات پیشرفته

برای تغییر تنظیمات crawler، فایل `crawler.py` را ویرایش کنید:

```python
# Rate limiting (پیش‌فرض: ۱-۲ ثانیه بین درخواست‌ها)
REQUEST_DELAY_MIN = 1.0
REQUEST_DELAY_MAX = 2.0

# Number of retries (پیش‌فرض: ۳)
MAX_RETRIES = 3
```

⚠️ **هشدار:** اگر REQUEST_DELAY را خیلی پایین بیاورید، TSETMC ممکن است IP شما را مسدود کند.

## عیب‌یابی

### خطای Timeout
- IP شما خارج از ایران است → از VPN ایرانی استفاده کنید
- اینترنت کند است → REQUEST_DELAY را افزایش دهید

### خطای 403 Forbidden
- TSETMC شما را مسدود کرده (درخواست‌های زیاد)
- ۲۴ ساعت صبر کنید یا IP را تغییر دهید

### داده‌ی ناقص برای برخی نمادها
- برخی نمادها تاریخچه‌ی کوتاه دارند (تازه وارد بازار شده‌اند)
- برخی نمادها متوقف شده‌اند (status='S')
- این طبیعی است و در backtest با sample_size check مدیریت می‌شود

### خطای Parsing
- TSETMC ممکن است فرمت پاسخ را تغییر دهد
- اگر خطای parsing گرفتید، فایل log را بررسی کنید و خط مربوطه را گزارش دهید

## پشتیبانی

اگر خطایی دیدید یا داده‌ای parse نشد:
1. فایل log در `data/logs/crawl_YYYYMMDD_HHMMSS.log` را بررسی کنید
2. خطای دقیق را در فایل ذخیره کنید
3. یا کد را به‌صورت دستی روی همان نماد تست کنید

## منابع

- TSETMC: http://www.tsetmc.com
- مستندات غیررسمی TSETMC API: https://github.com/smb59/TSETMC
- تبدیل تاریخ شمسی: https://github.com/jdatetime/pyjdal
