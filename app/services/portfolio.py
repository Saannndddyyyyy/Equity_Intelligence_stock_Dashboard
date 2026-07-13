import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.watchlist import Watchlist
from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)


class PortfolioService:
    def __init__(self, db: Session):
        self.db = db
        self.market_data = MarketDataService()

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Calculates valuation and returns for all assets currently held in the watchlist.
        """
        # Query watchlist items with holdings (quantity > 0)
        holdings = self.db.query(Watchlist).filter(Watchlist.quantity > 0).all()

        total_cost_value = 0.0
        total_market_value = 0.0
        holdings_summary = []

        for item in holdings:
            try:
                # Fetch live price
                quote = self.market_data.get_live_quote(item.symbol)
                current_price = quote["price"]
            except Exception as e:
                logger.error(
                    f"Failed to fetch live quote for portfolio calculation on {item.symbol}: {e}"
                )
                # Fallback to average_cost or purchase_price if live quote fails
                current_price = item.average_cost or item.purchase_price or 0.0

            quantity = item.quantity
            cost_basis = item.average_cost or item.purchase_price or 0.0

            cost_value = cost_basis * quantity
            market_value = current_price * quantity

            unrealized_pnl = market_value - cost_value
            pnl_percent = (unrealized_pnl / cost_value * 100) if cost_value > 0 else 0.0

            total_cost_value += cost_value
            total_market_value += market_value

            holdings_summary.append(
                {
                    "symbol": item.symbol,
                    "company_name": item.company_name,
                    "quantity": quantity,
                    "average_cost": cost_basis,
                    "current_price": current_price,
                    "cost_value": cost_value,
                    "market_value": market_value,
                    "unrealized_pnl": unrealized_pnl,
                    "pnl_percent": pnl_percent,
                    "target_price": item.target_price,
                    "stop_loss": item.stop_loss,
                }
            )

        # Calculate allocation percentages and aggregate stats
        total_pnl = total_market_value - total_cost_value
        total_pnl_percent = (
            (total_pnl / total_cost_value * 100) if total_cost_value > 0 else 0.0
        )

        for holding in holdings_summary:
            holding["allocation_percent"] = (
                (holding["market_value"] / total_market_value * 100)
                if total_market_value > 0
                else 0.0
            )

        return {
            "total_cost_value": total_cost_value,
            "total_market_value": total_market_value,
            "total_pnl": total_pnl,
            "total_pnl_percent": total_pnl_percent,
            "holdings": holdings_summary,
            "valuation_date": datetime.now().isoformat(),
        }

    def generate_daily_summary_text(self) -> str:
        """
        Generates a text summary of the portfolio performance suitable for daily emails.
        """
        summary = self.get_portfolio_summary()

        text = f"DAILY PORTFOLIO SUMMARY - {datetime.now().strftime('%Y-%m-%d')}\n"
        text += "=" * 50 + "\n"
        text += f"Total Cost Value:    INR {summary['total_cost_value']:,.2f}\n"
        text += f"Total Market Value:  INR {summary['total_market_value']:,.2f}\n"
        text += f"Total PnL:           INR {summary['total_pnl']:,.2f} ({summary['total_pnl_percent']:.2f}%)\n"
        text += "=" * 50 + "\n"

        if not summary["holdings"]:
            text += "No active holdings in portfolio.\n"
            return text

        text += f"{'Symbol':<10} | {'Qty':<6} | {'Avg Cost':<10} | {'LTP':<10} | {'PnL (%)':<15} | {'Allocation (%)':<15}\n"
        text += "-" * 80 + "\n"
        for h in summary["holdings"]:
            text += f"{h['symbol']:<10} | {h['quantity']:<6} | INR {h['average_cost']:<8,.2f} | INR {h['current_price']:<8,.2f} | INR {h['unrealized_pnl']:<7,.2f} ({h['pnl_percent']:.1f}%) | {h['allocation_percent']:.1f}%\n"

        return text

    def generate_weekly_report_text(self) -> str:
        """
        Generates a comprehensive weekly investment report including technical indicators.
        """
        summary = self.get_portfolio_summary()

        text = f"WEEKLY INVESTMENT INTELLIGENCE REPORT - {datetime.now().strftime('%Y-%m-%d')}\n"
        text += "=" * 60 + "\n"
        text += f"Portfolio Market Value: INR {summary['total_market_value']:,.2f}\n"
        text += f"Total Returns:          INR {summary['total_pnl']:,.2f} ({summary['total_pnl_percent']:.2f}%)\n"
        text += "=" * 60 + "\n"

        text += "\nHolding Technical Health Checks:\n"
        text += "-" * 50 + "\n"

        for h in summary["holdings"]:
            tech = self.market_data.calculate_technical_indicators(h["symbol"])
            rsi = tech["rsi"]
            rsi_status = (
                "Oversold (Buy Catalyst)"
                if rsi < 30
                else "Overbought (Sell Risk)" if rsi > 70 else "Neutral"
            )

            text += f"\n* {h['symbol']} ({h['company_name']}):\n"
            text += f"  Price: INR {h['current_price']:,.2f} (Cost Basis: INR {h['average_cost']:,.2f})\n"
            text += f"  RSI: {rsi:.2f} ({rsi_status})\n"
            text += f"  SMA 20: INR {tech['sma_20']:,.2f} | SMA 50: INR {tech['sma_50']:,.2f}\n"

            # Simple technical alert
            if h["current_price"] < tech["sma_50"] and tech["sma_50"] > 0:
                text += "  [WARNING] Price is trading below the 50-day moving average. Bearish momentum.\n"
            elif h["current_price"] > tech["sma_20"]:
                text += "  [BULLISH] Price is trading above the 20-day moving average. Positive momentum.\n"

        return text
