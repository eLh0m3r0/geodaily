#!/usr/bin/env python3
"""
Dry run test script for sources.json to identify errors.
"""

import json
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
from pathlib import Path

class SourceTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.results = {
            'tier1_sources': [],
            'tier2_sources': [],
            'summary': {
                'total_sources': 0,
                'working': 0,
                'errors_403': 0,
                'errors_404': 0,
                'parsing_errors': 0,
                'other_errors': 0
            }
        }

    def load_sources(self, filepath):
        """Load sources from JSON file."""
        with open(filepath, 'r') as f:
            return json.load(f)

    def test_rss_source(self, source):
        """Test a single RSS source."""
        result = {
            'name': source['name'],
            'url': source['url'],
            'category': source['category'],
            'status': 'unknown',
            'error_type': None,
            'error_message': None
        }

        try:
            response = self.session.get(source['url'], timeout=10)
            result['status_code'] = response.status_code

            if response.status_code == 403:
                result['status'] = 'error'
                result['error_type'] = '403_forbidden'
                result['error_message'] = 'Access forbidden'
            elif response.status_code == 404:
                result['status'] = 'error'
                result['error_type'] = '404_not_found'
                result['error_message'] = 'URL not found'
            elif response.status_code >= 400:
                result['status'] = 'error'
                result['error_type'] = 'http_error'
                result['error_message'] = f'HTTP {response.status_code}'
            else:
                # Try to parse RSS
                feed = feedparser.parse(response.content)
                if feed.bozo and feed.bozo_exception:
                    result['status'] = 'error'
                    result['error_type'] = 'parsing_error'
                    result['error_message'] = str(feed.bozo_exception)
                elif not feed.entries:
                    result['status'] = 'error'
                    result['error_type'] = 'parsing_error'
                    result['error_message'] = 'No entries found in feed'
                else:
                    result['status'] = 'working'
                    result['entries_count'] = len(feed.entries)

        except requests.RequestException as e:
            result['status'] = 'error'
            result['error_type'] = 'network_error'
            result['error_message'] = str(e)
        except Exception as e:
            result['status'] = 'error'
            result['error_type'] = 'unknown_error'
            result['error_message'] = str(e)

        return result

    def test_web_source(self, source):
        """Test a single web scraping source."""
        result = {
            'name': source['name'],
            'url': source['url'],
            'category': source['category'],
            'method': source.get('method', 'basic'),
            'status': 'unknown',
            'error_type': None,
            'error_message': None
        }

        try:
            response = self.session.get(source['url'], timeout=10)
            result['status_code'] = response.status_code

            if response.status_code == 403:
                result['status'] = 'error'
                result['error_type'] = '403_forbidden'
                result['error_message'] = 'Access forbidden'
            elif response.status_code == 404:
                result['status'] = 'error'
                result['error_type'] = '404_not_found'
                result['error_message'] = 'URL not found'
            elif response.status_code >= 400:
                result['status'] = 'error'
                result['error_type'] = 'http_error'
                result['error_message'] = f'HTTP {response.status_code}'
            else:
                # Try to parse with selectors
                soup = BeautifulSoup(response.content, 'html.parser')
                selectors = source.get('selectors', {})

                if selectors:
                    container_selector = selectors.get('container', 'article')
                    containers = soup.select(container_selector)

                    if not containers:
                        result['status'] = 'error'
                        result['error_type'] = 'parsing_error'
                        result['error_message'] = f'No containers found with selector: {container_selector}'
                    else:
                        # Try to extract sample data
                        sample_container = containers[0]
                        title_selector = selectors.get('title', 'h2, h3, .title')
                        title_elem = sample_container.select_one(title_selector)

                        if not title_elem:
                            result['status'] = 'error'
                            result['error_type'] = 'parsing_error'
                            result['error_message'] = f'No title found with selector: {title_selector}'
                        else:
                            result['status'] = 'working'
                            result['containers_found'] = len(containers)
                else:
                    result['status'] = 'working'

        except requests.RequestException as e:
            result['status'] = 'error'
            result['error_type'] = 'network_error'
            result['error_message'] = str(e)
        except Exception as e:
            result['status'] = 'error'
            result['error_type'] = 'unknown_error'
            result['error_message'] = str(e)

        return result

    def run_tests(self, sources_data):
        """Run tests on all sources."""
        print("Starting dry run test of sources...\n")

        # Test Tier 1 sources (RSS)
        print("Testing Tier 1 sources (RSS feeds):")
        for source in sources_data['tier1_sources']:
            print(f"  Testing {source['name']}...")
            result = self.test_rss_source(source)
            self.results['tier1_sources'].append(result)

            if result['status'] == 'working':
                print(f"    ✅ Working ({result.get('entries_count', 0)} entries)")
            else:
                print(f"    ❌ {result['error_type']}: {result['error_message']}")

            time.sleep(1)  # Be respectful to servers

        print("\nTesting Tier 2 sources (Web scraping):")
        for source in sources_data['tier2_sources']:
            print(f"  Testing {source['name']}...")
            result = self.test_web_source(source)
            self.results['tier2_sources'].append(result)

            if result['status'] == 'working':
                containers = result.get('containers_found', 0)
                print(f"    ✅ Working ({containers} containers found)")
            else:
                print(f"    ❌ {result['error_type']}: {result['error_message']}")

            time.sleep(1)  # Be respectful to servers

        # Calculate summary
        all_results = self.results['tier1_sources'] + self.results['tier2_sources']
        self.results['summary']['total_sources'] = len(all_results)

        for result in all_results:
            if result['status'] == 'working':
                self.results['summary']['working'] += 1
            elif result['error_type'] == '403_forbidden':
                self.results['summary']['errors_403'] += 1
            elif result['error_type'] == '404_not_found':
                self.results['summary']['errors_404'] += 1
            elif result['error_type'] == 'parsing_error':
                self.results['summary']['parsing_errors'] += 1
            else:
                self.results['summary']['other_errors'] += 1

    def save_results(self, filepath):
        """Save test results to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nResults saved to {filepath}")

    def print_summary(self):
        """Print test summary."""
        summary = self.results['summary']
        print("\n" + "="*50)
        print("DRY RUN TEST SUMMARY")
        print("="*50)
        print(f"Total sources tested: {summary['total_sources']}")
        print(f"Working sources: {summary['working']} ({summary['working']/summary['total_sources']*100:.1f}%)")
        print(f"403 Forbidden errors: {summary['errors_403']}")
        print(f"404 Not Found errors: {summary['errors_404']}")
        print(f"Parsing errors: {summary['parsing_errors']}")
        print(f"Other errors: {summary['other_errors']}")

def main():
    tester = SourceTester()

    # Load sources
    sources_file = Path("sources.json")
    if not sources_file.exists():
        print("❌ sources.json not found!")
        return

    sources_data = tester.load_sources(sources_file)

    # Run tests
    tester.run_tests(sources_data)

    # Print summary
    tester.print_summary()

    # Save results
    tester.save_results("dry_run_results.json")

if __name__ == "__main__":
    main()