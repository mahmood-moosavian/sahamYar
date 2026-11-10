/**
 * TSETMC Crawler — Node.js version
 *
 * Fetches real historical data from Tehran Stock Exchange (TSETMC)
 * and saves as CSV files compatible with the backtest framework.
 *
 * Usage:
 *   node crawler.js --mode test     (10 symbols, ~2 min)
 *   node crawler.js --mode medium   (100 symbols, ~40 min)
 *   node crawler.js --mode full     (all ~5000 symbols, 6-12 hours)
 *   node crawler.js --mode medium --resume   (resume interrupted)
 *
 * Requirements:
 *   npm install
 *   (or: npm install axios cheerio)
 *
 * NOTE: TSETMC blocks non-Iranian IPs. Run from a machine in Iran
 * or via Iranian VPN.
 */

const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');

// ============================================================
// Configuration
// ============================================================

const TSETMC_BASE = 'http://www.tsetmc.com';
const TSETMC_BASE_HTTPS = 'https://www.tsetmc.com';

const URLS = {
  symbolsList: `${TSETMC_BASE}/Loader.aspx?ParTree=111C1417`,
  tradeHistory: `${TSETMC_BASE}/tsev2/data/InstTradeHistory.aspx`,
  instInfo: `${TSETMC_BASE}/tsev2/data/instinfo.aspx`,
  clientTypes: `${TSETMC_BASE}/tsev2/data/clienttype.aspx`,
  marketWatch: `${TSETMC_BASE}/tsev2/data/MarketWatchInit.aspx`,
  marketState: `${TSETMC_BASE}/tsev2/data/MarketState.aspx`,
};

const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
];

const REQUEST_DELAY_MIN = 1000;  // ms
const REQUEST_DELAY_MAX = 2000;  // ms
const MAX_RETRIES = 3;
const RETRY_DELAY = 5000;  // ms

// TEDPIX InsCode (شاخص کل)
const TEDPIX_INSCODE = '32097828799138957';

// Paths
const SCRIPT_DIR = __dirname;
const DATA_DIR = path.join(SCRIPT_DIR, '..', 'data', 'csv');
const STATE_FILE = path.join(SCRIPT_DIR, '..', 'data', 'crawl_state.json');
const LOG_DIR = path.join(SCRIPT_DIR, '..', 'data', 'logs');

// Ensure directories exist
fs.mkdirSync(DATA_DIR, { recursive: true });
fs.mkdirSync(LOG_DIR, { recursive: true });

// ============================================================
// HTTP Client with retry and rate limiting
// ============================================================

const httpClient = axios.create({
  timeout: 30000,
  maxRedirects: 5,
  headers: {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.6',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
  },
});

let stats = {
  symbolsTotal: 0,
  symbolsCrawled: 0,
  symbolsFailed: 0,
  candlesTotal: 0,
  clientTypesTotal: 0,
  requestsMade: 0,
  requestsFailed: 0,
  startTime: new Date().toISOString(),
};

let crawledSymbols = new Set();
let failedSymbols = new Set();

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function getRandomDelay() {
  return REQUEST_DELAY_MIN + Math.random() * (REQUEST_DELAY_MAX - REQUEST_DELAY_MIN);
}

function getRandomUserAgent() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

async function makeRequest(url, params = {}) {
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      // Random delay
      await sleep(getRandomDelay());

      const response = await httpClient.get(url, {
        params,
        headers: { 'User-Agent': getRandomUserAgent() },
      });

      stats.requestsMade++;

      if (response.status === 200) {
        return response.data;
      } else {
        console.warn(`  HTTP ${response.status} (attempt ${attempt})`);
        await sleep(RETRY_DELAY * attempt);
      }
    } catch (error) {
      const code = error.code || 'UNKNOWN';
      const msg = error.message || String(error);
      console.warn(`  Error ${code} (attempt ${attempt}): ${msg.substring(0, 100)}`);
      await sleep(RETRY_DELAY);
    }
  }

  stats.requestsFailed++;
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
      // Escape quotes and wrap in quotes if contains comma or quote
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

/**
 * Parse TSETMC semicolon-comma format
 * Format: "header1,header2;row1col1,row1col2;row2col1,row2col2"
 */
function parseTsetmcResponse(text) {
  if (!text || typeof text !== 'string') return [];

  // Split by semicolon (rows)
  const rows = text.trim().split(';');
  if (rows.length < 2) return [];

  // First row is header
  const headers = rows[0].split(',');
  const data = [];

  for (let i = 1; i < rows.length; i++) {
    const cols = rows[i].split(',');
    if (cols.length < headers.length) continue;

    const row = {};
    for (let j = 0; j < headers.length; j++) {
      row[headers[j].trim()] = cols[j] ? cols[j].trim() : '';
    }
    data.push(row);
  }

  return data;
}

async function crawlSymbols() {
  console.log('\n============================================================');
  console.log('STEP 1: Crawling symbols list...');
  console.log('============================================================\n');

  // Try MarketWatch endpoint (more reliable than Loader.aspx)
  const response = await makeRequest(URLS.marketWatch, { h: '0', r: '0' });

  if (!response) {
    console.error('Failed to fetch symbols list');
    return [];
  }

  // Save raw response for debugging
  fs.writeFileSync(
    path.join(DATA_DIR, '_raw_marketwatch.txt'),
    response,
    'utf8'
  );

  const symbols = [];

  // MarketWatch format: semicolon-separated rows, comma-separated columns
  // First line might be header or data
  const lines = response.trim().split(';');

  for (let i = 0; i < lines.length; i++) {
    const cols = lines[i].split(',');
    if (cols.length < 5) continue;

    const insCode = cols[0] ? cols[0].trim() : '';
    const ticker = cols[1] ? cols[1].trim() : '';
    const fullname = cols[2] ? cols[2].trim() : '';

    // Skip header row
    if (insCode === 'InsCode' || !insCode || !insCode.match(/^\d+$/)) continue;

    symbols.push({
      ins_code: insCode,
      ticker: ticker,
      fullname: fullname,
      sector_code: cols[4] ? cols[4].trim() : '0',
      sector_name: '',
      flow: cols[3] ? cols[3].trim() : '1',
      status: 'A',
      listed_at: '',
      delisted_at: '',
      updated_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
    });
  }

  if (symbols.length === 0) {
    // Fallback: try Loader.aspx
    console.log('  MarketWatch returned no data, trying Loader.aspx...');
    const html = await makeRequest(URLS.symbolsList);
    if (html) {
      // Save raw for debugging
      fs.writeFileSync(
        path.join(DATA_DIR, '_raw_loader.txt'),
        html,
        'utf8'
      );
      // TODO: parse Loader.aspx HTML
    }
  }

  if (symbols.length > 0) {
    saveCsv('symbols.csv', symbols);
    stats.symbolsTotal = symbols.length;
    console.log(`  ✓ Found ${symbols.length} symbols`);
    console.log(`  ✓ Saved to data/csv/symbols.csv`);
  }

  return symbols;
}

async function crawlCandles(insCode) {
  const response = await makeRequest(URLS.tradeHistory, {
    i: insCode,
    Top: '999999',
    A: '0',
  });

  if (!response) return [];

  // Parse TSETMC format
  const rows = parseTsetmcResponse(response);
  if (rows.length === 0) return [];

  const candles = [];

  for (const row of rows) {
    try {
      const dateJalali = parseInt(row.DEven || '0', 10);
      if (!dateJalali || isNaN(dateJalali)) continue;

      const close = parseFloat(row.PClosing || '0');
      if (!close) continue;

      candles.push({
        ins_code: insCode,
        date_jalali: dateJalali,
        open: parseFloat(row.PriceFirst || close),
        high: parseFloat(row.PriceMax || close),
        low: parseFloat(row.PriceMin || close),
        close: close,
        last_price: parseFloat(row.PDrCotVal || close),
        yesterday: parseFloat(row.PriceYesterday || close),
        volume: parseInt(parseFloat(row.QTotTran5J || '0'), 10),
        trade_count: parseInt(parseFloat(row.ZTotTran || '0'), 10),
        value: parseInt(parseFloat(row.QTotCap || '0'), 10),
        max_allowed: parseFloat(row.PSGelStaMax || close * 1.05),
        min_allowed: parseFloat(row.PSGelStaMin || close * 0.95),
      });
    } catch (e) {
      // Skip invalid rows
    }
  }

  return candles;
}

async function crawlClientTypes(insCode) {
  const response = await makeRequest(URLS.clientTypes, { i: insCode });

  if (!response) return [];

  const rows = parseTsetmcResponse(response);
  if (rows.length === 0) return [];

  const clientTypes = [];

  for (const row of rows) {
    try {
      // Date field might be named differently
      const dateStr = row.Date || row[Object.keys(row)[0]] || '0';
      const dateJalali = parseInt(dateStr, 10);
      if (!dateJalali || isNaN(dateJalali)) continue;

      // Get field values with fallbacks
      const keys = Object.keys(row);
      const get = (idx) => parseFloat(row[keys[idx]] || '0') || 0;

      clientTypes.push({
        ins_code: insCode,
        date_jalali: dateJalali,
        buy_real_count: parseInt(row.NumberOfBuyCanReal || get(1), 10),
        sell_real_count: parseInt(row.NumberOfSellCanReal || get(2), 10),
        buy_legal_count: parseInt(row.NumberOfBuyCanLegal || get(3), 10),
        sell_legal_count: parseInt(row.NumberOfSellCanLegal || get(4), 10),
        buy_real_volume: parseInt(row.VolumeBuyCanReal || get(5), 10),
        sell_real_volume: parseInt(row.VolumeSellCanReal || get(6), 10),
        buy_legal_volume: parseInt(row.VolumeBuyCanLegal || get(7), 10),
        sell_legal_volume: parseInt(row.VolumeSellCanLegal || get(8), 10),
        buy_real_value: parseInt(row.ValueBuyCanReal || get(9), 10),
        sell_real_value: parseInt(row.ValueSellCanReal || get(10), 10),
        buy_legal_value: parseInt(row.ValueBuyCanLegal || get(11), 10),
        sell_legal_value: parseInt(row.ValueSellCanLegal || get(12), 10),
      });
    } catch (e) {
      // Skip invalid rows
    }
  }

  return clientTypes;
}

async function crawlMarketIndex() {
  console.log('\n  Crawling market index (TEDPIX)...');

  const response = await makeRequest(URLS.tradeHistory, {
    i: TEDPIX_INSCODE,
    Top: '999999',
    A: '0',
  });

  if (!response) return [];

  const rows = parseTsetmcResponse(response);
  if (rows.length === 0) return [];

  const indexData = [];

  for (const row of rows) {
    try {
      const dateJalali = parseInt(row.DEven || '0', 10);
      if (!dateJalali) continue;

      const close = parseFloat(row.PClosing || '0');
      const yesterday = parseFloat(row.PriceYesterday || close);
      const changePct = yesterday > 0 ? ((close - yesterday) / yesterday * 100) : 0;

      indexData.push({
        date_jalali: dateJalali,
        index_value: close,
        index_change_pct: changePct,
      });
    } catch (e) {
      // Skip
    }
  }

  if (indexData.length > 0) {
    saveCsv('market_index.csv', indexData);
    console.log(`  ✓ Saved ${indexData.length} market index records`);
  }

  return indexData;
}

// ============================================================
// State Management (for resume)
// ============================================================

function saveState() {
  const state = {
    crawledSymbols: Array.from(crawledSymbols),
    failedSymbols: Array.from(failedSymbols),
    stats,
  };
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
}

function loadState() {
  if (!fs.existsSync(STATE_FILE)) return false;

  try {
    const state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    crawledSymbols = new Set(state.crawledSymbols || []);
    failedSymbols = new Set(state.failedSymbols || []);
    stats = { ...stats, ...state.stats };
    console.log(`  ✓ Resumed: ${crawledSymbols.size} symbols already crawled`);
    return true;
  } catch (e) {
    return false;
  }
}

// ============================================================
// Main Crawl Loop
// ============================================================

async function crawlAll(maxSymbols = null) {
  const startTime = Date.now();

  // Step 1: Get symbols list
  let symbols = [];

  // Check if symbols.csv already exists (resume mode)
  const symbolsFile = path.join(DATA_DIR, 'symbols.csv');
  if (fs.existsSync(symbolsFile)) {
    console.log('  Loading symbols from existing CSV...');
    const content = fs.readFileSync(symbolsFile, 'utf8');
    const lines = content.split('\n').filter(l => l.trim());
    const headers = lines[0].split(',');

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(',');
      if (cols.length >= 3) {
        symbols.push({
          ins_code: cols[0],
          ticker: cols[1],
          fullname: cols[2],
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
    console.error('No symbols found. Cannot continue.');
    return;
  }

  // Filter to active symbols with valid InsCode
  let activeSymbols = symbols.filter(s =>
    s.status === 'A' && s.ins_code && /^\d+$/.test(s.ins_code)
  );

  console.log(`\n  Active symbols: ${activeSymbols.length}`);

  if (maxSymbols) {
    activeSymbols = activeSymbols.slice(0, maxSymbols);
    console.log(`  Limited to: ${activeSymbols.length} symbols`);
  }

  // Step 2: Crawl candles and client types for each symbol
  console.log('\n============================================================');
  console.log('STEP 2: Crawling candles and client types per symbol...');
  console.log('============================================================\n');

  // Clear existing candle/client CSV files (we'll rebuild them)
  const candlesFile = path.join(DATA_DIR, 'daily_candles.csv');
  const clientTypesFile = path.join(DATA_DIR, 'client_types.csv');
  if (fs.existsSync(candlesFile)) fs.unlinkSync(candlesFile);
  if (fs.existsSync(clientTypesFile)) fs.unlinkSync(clientTypesFile);

  for (let idx = 0; idx < activeSymbols.length; idx++) {
    const sym = activeSymbols[idx];
    const insCode = sym.ins_code;
    const ticker = sym.ticker || '???';

    if (crawledSymbols.has(insCode)) continue;

    const progressPct = ((idx + 1) / activeSymbols.length * 100).toFixed(1);
    const elapsedMin = ((Date.now() - startTime) / 60000).toFixed(1);
    const etaMin = idx > 0
      ? (((Date.now() - startTime) / (idx + 1)) * (activeSymbols.length - idx - 1) / 60000).toFixed(1)
      : '?';

    console.log(`[${idx + 1}/${activeSymbols.length}] ${progressPct}% | ${ticker} (${insCode}) | Elapsed: ${elapsedMin}m | ETA: ${etaMin}m`);

    // Crawl candles
    try {
      const candles = await crawlCandles(insCode);
      if (candles.length > 0) {
        appendCsv('daily_candles.csv', candles);
        stats.candlesTotal += candles.length;
      } else {
        console.warn(`  ⚠ No candles for ${ticker}`);
      }
    } catch (e) {
      console.error(`  ✗ Error crawling candles for ${ticker}: ${e.message}`);
      failedSymbols.add(insCode);
    }

    // Crawl client types
    try {
      const clientTypes = await crawlClientTypes(insCode);
      if (clientTypes.length > 0) {
        appendCsv('client_types.csv', clientTypes);
        stats.clientTypesTotal += clientTypes.length;
      }
    } catch (e) {
      console.error(`  ✗ Error crawling client types for ${ticker}: ${e.message}`);
    }

    crawledSymbols.add(insCode);
    stats.symbolsCrawled++;

    // Save state every 10 symbols
    if ((idx + 1) % 10 === 0) {
      saveState();
    }
  }

  // Step 3: Crawl market index
  await crawlMarketIndex();

  // Save final state
  stats.endTime = new Date().toISOString();
  stats.durationMinutes = (Date.now() - startTime) / 60000;
  saveState();

  // Print summary
  printSummary();
}

function printSummary() {
  console.log('\n============================================================');
  console.log('CRAWL SUMMARY');
  console.log('============================================================');
  console.log(`  Duration:           ${stats.durationMinutes.toFixed(1)} minutes`);
  console.log(`  Symbols total:      ${stats.symbolsTotal}`);
  console.log(`  Symbols crawled:    ${stats.symbolsCrawled}`);
  console.log(`  Symbols failed:     ${failedSymbols.size}`);
  console.log(`  Candles fetched:    ${stats.candlesTotal.toLocaleString()}`);
  console.log(`  Client types:       ${stats.clientTypesTotal.toLocaleString()}`);
  console.log(`  HTTP requests:      ${stats.requestsMade.toLocaleString()}`);
  console.log(`  Failed requests:    ${stats.requestsFailed}`);
  console.log(`\n  Output directory:   ${DATA_DIR}`);
  console.log(`\n  Next step: Run backtest (Python)`);
  console.log(`    python main.py  # (without --generate-sample-data)`);
}

// ============================================================
// CLI
// ============================================================

function main() {
  const args = process.argv.slice(2);

  let mode = 'test';
  let maxSymbols = null;
  let resume = false;
  let marketIndexOnly = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--mode') {
      mode = args[++i];
    } else if (arg === '--symbols') {
      maxSymbols = parseInt(args[++i], 10);
    } else if (arg === '--resume') {
      resume = true;
    } else if (arg === '--market-index-only') {
      marketIndexOnly = true;
    } else if (arg === '--help' || arg === '-h') {
      console.log(`
TSETMC Crawler (Node.js)

Usage:
  node crawler.js [options]

Options:
  --mode <test|medium|full>   Crawl mode (default: test)
                              test=10 symbols, medium=100, full=all
  --symbols <N>               Override number of symbols
  --resume                    Resume from previous crawl
  --market-index-only         Only fetch TEDPIX market index
  -h, --help                  Show this help

Examples:
  node crawler.js --mode test       # Quick test (10 symbols, ~2 min)
  node crawler.js --mode medium     # Crawl 100 symbols (~40 min)
  node crawler.js --mode full       # Crawl all ~5000 symbols (6-12 hours)
  node crawler.js --mode medium --resume   # Resume interrupted crawl
`);
      process.exit(0);
    }
  }

  // Determine symbol count
  if (maxSymbols === null) {
    if (mode === 'test') maxSymbols = 10;
    else if (mode === 'medium') maxSymbols = 100;
    else maxSymbols = null; // full = all
  }

  console.log('============================================================');
  console.log('TSETMC Crawler (Node.js) — Real Data for Backtest Framework');
  console.log('============================================================');
  console.log(`\nMode: ${mode}`);
  console.log(`Symbols: ${maxSymbols || 'ALL'}`);
  console.log(`Resume: ${resume}`);
  console.log(`Output: ${DATA_DIR}\n`);

  if (resume) {
    loadState();
  }

  if (marketIndexOnly) {
    crawlMarketIndex().then(() => {
      console.log('\n✓ Done!');
    }).catch(err => {
      console.error('Error:', err);
      process.exit(1);
    });
  } else {
    crawlAll(maxSymbols).then(() => {
      console.log('\n✓ Done!');
    }).catch(err => {
      console.error('Error:', err);
      process.exit(1);
    });
  }
}

main();
