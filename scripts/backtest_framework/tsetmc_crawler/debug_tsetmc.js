/**
 * TSETMC Debug Script (Node.js)
 *
 * Shows the RAW response from TSETMC so we can fix the parser
 * to match the actual format.
 *
 * Run: node debug_tsetmc.js
 *
 * After running, send me the contents of:
 *   tsetmc_response_trade_history_http.txt
 *   tsetmc_response_client_types.txt
 */

const axios = require('axios');
const fs = require('fs');
const path = require('path');

const TSETMC_BASE = 'http://www.tsetmc.com';
const TSETMC_BASE_HTTPS = 'https://www.tsetmc.com';
const FOULAD_INSCODE = '46348559193224090';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.6',
  'Referer': 'http://www.tsetmc.com/',
  'Connection': 'keep-alive',
};

async function fetchUrl(url, params, label) {
  console.log(`\n${'='.repeat(70)}`);
  console.log(`Testing: ${label}`);
  console.log(`URL: ${url}`);
  console.log(`Params: ${JSON.stringify(params)}`);
  console.log('='.repeat(70));

  try {
    const response = await axios.get(url, {
      params,
      headers: HEADERS,
      timeout: 30000,
      maxRedirects: 5,
    });

    const text = response.data;
    console.log(`Status: ${response.status}`);
    console.log(`Size: ${text.length} bytes`);
    console.log(`Content-Type: ${response.headers['content-type'] || 'unknown'}`);

    console.log(`\n--- RAW RESPONSE (first 1500 chars) ---`);
    console.log(text.substring(0, 1500));
    if (text.length > 1500) {
      console.log(`... (${text.length - 1500} more chars)`);
    }
    console.log(`--- END RAW RESPONSE ---`);

    // Save full response to file
    const filename = `tsetmc_response_${label}.txt`;
    const content = `URL: ${url}\nParams: ${JSON.stringify(params)}\nStatus: ${response.status}\nSize: ${text.length}\nContent-Type: ${response.headers['content-type'] || 'unknown'}\n\n=== RAW RESPONSE ===\n${text}`;
    fs.writeFileSync(filename, content, 'utf8');
    console.log(`\n✓ Full response saved to: ${filename}`);

    return text;
  } catch (error) {
    const code = error.code || 'UNKNOWN';
    const msg = error.message || String(error);
    console.log(`Error: ${code} - ${msg}`);
    return null;
  }
}

async function main() {
  console.log('='.repeat(70));
  console.log('TSETMC Debug (Node.js) — Discovering actual response format');
  console.log('='.repeat(70));
  console.log('\nThis script tests multiple TSETMC endpoints and saves the raw');
  console.log('responses to files. We need to see the actual format to fix the parser.\n');

  // Test 1: Trade History (HTTP)
  await fetchUrl(
    `${TSETMC_BASE}/tsev2/data/InstTradeHistory.aspx`,
    { i: FOULAD_INSCODE, Top: '999999', A: '0' },
    'trade_history_http'
  );

  // Test 2: Trade History (HTTPS)
  await fetchUrl(
    `${TSETMC_BASE_HTTPS}/tsev2/data/InstTradeHistory.aspx`,
    { i: FOULAD_INSCODE, Top: '999999', A: '0' },
    'trade_history_https'
  );

  // Test 3: Trade History with Top=100
  await fetchUrl(
    `${TSETMC_BASE}/tsev2/data/InstTradeHistory.aspx`,
    { i: FOULAD_INSCODE, Top: '100', A: '0' },
    'trade_history_top100'
  );

  // Test 4: Instrument Info
  await fetchUrl(
    `${TSETMC_BASE}/tsev2/data/instinfo.aspx`,
    { i: FOULAD_INSCODE, c: '23' },
    'inst_info'
  );

  // Test 5: Client Types
  await fetchUrl(
    `${TSETMC_BASE}/tsev2/data/clienttype.aspx`,
    { i: FOULAD_INSCODE },
    'client_types'
  );

  // Test 6: Market Watch
  await fetchUrl(
    `${TSETMC_BASE}/tsev2/data/MarketWatchInit.aspx`,
    { h: '0', r: '0' },
    'market_watch'
  );

  // Test 7: Loader
  await fetchUrl(
    `${TSETMC_BASE}/Loader.aspx`,
    { ParTree: '111C1417' },
    'loader_symbols'
  );

  console.log(`\n${'='.repeat(70)}`);
  console.log('DEBUG COMPLETE');
  console.log('='.repeat(70));
  console.log('\nFiles saved:');
  console.log('  tsetmc_response_trade_history_http.txt  ← MOST IMPORTANT');
  console.log('  tsetmc_response_trade_history_https.txt');
  console.log('  tsetmc_response_trade_history_top100.txt');
  console.log('  tsetmc_response_inst_info.txt');
  console.log('  tsetmc_response_client_types.txt  ← ALSO IMPORTANT');
  console.log('  tsetmc_response_market_watch.txt');
  console.log('  tsetmc_response_loader_symbols.txt');

  console.log(`\n${'='.repeat(70)}`);
  console.log('WHAT TO SEND ME:');
  console.log('='.repeat(70));
  console.log('Open these 2 files and send me their contents:');
  console.log('  1. tsetmc_response_trade_history_http.txt');
  console.log('  2. tsetmc_response_client_types.txt');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
