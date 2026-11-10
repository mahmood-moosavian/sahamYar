/**
 * TSETMC Crawler V2 — Uses the NEW CDN API (JSON)
 *
 * TSETMC migrated to a new API at cdn.tsetmc.com/api/
 * This crawler uses the new JSON endpoints.
 *
 * Usage:
 *   node crawler_v2.js --mode test     (10 symbols)
 *   node crawler_v2.js --mode medium   (100 symbols)
 *   node crawler_v2.js --mode full     (all ~3300 symbols)
 *
 * Data sources:
 *   - Symbols:  /api/ClosingPrice/GetMarketWatch
 *   - Candles:  /api/ClosingPrice/GetClosingPriceDailyList/{InsCode}/{Top}
 *   - Client Types: /api/ClientType/GetClientType/{InsCode}/1/0
 *
 * NOTE: The new API returns only TODAY's client types (no history).
 * For historical client types, you need to crawl daily and accumulate.
 */

const axios = require('axios');
const fs = require('fs');
const path = require('path');

// ============================================================
// Configuration
// ============================================================

const CDN_API = 'https://cdn.tsetmc.com/api';
const DATA_DIR = path.join(__dirname, '..', 'data', 'csv');
const STATE_FILE = path.join(__dirname, '..', 'data', 'crawl_state_v2.json');

fs.mkdirSync(DATA_DIR, { recursive: true });

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.6',
  'Referer': 'https://www.tsetmc.com/',
  'Origin': 'https://www.tsetmc.com',
};

const REQUEST_DELAY = 500;  // ms between requests (CDN API is faster)
const MAX_RETRIES = 3;
const RETRY_DELAY = 3000;

// ============================================================
// Gregorian to Jalali date conversion
// ============================================================

function gregorianToJalaliInt(gy, gm, gd) {
  // Algorithm by Kazimierz M. Borkowski
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let jy;
  if (gy > 1600) {
    jy = 979;
    gy -= 1600;
  } else {
    jy = 0;
    gy -= 621;
  }
  const gy2 = (gm > 2) ? (gy + 1) : gy;
  let days = (365 * gy) + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) - 80 + gd + g_d_m[gm - 1];
  jy += 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  const jm = (days < 186) ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
  const jd = 1 + ((days < 186) ? (days % 31) : ((days - 186) % 30));
  return jy * 10000 + jm * 100 + jd;
}

function dEvenToJalali(dEven) {
  // dEven is YYYYMMDD in Gregorian
  const str = String(dEven);
  if (str.length !== 8) return 0;
  const gy = parseInt(str.substring(0, 4), 10);
  const gm = parseInt(str.substring(4, 6), 10);
  const gd = parseInt(str.substring(6, 8), 10);
  return gregorianToJalaliInt(gy, gm, gd);
}

// ============================================================
// HTTP Client
// ============================================================

const httpClient = axios.create({
  timeout: 30000,
  headers: HEADERS,
});

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function makeRequest(url) {
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      await sleep(REQUEST_DELAY);
      const response = await httpClient.get(url);
      return response.data;
    } catch (error) {
      console.warn(`  ⚠ Attempt ${attempt} failed: ${error.code || error.message}`);
      if (attempt < MAX_RETRIES) {
        await sleep(RETRY_DELAY);
      }
    }
  }
  return null;
}

// ============================================================
// CSV Helpers
// ============================================================

function saveCsv(filename, rows) {
  if (!rows || rows.length === 0) return;
  const filepath = path.join(DATA_DIR, filename);
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(',')];

  for (const row of rows) {
    const values = headers.map(h => {
      const v = row[h];
      if (v === null || v === undefined) return '';
      const s = String(v);
      if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    });
    lines.push(values.join(','));
  }

  fs.writeFileSync(filepath, lines.join('\n'), 'utf8');
  return filepath;
}

function appendCsv(filename, rows) {
  if (!rows || rows.length === 0) return;
  const filepath = path.join(DATA_DIR, filename);
  const headers = Object.keys(rows[0]);
  const fileExists = fs.existsSync(filepath);

  const lines = [];
  if (!fileExists) {
    lines.push(headers.join(','));
  }

  for (const row of rows) {
    const values = headers.map(h => {
      const v = row[h];
      if (v === null || v === undefined) return '';
      const s = String(v);
      if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    });
    lines.push(values.join(','));
  }

  fs.appendFileSync(filepath, lines.join('\n') + '\n', 'utf8');
}

// ============================================================
// Crawl Functions
// ============================================================

async function crawlSymbols() {
  console.log('\n============================================================');
  console.log('STEP 1: Fetching symbols list from CDN API...');
  console.log('============================================================\n');

  const url = `${CDN_API}/ClosingPrice/GetMarketWatch?market=0&withBestLimits=false&hEven=0&RefID=0`;
  const data = await makeRequest(url);

  if (!data || !data.marketwatch) {
    console.error('✗ Failed to fetch symbols');
    return [];
  }

  const symbols = data.marketwatch.map(item => {
    let status = 'A';
    if (item.yMarNSC === 'AS' || item.yMarNSC === 'NO') {
      status = item.yMarNSC === 'AS' ? 'S' : 'A';
    }

    return {
      ins_code: String(item.insCode || ''),
      ticker: String(item.lva || ''),
      fullname: String(item.lvc || ''),
      sector_code: String(item.csv || item.cGrValCot || '0'),
      sector_name: '',
      flow: String(item.flow || '1'),
      status: status,
      eps: parseFloat(item.eps || 0),
      pe: parseFloat(item.pe || 0),
      listed_at: '',
      delisted_at: '',
      updated_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
    };
  }).filter(s => s.ins_code && s.ins_code !== '0');

  // NEW: Save fundamentals from MarketWatch (EPS and PE are available here!)
  if (symbols.length > 0) {
    const fundamentals = symbols.map(s => ({
      ins_code: s.ins_code,
      fiscal_period: 'current',
      eps: s.eps || 0,
      estimated_eps: s.eps || 0,  // Use EPS as estimate (TSETMC doesn't provide separate estimate)
      sector_pe: s.pe || 0,       // PE from TSETMC
      nav: 0,
      report_date: new Date().toISOString().substring(0, 10),
    })).filter(f => f.eps > 0 || f.sector_pe > 0);

    saveCsv('fundamentals.csv', fundamentals);
    console.log(`  ✓ Saved ${fundamentals.length} fundamental records (EPS, PE) to fundamentals.csv`);
  }

  if (symbols.length > 0) {
    // Show breakdown by flow type
    const flowCounts = {};
    symbols.forEach(s => {
      flowCounts[s.flow] = (flowCounts[s.flow] || 0) + 1;
    });
    console.log(`  Flow breakdown:`);
    Object.entries(flowCounts).forEach(([flow, count]) => {
      const flowName = { '1': 'بورس', '2': 'فرابورس', '3': 'بازار پایه/اختیار', '4': 'صندوق' }[flow] || `flow=${flow}`;
      console.log(`    ${flowName}: ${count}`);
    });

    // Sort: flow=1 (بورس) first, then flow=2 (فرابورس), then by ticker
    symbols.sort((a, b) => {
      const flowOrder = { '1': 0, '2': 1, '4': 2, '3': 3 };
      const fa = flowOrder[a.flow] ?? 9;
      const fb = flowOrder[b.flow] ?? 9;
      if (fa !== fb) return fa - fb;
      return a.ticker.localeCompare(b.ticker);
    });

    saveCsv('symbols.csv', symbols);
    console.log(`  ✓ Found ${symbols.length} symbols (sorted: بورس → فرابورس → others)`);
    console.log(`  ✓ Saved to data/csv/symbols.csv`);

    // Show sample (now showing بورس stocks first)
    console.log(`\n  Sample symbols (بورس first):`);
    symbols.slice(0, 5).forEach(s => {
      console.log(`    ${s.ticker} → ${s.ins_code} (flow=${s.flow}, status=${s.status})`);
    });
  }

  return symbols;
}

async function crawlCandles(insCode) {
  // Use Top=999999 to get all available history (Top=0 may return 0 rows)
  const url = `${CDN_API}/ClosingPrice/GetClosingPriceDailyList/${insCode}/999999`;
  const data = await makeRequest(url);

  if (!data || !data.closingPriceDaily) {
    return [];
  }

  const candles = data.closingPriceDaily.map(item => {
    const dateJalali = dEvenToJalali(item.dEven);
    const close = parseFloat(item.pClosing || 0);
    const yesterday = parseFloat(item.priceYesterday || close);

    return {
      ins_code: String(insCode),
      date_jalali: dateJalali,
      open: parseFloat(item.priceFirst || close),
      high: parseFloat(item.priceMax || close),
      low: parseFloat(item.priceMin || close),
      close: close,
      last_price: parseFloat(item.pDrCotVal || close),
      yesterday: yesterday,
      volume: parseInt(item.qTotTran5J || 0, 10),
      trade_count: parseInt(item.zTotTran || 0, 10),
      value: parseInt(item.qTotCap || 0, 10),
      max_allowed: close * 1.05,  // estimate (±5%)
      min_allowed: close * 0.95,
    };
  }).filter(c => c.date_jalali > 0 && c.close > 0);

  return candles;
}

async function crawlClientTypes(insCode) {
  const url = `${CDN_API}/ClientType/GetClientType/${insCode}/1/0`;
  const data = await makeRequest(url);

  if (!data || !data.clientType) {
    return [];
  }

  const ct = data.clientType;

  // The new API returns only today's data (no dEven field in response)
  // We use today's date
  const today = new Date();
  const dateJalali = gregorianToJalaliInt(
    today.getFullYear(),
    today.getMonth() + 1,
    today.getDate()
  );

  // Field mapping:
  // I = Individual (حقیقی/Real)
  // N = Non-individual (حقوقی/Legal)
  // buy_I_Volume = volume bought by real persons
  // buy_N_Volume = volume bought by legal entities
  return [{
    ins_code: String(insCode),
    date_jalali: dateJalali,
    buy_real_count: parseInt(ct.buy_CountI || 0, 10),
    sell_real_count: parseInt(ct.sell_CountI || 0, 10),
    buy_legal_count: parseInt(ct.buy_CountN || 0, 10),
    sell_legal_count: parseInt(ct.sell_CountN || 0, 10),
    buy_real_volume: parseInt(ct.buy_I_Volume || 0, 10),
    sell_real_volume: parseInt(ct.sell_I_Volume || 0, 10),
    buy_legal_volume: parseInt(ct.buy_N_Volume || 0, 10),
    sell_legal_volume: parseInt(ct.sell_N_Volume || 0, 10),
    // Values not available in new API - calculate from volume × price
    // We'll fill these after getting the closing price
    buy_real_value: 0,
    sell_real_value: 0,
    buy_legal_value: 0,
    sell_legal_value: 0,
  }];
}

// ============================================================
// State Management
// ============================================================

function saveState(crawledSet) {
  const state = {
    crawledSymbols: Array.from(crawledSet),
    lastRun: new Date().toISOString(),
  };
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
}

function loadState() {
  if (!fs.existsSync(STATE_FILE)) return new Set();
  try {
    const state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    return new Set(state.crawledSymbols || []);
  } catch (e) {
    return new Set();
  }
}

// ============================================================
// Market Index (TEDPIX) — Historical daily values
// ============================================================

async function crawlMarketIndex() {
  console.log('\n  Fetching market index (TEDPIX) history...');

  // TEDPIX InsCode — شاخص کل
  const TEDPIX_INSCODE = '32097828799138957';
  const url = `${CDN_API}/ClosingPrice/GetClosingPriceDailyList/${TEDPIX_INSCODE}/999999`;
  const data = await makeRequest(url);

  if (!data || !data.closingPriceDaily) {
    console.log('  ⚠ No market index data from TEDPIX InsCode, trying alternative...');

    // Try alternative: use MarketOverview for today + calculate historical from all symbols
    const overviewUrl = `${CDN_API}/MarketData/GetMarketOverview/0`;
    const overview = await makeRequest(overviewUrl);

    if (overview && overview.marketOverview) {
      const mo = overview.marketOverview;
      const today = new Date();
      const dateJalali = gregorianToJalaliInt(today.getFullYear(), today.getMonth() + 1, today.getDate());

      const indexData = [{
        date_jalali: dateJalali,
        index_value: mo.indexLastValue || 0,
        index_change_pct: mo.indexChange && mo.indexLastValue
          ? (mo.indexChange / (mo.indexLastValue - mo.indexChange) * 100) : 0,
      }];

      saveCsv('market_index.csv', indexData);
      console.log(`  ✓ Saved ${indexData.length} market index records (today only from MarketOverview)`);
      return indexData;
    }
    return [];
  }

  const indexData = data.closingPriceDaily.map(item => {
    const dateJalali = dEvenToJalali(item.dEven);
    const close = parseFloat(item.pClosing || 0);
    const yesterday = parseFloat(item.priceYesterday || close);
    const changePct = yesterday > 0 ? ((close - yesterday) / yesterday * 100) : 0;

    return {
      date_jalali: dateJalali,
      index_value: close,
      index_change_pct: changePct,
    };
  }).filter(d => d.date_jalali > 0 && d.index_value > 0);

  if (indexData.length > 0) {
    saveCsv('market_index.csv', indexData);
    console.log(`  ✓ Saved ${indexData.length} market index records (historical TEDPIX)`);
  }

  return indexData;
}

// ============================================================
// Main Crawl
// ============================================================

async function crawlAll(maxSymbols = null) {
  const startTime = Date.now();

  // Step 1: Get symbols
  let symbols = [];

  // Try loading from cache first
  const symbolsFile = path.join(DATA_DIR, 'symbols.csv');
  if (fs.existsSync(symbolsFile)) {
    console.log('  Loading symbols from cache...');
    const content = fs.readFileSync(symbolsFile, 'utf8');
    const lines = content.split('\n').filter(l => l.trim());
    const headers = lines[0].split(',');

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(',');
      if (cols.length >= 3 && cols[0] && /^\d+$/.test(cols[0])) {
        symbols.push({
          ins_code: cols[0],
          ticker: cols[1] || '',
          fullname: cols[2] || '',
          sector_code: cols[3] || '0',
          flow: cols[5] || '1',
          status: cols[6] || 'A',
        });
      }
    }
    console.log(`  ✓ Loaded ${symbols.length} symbols from cache`);
  }

  if (symbols.length === 0) {
    symbols = await crawlSymbols();
  }

  if (symbols.length === 0) {
    console.error('No symbols. Cannot continue.');
    return;
  }

  // Filter: only active AND only بورس (flow=1) or فرابورس (flow=2)
  // Skip options (flow=3) and other special instruments
  let activeSymbols = symbols.filter(s =>
    s.status === 'A' &&
    s.ins_code &&
    /^\d+$/.test(s.ins_code) &&
    (s.flow === '1' || s.flow === '2')  // Only بورس and فرابورس
  );

  console.log(`\n  Active بورس+فرابورس symbols: ${activeSymbols.length}`);
  console.log(`  (Filtered out options, funds, and other special instruments)`);

  if (maxSymbols) {
    activeSymbols = activeSymbols.slice(0, maxSymbols);
    console.log(`  Limited to: ${activeSymbols.length}`);
  }

  // Step 2: Crawl candles and client types
  console.log('\n============================================================');
  console.log('STEP 2: Crawling candles and client types...');
  console.log('============================================================\n');

  // SANITY CHECK: Test فولاد first to verify API works
  console.log('  Sanity check: Testing فولاد (46348559193224090)...');
  const testCandles = await crawlCandles('46348559193224090');
  if (testCandles.length > 0) {
    console.log(`  ✓ فولاد: ${testCandles.length} candles. API is working!\n`);
  } else {
    console.log(`  ✗ فولاد returned 0 candles. API may have issues.\n`);
  }

  // Clear old files
  const candlesFile = path.join(DATA_DIR, 'daily_candles.csv');
  const clientTypesFile = path.join(DATA_DIR, 'client_types.csv');
  if (fs.existsSync(candlesFile)) fs.unlinkSync(candlesFile);
  if (fs.existsSync(clientTypesFile)) fs.unlinkSync(clientTypesFile);

  const crawled = loadState();
  let totalCandles = 0;
  let totalClientTypes = 0;
  let failed = 0;
  let successCount = 0;

  for (let idx = 0; idx < activeSymbols.length; idx++) {
    const sym = activeSymbols[idx];
    const insCode = sym.ins_code;
    const ticker = sym.ticker || '???';

    if (crawled.has(insCode)) continue;

    const pct = ((idx + 1) / activeSymbols.length * 100).toFixed(1);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);

    // Crawl candles
    let candleCount = 0;
    try {
      const candles = await crawlCandles(insCode);
      candleCount = candles.length;
      if (candleCount > 0) {
        appendCsv('daily_candles.csv', candles);
        totalCandles += candleCount;
        successCount++;
      }
    } catch (e) {
      failed++;
    }

    // Show progress with candle count
    process.stdout.write(`[${idx + 1}/${activeSymbols.length}] ${pct}% | ${ticker.padEnd(15)} | ${candleCount} candles | ${elapsed}s\r`);

    // Crawl client types (today only)
    try {
      const ct = await crawlClientTypes(insCode);
      if (ct.length > 0) {
        appendCsv('client_types.csv', ct);
        totalClientTypes += ct.length;
      }
    } catch (e) {
      // Client types might fail for some symbols
    }

    crawled.add(insCode);

    // Save state every 20 symbols
    if ((idx + 1) % 20 === 0) {
      saveState(crawled);
    }
  }

  // Save final state
  saveState(crawled);

  // Step 3: Crawl market index (TEDPIX)
  await crawlMarketIndex();

  // Summary
  const duration = ((Date.now() - startTime) / 1000).toFixed(0);
  console.log('\n\n============================================================');
  console.log('CRAWL COMPLETE');
  console.log('============================================================');
  console.log(`  Duration:          ${duration}s`);
  console.log(`  Symbols crawled:   ${crawled.size}`);
  console.log(`  Failed:            ${failed}`);
  console.log(`  Total candles:     ${totalCandles.toLocaleString()}`);
  console.log(`  Client types:      ${totalClientTypes.toLocaleString()}`);
  console.log(`  Output:            ${DATA_DIR}`);
  console.log(`\n  Files:`);
  console.log(`    symbols.csv`);
  console.log(`    daily_candles.csv`);
  console.log(`    client_types.csv`);
  console.log(`\n  ⚠ Note: Client types are TODAY's data only.`);
  console.log(`    Run this crawler daily to build historical data.`);
  console.log(`\n  Next: Run backtest with Python:`);
  console.log(`    cd .. && python main.py`);
}

// ============================================================
// CLI
// ============================================================

function main() {
  const args = process.argv.slice(2);
  let mode = 'test';
  let maxSymbols = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--mode') {
      mode = args[++i];
    } else if (args[i] === '--symbols') {
      maxSymbols = parseInt(args[++i], 10);
    } else if (args[i] === '--help' || args[i] === '-h') {
      console.log(`
TSETMC Crawler V2 (Node.js) — Uses new CDN API

Usage:
  node crawler_v2.js [options]

Options:
  --mode <test|medium|full>   Crawl mode (default: test)
                              test=10, medium=100, full=all
  --symbols <N>               Override symbol count
  -h, --help                  Show help

Examples:
  node crawler_v2.js --mode test       # 10 symbols (~30 sec)
  node crawler_v2.js --mode medium     # 100 symbols (~2 min)
  node crawler_v2.js --mode full       # all ~3300 symbols (~30 min)
`);
      process.exit(0);
    }
  }

  if (maxSymbols === null) {
    if (mode === 'test') maxSymbols = 10;
    else if (mode === 'medium') maxSymbols = 100;
    else maxSymbols = null;
  }

  console.log('============================================================');
  console.log('TSETMC Crawler V2 — New CDN API');
  console.log('============================================================');
  console.log(`Mode: ${mode}`);
  console.log(`Symbols: ${maxSymbols || 'ALL'}`);
  console.log(`Output: ${DATA_DIR}\n`);

  crawlAll(maxSymbols).catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

main();
