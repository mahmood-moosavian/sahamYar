/**
 * TSETMC Parser Test (Node.js)
 *
 * Tests the parser logic with mock TSETMC responses.
 * Does NOT require actual TSETMC access.
 *
 * Run: node test_parser.js
 */

// ============================================================
// Mock TSETMC responses (based on actual API format)
// Format: rows separated by ';', columns by ','
// ============================================================

const MOCK_TRADE_HISTORY = 'DEven,PBrDr,PriceYesterday,PDrCotVal,PClosing,ZTotTran,QTotTran5J,QTotCap,PriceMin,PriceMax,PriceFirst,PSGelStaMax,PSGelStaMin;14051116,19620,19050,19620,19620,493,1852164,36339457680,19620,19620,19620,20002,18097;14051115,19200,18480,19200,19200,400,1500000,28800000,19200,19200,19200,19404,17556;14051114,18900,18000,18900,18900,350,1200000,22680000,18900,18900,18900,18900,17100;14051113,18500,17600,18500,18500,300,1100000,20350000,18500,18500,18500,18480,16732;14051112,18200,17300,18200,18200,280,1000000,18200000,18200,18200,18200,18165,16455';

const MOCK_CLIENT_TYPES = 'Date,NumberOfBuyCanReal,NumberOfSellCanReal,NumberOfBuyCanLegal,NumberOfSellCanLegal,VolumeBuyCanReal,VolumeSellCanReal,VolumeBuyCanLegal,VolumeSellCanLegal,ValueBuyCanReal,ValueSellCanReal,ValueBuyCanLegal,ValueSellCanLegal;14051116,27,438,2,1,1581981,780681,200000,1001300,31038467220,15316961220,3924000000,19645506000;14051115,30,410,3,2,1800000,650000,300000,1200000,34560000000,12480000000,5760000000,23040000000;14051114,25,380,1,3,1100000,520000,150000,900000,20790000000,9880000000,2850000000,17100000000';

const MOCK_MARKET_WATCH = 'InsCode,LVal18AFC,LVal30,FlowID,CSecVal;46348559193224090,فولاد,فولاد مباركه اصفهان,1,27;35425587644337450,فملی,ملي‌ صنايع‌ مس‌ ايران,1,27;3407806799514469,شاروم,پتروشيمي اروميه,1,44;48241092863917835,ولپارس,ليزينگ پارسيان,2,32';

// ============================================================
// Parser (same logic as in crawler.js)
// ============================================================

function parseTsetmcResponse(text) {
  if (!text || typeof text !== 'string') return [];

  const rows = text.trim().split(';');
  if (rows.length < 2) return [];

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

// ============================================================
// Tests
// ============================================================

function testParseTradeHistory() {
  console.log('='.repeat(60));
  console.log('TEST 1: Parse Trade History (candles)');
  console.log('='.repeat(60));

  const rows = parseTsetmcResponse(MOCK_TRADE_HISTORY);
  console.log(`\nParsed ${rows.length} candles`);

  if (rows.length === 0) {
    console.log('❌ No candles parsed');
    return false;
  }

  console.log('\nFirst candle:');
  for (const [k, v] of Object.entries(rows[0])) {
    console.log(`  ${k}: ${v}`);
  }

  // Verify required fields
  const required = ['DEven', 'PClosing', 'PDrCotVal', 'PriceYesterday', 'ZTotTran', 'QTotTran5J', 'QTotCap'];
  const missing = required.filter(f => !(f in rows[0]));
  if (missing.length > 0) {
    console.log(`\n❌ Missing fields: ${missing.join(', ')}`);
    return false;
  }

  console.log('\n✓ All required fields present');
  return true;
}

function testParseClientTypes() {
  console.log(`\n${'='.repeat(60)}`);
  console.log('TEST 2: Parse Client Types (حقوقی/حقیقی)');
  console.log('='.repeat(60));

  const rows = parseTsetmcResponse(MOCK_CLIENT_TYPES);
  console.log(`\nParsed ${rows.length} client type records`);

  if (rows.length === 0) {
    console.log('❌ No client types parsed');
    return false;
  }

  console.log('\nFirst record:');
  for (const [k, v] of Object.entries(rows[0])) {
    console.log(`  ${k}: ${v}`);
  }

  const required = ['Date', 'NumberOfBuyCanReal', 'NumberOfSellCanReal',
    'NumberOfBuyCanLegal', 'NumberOfSellCanLegal',
    'VolumeBuyCanReal', 'VolumeSellCanReal',
    'VolumeBuyCanLegal', 'VolumeSellCanLegal',
    'ValueBuyCanReal', 'ValueSellCanReal',
    'ValueBuyCanLegal', 'ValueSellCanLegal'];
  const missing = required.filter(f => !(f in rows[0]));
  if (missing.length > 0) {
    console.log(`\n❌ Missing fields: ${missing.join(', ')}`);
    return false;
  }

  console.log('\n✓ All required fields present');
  return true;
}

function testParseMarketWatch() {
  console.log(`\n${'='.repeat(60)}`);
  console.log('TEST 3: Parse Market Watch (symbols list)');
  console.log('='.repeat(60));

  const rows = parseTsetmcResponse(MOCK_MARKET_WATCH);
  console.log(`\nParsed ${rows.length} symbols`);

  if (rows.length === 0) {
    console.log('❌ No symbols parsed');
    return false;
  }

  console.log('\nFirst symbol:');
  for (const [k, v] of Object.entries(rows[0])) {
    console.log(`  ${k}: ${v}`);
  }

  // Check if known symbol exists
  const foulad = rows.find(r => r.LVal18AFC === 'فولاد');
  if (foulad) {
    console.log(`\n✓ Found فولاد with InsCode: ${foulad.InsCode}`);
  }

  const required = ['InsCode', 'LVal18AFC', 'LVal30', 'FlowID', 'CSecVal'];
  const missing = required.filter(f => !(f in rows[0]));
  if (missing.length > 0) {
    console.log(`\n❌ Missing fields: ${missing.join(', ')}`);
    return false;
  }

  console.log('\n✓ All required fields present');
  return true;
}

function main() {
  console.log('TSETMC Crawler (Node.js) — Parser Test\n');
  console.log('This test verifies the parser logic with mock TSETMC data.');
  console.log('No actual TSETMC access required.\n');

  const tests = [
    { name: 'Parse Trade History', fn: testParseTradeHistory },
    { name: 'Parse Client Types', fn: testParseClientTypes },
    { name: 'Parse Market Watch', fn: testParseMarketWatch },
  ];

  let passed = 0;
  for (const test of tests) {
    try {
      if (test.fn()) {
        passed++;
      }
    } catch (e) {
      console.log(`\n❌ ${test.name} failed with error: ${e.message}`);
    }
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log(`RESULT: ${passed}/${tests.length} tests passed`);
  console.log('='.repeat(60));

  if (passed === tests.length) {
    console.log('\n✓ All parser tests passed!');
    console.log('\nNext step: Run debug to see actual TSETMC format:');
    console.log('  node debug_tsetmc.js');
  } else {
    console.log('\n❌ Some tests failed. Check the parser logic.');
    process.exit(1);
  }
}

main();
