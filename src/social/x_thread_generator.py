#!/usr/bin/env python3
"""
X.com (Twitter) thread generator for GeoPolitical Daily.
Generates Czech threads from AI analyses with minimal API calls.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from ..config import Config
from ..models import AIAnalysis

logger = logging.getLogger(__name__)

# Unified prompt that handles everything in one Claude call
UNIFIED_THREAD_PROMPT = """
Jsi expert na geopolitiku a sociální média. Z této anglické analýzy vytvoř české vlákno pro X.com (Twitter).

PŮVODNÍ ANALÝZA:
Titul: {title}
Shrnutí: {summary}
Proč je to důležité: {why_it_matters}
Co ostatní přehlížejí: {what_others_miss}
Co sledovat: {what_to_watch}
Impact skóre: {impact_score}/10
Naléhavost: {urgency}/10
Typ obsahu: {content_type}

ÚKOL - vytvoř české vlákno:
1. 5-8 tweetů (každý MUSÍ mít max 280 znaků včetně mezer)
2. První tweet: Silný hook co zaujme české čtenáře (max 260 znaků pro prostor na engagement)
3. Prostřední tweety: Klíčové informace, kontext pro ČR/střední Evropu  
4. Poslední tweet: Závěr + výzva k akci
5. Použij 1-2 relevantní emoji na tweet (🔍📊🌍⚡💡🎯🚨📈)
6. Přidej 2-3 české hashtagy na konec posledního tweetu

FORMÁT ODPOVĚDI (přesně tento JSON):
{{
  "thread_title": "Krátký český název tématu (max 50 znaků)",
  "tweets": [
    {{
      "number": 1,
      "content": "Text tweetu včetně emoji",
      "char_count": 250
    }}
  ],
  "hashtags": ["#geopolitika", "#bezpečnost", "#analýza"],
  "estimated_engagement": 8.5,
  "main_topic": "one_word_topic_identifier"
}}

DŮLEŽITÉ:
- Piš PŘÍMO v češtině, profesionálně ale srozumitelně
- Každý tweet musí fungovat samostatně i jako část vlákna
- Použij čísla a fakta kde to dává smysl
- Zdůrazni dopady na ČR/EU když jsou relevantní
- Tweets čísluj ve formátu "1/7" na začátku
"""


class XThreadGenerator:
    """Generates X.com threads from AI analyses with minimal API calls"""
    
    def __init__(self):
        """Initialize thread generator"""
        self.output_dir = Config.PROJECT_ROOT / "docs" / "threads"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_thread_from_analysis(self, analysis: AIAnalysis, api_client) -> Optional[Dict]:
        """
        Generate X.com thread from AI analysis using Claude API
        
        Args:
            analysis: AIAnalysis object with story data
            api_client: Claude API client instance
            
        Returns:
            Thread data dict or None if generation fails
        """
        try:
            # Prepare prompt with analysis data
            # Create a summary from the available data
            summary = f"{analysis.why_important[:100]}..." if len(analysis.why_important) > 100 else analysis.why_important
            
            prompt = UNIFIED_THREAD_PROMPT.format(
                title=analysis.story_title,
                summary=summary,
                why_it_matters=analysis.why_important,
                what_others_miss=analysis.what_overlooked,
                what_to_watch=analysis.prediction,
                impact_score=analysis.impact_dimension_score,
                urgency=analysis.urgency_score,
                content_type=analysis.content_type.value if hasattr(analysis.content_type, 'value') else str(analysis.content_type)
            )
            
            # Single Claude API call for everything
            logger.info(f"Generating X.com thread for: {analysis.story_title[:50]}...")
            
            # Sonnet 5 rejects non-default sampling params (temperature), so
            # creativity is steered via the prompt instead.
            response = api_client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=4000,  # Headroom for adaptive thinking + thread text
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse response (skip thinking blocks on adaptive-thinking models)
            response_text = "".join(
                block.text for block in response.content
                if getattr(block, 'type', None) == 'text'
            )
            
            # Extract JSON from response
            try:
                # Try to parse as direct JSON first
                thread_data = json.loads(response_text)
            except json.JSONDecodeError:
                # If not direct JSON, try to extract it
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    thread_data = json.loads(json_match.group())
                else:
                    logger.error("Could not parse thread JSON from Claude response")
                    return None
            
            # Add metadata
            thread_data['source_analysis_id'] = analysis.story_title
            thread_data['generated_at'] = datetime.now().isoformat()
            
            # Validate character counts
            for tweet in thread_data.get('tweets', []):
                actual_length = len(tweet['content'])
                tweet['char_count'] = actual_length
                if actual_length > 280:
                    logger.warning(f"Tweet {tweet['number']} exceeds 280 chars: {actual_length}")
            
            logger.info(f"Successfully generated thread with {len(thread_data.get('tweets', []))} tweets")
            return thread_data
            
        except Exception as e:
            logger.error(f"Failed to generate thread: {str(e)}")
            return None
    
    def generate_mock_thread(self, analysis: AIAnalysis) -> Dict:
        """Generate mock thread for testing without API calls"""
        # Generate realistic tweet lengths
        title_short = analysis.story_title[:80] if len(analysis.story_title) > 80 else analysis.story_title
        
        tweet1 = f"1/5 🔍 ANALÝZA: {title_short}... Co to znamená pro ČR? 🧵"
        tweet2 = f"2/5 📊 Klíčová fakta: {analysis.why_important[:120]}..."
        tweet3 = f"3/5 ⚡ Co přehlížíme: {analysis.what_overlooked[:100]}..."
        tweet4 = f"4/5 🎯 Co sledovat: {analysis.prediction[:100]}..."
        tweet5 = "5/5 💡 Závěr: Situace se rychle vyvíjí. Sledujte náš newsletter pro detailní analýzy. #geopolitika #bezpečnost"
        
        return {
            "thread_title": f"Test: {analysis.story_title[:40]}",
            "tweets": [
                {"number": 1, "content": tweet1, "char_count": len(tweet1)},
                {"number": 2, "content": tweet2, "char_count": len(tweet2)},
                {"number": 3, "content": tweet3, "char_count": len(tweet3)},
                {"number": 4, "content": tweet4, "char_count": len(tweet4)},
                {"number": 5, "content": tweet5, "char_count": len(tweet5)}
            ],
            "hashtags": ["#geopolitika", "#bezpečnost", "#analýza"],
            "estimated_engagement": 7.5,
            "main_topic": "test_topic",
            "source_analysis_id": analysis.story_title,
            "generated_at": datetime.now().isoformat()
        }
    
    def export_html(self, threads: List[Dict], date_str: str = None) -> str:
        """
        Generate HTML preview of threads
        
        Args:
            threads: List of thread data dicts
            date_str: Optional date string for filename
            
        Returns:
            Path to generated HTML file
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X.com vlákna - {date_str}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f7f9fa;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #14171a;
            font-size: 24px;
            margin-bottom: 20px;
        }}
        .thread-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }}
        .thread {{
            background: white;
            border: 1px solid #e1e8ed;
            border-radius: 16px;
            padding: 20px;
        }}
        .thread-title {{
            font-size: 18px;
            font-weight: bold;
            color: #14171a;
            margin-bottom: 15px;
            border-bottom: 2px solid #1da1f2;
            padding-bottom: 10px;
        }}
        .tweet {{
            padding: 12px;
            border-bottom: 1px solid #e1e8ed;
            position: relative;
        }}
        .tweet:last-of-type {{
            border-bottom: none;
        }}
        .tweet-number {{
            color: #536471;
            font-weight: bold;
            font-size: 14px;
        }}
        .tweet-content {{
            color: #14171a;
            font-size: 15px;
            line-height: 1.4;
            margin: 8px 0;
            white-space: pre-wrap;
        }}
        .char-count {{
            position: absolute;
            right: 12px;
            top: 12px;
            color: #536471;
            font-size: 12px;
            background: #f7f9fa;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .char-count.warning {{
            color: #ff6600;
            font-weight: bold;
        }}
        .char-count.error {{
            color: #e0245e;
            font-weight: bold;
        }}
        .hashtags {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e1e8ed;
        }}
        .hashtag {{
            display: inline-block;
            color: #1da1f2;
            margin-right: 10px;
            font-size: 14px;
        }}
        .thread-meta {{
            margin-top: 10px;
            padding: 10px;
            background: #f7f9fa;
            border-radius: 8px;
            font-size: 13px;
            color: #536471;
        }}
        .copy-button {{
            background: #1da1f2;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 10px;
        }}
        .copy-button:hover {{
            background: #1a91da;
        }}
        .header-info {{
            background: #fff;
            padding: 20px;
            border-radius: 16px;
            margin-bottom: 20px;
            border: 1px solid #e1e8ed;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-info">
            <h1>🐦 X.com vlákna - GeoPolitical Daily</h1>
            <p style="color: #536471;">Vygenerováno: {datetime.now().strftime("%d.%m.%Y %H:%M")} | Počet vláken: {len(threads)}</p>
            <p style="color: #536471; font-size: 14px;">
                Náhled vláken pro manuální publikaci na X.com. Každé vlákno je optimalizováno pro maximální engagement českého publika.
            </p>
        </div>
        
        <div class="thread-grid">
"""
        
        for i, thread in enumerate(threads, 1):
            html += f"""
            <div class="thread">
                <div class="thread-title">
                    {i}. {thread.get('thread_title', 'Bez názvu')}
                </div>
"""
            
            tweets = thread.get('tweets', [])
            for tweet in tweets:
                char_count = tweet.get('char_count', 0)
                char_class = ''
                if char_count > 280:
                    char_class = 'error'
                elif char_count > 270:
                    char_class = 'warning'
                
                html += f"""
                <div class="tweet">
                    <span class="char-count {char_class}">{char_count}/280</span>
                    <div class="tweet-content">{tweet.get('content', '')}</div>
                </div>
"""
            
            # Add hashtags
            hashtags = thread.get('hashtags', [])
            if hashtags:
                html += '<div class="hashtags">'
                for tag in hashtags:
                    html += f'<span class="hashtag">{tag}</span>'
                html += '</div>'
            
            # Add metadata
            html += f"""
                <div class="thread-meta">
                    <div>📊 Odhadovaný engagement: {thread.get('estimated_engagement', 'N/A')}/10</div>
                    <div>🏷️ Téma: {thread.get('main_topic', 'N/A')}</div>
                    <div>⏰ Vygenerováno: {thread.get('generated_at', 'N/A')[:16]}</div>
                </div>
                <button class="copy-button" onclick="copyThread({i})">📋 Kopírovat vlákno</button>
            </div>
"""
        
        html += """
        </div>
    </div>
    
    <script>
        function copyThread(threadNum) {
            // TODO: Implement copy functionality
            alert('Funkce kopírování bude implementována v další verzi');
        }
    </script>
</body>
</html>"""
        
        # Save HTML
        output_path = self.output_dir / f"threads-{date_str}.html"
        output_path.write_text(html, encoding='utf-8')
        
        logger.info(f"Thread preview exported to: {output_path}")
        return str(output_path)
    
    def export_json(self, threads: List[Dict], date_str: str = None) -> str:
        """Export threads as JSON for potential API integration"""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        output_path = self.output_dir / f"threads-{date_str}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(threads, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Thread data exported to: {output_path}")
        return str(output_path)