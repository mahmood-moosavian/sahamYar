/**
 * Data Inspector — Shows what's in your CSV files
 * Run this to debug data issues before running backtest.
 *
 * Usage: node inspect_data.js
 */

const fs = require('fs');
const path = require('path');
const DataLoader = require('./lib/data_loader');

const configPath = path.join(__dirname, 'config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const dataLoader = new DataLoader(config);

console.log('='.repeat(60));
console.log('DATA INSPECTOR');
console.log('='.repeat(60));

// Symbols
try {
  const symbols = dataLoader.loadSymbols();
  console.log(`\n📊 Symbols: ${symbols.length} total`);
  console.log(`   Active: ${symbols.filter(s => s.status === 'A' || s.status === 'NO').length}`);
  console.log(`   Sample:`);
  symbols.slice(0, 5).forEach(s => {
    console.log(`     ${s.ticker} → ins_code=${s.ins_code}, status=${s.status}`);
  });
} catch (e) {
  console.log(`\n❌ Symbols error: ${e.message}`);
}

// Candles
try {
  const candles = dataLoader.loadCandles();
  console.log(`\n📈 Candles: ${candles.length} total`);

  if (candles.length > 0) {
    // Date range
    const dates = candles.map(c => c.date_jalali).filter(d => d > 0).sort((a, b) => a - b);
    console.log(`   Date range: ${dates[0]} to ${dates[dates.length - 1]}`);
    console.log(`   Unique dates: ${new Set(dates).size}`);

    // Candles per symbol
    const bySymbol = {};
    for (const c of candles) {
      bySymbol[c.ins_code] = (bySymbol[c.ins_code] || 0) + 1;
    }
    const counts = Object.values(bySymbol).sort((a, b) => b - a);
    console.log(`   Symbols with candles: ${Object.keys(bySymbol).length}`);
    console.log(`   Candles per symbol: max=${counts[0]}, median=${counts[Math.floor(counts.length / 2)]}, min=${counts[counts.length - 1]}`);

    // Sample candle
    console.log(`   Sample candle:`);
    console.log(`     ${JSON.stringify(candles[0], null, 2)}`);
  } else {
    console.log(`   ⚠ No candles! Run the crawler first.`);
  }
} catch (e) {
  console.log(`\n❌ Candles error: ${e.message}`);
}

// Client Types
try {
  const ct = dataLoader.loadClientTypes();
  console.log(`\n👥 Client Types: ${ct.length} total`);
  if (ct.length > 0) {
    const dates = ct.map(c => c.date_jalali).filter(d => d > 0).sort((a, b) => a - b);
    console.log(`   Date range: ${dates[0]} to ${dates[dates.length - 1]}`);
    console.log(`   Unique dates: ${new Set(dates).size}`);
    console.log(`   Sample: ${JSON.stringify(ct[0], null, 2)}`);
  }
} catch (e) {
  console.log(`\n❌ Client types error: ${e.message}`);
}

// Market Index
try {
  const idx = dataLoader.loadMarketIndex();
  console.log(`\n📊 Market Index: ${idx.length} records`);
  if (idx.length > 0) {
    console.log(`   Sample: ${JSON.stringify(idx[0])}`);
  }
} catch (e) {
  console.log(`\n❌ Market index error: ${e.message}`);
}

// Fundamentals
try {
  const funds = dataLoader.loadFundamentals();
  console.log(`\n💼 Fundamentals: ${funds.length} records`);
} catch (e) {
  console.log(`\n❌ Fundamentals error: ${e.message}`);
}

console.log('\n' + '='.repeat(60));
console.log('DIAGNOSTIC');
console.log('='.repeat(60));

// Check for common issues
const candles = dataLoader._candles || [];
const issues = [];

if (candles.length === 0) {
  issues.push('No candles data — run crawler first');
} else if (candles.length < 1000) {
  issues.push(`Very few candles (${candles.length}) — crawler may not have fetched full history`);
}

// Use loop instead of Math.min/max(...spread) to avoid stack overflow
let minDate = Infinity;
let maxDate = -Infinity;
for (const c of candles) {
  if (c.date_jalali > 0) {
    if (c.date_jalali < minDate) minDate = c.date_jalali;
    if (c.date_jalali > maxDate) maxDate = c.date_jalali;
  }
}
if (minDate !== Infinity) {
  const dateSpan = maxDate - minDate;

  // Check if dates look like Jalali (should start with 13xx or 14xx)
  if (minDate > 20000000) {
    issues.push(`Dates appear to be GREGORIAN not Jalali! min=${minDate}`);
    issues.push('  → The crawler should convert Gregorian to Jalali. Check crawler_v2.js');
  }

  if (dateSpan < 10000) {
    // Less than ~1 year of data (Jalali date span of 10000 = 1 year)
    issues.push(`Very short date span (${dateSpan}). Need at least 1 year of history.`);
  }
}

if (issues.length > 0) {
  console.log('\n⚠ Issues found:');
  issues.forEach((issue, i) => console.log(`  ${i + 1}. ${issue}`));
} else {
  console.log('\n✓ No issues detected. Data looks good!');
}

console.log('\n' + '='.repeat(60));
console.log('RECOMMENDATIONS');
console.log('='.repeat(60));

if (candles.length < 5000) {
  console.log('\n📌 You need more candle data:');
  console.log('   1. Re-run the crawler with more symbols:');
  console.log('      cd ../tsetmc_crawler');
  console.log('      node crawler_v2.js --mode medium  (100 symbols)');
  console.log('   2. Make sure crawler uses Top=999999 (not Top=0)');
  console.log('   3. Check crawler output for errors');
}

if (candleDates.length > 0 && Math.min(...candleDates) > 20000000) {
  console.log('\n📌 Date format issue:');
  console.log('   Dates are Gregorian, need to be Jalali.');
  console.log('   The crawler_v2.js has a dEvenToJalali() function.');
  console.log('   Make sure you are using the latest crawler_v2.js.');
}

console.log('\n📌 After fixing data, run:');
console.log('   node backtest.js');
