#!/usr/bin/env python3
"""
Sample Data Generator for Backtest Framework
Generates synthetic but realistic TSETMC-like data for testing the framework.

This is for testing the framework BEFORE you have real data.
Once you have real TSETMC data, replace the CSV files with real data.

The synthetic data uses:
- Geometric Brownian Motion for prices
- Simulated smart money patterns (legal entities buy before pumps)
- Sector-based correlations
- Realistic EPS and P/E distributions
"""
import os
import sys
import random
import csv
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

# Setup paths
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

# Output directory
OUTPUT_DIR = Path(__file__).parent / "csv"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Configuration
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# Number of synthetic symbols (reduced for faster testing)
N_SYMBOLS = 50

# Date range (Jalali integer dates)
# Reduced period for faster testing
START_DATE = datetime(2023, 3, 21)   # ~1402/01/01
END_DATE = datetime(2025, 6, 22)     # ~1404/03/31

# Sectors (based on real TSETMC sector codes)
SECTORS = [
    (1, "کشاورزی و دامپروری"),
    (5, "صنایع غذایی و آشامیدنی به جز قند و شکر"),
    (13, "نساجی"),
    (14, "سایر معادن"),
    (15, "سیمان، آهک و گچ"),
    (17, "منسوجات"),
    (19, "چوب و محصولات چوبی"),
    (22, "نشریات و چاپ"),
    (27, "فلزات اساسی"),
    (29, "ماشین‌آلات و دستگاه‌های برقی"),
    (31, "خودرو، قطعات و ماشین‌آلات کشاورزی"),
    (33, "سایر وسایل حمل و نقل"),
    (34, "ساخت محصولات فلزی"),
    (36, "تأسیسات، تجهیزات و ماشین‌آلات اداری"),
    (37, "تأسیسات و ماشین‌آلات مهندسی"),
    (39, "ابزار پزشکی"),
    (43, "کاشی و سرامیک"),
    (44, "محصولات شیمیایی"),
    (45, "لاستیک و پلاستیک"),
    (50, "ساخت و ساز"),
    (53, "خرده فروشی به جز فروش وسایل نقلیه"),
    (61, "نقل و انتقالات هوایی"),
    (64, "خدمات نرم‌افزاری و فناوری اطلاعات"),
    (65, "بانک‌ها و موسسات اعتباری"),
    (69, "اسناد خزانه اسلامی"),
]

# Persian ticker prefixes (real-world)
TICKER_TEMPLATES = [
    "ف{name}", "خ{name}", "ب{name}", "س{name}",
    "ش{name}", "و{name}", "ن{name}", "{name}تسه",
]

NAME_POOL = [
    "ملت", "ملی", "سپه", "تجارت", "صادرات", "ولسپهر", "وبملت",
    "فولاد", "خزر", "فملی", "فولا", "سفارس", "فسدید", "فجر",
    "بساما", "بپاس", "ساروم", "شاروم", "سپنتا", "چافست",
    "خودرو", "سایپا", "مولی", "خزر", "سارا", "وغدیر",
    "خپارس", "خلیز", "خکر", "ختراک", "خزمین", "خازاد",
]

def generate_ins_code() -> str:
    """Generate a 17-digit numeric code (like TSETMC InsCode)"""
    return str(np.random.randint(10**16, 10**17 - 1))

def generate_ticker(name: str, used: set) -> str:
    """Generate a unique ticker symbol"""
    for prefix in TICKER_TEMPLATES:
        candidate = prefix.format(name=name)
        if candidate not in used:
            used.add(candidate)
            return candidate
    # Fallback: append random number
    candidate = f"ف{name}{np.random.randint(10, 99)}"
    used.add(candidate)
    return candidate

def jalali_to_int(jalali_str: str) -> int:
    """Convert '1404/06/15' to 14040615"""
    y, m, d = jalali_str.split('/')
    return int(y) * 10000 + int(m) * 100 + int(d)

def gregorian_to_jalali_int(g: datetime) -> int:
    """Approximate conversion (for synthetic data only).
    Real conversion should use jdatetime library."""
    # Approximate: Iranian new year is around March 21
    # Year offset: 1400 = 2021-2022
    if g.month >= 3 and g.day >= 21 or g.month > 3:
        jy = g.year - 621
        days_into_year = (g - datetime(g.year, 3, 21)).days
    else:
        jy = g.year - 622
        days_into_year = (g - datetime(g.year - 1, 3, 21)).days
    
    # Approximate month/day
    if days_into_year < 31:
        jm, jd = 1, days_into_year + 1
    elif days_into_year < 62:
        jm, jd = 2, days_into_year - 30
    elif days_into_year < 93:
        jm, jd = 3, days_into_year - 61
    elif days_into_year < 124:
        jm, jd = 4, days_into_year - 92
    elif days_into_year < 155:
        jm, jd = 5, days_into_year - 123
    elif days_into_year < 186:
        jm, jd = 6, days_into_year - 154
    elif days_into_year < 216:
        jm, jd = 7, days_into_year - 185
    elif days_into_year < 246:
        jm, jd = 8, days_into_year - 215
    elif days_into_year < 276:
        jm, jd = 9, days_into_year - 245
    elif days_into_year < 306:
        jm, jd = 10, days_into_year - 275
    elif days_into_year < 336:
        jm, jd = 11, days_into_year - 305
    else:
        jm, jd = 12, days_into_year - 335
    
    return jy * 10000 + jm * 100 + jd

def generate_symbols(n: int) -> pd.DataFrame:
    """Generate n synthetic symbols"""
    used_tickers = set()
    symbols = []
    for i in range(n):
        name = random.choice(NAME_POOL)
        ticker = generate_ticker(name, used_tickers)
        sector_code, sector_name = random.choice(SECTORS)
        ins_code = generate_ins_code()
        # Some symbols are delisted (~5%)
        if random.random() < 0.05:
            status = "D"
            delisted_at = START_DATE + timedelta(days=random.randint(200, 800))
            listed_at = START_DATE
        else:
            status = "A"
            listed_at = START_DATE - timedelta(days=random.randint(365, 365*5))
            delisted_at = None
        
        symbols.append({
            'ins_code': ins_code,
            'ticker': ticker,
            'fullname': f"شرکت {ticker} {sector_name}",
            'sector_code': sector_code,
            'sector_name': sector_name,
            'flow': 1,
            'status': status,
            'listed_at': listed_at.strftime('%Y-%m-%d'),
            'delisted_at': delisted_at.strftime('%Y-%m-%d') if delisted_at else '',
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
    return pd.DataFrame(symbols)

def generate_price_series(start_price: float, n_days: int, 
                          daily_vol: float = 0.025, drift: float = 0.0003,
                          has_smart_money_pattern: bool = True) -> np.ndarray:
    """Generate synthetic price series using GBM with optional smart money patterns"""
    # Vectorized GBM (much faster)
    returns = np.random.normal(drift, daily_vol, n_days)
    prices = np.zeros(n_days)
    prices[0] = start_price
    
    # Cumulative product for base prices (faster than loop)
    cum_factors = np.cumprod(1 + returns)
    prices = start_price * cum_factors
    
    # Inject smart money pattern every ~60 days
    if has_smart_money_pattern:
        for i in range(60, n_days, 60):
            pump_day = i + random.randint(5, 15)
            if pump_day < n_days:
                pump_size = random.uniform(0.05, 0.15)
                # Apply pump and let it stay (mean reversion is minor)
                prices[pump_day:] = prices[pump_day:] * (1 + pump_size) / prices[pump_day] * prices[pump_day-1] * (1 + pump_size)
    
    return prices

def generate_candles(symbols: pd.DataFrame) -> pd.DataFrame:
    """Generate daily candles for all symbols"""
    all_candles = []
    date_range = [START_DATE + timedelta(days=i) for i in range((END_DATE - START_DATE).days)]
    
    for _, sym in symbols.iterrows():
        if sym['status'] == 'D':
            delisted_dt = datetime.strptime(sym['delisted_at'], '%Y-%m-%d') if sym['delisted_at'] else END_DATE
            n_days = (delisted_dt - START_DATE).days
        else:
            n_days = len(date_range)
        
        if n_days <= 0:
            continue
        
        # Base price between 1,000 and 100,000 Tomans
        base_price = random.choice([1000, 2000, 5000, 10000, 20000, 50000, 80000])
        daily_vol = random.uniform(0.015, 0.04)
        drift = random.uniform(-0.0005, 0.001)
        has_pattern = random.random() < 0.4  # 40% have smart money patterns
        
        closes = generate_price_series(base_price, n_days, daily_vol, drift, has_pattern)
        
        for i, date in enumerate(date_range[:n_days]):
            # Skip Fridays in Iran (weekly holiday)
            if date.weekday() == 4:  # Monday=0, Friday=4
                continue
            
            close = round(closes[i], 2)
            yesterday = round(closes[i-1], 2) if i > 0 else close
            open_price = round(yesterday * (1 + random.uniform(-0.02, 0.02)), 2)
            high = round(max(open_price, close) * (1 + random.uniform(0, 0.03)), 2)
            low = round(min(open_price, close) * (1 - random.uniform(0, 0.03)), 2)
            volume = int(random.uniform(100000, 10000000))
            trade_count = int(random.uniform(100, 5000))
            value = int(volume * close)
            max_allowed = round(yesterday * 1.05, 2)  # +5%
            min_allowed = round(yesterday * 0.95, 2)  # -5%
            
            all_candles.append({
                'ins_code': sym['ins_code'],
                'date_jalali': gregorian_to_jalali_int(date),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'last_price': close,
                'yesterday': yesterday,
                'volume': volume,
                'trade_count': trade_count,
                'value': value,
                'max_allowed': max_allowed,
                'min_allowed': min_allowed,
            })
    
    return pd.DataFrame(all_candles)

def generate_client_types(candles: pd.DataFrame, symbols: pd.DataFrame) -> pd.DataFrame:
    """Generate client type data (حقوقی/حقیقی) correlated with future price movements"""
    all_clients = []
    
    for ins_code, sym_candles in candles.groupby('ins_code'):
        sym_candles = sym_candles.sort_values('date_jalali').reset_index(drop=True)
        
        for i, row in sym_candles.iterrows():
            # Base split: 70% real, 30% legal
            real_pct = random.uniform(0.5, 0.9)
            legal_pct = 1 - real_pct
            
            total_volume = row['volume']
            total_value = row['value']
            
            # Look ahead 1-3 days: if price will rise, legal entities bought more
            future_rise = False
            if i + 3 < len(sym_candles):
                future_close = sym_candles.iloc[i+3]['close']
                if future_close > row['close'] * 1.02:
                    future_rise = True
            
            if future_rise:
                # Legal entities are net buyers (smart money pattern)
                legal_pct = min(0.6, legal_pct * 1.5)
                real_pct = 1 - legal_pct
                buy_legal_volume = int(total_volume * legal_pct * 0.7)  # 70% of legal volume is buying
                sell_legal_volume = int(total_volume * legal_pct * 0.3)
                buy_real_volume = int(total_volume * real_pct * 0.4)  # 40% of real is buying
                sell_real_volume = int(total_volume * real_pct * 0.6)
            else:
                # Normal or distribution pattern
                buy_legal_volume = int(total_volume * legal_pct * 0.5)
                sell_legal_volume = int(total_volume * legal_pct * 0.5)
                buy_real_volume = int(total_volume * real_pct * 0.5)
                sell_real_volume = int(total_volume * real_pct * 0.5)
            
            all_clients.append({
                'ins_code': ins_code,
                'date_jalali': row['date_jalali'],
                'buy_real_count': int(random.uniform(50, 500)),
                'sell_real_count': int(random.uniform(50, 500)),
                'buy_legal_count': int(random.uniform(1, 20)),
                'sell_legal_count': int(random.uniform(1, 20)),
                'buy_real_volume': buy_real_volume,
                'sell_real_volume': sell_real_volume,
                'buy_legal_volume': buy_legal_volume,
                'sell_legal_volume': sell_legal_volume,
                'buy_real_value': int(buy_real_volume * row['close']),
                'sell_real_value': int(sell_real_volume * row['close']),
                'buy_legal_value': int(buy_legal_volume * row['close']),
                'sell_legal_value': int(sell_legal_volume * row['close']),
            })
    
    return pd.DataFrame(all_clients)

def generate_fundamentals(symbols: pd.DataFrame, candles: pd.DataFrame) -> pd.DataFrame:
    """Generate quarterly fundamentals"""
    all_fundamentals = []
    
    quarters = ['1402/Q1', '1402/Q2', '1402/Q3', '1402/Q4',
                '1403/Q1', '1403/Q2', '1403/Q3', '1403/Q4',
                '1404/Q1', '1404/Q2']
    
    for _, sym in symbols.iterrows():
        if sym['status'] == 'D':
            continue
        
        # Generate base EPS for this symbol (from -5000 to +5000 Tomans)
        base_eps = random.uniform(-5000, 5000)
        
        for q in quarters:
            # EPS grows or shrinks gradually
            eps = base_eps * (1 + random.uniform(-0.2, 0.3))
            estimated_eps = eps * 4 * random.uniform(0.8, 1.2)  # annualized estimate
            sector_pe = random.uniform(5, 15)
            nav = random.choice([0, random.uniform(5000, 50000)])
            
            # Report date is end of quarter + ~45 days
            year = int(q.split('/')[0])
            quarter = int(q.split('/')[1][1])
            quarter_end_month = quarter * 3
            # Approximate Gregorian date for quarter end
            quarter_end = datetime(2022 + (year - 1401), ((quarter_end_month - 1) % 12) + 1, 30)
            report_date = quarter_end + timedelta(days=45)
            
            all_fundamentals.append({
                'ins_code': sym['ins_code'],
                'fiscal_period': q,
                'eps': round(eps, 2),
                'estimated_eps': round(estimated_eps, 2),
                'sector_pe': round(sector_pe, 2),
                'nav': round(nav, 2) if nav else 0,
                'report_date': report_date.strftime('%Y-%m-%d'),
            })
    
    return pd.DataFrame(all_fundamentals)

def generate_market_index(candles: pd.DataFrame) -> pd.DataFrame:
    """Generate TEDPIX-like market index from equal-weighted average of all symbols"""
    daily_avg = candles.groupby('date_jalali')['close'].mean().reset_index()
    daily_avg.columns = ['date_jalali', 'index_value']
    daily_avg = daily_avg.sort_values('date_jalali').reset_index(drop=True)
    daily_avg['index_change_pct'] = daily_avg['index_value'].pct_change() * 100
    daily_avg['index_change_pct'] = daily_avg['index_change_pct'].fillna(0)
    return daily_avg

def main():
    print("=" * 60)
    print("Sample Data Generator for Backtest Framework")
    print("=" * 60)
    
    print(f"\n[1/5] Generating {N_SYMBOLS} symbols...")
    symbols = generate_symbols(N_SYMBOLS)
    symbols.to_csv(OUTPUT_DIR / "symbols.csv", index=False, encoding='utf-8-sig')
    print(f"  ✓ Saved {len(symbols)} symbols to symbols.csv")
    
    print(f"\n[2/5] Generating daily candles...")
    candles = generate_candles(symbols)
    candles.to_csv(OUTPUT_DIR / "daily_candles.csv", index=False, encoding='utf-8-sig')
    print(f"  ✓ Saved {len(candles):,} candle records to daily_candles.csv")
    
    print(f"\n[3/5] Generating client types (حقوقی/حقیقی)...")
    client_types = generate_client_types(candles, symbols)
    client_types.to_csv(OUTPUT_DIR / "client_types.csv", index=False, encoding='utf-8-sig')
    print(f"  ✓ Saved {len(client_types):,} client type records to client_types.csv")
    
    print(f"\n[4/5] Generating fundamentals (quarterly)...")
    fundamentals = generate_fundamentals(symbols, candles)
    fundamentals.to_csv(OUTPUT_DIR / "fundamentals.csv", index=False, encoding='utf-8-sig')
    print(f"  ✓ Saved {len(fundamentals):,} fundamental records to fundamentals.csv")
    
    print(f"\n[5/5] Generating market index (TEDPIX-like)...")
    market_index = generate_market_index(candles)
    market_index.to_csv(OUTPUT_DIR / "market_index.csv", index=False, encoding='utf-8-sig')
    print(f"  ✓ Saved {len(market_index)} market index records to market_index.csv")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Symbols:        {len(symbols):>6}")
    print(f"  Active:         {len(symbols[symbols.status == 'A']):>6}")
    print(f"  Delisted:       {len(symbols[symbols.status == 'D']):>6}")
    print(f"  Sectors:        {symbols.sector_code.nunique():>6}")
    print(f"  Date range:     {candles.date_jalali.min()} to {candles.date_jalali.max()}")
    print(f"  Candles:        {len(candles):>6,}")
    print(f"  Client types:   {len(client_types):>6,}")
    print(f"  Fundamentals:   {len(fundamentals):>6,}")
    print(f"  Output dir:     {OUTPUT_DIR}")
    print("\n✓ Sample data generation complete!")

if __name__ == "__main__":
    main()
