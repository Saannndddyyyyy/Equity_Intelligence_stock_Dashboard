import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.config import settings
from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)


class NewsService:
    def __init__(self):
        self.news_api_key = settings.NEWS_API_KEY
        self.finnhub_api_key = settings.FINNHUB_API_KEY

    def fetch_company_news(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetches news articles related to the specified symbol.
        Tries Finnhub first, falls back to NewsAPI, and finally defaults to yfinance news feed.
        """
        news_items = []

        # 1. Try Finnhub if API key is present
        if (
            self.finnhub_api_key
            and self.finnhub_api_key != "mock_finnhub_api_key_for_testing"
        ):
            try:
                # Get news from the last 7 days
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

                # yfinance symbol might contain .NS/ .BO, but Finnhub uses standard symbols or exchange suffixes
                # Finnhub handles US symbols best, but we clean Indian symbols to see if it responds
                clean_symbol = symbol.replace(".NS", "").replace(".BO", "")
                url = f"https://finnhub.io/api/v1/company-news?symbol={clean_symbol}&from={start_date}&to={end_date}&token={self.finnhub_api_key}"

                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    for item in data:
                        news_items.append(
                            {
                                "title": item.get("headline", ""),
                                "summary": item.get("summary", ""),
                                "url": item.get("url", ""),
                                "source": item.get("source", "Finnhub"),
                                "published_at": datetime.fromtimestamp(
                                    item.get(
                                        "datetime", int(datetime.now().timestamp())
                                    )
                                ).isoformat(),
                            }
                        )
                    if news_items:
                        logger.info(
                            f"Successfully fetched {len(news_items)} articles from Finnhub for {symbol}"
                        )
                        return news_items
            except Exception as e:
                logger.error(f"Finnhub API news fetch failed for {symbol}: {e}")

        # 2. Try NewsAPI if API key is present
        if self.news_api_key and self.news_api_key != "mock_news_api_key_for_testing":
            try:
                # Search NewsAPI using the company name or symbol
                # For Indian equities, search for the symbol or company name
                query = symbol.replace(".NS", "").replace(".BO", "")
                url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&pageSize=10&apiKey={self.news_api_key}"

                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    articles = data.get("articles", [])
                    for article in articles:
                        news_items.append(
                            {
                                "title": article.get("title", ""),
                                "summary": article.get("description", ""),
                                "url": article.get("url", ""),
                                "source": article.get("source", {}).get(
                                    "name", "NewsAPI"
                                ),
                                "published_at": article.get("publishedAt", ""),
                            }
                        )
                    if news_items:
                        logger.info(
                            f"Successfully fetched {len(news_items)} articles from NewsAPI for {symbol}"
                        )
                        return news_items
            except Exception as e:
                logger.error(f"NewsAPI fetch failed for {symbol}: {e}")

        # 3. Fallback to yfinance news feed (resilient, no api key required)
        try:
            logger.info(f"Using yfinance news feed fallback for {symbol}")
            ticker = MarketDataService.get_ticker(symbol)
            yf_news = ticker.news
            if yf_news:
                for item in yf_news:
                    # Handle new nested content schema vs old flat schema
                    content = item.get("content", item)

                    # Resolve publication time/date
                    pub_date = ""
                    if "pubDate" in content:
                        pub_date = content["pubDate"]
                    elif "providerPublishTime" in item:
                        pub_time = item["providerPublishTime"]
                        pub_date = datetime.fromtimestamp(pub_time).isoformat()
                    else:
                        pub_date = datetime.now().isoformat()

                    title = content.get("title", "")
                    summary = (
                        content.get("summary") or content.get("description") or title
                    )

                    # Resolve URL link
                    url = ""
                    if "canonicalUrl" in content and isinstance(
                        content["canonicalUrl"], dict
                    ):
                        url = content["canonicalUrl"].get("url", "")
                    elif "clickThroughUrl" in content and isinstance(
                        content["clickThroughUrl"], dict
                    ):
                        url = content["clickThroughUrl"].get("url", "")
                    else:
                        url = content.get("link", "")

                    # Resolve provider/source
                    source = "yfinance"
                    if "provider" in content:
                        if isinstance(content["provider"], dict):
                            source = content["provider"].get("displayName", "yfinance")
                        else:
                            source = str(content["provider"])
                    else:
                        source = item.get("publisher", "yfinance")

                    news_items.append(
                        {
                            "title": title,
                            "summary": summary,
                            "url": url,
                            "source": source,
                            "published_at": pub_date,
                        }
                    )
                logger.info(
                    f"Successfully fetched {len(news_items)} articles from yfinance for {symbol}"
                )
                return news_items
        except Exception as e:
            logger.error(f"yfinance news feed fallback failed for {symbol}: {e}")

        return []
