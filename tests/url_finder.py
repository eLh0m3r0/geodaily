#!/usr/bin/env python3
"""
Script to find alternative URLs for sources with 403/404 errors.
"""

import requests
import feedparser
from urllib.parse import urlparse, urljoin
import time

class URLFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def test_url(self, url):
        """Test if URL is accessible and returns valid content."""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                # Try to parse as RSS
                feed = feedparser.parse(response.content)
                if not feed.bozo:
                    return {
                        'status': 'working',
                        'entries': len(feed.entries),
                        'status_code': response.status_code
                    }
                else:
                    return {
                        'status': 'parsing_error',
                        'error': str(feed.bozo_exception),
                        'status_code': response.status_code
                    }
            else:
                return {
                    'status': 'error',
                    'status_code': response.status_code
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def find_alternatives(self, base_url, name):
        """Try common alternative RSS URLs."""
        parsed = urlparse(base_url)
        domain = parsed.netloc
        path_parts = parsed.path.strip('/').split('/')

        alternatives = []

        # Common RSS URL patterns
        patterns = [
            f"https://{domain}/feed/",
            f"https://{domain}/rss/",
            f"https://{domain}/rss.xml",
            f"https://{domain}/feed.xml",
            f"https://{domain}/feeds/posts/default",
            f"https://{domain}/?feed=rss2",
            f"https://{domain}/rss/all.xml",
            f"https://{domain}/feed/rss/",
        ]

        # Add domain-specific patterns
        if 'politico' in domain:
            patterns.extend([
                f"https://{domain}/rss/world.xml",
                f"https://{domain}/rss/foreign.xml",
                f"https://{domain}/rss/international.xml"
            ])
        elif 'economist' in domain:
            patterns.extend([
                f"https://{domain}/feeds/rss.xml",
                f"https://{domain}/rss.xml"
            ])
        elif 'amnesty' in domain:
            patterns.extend([
                f"https://{domain}/en/rss/",
                f"https://{domain}/rss/news.xml"
            ])
        elif 'chathamhouse' in domain:
            patterns.extend([
                f"https://{domain}/feed/",
                f"https://{domain}/rss.xml"
            ])
        elif 'defenseone' in domain:
            patterns.extend([
                f"https://{domain}/feeds/rss/",
                f"https://{domain}/feed/"
            ])
        elif 'janes' in domain:
            patterns.extend([
                f"https://{domain}/feeds/rss/",
                f"https://{domain}/rss/defense.xml"
            ])
        elif 'ecfr' in domain:
            patterns.extend([
                f"https://{domain}/feed/",
                f"https://{domain}/rss/"
            ])
        elif 'dw.com' in domain:
            patterns.extend([
                f"https://{domain}/rss/xml/rss_en_uk",
                f"https://{domain}/rss/xml/rss_en_world"
            ])
        elif 'brookings' in domain:
            patterns.extend([
                f"https://{domain}/feed/?post_type=research",
                f"https://{domain}/feed/?cat=1"
            ])
        elif 'carnegie' in domain:
            patterns.extend([
                f"https://{domain}/feed/",
                f"https://{domain}/rss.xml"
            ])

        print(f"Testing alternative URLs for {name}...")

        for url in patterns:
            if url != base_url:  # Don't test the original failing URL
                result = self.test_url(url)
                if result['status'] == 'working':
                    print(f"  ✅ Found working URL: {url} ({result['entries']} entries)")
                    alternatives.append({
                        'url': url,
                        'entries': result['entries']
                    })
                time.sleep(0.5)  # Be respectful

        return alternatives

def main():
    finder = URLFinder()

    # Sources with 403 errors
    sources_403 = [
        ("War on the Rocks", "https://warontherocks.com/feed/"),
        ("Politico Foreign", "https://www.politico.com/rss/politics.xml"),
        ("Economist World Politics", "https://www.economist.com/world-politics/rss.xml"),
        ("Chatham House Research", "https://www.chathamhouse.org/rss/research"),
        ("Amnesty International", "https://www.amnesty.org/rss.xml")
    ]

    # Sources with 404 errors
    sources_404 = [
        ("Defense One RSS", "https://www.defenseone.com/rss.xml"),
        ("Jane's Defence", "https://www.janes.com/rss/"),
        ("European Council on Foreign Relations", "https://ecfr.eu/rss.xml"),
        ("Council on Foreign Relations Articles", "https://www.cfr.org/articles/"),
        ("Atlantic Council Articles", "https://www.atlanticcouncil.org/articles/")
    ]

    # Sources with parsing errors
    sources_parsing = [
        ("DW News", "https://rss.dw.com/xml/rss_en_all"),
        ("Brookings Institution", "https://www.brookings.edu/feed/"),
        ("Carnegie Endowment", "https://carnegieendowment.org/rss/")
    ]

    all_sources = sources_403 + sources_404 + sources_parsing

    results = {}

    for name, url in all_sources:
        print(f"\n=== {name} ===")
        alternatives = finder.find_alternatives(url, name)
        results[name] = {
            'original_url': url,
            'alternatives': alternatives
        }

    print("\n" + "="*50)
    print("SUMMARY OF ALTERNATIVE URLS FOUND")
    print("="*50)

    for name, data in results.items():
        print(f"\n{name}:")
        if data['alternatives']:
            for alt in data['alternatives']:
                print(f"  ✅ {alt['url']} ({alt['entries']} entries)")
        else:
            print("  ❌ No working alternatives found")

if __name__ == "__main__":
    main()