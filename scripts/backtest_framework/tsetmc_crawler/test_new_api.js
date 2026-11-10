/**
 * TSETMC API Test — Verify the NEW CDN API endpoints work
 *
 * TSETMC migrated to a new API at cdn.tsetmc.com/api/
 * This returns JSON data (not the old semicolon format).
 *
 * Run: node test_new_api.js
 */

const axios = require('axios');

const CDN_API = 'https://cdn.tsetmc.com/api';
const FOULAD = '46348559193224090';  // فولاد

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.6',
  'Referer': 'https://www.tsetmc.com/',
  'Origin': 'https://www.tsetmc.com',
};

async function testEndpoint(name, url) {
  console.log(`\n${'='.repeat(70)}`);
  console.log(`TEST: ${name}`);
  console.log(`URL: ${url}`);
  console.log('='.repeat(70));

  try {
    const res = await axios.get(url, {
      headers: HEADERS,
      timeout: 30000,
    });

    console.log(`Status: ${res.status}`);
    console.log(`Content-Type: ${res.headers['content-type'] || '?'}`);

    const data = res.data;

    // Check if it's JSON
    if (typeof data === 'object') {
      console.log(`✓ JSON response received!`);
      console.log(`Top-level keys: ${Object.keys(data).join(', ')}`);

      // Show structure
      for (const [key, value] of Object.entries(data)) {
        if (Array.isArray(value)) {
          console.log(`  ${key}: Array[${value.length}]`);
          if (value.length > 0) {
            console.log(`    First item keys: ${Object.keys(value[0]).join(', ')}`);
            console.log(`    First item: ${JSON.stringify(value[0]).substring(0, 300)}`);
          }
        } else if (typeof value === 'object' && value !== null) {
          console.log(`  ${key}: Object`);
          console.log(`    Keys: ${Object.keys(value).join(', ')}`);
          console.log(`    Value: ${JSON.stringify(value).substring(0, 300)}`);
        } else {
          console.log(`  ${key}: ${value}`);
        }
      }
      return data;
    } else {
      // String response
      const text = String(data);
      console.log(`Size: ${text.length} chars`);
      console.log(`Type: ${text.substring(0, 50)}`);
      console.log(`First 200 chars: ${text.substring(0, 200)}`);
      return null;
    }
  } catch (err) {
    console.log(`ERROR: ${err.code || ''} ${err.message}`);
    if (err.response) {
      console.log(`Response status: ${err.response.status}`);
      console.log(`Response data: ${JSON.stringify(err.response.data).substring(0, 300)}`);
    }
    return null;
  }
}

async function main() {
  console.log('='.repeat(70));
  console.log('TSETMC NEW CDN API Test');
  console.log('='.repeat(70));
  console.log(`Base URL: ${CDN_API}`);
  console.log(`Test symbol: فولاد (${FOULAD})\n`);

  // Test 1: Market Watch (all symbols)
  await testEndpoint(
    'Market Watch (all symbols)',
    `${CDN_API}/ClosingPrice/GetMarketWatch?market=0&withBestLimits=false&hEven=0&RefID=0`
  );

  // Test 2: Single quote (live price for فولاد)
  await testEndpoint(
    'Single Quote (فولاد live)',
    `${CDN_API}/ClosingPrice/GetClosingPriceInfo/${FOULAD}`
  );

  // Test 3: Daily history (candles for فولاد)
  await testEndpoint(
    'Daily History (فولاد candles, Top=100)',
    `${CDN_API}/ClosingPrice/GetClosingPriceDailyList/${FOULAD}/100`
  );

  // Test 4: Client Types (حقوقی/حقیقی for فولاد)
  await testEndpoint(
    'Client Types (فولاد حقوقی/حقیقی)',
    `${CDN_API}/ClientType/GetClientType/${FOULAD}/1/0`
  );

  // Test 5: Search
  await testEndpoint(
    'Search (فولاد)',
    `${CDN_API}/Instrument/GetInstrumentSearch/فولاد`
  );

  // Test 6: Market Overview
  await testEndpoint(
    'Market Overview (all markets)',
    `${CDN_API}/MarketData/GetMarketOverview/0`
  );

  console.log(`\n${'='.repeat(70)}`);
  console.log('TEST COMPLETE');
  console.log('='.repeat(70));
  console.log('\nCopy the output above and send it to me.');
  console.log('I will then update the crawler to use these endpoints.');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
