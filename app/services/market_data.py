import yfinance as yf
import pandas as pd
import logging
import time
from typing import Dict, Any

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketDataService:
    @staticmethod
    def get_ticker(symbol: str) -> yf.Ticker:
        """
        Retrieves a yfinance Ticker instance for the symbol.
        Automatically appends .NS for Indian markets if exchange/suffix is missing.
        """
        clean_symbol = symbol.strip().upper()
        if not (clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO")):
            # Default to National Stock Exchange (NSE) if no exchange suffix is provided
            clean_symbol = f"{clean_symbol}.NS"
        return yf.Ticker(clean_symbol)

    def get_live_quote(
        self, symbol: str, retries: int = 3, delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Fetches the current market price and volume for a symbol with retries.
        """
        ticker = self.get_ticker(symbol)
        for attempt in range(retries):
            try:
                # Use history to get the latest day's data (realtime/most recent)
                history = ticker.history(period="1d", interval="1m")
                if history.empty:
                    # Fallback to period="5d" if "1d" is unavailable due to market hours/holidays
                    history = ticker.history(period="5d")

                if history.empty:
                    raise ValueError(f"No market data returned for symbol: {symbol}")

                last_row = history.iloc[-1]

                # Check for average volume to check spikes
                avg_vol = self.get_average_volume(symbol)

                return {
                    "price": float(last_row["Close"]),
                    "volume": int(last_row["Volume"]),
                    "high": float(last_row["High"]),
                    "low": float(last_row["Low"]),
                    "avg_volume": avg_vol,
                    "timestamp": (
                        last_row.name.to_pydatetime()
                        if hasattr(last_row.name, "to_pydatetime")
                        else last_row.name
                    ),
                }
            except Exception as e:
                logger.error(
                    f"Error fetching live quote for {symbol} (Attempt {attempt+1}/{retries}): {e}"
                )
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    raise e

    def get_average_volume(self, symbol: str, days: int = 20) -> int:
        """
        Calculates the average trading volume of the stock over the past N days.
        """
        try:
            ticker = self.get_ticker(symbol)
            history = ticker.history(
                period=f"{days * 2}d"
            )  # Get extra history to ensure we cover trading days
            if history.empty:
                return 0
            # Calculate rolling average volume
            avg_vol = history["Volume"].tail(days).mean()
            return int(avg_vol) if not pd.isna(avg_vol) else 0
        except Exception as e:
            logger.error(f"Error calculating average volume for {symbol}: {e}")
            return 0

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        Retrieves company info including name, sector, dividends, splits, and promoter holdings.
        """
        ticker = self.get_ticker(symbol)
        info = {}
        try:
            raw_info = ticker.info
            info["company_name"] = (
                raw_info.get("longName") or raw_info.get("shortName") or symbol
            )
            info["sector"] = raw_info.get("sector")
            info["industry"] = raw_info.get("industry")

            # Extract dividend yield
            info["dividend_yield"] = raw_info.get("dividendYield")
            info["dividend_rate"] = raw_info.get("dividendRate")

            # Promoter Holdings / Insider Data
            major_holders = ticker.major_holders
            promoter_holding = 0.0
            if major_holders is not None and not major_holders.empty:
                try:
                    # yfinance returns promoter percentage in columns. Let's parse if available.
                    # Usually: "insidersPercentHeld" or inside major_holders dataframe
                    promoter_holding = raw_info.get("insidersPercentHeld", 0.0) * 100
                except Exception:
                    pass
            info["promoter_holding_percent"] = promoter_holding

        except Exception as e:
            logger.warning(
                f"Metadata fetch failed for {symbol}: {e}. Swapping to standard parsing."
            )
            info["company_name"] = symbol
            info["sector"] = "Unknown"
            info["industry"] = "Unknown"
            info["dividend_yield"] = 0.0
            info["promoter_holding_percent"] = 0.0

        return info

    def calculate_technical_indicators(
        self, symbol: str, period: str = "6mo"
    ) -> Dict[str, Any]:
        """
        Computes standard technical indicators: 20-day SMA, 50-day SMA, 14-day RSI, and MACD.
        """
        ticker = self.get_ticker(symbol)
        try:
            df = ticker.history(period=period)
            if df.empty or len(df) < 26:
                return {
                    "rsi": 50.0,
                    "macd": 0.0,
                    "macd_signal": 0.0,
                    "sma_20": 0.0,
                    "sma_50": 0.0,
                }

            # 1. Simple Moving Averages
            df["SMA_20"] = df["Close"].rolling(window=20).mean()
            df["SMA_50"] = df["Close"].rolling(window=50).mean()

            # 2. RSI (14 days)
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            df["RSI_14"] = 100 - (100 / (1 + rs))

            # 3. MACD (12, 26, 9)
            exp1 = df["Close"].ewm(span=12, adjust=False).mean()
            exp2 = df["Close"].ewm(span=26, adjust=False).mean()
            df["MACD"] = exp1 - exp2
            df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

            last_row = df.iloc[-1]
            return {
                "rsi": (
                    float(last_row["RSI_14"])
                    if not pd.isna(last_row["RSI_14"])
                    else 50.0
                ),
                "macd": (
                    float(last_row["MACD"]) if not pd.isna(last_row["MACD"]) else 0.0
                ),
                "macd_signal": (
                    float(last_row["MACD_Signal"])
                    if not pd.isna(last_row["MACD_Signal"])
                    else 0.0
                ),
                "sma_20": (
                    float(last_row["SMA_20"])
                    if not pd.isna(last_row["SMA_20"])
                    else 0.0
                ),
                "sma_50": (
                    float(last_row["SMA_50"])
                    if not pd.isna(last_row["SMA_50"])
                    else 0.0
                ),
            }
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {e}")
            return {
                "rsi": 50.0,
                "macd": 0.0,
                "macd_signal": 0.0,
                "sma_20": 0.0,
                "sma_50": 0.0,
            }
