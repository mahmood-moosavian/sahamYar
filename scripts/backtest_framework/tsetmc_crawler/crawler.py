#!/usr/bin/env python3
"""
TSETMC Crawler — Fetches real historical data from Tehran Stock Exchange

This crawler downloads:
1. All symbols list (one-time, ~5000 symbols)
2. Daily candles (OHLCV) for each symbol
3. Client types (حقوقی/حقیقی) for each symbol
4. Market index (TEDPIX) daily values

Data is saved as CSV files compatible with the backtest framework.

USAGE:
    # Quick test: crawl 10 symbols
    python tsetmc_crawler.py --mode test

    # Crawl top 100 most active symbols (recommended for first run)
    python tsetmc_crawler.py --mode medium --symbols 100

    # Crawl ALL active symbols (~5000, takes 6-12 hours)
    python tsetmc_crawler.py --mode full

    # Resume interrupted crawl
    python tsetmc_crawler.py --mode medium --symbols 100 --resume

REQUIREMENTS:
    pip install requests beautifulsoup4 jdatetime

NOTE:
    TSETMC blocks non-Iranian IPs. Run this from a machine in Iran
    or via an Iranian VPN/proxy.

    TSETMC may rate-limit aggressive crawlers. This script uses
    conservative delays (1-2 seconds between requests) to avoid blocks.
"""
import os
import sys
import time
import json
import argparse
import logging
import random
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# Optional: Jalali date conversion
try:
    import jdatetime
    HAS_JDATETIME = True
except ImportError:
    HAS_JDATETIME = False
    print("⚠️  jdatetime not installed. Install with: pip install jdatetime")
    print("   Date conversion will use approximate method.\n")

# ============================================================
# Configuration
# ============================================================
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data" / "csv"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TSETMC_BASE = "http://www.tsetmc.com"

# Endpoints
URL_SYMBOLS_LIST = f"{TSETMC_BASE}/Loader.aspx?ParTree=111C1417"
URL_TRADE_HISTORY = f"{TSETMC_BASE}/tsev2/data/InstTradeHistory.aspx"
URL_INST_INFO = f"{TSETMC_BASE}/tsev2/data/instinfo.aspx"
URL_CLIENT_TYPES = f"{TSETMC_BASE}/tsev2/data/clienttype.aspx"
URL_MARKET_WATCH = f"{TSETMC_BASE}/tsev2/data/MarketWatchInit.aspx"
URL_MARKET_STATE = f"{TSETMC_BASE}/tsev2/data/MarketState.aspx"

# Request settings
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# Rate limiting
REQUEST_DELAY_MIN = 1.0   # seconds between requests
REQUEST_DELAY_MAX = 2.0   # random delay between min and max
MAX_RETRIES = 3
RETRY_DELAY = 5   # seconds before retry on failure

# Resume state
STATE_FILE = SCRIPT_DIR / "data" / "crawl_state.json"

# Logging
LOG_DIR = SCRIPT_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


class TSETMCCrawler:
    """Main crawler class for TSETMC data"""
    
    def __init__(self, resume: bool = False):
        self.session = requests.Session()
        self.resume = resume
        self.crawled_symbols = set()
        self.failed_symbols = set()
        self.stats = {
            'symbols_total': 0,
            'symbols_crawled': 0,
            'symbols_failed': 0,
            'candles_total': 0,
            'client_types_total': 0,
            'requests_made': 0,
            'requests_failed': 0,
            'start_time': datetime.now().isoformat(),
        }
        
        if resume and STATE_FILE.exists():
            self._load_state()
    
    def _get_headers(self) -> Dict:
        """Get randomized headers"""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.6',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
    def _make_request(self, url: str, params: Dict = None) -> Optional[str]:
        """Make HTTP request with retry logic and rate limiting"""
        for attempt in range(MAX_RETRIES):
            try:
                # Random delay
                delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
                time.sleep(delay)
                
                response = self.session.get(
                    url, params=params, headers=self._get_headers(),
                    timeout=30, allow_redirects=True
                )
                self.stats['requests_made'] += 1
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 403:
                    logger.warning(f"403 Forbidden (attempt {attempt+1}): {url}")
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    time.sleep(RETRY_DELAY)
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout (attempt {attempt+1}): {url}")
                time.sleep(RETRY_DELAY)
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error (attempt {attempt+1}): {e}")
                time.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(RETRY_DELAY)
        
        self.stats['requests_failed'] += 1
        return None
    
    # ============================================================
    # Step 1: Crawl all symbols
    # ============================================================
    def crawl_symbols(self) -> List[Dict]:
        """Fetch list of all symbols from TSETMC"""
        logger.info("=" * 60)
        logger.info("STEP 1: Crawling symbols list...")
        logger.info("=" * 60)
        
        html = self._make_request(URL_SYMBOLS_LIST)
        if not html:
            logger.error("Failed to fetch symbols list")
            return []
        
        # Parse HTML to extract symbol data
        soup = BeautifulSoup(html, 'html.parser')
        symbols = []
        
        # TSETMC uses a specific HTML structure with embedded JavaScript arrays
        # Look for script tags containing symbol data
        for script in soup.find_all('script'):
            text = script.string or script.text or ''
            # Look for pattern: InstSimpleData = [...]
            if 'InstSimpleData' in text or 'AvalData' in text:
                # Extract the array
                # Format: ['InsCode','LVal18AFC','LVal30','Flow','CSecVal','...
                start = text.find("[")
                end = text.rfind("]")
                if start > 0 and end > start:
                    array_str = text[start:end+1]
                    symbols = self._parse_symbols_array(array_str)
                    break
        
        if not symbols:
            # Fallback: try MarketWatch endpoint
            logger.info("Primary parse failed, trying MarketWatch endpoint...")
            symbols = self._crawl_symbols_via_marketwatch()
        
        # Save to CSV
        if symbols:
            self._save_symbols_csv(symbols)
            self.stats['symbols_total'] = len(symbols)
            logger.info(f"✓ Found {len(symbols)} symbols")
            logger.info(f"✓ Saved to {DATA_DIR}/symbols.csv")
        
        return symbols
    
    def _parse_symbols_array(self, array_str: str) -> List[Dict]:
        """Parse TSETMC's JavaScript array format"""
        symbols = []
        # Remove brackets and split by '],['
        array_str = array_str.strip('[]')
        rows = array_str.split('],[')
        
        for row in rows:
            # Split by comma, handle quoted strings
            parts = []
            current = ""
            in_quote = False
            for char in row:
                if char == "'":
                    in_quote = not in_quote
                elif char == ',' and not in_quote:
                    parts.append(current.strip("'"))
                    current = ""
                else:
                    current += char
            if current:
                parts.append(current.strip("'"))
            
            if len(parts) >= 6:
                ins_code = parts[0].strip()
                ticker = parts[1].strip()
                fullname = parts[2].strip()
                flow = parts[3].strip()
                sector_code = parts[4].strip()
                
                # Filter out invalid entries
                if ins_code and ins_code.isdigit() and ticker:
                    symbols.append({
                        'ins_code': ins_code,
                        'ticker': ticker,
                        'fullname': fullname,
                        'sector_code': sector_code if sector_code.isdigit() else 0,
                        'sector_name': '',  # will be filled later
                        'flow': flow if flow.isdigit() else 1,
                        'status': 'A',
                        'listed_at': '',
                        'delisted_at': '',
                        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })
        
        return symbols
    
    def _crawl_symbols_via_marketwatch(self) -> List[Dict]:
        """Fallback: use MarketWatch endpoint"""
        html = self._make_request(URL_MARKET_WATCH, params={'h': '0', 'r': '0'})
        if not html:
            return []
        
        # MarketWatch returns semicolon-separated data
        # Format: InsCode,LVal18AFC,LVal30,FlowID,CSecVal,CGrpVal,CAnoVal,...
        lines = html.strip().split('\n')
        symbols = []
        for line in lines[1:]:  # skip header
            parts = line.split(',')
            if len(parts) >= 5:
                symbols.append({
                    'ins_code': parts[0].strip(),
                    'ticker': parts[1].strip(),
                    'fullname': parts[2].strip(),
                    'sector_code': parts[4].strip() if parts[4].strip().isdigit() else 0,
                    'sector_name': '',
                    'flow': parts[3].strip() if parts[3].strip().isdigit() else 1,
                    'status': 'A',
                    'listed_at': '',
                    'delisted_at': '',
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })
        
        return symbols
    
    def _save_symbols_csv(self, symbols: List[Dict]):
        """Save symbols to CSV"""
        import pandas as pd
        df = pd.DataFrame(symbols)
        df.to_csv(DATA_DIR / "symbols.csv", index=False, encoding='utf-8-sig')
    
    # ============================================================
    # Step 2: Crawl daily candles for each symbol
    # ============================================================
    def crawl_candles(self, ins_code: str) -> List[Dict]:
        """Fetch daily trade history for a symbol"""
        params = {
            'i': ins_code,
            'Top': '999999',  # get all available history
            'A': '0',  # 0 = adjusted, 1 = non-adjusted
        }
        
        response = self._make_request(URL_TRADE_HISTORY, params=params)
        if not response:
            return []
        
        # Response format: semicolon-separated rows
        # Header: DEven;PBrDr;PriceYesterday;PDrCotVal;PClosing;ZTotTran;...
        lines = response.strip().split(';')
        if len(lines) < 2:
            return []
        
        header = lines[0].split(',')
        candles = []
        
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) < len(header):
                continue
            
            row = dict(zip(header, parts))
            
            try:
                # TSETMC date format: YYYYMMDD (Jalali)
                date_jalali = int(row.get('DEven', 0))
                if date_jalali == 0:
                    continue
                
                close = float(row.get('PClosing', 0))
                last_price = float(row.get('PDrCotVal', 0))
                yesterday = float(row.get('PriceYesterday', close))
                
                candle = {
                    'ins_code': ins_code,
                    'date_jalali': date_jalali,
                    'open': float(row.get('PriceFirst', close)),
                    'high': float(row.get('PriceMax', close)),
                    'low': float(row.get('PriceMin', close)),
                    'close': close,
                    'last_price': last_price,
                    'yesterday': yesterday,
                    'volume': int(float(row.get('QTotTran5J', 0))),
                    'trade_count': int(float(row.get('ZTotTran', 0))),
                    'value': int(float(row.get('QTotCap', 0))),
                    'max_allowed': float(row.get('PSGelStaMax', close * 1.05)),
                    'min_allowed': float(row.get('PSGelStaMin', close * 0.95)),
                }
                candles.append(candle)
            except (ValueError, KeyError) as e:
                logger.debug(f"Error parsing candle for {ins_code}: {e}")
                continue
        
        return candles
    
    # ============================================================
    # Step 3: Crawl client types (حقوقی/حقیقی)
    # ============================================================
    def crawl_client_types(self, ins_code: str) -> List[Dict]:
        """Fetch client type data (real vs legal buyers/sellers)"""
        params = {'i': ins_code}
        response = self._make_request(URL_CLIENT_TYPES, params=params)
        if not response:
            return []
        
        # Response format: semicolon-separated
        # Header: Date;Number of Buy real;Number of Sell real;...
        lines = response.strip().split(';')
        if len(lines) < 2:
            return []
        
        header = lines[0].split(',')
        client_types = []
        
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) < len(header):
                continue
            
            row = dict(zip(header, parts))
            
            try:
                # Date format varies, may be YYYYMMDD
                date_str = row.get('Date', row.get(list(row.keys())[0] if row else '', '0'))
                date_jalali = int(date_str) if date_str.isdigit() else 0
                if date_jalali == 0:
                    continue
                
                ct = {
                    'ins_code': ins_code,
                    'date_jalali': date_jalali,
                    'buy_real_count': int(float(row.get('NumberOfBuyCanReal', 0) or row.get(list(row.keys())[1], 0))),
                    'sell_real_count': int(float(row.get('NumberOfSellCanReal', 0) or row.get(list(row.keys())[2], 0))),
                    'buy_legal_count': int(float(row.get('NumberOfBuyCanLegal', 0) or row.get(list(row.keys())[3], 0))),
                    'sell_legal_count': int(float(row.get('NumberOfSellCanLegal', 0) or row.get(list(row.keys())[4], 0))),
                    'buy_real_volume': int(float(row.get('VolumeBuyCanReal', 0) or row.get(list(row.keys())[5], 0))),
                    'sell_real_volume': int(float(row.get('VolumeSellCanReal', 0) or row.get(list(row.keys())[6], 0))),
                    'buy_legal_volume': int(float(row.get('VolumeBuyCanLegal', 0) or row.get(list(row.keys())[7], 0))),
                    'sell_legal_volume': int(float(row.get('VolumeSellCanLegal', 0) or row.get(list(row.keys())[8], 0))),
                    'buy_real_value': int(float(row.get('ValueBuyCanReal', 0) or row.get(list(row.keys())[9], 0))),
                    'sell_real_value': int(float(row.get('ValueSellCanReal', 0) or row.get(list(row.keys())[10], 0))),
                    'buy_legal_value': int(float(row.get('ValueBuyCanLegal', 0) or row.get(list(row.keys())[11], 0))),
                    'sell_legal_value': int(float(row.get('ValueSellCanLegal', 0) or row.get(list(row.keys())[12], 0))),
                }
                client_types.append(ct)
            except (ValueError, KeyError, IndexError) as e:
                logger.debug(f"Error parsing client type for {ins_code}: {e}")
                continue
        
        return client_types
    
    # ============================================================
    # Step 4: Crawl market index (TEDPIX)
    # ============================================================
    def crawl_market_index(self) -> List[Dict]:
        """Fetch TEDPIX market index history"""
        logger.info("Crawling market index (TEDPIX)...")
        
        # TEDPIX InsCode is 32097828799138957
        params = {'i': '32097828799138957', 'Top': '999999', 'A': '0'}
        response = self._make_request(URL_TRADE_HISTORY, params=params)
        if not response:
            return []
        
        lines = response.strip().split(';')
        if len(lines) < 2:
            return []
        
        header = lines[0].split(',')
        index_data = []
        
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) < len(header):
                continue
            
            row = dict(zip(header, parts))
            try:
                date_jalali = int(row.get('DEven', 0))
                if date_jalali == 0:
                    continue
                
                close = float(row.get('PClosing', 0))
                yesterday = float(row.get('PriceYesterday', close))
                change_pct = ((close - yesterday) / yesterday * 100) if yesterday > 0 else 0
                
                index_data.append({
                    'date_jalali': date_jalali,
                    'index_value': close,
                    'index_change_pct': change_pct,
                })
            except (ValueError, KeyError):
                continue
        
        if index_data:
            import pandas as pd
            df = pd.DataFrame(index_data).sort_values('date_jalali')
            df.to_csv(DATA_DIR / "market_index.csv", index=False, encoding='utf-8-sig')
            logger.info(f"✓ Saved {len(index_data)} market index records")
        
        return index_data
    
    # ============================================================
    # Main crawl loop
    # ============================================================
    def crawl_all(self, max_symbols: int = None):
        """Crawl all data: symbols → candles → client_types → market_index"""
        start_time = datetime.now()
        
        # Step 1: Get symbols list
        if not (self.resume and (DATA_DIR / "symbols.csv").exists()):
            symbols = self.crawl_symbols()
        else:
            import pandas as pd
            symbols = pd.read_csv(DATA_DIR / "symbols.csv").to_dict('records')
            logger.info(f"✓ Loaded {len(symbols)} symbols from cache (resume mode)")
        
        if not symbols:
            logger.error("No symbols found. Cannot continue.")
            return
        
        # Filter to active symbols with valid InsCode
        active_symbols = [s for s in symbols if s.get('status') == 'A' and s.get('ins_code', '').isdigit()]
        logger.info(f"Active symbols: {len(active_symbols)}")
        
        if max_symbols:
            # Sort by activity (we'd need to fetch MarketWatch for this)
            # For now, just take first N
            active_symbols = active_symbols[:max_symbols]
            logger.info(f"Limited to {len(active_symbols)} symbols")
        
        # Step 2: Crawl candles and client types for each symbol
        all_candles = []
        all_client_types = []
        
        logger.info("=" * 60)
        logger.info("STEP 2: Crawling candles and client types per symbol...")
        logger.info("=" * 60)
        
        for idx, sym in enumerate(active_symbols, 1):
            ins_code = sym['ins_code']
            ticker = sym.get('ticker', '???')
            
            # Skip if already crawled (resume mode)
            if ins_code in self.crawled_symbols:
                continue
            
            progress_pct = idx / len(active_symbols) * 100
            elapsed = (datetime.now() - start_time).total_seconds()
            eta = (elapsed / idx) * (len(active_symbols) - idx) if idx > 0 else 0
            
            logger.info(f"[{idx}/{len(active_symbols)}] {progress_pct:.1f}% | {ticker} ({ins_code}) | "
                       f"Elapsed: {elapsed/60:.1f}m | ETA: {eta/60:.1f}m")
            
            # Crawl candles
            try:
                candles = self.crawl_candles(ins_code)
                if candles:
                    all_candles.extend(candles)
                    self.stats['candles_total'] += len(candles)
                else:
                    logger.warning(f"  No candles for {ticker}")
            except Exception as e:
                logger.error(f"  Error crawling candles for {ticker}: {e}")
                self.failed_symbols.add(ins_code)
            
            # Crawl client types
            try:
                client_types = self.crawl_client_types(ins_code)
                if client_types:
                    all_client_types.extend(client_types)
                    self.stats['client_types_total'] += len(client_types)
            except Exception as e:
                logger.error(f"  Error crawling client types for {ticker}: {e}")
            
            self.crawled_symbols.add(ins_code)
            self.stats['symbols_crawled'] += 1
            
            # Save state every 10 symbols
            if idx % 10 == 0:
                self._save_state()
                # Also save incremental CSV (for resume)
                self._save_incremental_csvs(all_candles, all_client_types)
                # Reset lists to free memory
                all_candles = []
                all_client_types = []
        
        # Step 3: Crawl market index
        self.crawl_market_index()
        
        # Save final stats
        self.stats['end_time'] = datetime.now().isoformat()
        self.stats['duration_minutes'] = (datetime.now() - start_time).total_seconds() / 60
        self._save_state()
        
        # Final summary
        self._print_summary()
    
    def _save_incremental_csvs(self, candles: List[Dict], client_types: List[Dict]):
        """Save data incrementally (append mode for resume support)"""
        import pandas as pd
        
        if candles:
            df = pd.DataFrame(candles)
            csv_path = DATA_DIR / "daily_candles.csv"
            mode = 'a' if csv_path.exists() else 'w'
            header = not csv_path.exists()
            df.to_csv(csv_path, mode=mode, header=header, index=False, encoding='utf-8-sig')
        
        if client_types:
            df = pd.DataFrame(client_types)
            csv_path = DATA_DIR / "client_types.csv"
            mode = 'a' if csv_path.exists() else 'w'
            header = not csv_path.exists()
            df.to_csv(csv_path, mode=mode, header=header, index=False, encoding='utf-8-sig')
    
    def _save_state(self):
        """Save crawl state for resume"""
        state = {
            'crawled_symbols': list(self.crawled_symbols),
            'failed_symbols': list(self.failed_symbols),
            'stats': self.stats,
        }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def _load_state(self):
        """Load state from previous run"""
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        self.crawled_symbols = set(state.get('crawled_symbols', []))
        self.failed_symbols = set(state.get('failed_symbols', []))
        self.stats.update(state.get('stats', {}))
        logger.info(f"✓ Resumed from previous state: {len(self.crawled_symbols)} symbols already crawled")
    
    def _print_summary(self):
        """Print final summary"""
        print("\n" + "=" * 60)
        print("CRAWL SUMMARY")
        print("=" * 60)
        print(f"  Duration:           {self.stats.get('duration_minutes', 0):.1f} minutes")
        print(f"  Symbols total:      {self.stats.get('symbols_total', 0)}")
        print(f"  Symbols crawled:    {self.stats.get('symbols_crawled', 0)}")
        print(f"  Symbols failed:     {len(self.failed_symbols)}")
        print(f"  Candles fetched:    {self.stats.get('candles_total', 0):,}")
        print(f"  Client types:       {self.stats.get('client_types_total', 0):,}")
        print(f"  HTTP requests:      {self.stats.get('requests_made', 0):,}")
        print(f"  Failed requests:    {self.stats.get('requests_failed', 0):,}")
        print(f"\n  Output directory:   {DATA_DIR}")
        print(f"\n  Next step: Run backtest")
        print(f"    python main.py  # (without --generate-sample-data)")


def main():
    parser = argparse.ArgumentParser(description='TSETMC Crawler for Backtest Framework')
    parser.add_argument('--mode', choices=['test', 'medium', 'full'], default='test',
                        help='test=10 symbols, medium=100, full=all')
    parser.add_argument('--symbols', type=int, default=None,
                        help='Override number of symbols to crawl')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from previous crawl')
    parser.add_argument('--market-index-only', action='store_true',
                        help='Only fetch market index (TEDPIX)')
    
    args = parser.parse_args()
    
    # Determine symbol count
    if args.symbols:
        max_symbols = args.symbols
    elif args.mode == 'test':
        max_symbols = 10
    elif args.mode == 'medium':
        max_symbols = 100
    else:  # full
        max_symbols = None
    
    print("=" * 60)
    print("TSETMC Crawler — Real Data for Backtest Framework")
    print("=" * 60)
    print(f"\nMode: {args.mode}")
    print(f"Symbols: {max_symbols or 'ALL'}")
    print(f"Resume: {args.resume}")
    print(f"Output: {DATA_DIR}\n")
    
    crawler = TSETMCCrawler(resume=args.resume)
    
    if args.market_index_only:
        crawler.crawl_market_index()
    else:
        crawler.crawl_all(max_symbols=max_symbols)


if __name__ == "__main__":
    # Check dependencies
    try:
        import requests
        import bs4
    except ImportError:
        print("Missing dependencies. Install with:")
        print("  pip install requests beautifulsoup4 jdatetime pandas")
        sys.exit(1)
    
    # Import pandas here to avoid loading if just checking help
    try:
        import pandas as pd
    except ImportError:
        print("pandas not installed. Install with: pip install pandas")
        sys.exit(1)
    
    main()
