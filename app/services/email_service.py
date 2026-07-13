import smtplib
import hashlib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models.alert import Alert

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, db: Session):
        self.db = db
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.to_email = settings.ALERT_RECEIVER_EMAIL

    def generate_alert_hash(self, symbol: str, event_type: str, date_str: str) -> str:
        """
        Creates a unique hash for deduplication based on symbol, event type, and date.
        """
        raw_str = f"{symbol}_{event_type}_{date_str}".upper()
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def is_duplicate_alert(self, alert_hash: str) -> bool:
        """
        Checks if an alert with the same hash has already been dispatched.
        """
        existing = self.db.query(Alert).filter(Alert.alert_hash == alert_hash).first()
        return existing is not None

    def send_email(self, subject: str, html_content: str) -> bool:
        """
        Dispatches an HTML email using SMTP. Falls back gracefully if host/port is missing or fails.
        """
        if (
            not self.smtp_user
            or not self.smtp_password
            or self.smtp_user.startswith("mock_")
        ):
            logger.warning(
                f"SMTP credentials not configured. Skipping email dispatch for: {subject}"
            )
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = self.to_email
            msg.attach(MIMEText(html_content, "html"))

            # Standard SMTP connection with STARTTLS
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, self.to_email, msg.as_string())

            logger.info(f"Email successfully dispatched: {subject}")
            return True
        except Exception as e:
            logger.error(f"SMTP email dispatch failed: {e}")
            return False

    def trigger_material_alert(
        self,
        symbol: str,
        event_type: str,
        severity: str,
        summary: str,
        market_impact: str,
        suggested_action: str,
        confidence_score: Optional[float] = None,
        key_risks: str = "N/A",
        sources: str = "yfinance",
        ai_recommendation_id: Optional[int] = None,
    ) -> bool:
        """
        Processes a material alert, checks for duplicate alerts, stores it in the database,
        and dispatches an HTML email notification.
        """
        # Deduplicate using date string to prevent duplicate alerts within the same calendar day
        date_str = datetime.now().strftime("%Y-%m-%d")
        alert_hash = self.generate_alert_hash(symbol, event_type, date_str)

        if self.is_duplicate_alert(alert_hash):
            logger.info(
                f"Duplicate alert detected for {symbol} - {event_type} on {date_str}. Suppressing notification."
            )
            return False

        # Store alert in DB first to ensure log integrity
        db_alert = Alert(
            symbol=symbol,
            event_type=event_type,
            severity=severity,
            summary=summary,
            market_impact=market_impact,
            suggested_action=suggested_action,
            confidence_score=confidence_score,
            key_risks=key_risks,
            sources=sources,
            alert_hash=alert_hash,
        )
        self.db.add(db_alert)
        try:
            self.db.commit()
            self.db.refresh(db_alert)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to log alert to database: {e}")
            return False

        # Format HTML Newsletter
        subject = f"[{severity.upper()} IMPACT] {event_type} Alert: {symbol}"
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f6f9;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-top: 5px solid {'#e74c3c' if severity.upper() == 'HIGH' else '#f39c12' if severity.upper() == 'MEDIUM' else '#3498db'};">
                    <h2 style="color: #2c3e50; margin-top: 0;">Material Event Alert: {symbol}</h2>
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                        <tr style="background-color: #f8f9fa;">
                            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #eee; width: 35%;">Stock</td>
                            <td style="padding: 10px; border-bottom: 1px solid #eee;">{symbol}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #eee;">Event</td>
                            <td style="padding: 10px; border-bottom: 1px solid #eee;">{event_type}</td>
                        </tr>
                        <tr style="background-color: #f8f9fa;">
                            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #eee;">Severity</td>
                            <td style="padding: 10px; border-bottom: 1px solid #eee; color: {'#e74c3c' if severity.upper() == 'HIGH' else '#f39c12'}; font-weight: bold;">{severity.upper()}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #eee;">Confidence Score</td>
                            <td style="padding: 10px; border-bottom: 1px solid #eee;">{f"{confidence_score}%" if confidence_score else 'N/A'}</td>
                        </tr>
                    </table>
                    
                    <h3 style="color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px;">Event Summary</h3>
                    <p style="color: #34495e; line-height: 1.6;">{summary}</p>
                    
                    <h3 style="color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px;">Market Impact</h3>
                    <p style="color: #34495e; line-height: 1.6;">{market_impact}</p>
                    
                    <h3 style="color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px;">Suggested Action</h3>
                    <p style="color: #27ae60; font-weight: bold; line-height: 1.6;">{suggested_action}</p>

                    <h3 style="color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px;">Key Risks</h3>
                    <p style="color: #7f8c8d; line-height: 1.6;">{key_risks}</p>

                    <h3 style="color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px;">Sources Cited</h3>
                    <p style="color: #7f8c8d; line-height: 1.6; font-size: 13px;">{sources}</p>
                    
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0 20px 0;">
                    <p style="font-size: 11px; color: #95a5a6; text-align: center;">Equity Stock Monitoring and Investment Intelligence System. Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.</p>
                </div>
            </body>
        </html>
        """
        # Dispatch
        self.send_email(subject, html)
        return True
