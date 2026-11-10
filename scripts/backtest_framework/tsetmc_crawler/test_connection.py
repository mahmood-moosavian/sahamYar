#!/usr/bin/env python3
"""Quick test: verify TSETMC crawler can fetch data"""
import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler import TSETMCCrawler, TSETMC_BASE, URL_TRADE_HISTORY, URL_CLIENT_TYPES

def test_connection():
    """Test basic connectivity to TSETMC"""
    print("=" * 60)
    print("TEST 1: Connection to TSETMC")
    print("=" * 60)
    
    import requests
    try:
        print(f"\nTrying: {TSETMC_BASE}")
        response = requests.get(
            TSETMC_BASE,
            timeout=15,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0)'}
        )
        print(f"  Status: {response.status_code}")
        print(f"  Size: {len(response.text)} bytes")
        if response.status_code == 200:
            print("  ✓ Connection OK!")
            return True
        else:
            print(f"  ✗ HTTP {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print("  ✗ TIMEOUT (likely geo-blocked)")
        print("  → Run this script from a machine in Iran or via Iranian VPN")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"  ✗ Connection error: {e}")
        return False

def test_single_symbol():
    """Test fetching data for a known symbol (فولاد - InsCode: 46348559193224090)"""
    print("\n" + "=" * 60)
    print("TEST 2: Fetch single symbol (فولاد)")
    print("=" * 60)
    
    # فولاد مبارکه اصفهان - one of the most active stocks
    FOULAD_INSCODE = "46348559193224090"
    
    crawler = TSETMCCrawler()
    
    print(f"\nFetching trade history for فولاد (InsCode: {FOULAD_INSCODE})...")
    candles = crawler.crawl_candles(FOULAD_INSCODE)
    
    if candles:
        print(f"  ✓ Got {len(candles)} candle records")
        print(f"  First: {candles[0]}")
        print(f"  Last:  {candles[-1]}")
    else:
        print("  ✗ No candles returned")
        return False
    
    print(f"\nFetching client types for فولاد...")
    client_types = crawler.crawl_client_types(FOULAD_INSCODE)
    
    if client_types:
        print(f"  ✓ Got {len(client_types)} client type records")
        print(f"  Last:  {client_types[-1]}")
    else:
        print("  ✗ No client types returned")
        return False
    
    return True

def main():
    print("TSETMC Crawler — Quick Test\n")
    
    # Test 1: Connection
    if not test_connection():
        print("\n❌ Cannot connect to TSETMC from this environment.")
        print("   Possible reasons:")
        print("   1. You're outside Iran (TSETMC geo-blocks foreign IPs)")
        print("   2. Network/firewall blocking the request")
        print("   3. TSETMC is temporarily down")
        print("\n   SOLUTIONS:")
        print("   - Run this script from a machine in Iran")
        print("   - Use an Iranian VPN/proxy")
        print("   - Use a cloud server in Iran (e.g., ArvanCloud, ParsPack)")
        sys.exit(1)
    
    # Test 2: Single symbol
    if not test_single_symbol():
        print("\n❌ Could not fetch symbol data. Check the response format.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED — Crawler is working!")
    print("=" * 60)
    print("\nNext step:")
    print("  python crawler.py --mode test       # Crawl 10 symbols")
    print("  python crawler.py --mode medium     # Crawl 100 symbols (recommended)")
    print("  python crawler.py --mode full       # Crawl all ~5000 symbols")


if __name__ == "__main__":
    main()
