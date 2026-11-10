/**
 * SIMPLE TSETMC Debug — Shows responses directly in terminal
 *
 * Run: node debug_simple.js
 *
 * Just copy-paste the terminal output to me.
 */

const axios = require('axios');

const TSETMC = 'http://www.tsetmc.com';
const FOULAD = '46348559193224090';  // فولاد

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': '*/*',
  'Accept-Language': 'fa-IR,fa;q=0.9',
  'Referer': 'http://www.tsetmc.com/',
};

async function test(name, url, params) {
  console.log('\n' + '='.repeat(70));
  console.log(`TEST: ${name}`);
  console.log(`URL: ${url}`);
  console.log(`Params: ${JSON.stringify(params)}`);
  console.log('='.repeat(70));

  try {
    const res = await axios.get(url, {
      params,
      headers: HEADERS,
      timeout: 30000,
    });

    const text = typeof res.data === 'string' ? res.data : JSON.stringify(res.data);

    console.log(`\nStatus: ${res.status}`);
    console.log(`Size: ${text.length} chars`);
    console.log(`Content-Type: ${res.headers['content-type'] || '?'}`);

    console.log(`\n--- FIRST 500 CHARS ---`);
    console.log(text.substring(0, 500));
    console.log(`--- END ---\n`);

    return text;
  } catch (err) {
    console.log(`\nERROR: ${err.code || ''} ${err.message}`);
    return null;
  }
}

async function main() {
  console.log('TSETMC Simple Debug');
  console.log('Copy the output below and send it to me.\n');

  // Test 1: MarketWatch
  await test(
    'MarketWatch (symbols list)',
    `${TSETMC}/tsev2/data/MarketWatchInit.aspx`,
    { h: '0', r: '0' }
  );

  // Test 2: Trade History for فولاد
  await test(
    'Trade History (فولاد daily candles)',
    `${TSETMC}/tsev2/data/InstTradeHistory.aspx`,
    { i: FOULAD, Top: '100', A: '0' }
  );

  // Test 3: Client Types for فولاد
  await test(
    'Client Types (فولاد حقوقی/حقیقی)',
    `${TSETMC}/tsev2/data/clienttype.aspx`,
    { i: FOULAD }
  );

  // Test 4: Instrument Info
  await test(
    'Instrument Info (فولاد live)',
    `${TSETMC}/tsev2/data/instinfo.aspx`,
    { i: FOULAD, c: '23' }
  );

  console.log('\n' + '='.repeat(70));
  console.log('DONE — Please copy the output above and send it to me');
  console.log('='.repeat(70));
}

main().catch(console.error);
