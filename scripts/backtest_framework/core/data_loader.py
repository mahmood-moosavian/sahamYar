"""
Data Loader for Backtest Framework
Loads data from CSV files or PostgreSQL into pandas DataFrames.
"""
import os
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import yaml


class DataLoader:
    """Load market data from CSV files or PostgreSQL"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.data_source = self.config['DATA_SOURCE']
        self._symbols = None
        self._candles = None
        self._client_types = None
        self._fundamentals = None
        self._market_index = None
    
    @property
    def data_dir(self) -> Path:
        if self.data_source == "csv":
            base = Path(__file__).parent.parent
            return base / self.config['CSV']['data_dir']
        raise ValueError("data_dir only available for CSV source")
    
    def load_symbols(self) -> pd.DataFrame:
        """Load symbols master data"""
        if self._symbols is not None:
            return self._symbols
        
        if self.data_source == "csv":
            path = self.data_dir / "symbols.csv"
            if not path.exists():
                raise FileNotFoundError(
                    f"symbols.csv not found at {path}\n"
                    f"Run sample_data_generator.py first to create sample data."
                )
            self._symbols = pd.read_csv(path, encoding='utf-8-sig')
        elif self.data_source == "postgres":
            self._symbols = self._load_from_postgres("SELECT * FROM symbols")
        else:
            raise ValueError(f"Unknown data source: {self.data_source}")
        
        # Filter to active symbols by default
        if 'status' in self._symbols.columns:
            self._symbols['is_active'] = self._symbols['status'] == 'A'
        
        return self._symbols
    
    def load_candles(self) -> pd.DataFrame:
        """Load daily candles (OHLCV)"""
        if self._candles is not None:
            return self._candles
        
        if self.data_source == "csv":
            path = self.data_dir / "daily_candles.csv"
            if not path.exists():
                raise FileNotFoundError(f"daily_candles.csv not found at {path}")
            self._candles = pd.read_csv(path, encoding='utf-8-sig')
        elif self.data_source == "postgres":
            self._candles = self._load_from_postgres("SELECT * FROM daily_candles")
        
        # Sort by symbol and date
        self._candles = self._candles.sort_values(['ins_code', 'date_jalali']).reset_index(drop=True)
        
        return self._candles
    
    def load_client_types(self) -> pd.DataFrame:
        """Load client type data (حقوقی/حقیقی)"""
        if self._client_types is not None:
            return self._client_types
        
        if self.data_source == "csv":
            path = self.data_dir / "client_types.csv"
            if not path.exists():
                raise FileNotFoundError(f"client_types.csv not found at {path}")
            self._client_types = pd.read_csv(path, encoding='utf-8-sig')
        elif self.data_source == "postgres":
            self._client_types = self._load_from_postgres("SELECT * FROM client_types")
        
        self._client_types = self._client_types.sort_values(
            ['ins_code', 'date_jalali']
        ).reset_index(drop=True)
        
        return self._client_types
    
    def load_fundamentals(self) -> pd.DataFrame:
        """Load quarterly fundamentals"""
        if self._fundamentals is not None:
            return self._fundamentals
        
        if self.data_source == "csv":
            path = self.data_dir / "fundamentals.csv"
            if not path.exists():
                raise FileNotFoundError(f"fundamentals.csv not found at {path}")
            self._fundamentals = pd.read_csv(path, encoding='utf-8-sig')
        elif self.data_source == "postgres":
            self._fundamentals = self._load_from_postgres("SELECT * FROM fundamentals")
        
        # Sort by symbol and report date (for look-ahead bias prevention)
        if 'report_date' in self._fundamentals.columns:
            self._fundamentals = self._fundamentals.sort_values(
                ['ins_code', 'report_date']
            ).reset_index(drop=True)
        
        return self._fundamentals
    
    def load_market_index(self) -> pd.DataFrame:
        """Load market index (TEDPIX) for benchmark comparison"""
        if self._market_index is not None:
            return self._market_index
        
        if self.data_source == "csv":
            path = self.data_dir / "market_index.csv"
            if not path.exists():
                raise FileNotFoundError(f"market_index.csv not found at {path}")
            self._market_index = pd.read_csv(path, encoding='utf-8-sig')
        elif self.data_source == "postgres":
            self._market_index = self._load_from_postgres("SELECT * FROM market_index")
        
        self._market_index = self._market_index.sort_values('date_jalali').reset_index(drop=True)
        return self._market_index
    
    def get_active_symbols(self, on_date: int = None) -> pd.DataFrame:
        """Get symbols that were active on a specific date"""
        symbols = self.load_symbols()
        
        if on_date is None:
            return symbols[symbols['is_active']] if 'is_active' in symbols.columns else symbols
        
        # Filter by listed_at and delisted_at
        result = symbols.copy()
        if 'listed_at' in result.columns:
            listed = pd.to_datetime(result['listed_at'], errors='coerce')
            # Convert on_date to datetime (approximate)
            year = on_date // 10000
            month = (on_date // 100) % 100
            day = on_date % 100
            on_dt = pd.to_datetime(f"{year + 621}-{month}-{day}", errors='coerce')
            result = result[listed <= on_dt]
        
        if 'delisted_at' in result.columns and result['delisted_at'].notna().any():
            delisted = pd.to_datetime(result['delisted_at'], errors='coerce')
            year = on_date // 10000
            month = (on_date // 100) % 100
            day = on_date % 100
            on_dt = pd.to_datetime(f"{year + 621}-{month}-{day}", errors='coerce')
            result = result[(delisted.isna()) | (delisted > on_dt)]
        
        return result
    
    def get_candles_up_to(self, ins_code: str, on_date: int, days: int = 365) -> pd.DataFrame:
        """Get historical candles for a symbol up to (but not including) a date.
        Used for backtesting — ensures no look-ahead bias."""
        candles = self.load_candles()
        sym_candles = candles[candles['ins_code'] == ins_code]
        sym_candles = sym_candles[sym_candles['date_jalali'] < on_date]
        return sym_candles.tail(days).reset_index(drop=True)
    
    def get_future_candles(self, ins_code: str, from_date: int, horizon_days: int) -> pd.DataFrame:
        """Get future candles for evaluation. 
        Note: This is for EVALUATION ONLY, never for signal generation."""
        candles = self.load_candles()
        sym_candles = candles[candles['ins_code'] == ins_code]
        sym_candles = sym_candles[sym_candles['date_jalali'] >= from_date]
        return sym_candles.head(horizon_days).reset_index(drop=True)
    
    def get_fundamentals_available_on(self, ins_code: str, on_date: int) -> pd.DataFrame:
        """Get fundamentals that were publicly available on a specific date.
        CRITICAL: Uses report_date to prevent look-ahead bias."""
        fundamentals = self.load_fundamentals()
        sym_funds = fundamentals[fundamentals['ins_code'] == ins_code]
        
        if 'report_date' not in sym_funds.columns:
            return sym_funds  # No bias protection if no report_date
        
        # Convert on_date (Jalali int) to Gregorian for comparison
        year = on_date // 10000
        month = (on_date // 100) % 100
        day = on_date % 100
        on_dt = pd.to_datetime(f"{year + 621}-{month}-{day}", errors='coerce')
        
        report_dates = pd.to_datetime(sym_funds['report_date'], errors='coerce')
        return sym_funds[report_dates <= on_dt]
    
    def _load_from_postgres(self, query: str) -> pd.DataFrame:
        """Load data from PostgreSQL using SQLAlchemy"""
        from sqlalchemy import create_engine
        cfg = self.config['POSTGRES']
        conn_str = f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['database']}"
        engine = create_engine(conn_str)
        return pd.read_sql(query, engine)
    
    def summary(self) -> Dict:
        """Return summary statistics of loaded data"""
        return {
            'symbols': len(self.load_symbols()),
            'active_symbols': len(self.get_active_symbols()),
            'candles': len(self.load_candles()),
            'client_types': len(self.load_client_types()),
            'fundamentals': len(self.load_fundamentals()),
            'market_index_records': len(self.load_market_index()),
            'date_range': {
                'start': int(self.load_candles()['date_jalali'].min()),
                'end': int(self.load_candles()['date_jalali'].max()),
            }
        }
