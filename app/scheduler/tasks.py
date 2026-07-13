import logging
from datetime import datetime, time as dtime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo
from app.database import SessionLocal
from app.models.watchlist import Watchlist
from app.models.market_data import PriceHistory
from app.services.market_data import MarketDataService
from app.services.news import NewsService
from app.services.email_service import EmailService
from app.services.portfolio import PortfolioService
from app.services.ai_engine import AIEngineService

logger = logging.getLogger(__name__)

# Load timezone for Indian Stock Market (IST)
IST = ZoneInfo("Asia/Kolkata")


def check_market_hours() -> bool:
    """
    Returns True if the current time is during Indian stock market hours
    (Monday - Friday, 9:15 AM to 3:30 PM IST).
    """
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    market_start = dtime(9, 15)
    market_end = dtime(15, 30)
    return market_start <= now.time() <= market_end


def monitor_stock_prices_task():
    """
    Job that runs every 15 minutes during market hours.
    Fetches live stock prices and flags ±5% price moves or 2x volume spikes.
    """
    if not check_market_hours():
        logger.info("Market is closed. Skipping price monitoring task.")
        return

    logger.info("Starting live stock price check cycle...")
    db = SessionLocal()
    market_service = MarketDataService()
    email_service = EmailService(db)

    try:
        stocks = db.query(Watchlist).all()
        for stock in stocks:
            try:
                # Fetch live quotes
                quote = market_service.get_live_quote(stock.symbol)
                current_price = quote["price"]
                current_volume = quote["volume"]
                avg_volume = quote["avg_volume"]

                # Log price history
                history = PriceHistory(
                    symbol=stock.symbol, price=current_price, volume=current_volume
                )
                db.add(history)

                # Fetch previous close or starting price to assess 5% shifts
                # yfinance get_live_quote gives high/low. Let's compare current price vs purchase_price/previous logs.
                # If we have previous price logs from today, let's fetch the first log of the day.
                today_start = datetime.now(IST).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                first_log = (
                    db.query(PriceHistory)
                    .filter(
                        PriceHistory.symbol == stock.symbol,
                        PriceHistory.timestamp >= today_start,
                    )
                    .order_by(PriceHistory.timestamp.asc())
                    .first()
                )

                reference_price = (
                    first_log.price
                    if first_log
                    else (stock.average_cost or current_price)
                )
                price_change_pct = (
                    ((current_price - reference_price) / reference_price * 100)
                    if reference_price > 0
                    else 0.0
                )

                # 1. Price trigger (exceeds ±5%)
                if abs(price_change_pct) >= 5.0:
                    email_service.trigger_material_alert(
                        symbol=stock.symbol,
                        event_type="PRICE_ALERT",
                        severity="High" if abs(price_change_pct) >= 7.0 else "Medium",
                        summary=f"Stock price shifted by {price_change_pct:.2f}% today, trading at INR {current_price:,.2f}.",
                        market_impact="Significant price volatility detected during active market hours.",
                        suggested_action="Review position weights; inspect underlying catalysts.",
                        confidence_score=75.0,
                        sources="yfinance live quote ticker",
                    )

                # 2. Volume spike (exceeds 2x average volume)
                # Ensure we have active trading day volume and avg_volume is greater than 0
                if avg_volume > 0 and current_volume >= (2 * avg_volume):
                    email_service.trigger_material_alert(
                        symbol=stock.symbol,
                        event_type="VOLUME_SPIKE",
                        severity="Medium",
                        summary=f"Trading volume spiked to {current_volume:,} shares, exceeding 2x the 20-day average volume of {avg_volume:,}.",
                        market_impact="High volume implies institutional interest (FII/DII activity) or key breakout attempts.",
                        suggested_action="Track price actions for breakouts or distribution patterns.",
                        confidence_score=70.0,
                        sources="yfinance live volume feed",
                    )
            except Exception as e:
                logger.error(f"Error checking live indicators for {stock.symbol}: {e}")

        db.commit()
    except Exception as e:
        logger.error(f"Price monitoring cycle failed: {e}")
    finally:
        db.close()


def monitor_news_task():
    """
    Job that runs hourly. Fetches news and triggers AI alerts for high impact articles.
    """
    logger.info("Starting hourly news monitor check...")
    db = SessionLocal()
    news_service = NewsService()
    email_service = EmailService(db)
    ai_service = AIEngineService()
    market_service = MarketDataService()

    # Keywords to classify articles as high impact
    high_impact_keywords = [
        "earnings",
        "dividend",
        "merger",
        "acquisition",
        "ceo",
        "cfo",
        "investigation",
        "litigation",
        "lawsuit",
        "bankruptcy",
        "default",
        "insider",
    ]

    try:
        stocks = db.query(Watchlist).all()
        for stock in stocks:
            try:
                articles = news_service.fetch_company_news(stock.symbol)
                for article in articles[
                    :3
                ]:  # Analyze top 3 articles to conserve tokens
                    title_lower = article["title"].lower()
                    summary_lower = article["summary"].lower()

                    # Check if any keyword matches
                    matches = [
                        kw
                        for kw in high_impact_keywords
                        if kw in title_lower or kw in summary_lower
                    ]
                    if matches:
                        logger.info(
                            f"High-impact news match {matches} for {stock.symbol}: {article['title']}"
                        )

                        # Fetch quote and info to pass to the AI model
                        company_info = market_service.get_stock_info(stock.symbol)
                        live_quote = market_service.get_live_quote(stock.symbol)
                        technicals = market_service.calculate_technical_indicators(
                            stock.symbol
                        )

                        # Generate AI Recommendation
                        ai_rec = ai_service.generate_recommendation(
                            symbol=stock.symbol,
                            company_info=company_info,
                            live_quote=live_quote,
                            technicals=technicals,
                            news_articles=[article],
                            trigger_event=f"High-Impact News: {article['title']}",
                        )

                        # Trigger alert with AI support if successful
                        if ai_rec.get("success"):
                            email_service.trigger_material_alert(
                                symbol=stock.symbol,
                                event_type="HIGH_IMPACT_NEWS",
                                severity="High",
                                summary=f"AI Analysis of event: '{article['title']}'.\n\nExecutive Summary: {ai_rec['executive_summary']}",
                                market_impact=ai_rec.get("market_impact")
                                or ai_rec.get(
                                    "why_it_matters", "Significant news catalyst."
                                ),
                                suggested_action=ai_rec.get("suggested_action", "Hold"),
                                confidence_score=float(
                                    ai_rec.get("confidence_score", 80.0)
                                ),
                                key_risks=ai_rec.get("risk_assessment", "N/A"),
                                sources=article.get("url")
                                or article.get("source")
                                or "News Feed",
                            )
                        else:
                            # Fallback if OpenAI API fails or is mock
                            email_service.trigger_material_alert(
                                symbol=stock.symbol,
                                event_type="NEWS_EVENT",
                                severity="Medium",
                                summary=article["title"] + "\n\n" + article["summary"],
                                market_impact="Unable to run deep AI valuation analysis (engine offline). Check source link.",
                                suggested_action="Manual review required.",
                                confidence_score=50.0,
                                key_risks="Event details unverified by AI engine.",
                                sources=article.get("url")
                                or article.get("source")
                                or "News Feed",
                            )
            except Exception as e:
                logger.error(f"Error processing news feed for {stock.symbol}: {e}")
    except Exception as e:
        logger.error(f"News monitor cycle failed: {e}")
    finally:
        db.close()


def generate_daily_summary_task():
    """
    Job that runs daily at market close. Generates portfolio summary.
    """
    logger.info("Generating daily portfolio performance newsletter...")
    db = SessionLocal()
    try:
        portfolio_service = PortfolioService(db)
        email_service = EmailService(db)

        summary_text = portfolio_service.generate_daily_summary_text()

        # Dispatch email
        subject = f"Daily Portfolio Performance Summary - {datetime.now().strftime('%Y-%m-%d')}"
        html_content = f"""
        <html>
            <body style="font-family: monospace; white-space: pre-wrap; padding: 20px; background-color: #f9f9f9;">
                <h2>Daily Portfolio Summary</h2>
                <hr>
                {summary_text}
            </body>
        </html>
        """
        email_service.send_email(subject, html_content)
        logger.info("Daily performance summary newsletter sent successfully.")
    except Exception as e:
        logger.error(f"Daily summary task failed: {e}")
    finally:
        db.close()


def generate_weekly_report_task():
    """
    Job that runs weekly on Sunday. Generates weekly report.
    """
    logger.info("Generating weekly investment intelligence report...")
    db = SessionLocal()
    try:
        portfolio_service = PortfolioService(db)
        email_service = EmailService(db)

        report_text = portfolio_service.generate_weekly_report_text()

        subject = f"Weekly Investment Intelligence Report - {datetime.now().strftime('%Y-%m-%d')}"
        html_content = f"""
        <html>
            <body style="font-family: monospace; white-space: pre-wrap; padding: 20px; background-color: #f9f9f9;">
                <h2>Weekly Investment Report</h2>
                <hr>
                {report_text}
            </body>
        </html>
        """
        email_service.send_email(subject, html_content)
        logger.info("Weekly intelligence report newsletter sent successfully.")
    except Exception as e:
        logger.error(f"Weekly report task failed: {e}")
    finally:
        db.close()


# Instantiate Scheduler
scheduler = BackgroundScheduler(timezone=IST)


def start_scheduler():
    """
    Starts all cron and interval jobs.
    """
    if not scheduler.running:
        # 1. 15-minute price checks (Mon-Fri 9:15 AM - 3:30 PM IST)
        # We run it between 9:00 AM and 4:00 PM to catch opening/closing blocks
        scheduler.add_job(
            monitor_stock_prices_task,
            trigger=CronTrigger(
                day_of_week="mon-fri", hour="9-16", minute="*/15", timezone=IST
            ),
            id="price_monitoring_job",
            replace_existing=True,
        )

        # 2. Hourly news checks (Mon-Fri 9:00 AM - 6:00 PM IST)
        scheduler.add_job(
            monitor_news_task,
            trigger=CronTrigger(
                day_of_week="mon-fri", hour="9-18", minute="0", timezone=IST
            ),
            id="news_monitoring_job",
            replace_existing=True,
        )

        # 3. Daily Summary newsletter (Mon-Fri at 5:00 PM IST)
        scheduler.add_job(
            generate_daily_summary_task,
            trigger=CronTrigger(
                day_of_week="mon-fri", hour="17", minute="0", timezone=IST
            ),
            id="daily_summary_job",
            replace_existing=True,
        )

        # 4. Weekly Report newsletter (Sunday at 7:00 PM IST)
        scheduler.add_job(
            generate_weekly_report_task,
            trigger=CronTrigger(day_of_week="sun", hour="19", minute="0", timezone=IST),
            id="weekly_report_job",
            replace_existing=True,
        )

        scheduler.start()
        logger.info("APScheduler initialized and all monitoring jobs registered.")
