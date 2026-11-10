/**
 * Data Loader — Reads CSV files into memory
 * Equivalent to Python's DataLoader class
 */

const fs = require('fs');
const path = require('path');

class DataLoader {
  constructor(config) {
    this.config = config;
    this.dataDir = path.join(__dirname, '..', '..', config.CSV?.data_dir || 'data/csv');
    this._symbols = null;
    this._candles = null;
    this._clientTypes = null;
    this._fundamentals = null;
    this._marketIndex = null;
  }

  /**
   * Simple CSV parser (handles quoted fields)
   */
  parseCsv(text) {
    const lines = text.trim().split('\n');
    if (lines.length === 0) return [];

    // Parse header
    const headers = this.parseCsvLine(lines[0]);
    const rows = [];

    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      const values = this.parseCsvLine(lines[i]);
      const row = {};
      for (let j = 0; j < headers.length; j++) {
        row[headers[j]] = values[j] || '';
      }
      rows.push(row);
    }
    return rows;
  }

  parseCsvLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === ',' && !inQuotes) {
        result.push(current);
        current = '';
      } else {
        current += char;
      }
    }
    result.push(current);
    return result;
  }

  toNumber(val) {
    if (val === null || val === undefined || val === '') return 0;
    const n = Number(val);
    return isNaN(n) ? 0 : n;
  }

  loadSymbols() {
    if (this._symbols) return this._symbols;
    const filePath = path.join(this.dataDir, 'symbols.csv');
    if (!fs.existsSync(filePath)) {
      throw new Error(`symbols.csv not found at ${filePath}`);
    }
    const text = fs.readFileSync(filePath, 'utf8');
    this._symbols = this.parseCsv(text);
    return this._symbols;
  }

  loadCandles() {
    if (this._candles) return this._candles;
    const filePath = path.join(this.dataDir, 'daily_candles.csv');
    if (!fs.existsSync(filePath)) {
      throw new Error(`daily_candles.csv not found at ${filePath}`);
    }
    const text = fs.readFileSync(filePath, 'utf8');
    let rows = this.parseCsv(text);

    // Convert types
    rows = rows.map(r => ({
      ins_code: String(r.ins_code || ''),
      date_jalali: parseInt(r.date_jalali || 0, 10),
      open: this.toNumber(r.open),
      high: this.toNumber(r.high),
      low: this.toNumber(r.low),
      close: this.toNumber(r.close),
      last_price: this.toNumber(r.last_price),
      yesterday: this.toNumber(r.yesterday),
      volume: parseInt(this.toNumber(r.volume), 10),
      trade_count: parseInt(this.toNumber(r.trade_count), 10),
      value: parseInt(this.toNumber(r.value), 10),
      max_allowed: this.toNumber(r.max_allowed),
      min_allowed: this.toNumber(r.min_allowed),
    }));

    // Sort by ins_code and date
    rows.sort((a, b) => {
      if (a.ins_code !== b.ins_code) return a.ins_code.localeCompare(b.ins_code);
      return a.date_jalali - b.date_jalali;
    });

    this._candles = rows;
    return rows;
  }

  loadClientTypes() {
    if (this._clientTypes) return this._clientTypes;
    const filePath = path.join(this.dataDir, 'client_types.csv');
    if (!fs.existsSync(filePath)) {
      console.warn(`client_types.csv not found — smart money signal will be limited`);
      this._clientTypes = [];
      return this._clientTypes;
    }
    const text = fs.readFileSync(filePath, 'utf8');
    let rows = this.parseCsv(text);

    rows = rows.map(r => ({
      ins_code: String(r.ins_code || ''),
      date_jalali: parseInt(r.date_jalali || 0, 10),
      buy_real_count: parseInt(this.toNumber(r.buy_real_count), 10),
      sell_real_count: parseInt(this.toNumber(r.sell_real_count), 10),
      buy_legal_count: parseInt(this.toNumber(r.buy_legal_count), 10),
      sell_legal_count: parseInt(this.toNumber(r.sell_legal_count), 10),
      buy_real_volume: parseInt(this.toNumber(r.buy_real_volume), 10),
      sell_real_volume: parseInt(this.toNumber(r.sell_real_volume), 10),
      buy_legal_volume: parseInt(this.toNumber(r.buy_legal_volume), 10),
      sell_legal_volume: parseInt(this.toNumber(r.sell_legal_volume), 10),
      buy_real_value: parseInt(this.toNumber(r.buy_real_value), 10),
      sell_real_value: parseInt(this.toNumber(r.sell_real_value), 10),
      buy_legal_value: parseInt(this.toNumber(r.buy_legal_value), 10),
      sell_legal_value: parseInt(this.toNumber(r.sell_legal_value), 10),
    }));

    rows.sort((a, b) => {
      if (a.ins_code !== b.ins_code) return a.ins_code.localeCompare(b.ins_code);
      return a.date_jalali - b.date_jalali;
    });

    this._clientTypes = rows;
    return rows;
  }

  loadFundamentals() {
    if (this._fundamentals) return this._fundamentals;
    const filePath = path.join(this.dataDir, 'fundamentals.csv');
    if (!fs.existsSync(filePath)) {
      this._fundamentals = [];
      return this._fundamentals;
    }
    const text = fs.readFileSync(filePath, 'utf8');
    this._fundamentals = this.parseCsv(text);
    return this._fundamentals;
  }

  loadMarketIndex() {
    if (this._marketIndex) return this._marketIndex;
    const filePath = path.join(this.dataDir, 'market_index.csv');
    if (!fs.existsSync(filePath)) {
      this._marketIndex = [];
      return this._marketIndex;
    }
    const text = fs.readFileSync(filePath, 'utf8');
    let rows = this.parseCsv(text);

    rows = rows.map(r => ({
      date_jalali: parseInt(r.date_jalali || 0, 10),
      index_value: this.toNumber(r.index_value),
      index_change_pct: this.toNumber(r.index_change_pct),
    }));

    rows.sort((a, b) => a.date_jalali - b.date_jalali);
    this._marketIndex = rows;
    return rows;
  }

  getActiveSymbols() {
    const symbols = this.loadSymbols();
    return symbols.filter(s => (s.status === 'A' || s.status === 'NO') && s.ins_code);
  }

  getCandlesUpTo(insCode, onDate, days = 365) {
    const candles = this.loadCandles();
    const filtered = candles.filter(c => c.ins_code === insCode && c.date_jalali < onDate);
    return filtered.slice(-days);
  }

  getFutureCandles(insCode, fromDate, horizonDays) {
    const candles = this.loadCandles();
    const filtered = candles.filter(c => c.ins_code === insCode && c.date_jalali >= fromDate);
    return filtered.slice(0, horizonDays);
  }

  getClientTypesUpTo(insCode, onDate, days = 10) {
    const ct = this.loadClientTypes();
    const filtered = ct.filter(c => c.ins_code === insCode && c.date_jalali < onDate);
    return filtered.slice(-days);
  }

  getFundamentalsFor(insCode) {
    const funds = this.loadFundamentals();
    return funds.filter(f => f.ins_code === insCode);
  }

  getBenchmarkReturn(onDate, horizonDays) {
    const idx = this.loadMarketIndex();
    const future = idx.filter(i => i.date_jalali >= onDate);
    if (future.length <= horizonDays) return 0;
    const start = future[0].index_value;
    const end = future[horizonDays].index_value;
    if (start === 0) return 0;
    return (end - start) / start * 100;
  }

  summary() {
    return {
      symbols: this.loadSymbols().length,
      activeSymbols: this.getActiveSymbols().length,
      candles: this.loadCandles().length,
      clientTypes: this.loadClientTypes().length,
      fundamentals: this.loadFundamentals().length,
      marketIndexRecords: this.loadMarketIndex().length,
    };
  }
}

module.exports = DataLoader;
