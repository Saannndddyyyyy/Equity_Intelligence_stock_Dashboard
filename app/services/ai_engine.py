import json
import logging
from datetime import date
from typing import Dict, Any, List
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)


class AIEngineService:
    def __init__(self):
        # Gracefully handle missing/mock keys
        self.api_key = settings.OPENAI_API_KEY
        if self.api_key and not self.api_key.startswith("mock_"):
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def get_current_horizon_month(self) -> int:
        """
        Calculates the current month index of the 9-month investment horizon.
        1 = Month 1, 9 = Month 9, >9 = Beyond Horizon.
        """
        start_date = settings.INVESTMENT_START_DATE
        today = date.today()
        # Calculate month difference
        months_diff = (
            (today.year - start_date.year) * 12 + (today.month - start_date.month) + 1
        )
        return max(1, months_diff)

    def get_horizon_rules_text(self, month: int) -> str:
        """
        Returns the instructions for the AI based on the current month of the horizon.
        """
        if 1 <= month <= 5:
            return (
                f"Currently in Month {month} of 9 (Months 1-5: GROWTH PHASE). "
                "Focus on identifying high-quality growth opportunities with strong fundamentals "
                "and positive catalysts. Recommend buying/accumulating if backed by solid evidence."
            )
        elif 6 <= month <= 7:
            return (
                f"Currently in Month {month} of 9 (Months 6-7: RISK REDUCTION PHASE). "
                "Focus on reducing portfolio risk. Recommend partial profit booking where appropriate. "
                "Be more conservative with new buys and emphasize capital preservation."
            )
        elif month == 8:
            return (
                "Currently in Month 8 of 9 (Month 8: EXIT PREPARATION PHASE). "
                "Focus on protecting gains. Formulate clear exit plans for every holding. "
                "Be extremely selective. New buy recommendations should be near-zero."
            )
        else:
            return (
                f"Currently in Month {month} of 9 (Month 9+: CAPITAL PRESERVATION & LIQUIDATION PHASE). "
                "Prioritize capital preservation. Systematically recommend liquidating (Sell/Strong Sell) "
                "all positions to prepare for full portfolio liquidation before the horizon ends."
            )

    def generate_recommendation(
        self,
        symbol: str,
        company_info: Dict[str, Any],
        live_quote: Dict[str, Any],
        technicals: Dict[str, Any],
        news_articles: List[Dict[str, Any]],
        trigger_event: str = "Scheduled Check",
    ) -> Dict[str, Any]:
        """
        Generates an evidence-based AI investment recommendation.
        Includes a fallback when the OpenAI client is unconfigured/mocked.
        """
        horizon_month = self.get_current_horizon_month()
        horizon_rules = self.get_horizon_rules_text(horizon_month)

        if not self.client:
            logger.warning(
                "OpenAI client not configured or mock key used. Skipping AI recommendation generation."
            )
            return {
                "success": False,
                "error": "AI recommendation engine is currently unavailable (OpenAI API key missing or invalid).",
            }

        # Format input data for the model
        news_summary = ""
        for i, art in enumerate(news_articles[:5]):
            news_summary += f"- [{art.get('source', 'News')}] {art.get('title')}: {art.get('summary')[:200]}...\n"

        prompt = f"""
You are a disciplined Quantitative Equity Analyst and Senior Portfolio Manager. Analyze the following Indian equity stock:

Symbol: {symbol}
Company Name: {company_info.get('company_name', symbol)}
Sector: {company_info.get('sector', 'Unknown')}
Current Price: {live_quote.get('price')}
High/Low: {live_quote.get('high')} / {live_quote.get('low')}
24h Volume: {live_quote.get('volume')}
20-day Average Volume: {live_quote.get('avg_volume')}
RSI: {technicals.get('rsi')}
MACD: {technicals.get('macd')}
MACD Signal: {technicals.get('macd_signal')}
SMA 20: {technicals.get('sma_20')}
SMA 50: {technicals.get('sma_50')}

Trigger Event: {trigger_event}

Recent Corporate News:
{news_summary if news_summary else "No recent news articles found."}

Investment Horizon Rules:
{horizon_rules}

Instructions:
1. Generate an investment analysis and recommendation tailored to the user's fixed 9-month investment timeline.
2. The recommendation MUST be one of: "Strong Buy", "Buy", "Accumulate", "Hold", "Reduce", "Sell", "Strong Sell".
3. Ground the analysis in objective evidence. Cite sources and data provided above.
4. Distinguish clearly between factual financial metrics and your qualitative analysis.
5. Provide a JSON response mapping strictly to the schema below.
"""

        system_message = """
You output investment analyses as a JSON object. The object must contain exactly these keys:
{
  "recommendation": "Strong Buy | Buy | Accumulate | Hold | Reduce | Sell | Strong Sell",
  "executive_summary": "string",
  "why_it_matters": "string",
  "historical_context": "string",
  "valuation_analysis": "string",
  "technical_analysis": "string",
  "risk_assessment": "string",
  "suggested_action": "string",
  "expected_holding_period": "string",
  "exit_strategy": "string",
  "confidence_score": 0-100,
  "supporting_evidence": "string",
  "sources": ["string"]
}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Highly cost-effective and capable of JSON outputs
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout=30,
            )

            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)
            result_json["success"] = True
            return result_json

        except Exception as e:
            logger.error(f"OpenAI API call failed for {symbol}: {e}")
            return {
                "success": False,
                "error": f"Failed to generate recommendation from OpenAI: {str(e)}",
            }
