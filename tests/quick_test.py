#!/usr/bin/env python3
"""
Quick test for Reuters and AP to check if network issues are resolved.
"""

import requests
import feedparser

def test_source(name, url):
    print(f"Testing {name}...")
    try:
        response = requests.get(url, timeout=10)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            if feed.bozo:
                print(f"  ❌ Parsing error: {feed.bozo_exception}")
            else:
                print(f"  ✅ Working! {len(feed.entries)} entries")
        else:
            print(f"  ❌ HTTP {response.status_code}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    test_source("Reuters", "https://feeds.reuters.com/reuters/worldNews")
    test_source("AP", "https://feeds.apnews.com/apf-worldnews")