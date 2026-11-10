/**
 * TSETMC API Discovery — Find the new API endpoints
 *
 * TSETMC has migrated to a SPA (Single Page Application).
 * The old /tsev2/data/*.aspx endpoints now return HTML instead of raw data.
 *
 * This script tries multiple approaches to find the working API:
 * 1. Get session cookies from main page
 * 2. Try old endpoints with cookies + proper headers
 * 3. Try common new API patterns (/api/...)
 * 4. Try CDN subdomain
 * 5. Extract API URLs from JavaScript bundles
 */

const axios = require('axios');
const https = require('https');

const TSETMC_HTTP = 'http://www.tsetmc.com';
const TSETMC_HTTPS = 'https://www.tsetmc.com';
const FOULAD = '46348559193224090';

const HEADERS_BROWSER = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
  'Accept-Language': 'fa-IR,fa;q=0.9,en-US;q=0.6,en;q=0.4',
  'Accept-Encoding': 'gzip, deflate, sdch',
  'Connection': 'keep-alive',
  'Upgrade-Insecure-Requests': '1',
};

const HEADERS_API = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/plain, */*; q=0.01',
  'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.6',
  'X-Requested-With': 'XMLHttpRequest',
  'Connection': 'keep-alive',
};

// Agent to handle HTTP -> HTTPS redirects
const agent = new https.Agent({
  rejectUnauthorized: false,
});

async function tryEndpoint(label, url, params, headers, useSession = null) {
  console.log(`\n--- ${label} ---`);
  console.log(`URL: ${url}`);
  console.log(`Params: ${JSON.stringify(params)}`);

  try {
    const config = {
      params,
      headers: { ...headers, ...(useSession ? { Cookie: useSession } : {}) },
      timeout: 15000,
      maxRedirects: 5,
      httpsAgent: agent,
    };

    const res = await axios.get(url, config);
    const text = typeof res.data === 'string' ? res.data : JSON.stringify(res.data);

    console.log(`Status: ${res.status}, Size: ${text.length}`);

    // Check if response is HTML (SPA shell) or actual data
    const isHtml = text.trim().startsWith('<!doctype') || text.trim().startsWith('<html');
    const isJson = text.trim().startsWith('{') || text.trim().startsWith('[');
    const isData = !isHtml && !isJson && text.includes(';') && text.includes(',');

    if (isHtml) {
      console.log(`Type: HTML (SPA shell - not useful)`);
    } else if (isJson) {
      console.log(`Type: JSON ✓`);
      console.log(`First 300 chars: ${text.substring(0, 300)}`);
    } else if (isData) {
      console.log(`Type: TSETMC Data format ✓✓✓`);
      console.log(`First 300 chars: ${text.substring(0, 300)}`);
    } else {
      console.log(`Type: Unknown`);
      console.log(`First 300 chars: ${text.substring(0, 300)}`);
    }

    // Capture cookies from response
    const cookies = res.headers['set-cookie'];
    if (cookies) {
      console.log(`Cookies received: ${cookies.length}`);
    }

    return { text, isHtml, isJson, isData, cookies };
  } catch (err) {
    console.log(`ERROR: ${err.code || ''} ${err.message}`);
    return null;
  }
}

async function main() {
  console.log('='.repeat(70));
  console.log('TSETMC API Discovery');
  console.log('='.repeat(70));
  console.log('\nThis script tries multiple approaches to find working endpoints.\n');

  // ============================================================
  // APPROACH 1: Get session cookies from main page first
  // ============================================================
  console.log('\n' + '='.repeat(70));
  console.log('APPROACH 1: Get session cookies from main page');
  console.log('='.repeat(70));

  let sessionCookies = '';
  try {
    const res = await axios.get(`${TSETMC_HTTPS}/`, {
      headers: HEADERS_BROWSER,
      timeout: 15000,
      maxRedirects: 5,
      httpsAgent: agent,
    });
    const cookies = res.headers['set-cookie'];
    if (cookies) {
      sessionCookies = cookies.map(c => c.split(';')[0]).join('; ');
      console.log(`✓ Got cookies: ${sessionCookies.substring(0, 100)}...`);
    } else {
      console.log('No cookies received');
    }
    console.log(`Main page size: ${res.data.length} chars`);
  } catch (err) {
    console.log(`Error getting main page: ${err.message}`);
  }

  // ============================================================
  // APPROACH 2: Try old endpoints with session cookies
  // ============================================================
  console.log('\n' + '='.repeat(70));
  console.log('APPROACH 2: Try old endpoints WITH cookies + AJAX headers');
  console.log('='.repeat(70));

  await tryEndpoint(
    'MarketWatch with cookies',
    `${TSETMC_HTTPS}/tsev2/data/MarketWatchInit.aspx`,
    { h: '0', r: '0' },
    { ...HEADERS_API, Referer: `${TSETMC_HTTPS}/` },
    sessionCookies
  );

  await tryEndpoint(
    'Trade History with cookies',
    `${TSETMC_HTTPS}/tsev2/data/InstTradeHistory.aspx`,
    { i: FOULAD, Top: '100', A: '0' },
    { ...HEADERS_API, Referer: `${TSETMC_HTTPS}/` },
    sessionCookies
  );

  await tryEndpoint(
    'Client Types with cookies',
    `${TSETMC_HTTPS}/tsev2/data/clienttype.aspx`,
    { i: FOULAD },
    { ...HEADERS_API, Referer: `${TSETMC_HTTPS}/` },
    sessionCookies
  );

  // ============================================================
  // APPROACH 3: Try common new API patterns
  // ============================================================
  console.log('\n' + '='.repeat(70));
  console.log('APPROACH 3: Try new API patterns (/api/...)');
  console.log('='.repeat(70));

  const apiPatterns = [
    { label: 'API MarketWatch', url: `${TSETMC_HTTPS}/api/marketwatch`, params: {} },
    { label: 'API InstInfo', url: `${TSETMC_HTTPS}/api/instinfo/${FOULAD}`, params: {} },
    { label: 'API Trade History', url: `${TSETMC_HTTPS}/api/tradehistory/${FOULAD}`, params: {} },
    { label: 'API Client Type', url: `${TSETMC_HTTPS}/api/clienttype/${FOULAD}`, params: {} },
    { label: 'API v2 MarketWatch', url: `${TSETMC_HTTPS}/api/v2/marketwatch`, params: {} },
    { label: 'API v2 InstInfo', url: `${TSETMC_HTTPS}/api/v2/instinfo/${FOULAD}`, params: {} },
  ];

  for (const p of apiPatterns) {
    await tryEndpoint(p.label, p.url, p.params, HEADERS_API, sessionCookies);
  }

  // ============================================================
  // APPROACH 4: Try CDN subdomain
  // ============================================================
  console.log('\n' + '='.repeat(70));
  console.log('APPROACH 4: Try CDN subdomain (cdn.tsetmc.com)');
  console.log('='.repeat(70));

  const cdnPatterns = [
    { label: 'CDN MarketWatch', url: 'http://cdn.tsetmc.com/tsev2/data/MarketWatchInit.aspx', params: { h: '0', r: '0' } },
    { label: 'CDN Trade History', url: 'http://cdn.tsetmc.com/tsev2/data/InstTradeHistory.aspx', params: { i: FOULAD, Top: '100', A: '0' } },
    { label: 'CDN Client Types', url: 'http://cdn.tsetmc.com/tsev2/data/clienttype.aspx', params: { i: FOULAD } },
  ];

  for (const p of cdnPatterns) {
    await tryEndpoint(p.label, p.url, p.params, HEADERS_API, sessionCookies);
  }

  // ============================================================
  // APPROACH 5: Try old http:// (not https)
  // ============================================================
  console.log('\n' + '='.repeat(70));
  console.log('APPROACH 5: Try HTTP (not HTTPS) with cookies');
  console.log('='.repeat(70));

  await tryEndpoint(
    'HTTP MarketWatch',
    `${TSETMC_HTTP}/tsev2/data/MarketWatchInit.aspx`,
    { h: '0', r: '0' },
    { ...HEADERS_API, Referer: `${TSETMC_HTTP}/` },
    sessionCookies
  );

  // ============================================================
  // APPROACH 6: Extract JS bundle URLs from main page
  // ============================================================
  console.log('\n' + '='.repeat(70));
  console.log('APPROACH 6: Extract JavaScript bundle URLs');
  console.log('='.repeat(70));

  try {
    const res = await axios.get(`${TSETMC_HTTPS}/`, {
      headers: HEADERS_BROWSER,
      timeout: 15000,
      httpsAgent: agent,
    });
    const html = res.data;

    // Find all script src URLs
    const scriptMatches = html.match(/<script[^>]*src="([^"]+)"/g) || [];
    console.log(`\nFound ${scriptMatches.length} script tags:`);
    scriptMatches.forEach((s, i) => {
      const srcMatch = s.match(/src="([^"]+)"/);
      if (srcMatch) {
        console.log(`  ${i + 1}. ${srcMatch[1]}`);
      }
    });

    // Try to fetch the first JS bundle and search for API patterns
    if (scriptMatches.length > 0) {
      const firstSrc = scriptMatches[0].match(/src="([^"]+)"/)[1];
      const jsUrl = firstSrc.startsWith('http') ? firstSrc : `${TSETMC_HTTPS}${firstSrc}`;
      console.log(`\nFetching JS bundle: ${jsUrl.substring(0, 80)}...`);

      try {
        const jsRes = await axios.get(jsUrl, {
          headers: HEADERS_BROWSER,
          timeout: 30000,
          httpsAgent: agent,
        });
        const jsText = jsRes.data;

        // Search for API patterns
        const apiPatterns = jsText.match(/["'`](\/api\/[^"'`]+)["'`]/g) || [];
        const dataPatterns = jsText.match(/["'`](\/tsev2\/[^"'`]+)["'`]/g) || [];
        const fetchPatterns = jsText.match(/["'`](\/data\/[^"'`]+)["'`]/g) || [];

        console.log(`JS bundle size: ${jsText.length} chars`);
        console.log(`\nAPI patterns found in JS:`);
        [...new Set([...apiPatterns, ...dataPatterns, ...fetchPatterns])].slice(0, 20).forEach(p => {
          console.log(`  ${p}`);
        });
      } catch (e) {
        console.log(`Error fetching JS: ${e.message}`);
      }
    }
  } catch (err) {
    console.log(`Error: ${err.message}`);
  }

  // ============================================================
  // Summary
  // ============================================================
  console.log('\n' + '='.repeat(70));
  console.log('DISCOVERY COMPLETE');
  console.log('='.repeat(70));
  console.log('\nPlease copy ALL the output above and send it to me.');
  console.log('I will identify which endpoint (if any) works,');
  console.log('and update the crawler to use it.');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
