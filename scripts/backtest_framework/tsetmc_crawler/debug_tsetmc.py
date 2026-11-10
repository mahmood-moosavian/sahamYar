#!/usr/bin/env python3
"""
TSETMC Debug Script — Shows the RAW response from TSETMC
so we can fix the parser to match the actual format.

Run this script and send me the contents of the output files:
  tsetmc_response_trade_history_http.txt
  tsetmc_response_client_types.txt
"""
import sys
import os
import requests
from pathlib import Path

# Configuration
TSETMC_BASE = "http://www.tsetmc.com"
TSETMC_BASE_HTTPS = "https://www.tsetmc.com"
FOULAD_INSCODE = "46348559193224090"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.6',
    'Referer': 'http://www.tsetmc.com/',
    'Connection': 'keep-alive',
}


def fetch_url(url, params=None, label=""):
    """Fetch URL and show raw response"""
    print(f"\n{'=' * 70}")
    print(f"Testing: {label}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"{'=' * 70}")

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Size: {len(response.text)} bytes")
        print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")

        # Show first 1500 chars of response
        text = response.text
        print(f"\n--- RAW RESPONSE (first 1500 chars) ---")
        print(text[:1500])
        if len(text) > 1500:
            print(f"... ({len(text) - 1500} more chars)")
        print(f"--- END RAW RESPONSE ---")

        # Save full response to file
        filename = f"tsetmc_response_{label}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"URL: {url}\n")
            f.write(f"Params: {params}\n")
            f.write(f"Status: {response.status_code}\n")
            f.write(f"Size: {len(text)}\n")
            f.write(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}\n\n")
            f.write("=== RAW RESPONSE ===\n")
            f.write(text)
        print(f"\n✓ Full response saved to: {filename}")

        return text
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return None


def main():
    print("=" * 70)
    print("TSETMC Debug — Discovering actual response format")
    print("=" * 70)
    print(f"\nThis script tests multiple TSETMC endpoints and saves the raw")
    print(f"responses to files. We need to see the actual format to fix the parser.\n")

    # Test 1: Trade History (HTTP) - main endpoint for daily candles
    fetch_url(
        f"{TSETMC_BASE}/tsev2/data/InstTradeHistory.aspx",
        params={'i': FOULAD_INSCODE, 'Top': '999999', 'A': '0'},
        label="trade_history_http"
    )

    # Test 2: Trade History (HTTPS) - try secure version
    fetch_url(
        f"{TSETMC_BASE_HTTPS}/tsev2/data/InstTradeHistory.aspx",
        params={'i': FOULAD_INSCODE, 'Top': '999999', 'A': '0'},
        label="trade_history_https"
    )

    # Test 3: Trade History with different Top parameter
    fetch_url(
        f"{TSETMC_BASE}/tsev2/data/InstTradeHistory.aspx",
        params={'i': FOULAD_INSCODE, 'Top': '100', 'A': '0'},
        label="trade_history_top100"
    )

    # Test 4: Instrument Info (live data)
    fetch_url(
        f"{TSETMC_BASE}/tsev2/data/instinfo.aspx",
        params={'i': FOULAD_INSCODE, 'c': '23'},
        label="inst_info"
    )

    # Test 5: Client Types (حقوقی/حقیقی)
    fetch_url(
        f"{TSETMC_BASE}/tsev2/data/clienttype.aspx",
        params={'i': FOULAD_INSCODE},
        label="client_types"
    )

    # Test 6: Market Watch
    fetch_url(
        f"{TSETMC_BASE}/tsev2/data/MarketWatchInit.aspx",
        params={'h': '0', 'r': '0'},
        label="market_watch"
    )

    # Test 7: Loader (symbols list)
    fetch_url(
        f"{TSETMC_BASE}/Loader.aspx",
        params={'ParTree': '111C1417'},
        label="loader_symbols"
    )

    print("\n" + "=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)
    print("\nFiles saved in current directory:")
    print("  tsetmc_response_trade_history_http.txt  ← MOST IMPORTANT")
    print("  tsetmc_response_trade_history_https.txt")
    print("  tsetmc_response_trade_history_top100.txt")
    print("  tsetmc_response_inst_info.txt")
    print("  tsetmc_response_client_types.txt  ← ALSO IMPORTANT")
    print("  tsetmc_response_market_watch.txt")
    print("  tsetmc_response_loader_symbols.txt")

    print("\n" + "=" * 70)
    print("WHAT TO SEND ME:")
    print("=" * 70)
    print("Please open these 2 files and send me their contents:")
    print("  1. tsetmc_response_trade_history_http.txt")
    print("  2. tsetmc_response_client_types.txt")
    print("\nThis will let me fix the parser to match TSETMC's actual format.")


if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        print("Error: requests not installed")
        print("Run: pip install requests")
        sys.exit(1)

    main()
