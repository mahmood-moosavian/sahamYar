/**
 * TSETMC Connection Test (Node.js)
 *
 * Quick test to verify TSETMC is accessible.
 *
 * Run: node test_connection.js
 */

const axios = require('axios');

const TSETMC_BASE = 'http://www.tsetmc.com';
const FOULAD_INSCODE = '46348559193224090';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
};

async function testConnection() {
  console.log('='.repeat(60));
  console.log('TEST 1: Connection to TSETMC');
  console.log('='.repeat(60));

  try {
    console.log(`\nTrying: ${TSETMC_BASE}`);
    const response = await axios.get(TSETMC_BASE, {
      headers: HEADERS,
      timeout: 15000,
    });

    console.log(`  Status: ${response.status}`);
    console.log(`  Size: ${response.data.length} bytes`);

    if (response.status === 200) {
      console.log('  ✓ Connection OK!');
      return true;
    } else {
      console.log(`  ✗ HTTP ${response.status}`);
      return false;
    }
  } catch (error) {
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      console.log('  ✗ TIMEOUT (likely geo-blocked)');
      console.log('  → Run this script from a machine in Iran or via Iranian VPN');
    } else if (error.code === 'ECONNREFUSED') {
      console.log('  ✗ Connection refused');
    } else {
      console.log(`  ✗ Error: ${error.code || 'UNKNOWN'} - ${error.message}`);
    }
    return false;
  }
}

async function testSingleSymbol() {
  console.log(`\n${'='.repeat(60)}`);
  console.log('TEST 2: Fetch single symbol (فولاد)');
  console.log('='.repeat(60));

  console.log(`\nFetching trade history for فولاد (InsCode: ${FOULAD_INSCODE})...`);

  try {
    const response = await axios.get(`${TSETMC_BASE}/tsev2/data/InstTradeHistory.aspx`, {
      params: { i: FOULAD_INSCODE, Top: '100', A: '0' },
      headers: HEADERS,
      timeout: 30000,
    });

    const text = response.data;
    console.log(`  Status: ${response.status}`);
    console.log(`  Size: ${text.length} bytes`);

    if (text && text.length > 50) {
      console.log(`  First 200 chars: ${text.substring(0, 200)}`);

      // Count rows (semicolon-separated)
      const rows = text.split(';');
      console.log(`  Rows: ${rows.length}`);

      if (rows.length > 1) {
        console.log(`  ✓ Got data!`);
        return true;
      } else {
        console.log(`  ✗ No data rows`);
        return false;
      }
    } else {
      console.log(`  ✗ Response too short or empty`);
      return false;
    }
  } catch (error) {
    console.log(`  ✗ Error: ${error.code || 'UNKNOWN'} - ${error.message}`);
    return false;
  }
}

async function main() {
  console.log('TSETMC Crawler (Node.js) — Quick Test\n');

  // Check axios
  try {
    require.resolve('axios');
  } catch (e) {
    console.log('Error: axios not installed');
    console.log('Run: npm install axios');
    process.exit(1);
  }

  // Test 1
  const connOk = await testConnection();
  if (!connOk) {
    console.log('\n❌ Cannot connect to TSETMC from this environment.');
    process.exit(1);
  }

  // Test 2
  const symbolOk = await testSingleSymbol();
  if (!symbolOk) {
    console.log('\n❌ Could not fetch symbol data.');
    console.log('   Run: node debug_tsetmc.js');
    console.log('   Then send me the output files to fix the parser.');
    process.exit(1);
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log('✓ ALL TESTS PASSED — Crawler is working!');
  console.log('='.repeat(60));
  console.log('\nNext step:');
  console.log('  node crawler.js --mode test       # Crawl 10 symbols');
  console.log('  node crawler.js --mode medium     # Crawl 100 symbols (recommended)');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
