"""
Email notification system for newsletter publication alerts.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional

from ..models import Newsletter, AIAnalysis
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

class EmailNotifier:
    """Sends email notifications to admin about newsletter status."""
    
    def __init__(self):
        """Initialize email notifier."""
        self.enabled = bool(Config.ADMIN_EMAIL and Config.SMTP_SERVER)
        if not self.enabled:
            logger.info("Email notifications disabled (missing ADMIN_EMAIL or SMTP_SERVER)")
        else:
            logger.info("Email notifier initialized")
    
    def notify_newsletter_ready(self, newsletter: Newsletter, analyses: List[AIAnalysis], publishing_summary: dict) -> bool:
        """
        Notify admin that newsletter is ready for publishing.
        
        Args:
            newsletter: Newsletter data
            analyses: AI analysis results
            publishing_summary: Publishing status summary
            
        Returns:
            True if notification sent successfully
        """
        if not self.enabled:
            logger.info("Email notification skipped (disabled)")
            return False
        
        try:
            subject = f"📧 Newsletter Ready: {newsletter.title} - {newsletter.date.strftime('%B %d, %Y')}"
            
            # Create email content
            html_content = self._create_notification_html(newsletter, analyses, publishing_summary)
            text_content = self._create_notification_text(newsletter, analyses, publishing_summary)
            
            # Send email
            success = self._send_email(subject, html_content, text_content)
            
            if success:
                logger.info("✅ Admin notification sent successfully")
            else:
                logger.error("❌ Failed to send admin notification")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending admin notification: {e}")
            return False
    
    def notify_pipeline_error(self, error_details: dict) -> bool:
        """
        Notify admin about pipeline errors.
        
        Args:
            error_details: Details about the error
            
        Returns:
            True if notification sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            subject = f"🚨 Newsletter Pipeline Error - {datetime.now().strftime('%Y-%m-%d')}"
            
            text_content = f"""
Newsletter Pipeline Error Alert

Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
Error: {error_details.get('error', 'Unknown error')}

Details:
{error_details.get('details', 'No additional details available')}

Please check the GitHub Actions logs for more information.
"""
            
            html_content = f"""
<h2>🚨 Newsletter Pipeline Error</h2>
<p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</p>
<p><strong>Error:</strong> {error_details.get('error', 'Unknown error')}</p>
<p><strong>Details:</strong> {error_details.get('details', 'No additional details available')}</p>
<p>Please check the GitHub Actions logs for more information.</p>
"""
            
            return self._send_email(subject, html_content, text_content)
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
            return False
    
    def _create_notification_html(self, newsletter: Newsletter, analyses: List[AIAnalysis], publishing_summary: dict) -> str:
        """Create HTML email content."""
        
        # Calculate stats
        avg_impact = sum(a.impact_score for a in analyses) / len(analyses) if analyses else 0
        total_sources = len(set().union(*[a.sources for a in analyses]))
        
        html = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: #1a365d; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .story-summary {{ background: #f7fafc; padding: 15px; margin: 10px 0; border-left: 4px solid #3182ce; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: #e2e8f0; padding: 15px; border-radius: 5px; text-align: center; flex: 1; }}
        .actions {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .button {{ background: #3182ce; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
        .footer {{ background: #f8f9fa; padding: 15px; font-size: 12px; color: #6c757d; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📧 Newsletter Ready for Publishing</h1>
        <p>{newsletter.title} - {newsletter.date.strftime('%B %d, %Y')}</p>
    </div>
    
    <div class="content">
        <div class="stats">
            <div class="stat">
                <h3>{len(analyses)}</h3>
                <p>Stories Selected</p>
            </div>
            <div class="stat">
                <h3>{avg_impact:.1f}/10</h3>
                <p>Avg Impact Score</p>
            </div>
            <div class="stat">
                <h3>{total_sources}</h3>
                <p>Unique Sources</p>
            </div>
        </div>
        
        <div class="actions">
            <h3>🎯 Next Steps</h3>
            <ol>
                <li>✅ <strong>GitHub Pages:</strong> Automatically published</li>
                <li>📱 <strong>Social Media:</strong> Share key insights (optional)</li>
            </ol>
        </div>

        <h3>📊 Publishing Status</h3>
        <ul>
            <li><strong>GitHub Pages:</strong> {publishing_summary.get('github_pages', 'Unknown')}</li>
            <li><strong>Legacy File:</strong> {publishing_summary.get('legacy_file', 'Generated')}</li>
        </ul>
        
        <h3>📰 Top Stories Preview</h3>
"""
        
        # Add story previews
        for i, analysis in enumerate(analyses[:3], 1):
            impact_emoji = "🔥" if analysis.impact_score >= 8 else "⚡" if analysis.impact_score >= 6 else "📊"
            
            html += f"""
        <div class="story-summary">
            <h4>{i}. {analysis.story_title} {impact_emoji} {analysis.impact_score}/10</h4>
            <p><strong>Why Important:</strong> {analysis.why_important[:100]}...</p>
        </div>
"""
        
        html += f"""
    </div>
    
    <div class="footer">
        <p>Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')} | Geopolitical Daily Newsletter System</p>
    </div>
</body>
</html>
"""
        
        return html
    
    def _create_notification_text(self, newsletter: Newsletter, analyses: List[AIAnalysis], publishing_summary: dict) -> str:
        """Create plain text email content."""
        
        avg_impact = sum(a.impact_score for a in analyses) / len(analyses) if analyses else 0
        
        text = f"""
📧 NEWSLETTER READY FOR PUBLISHING

{newsletter.title} - {newsletter.date.strftime('%B %d, %Y')}

QUICK STATS:
• Stories Selected: {len(analyses)}
• Average Impact Score: {avg_impact:.1f}/10

PUBLISHING STATUS:
✅ GitHub Pages: {publishing_summary.get('github_pages', 'Unknown')}
📊 Legacy File: Generated

NEXT STEPS:
1. ✅ GitHub Pages is live automatically
2. 📱 Share on social media (optional)

TOP STORIES:
"""
        
        for i, analysis in enumerate(analyses[:3], 1):
            impact_emoji = "🔥" if analysis.impact_score >= 8 else "⚡" if analysis.impact_score >= 6 else "📊"
            text += f"\n{i}. {analysis.story_title} {impact_emoji} {analysis.impact_score}/10"
        
        text += f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        
        return text
    
    def _send_email(self, subject: str, html_content: str, text_content: str) -> bool:
        """Send email using SMTP."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = Config.SMTP_FROM_EMAIL or Config.ADMIN_EMAIL
            msg['To'] = Config.ADMIN_EMAIL
            
            # Add text and HTML parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            if Config.SMTP_SERVER and Config.SMTP_PORT:
                with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                    if Config.SMTP_USE_TLS:
                        server.starttls()
                    
                    if Config.SMTP_USERNAME and Config.SMTP_PASSWORD:
                        server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
                    
                    server.send_message(msg)
                    return True
            else:
                logger.error("SMTP configuration incomplete")
                return False
                
        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return False