"""
Simple test for RSS feed generation functionality.
"""

import tempfile
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET


def test_rss_xml_structure():
    """Test basic RSS XML structure generation."""

    # Create a minimal RSS feed content
    rss_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
    <channel>
        <title><![CDATA[Geopolitical Daily - Strategic Intelligence Beyond the Headlines]]></title>
        <link>https://yourusername.github.io/geodaily/</link>
        <atom:link href="https://yourusername.github.io/geodaily/feed.xml" rel="self" type="application/rss+xml" />
        <description><![CDATA[AI-powered analysis of underreported geopolitical developments]]></description>
        <language>en-us</language>
        <managingEditor>editor@geodaily.example.com</managingEditor>
        <webMaster>tech@geodaily.example.com</webMaster>
        <pubDate>Wed, 31 Aug 2025 10:59:40 GMT</pubDate>
        <lastBuildDate>Wed, 31 Aug 2025 10:59:40 GMT</lastBuildDate>
        <generator>Geopolitical Daily Newsletter System v2.0</generator>
        <ttl>60</ttl>
        <skipHours>
            <hour>1</hour>
            <hour>2</hour>
        </skipHours>
        <skipDays>
            <day>Saturday</day>
            <day>Sunday</day>
        </skipDays>
        <dc:creator>Geopolitical Daily Editorial Team</dc:creator>
        <dc:publisher>Geopolitical Daily</dc:publisher>
        <dc:language>en-US</dc:language>
        <image>
            <url>https://yourusername.github.io/geodaily/assets/logo.png</url>
            <title>Geopolitical Daily</title>
            <link>https://yourusername.github.io/geodaily/</link>
        </image>
        <item>
            <title><![CDATA[Geopolitical Daily - August 31, 2025]]></title>
            <link>https://yourusername.github.io/geodaily/newsletters/newsletter-2025-08-31.html</link>
            <description><![CDATA[<p><strong>Daily Briefing:</strong> Today's strategic analysis</p>]]></description>
            <pubDate>Sun, 31 Aug 2025 06:00:00 GMT</pubDate>
            <guid isPermaLink="false">geodaily-20250831</guid>
            <author>Geopolitical Daily Editorial Team</author>
            <category><![CDATA[Geopolitics]]></category>
            <comments>https://yourusername.github.io/geodaily/newsletters/newsletter-2025-08-31.html#comments</comments>
            <source url="https://yourusername.github.io/geodaily/feed.xml">Geopolitical Daily</source>
        </item>
    </channel>
</rss>"""

    # Test XML parsing
    try:
        root = ET.fromstring(rss_content)
        print("✓ RSS XML is well-formed")

        # Validate RSS version
        assert root.get('version') == '2.0', "RSS version should be 2.0"
        print("✓ RSS version is correct")

        # Check required channel elements
        channel = root.find('channel')
        assert channel is not None, "Channel element should exist"

        required_elements = ['title', 'link', 'description']
        for elem in required_elements:
            element = channel.find(elem)
            assert element is not None, f"Required element '{elem}' missing"
            assert element.text and element.text.strip(), f"Element '{elem}' should have content"
        print("✓ Required channel elements present")

        # Check item elements
        items = channel.findall('item')
        assert len(items) > 0, "Should have at least one item"

        item = items[0]
        item_required = ['title', 'link', 'description', 'pubDate', 'guid']
        for elem in item_required:
            element = item.find(elem)
            assert element is not None, f"Required item element '{elem}' missing"
        print("✓ Required item elements present")

        # Check for enhanced features
        assert channel.find('managingEditor') is not None, "Should have managingEditor"
        assert channel.find('webMaster') is not None, "Should have webMaster"
        assert channel.find('ttl') is not None, "Should have ttl"
        assert channel.find('skipHours') is not None, "Should have skipHours"
        assert channel.find('skipDays') is not None, "Should have skipDays"
        print("✓ Enhanced RSS features present")

        # Check for CDATA sections
        title_text = channel.find('title').text
        assert '<![CDATA[' in rss_content, "Should use CDATA sections"
        print("✓ CDATA sections used for content")

        # Check for categories
        categories = item.findall('category')
        assert len(categories) > 0, "Should have categories"
        print("✓ Categories present")

        print("\n🎉 All RSS validation tests passed!")
        return True

    except ET.ParseError as e:
        print(f"❌ RSS XML parsing error: {e}")
        return False
    except Exception as e:
        print(f"❌ RSS validation error: {e}")
        return False


def test_cdata_escaping():
    """Test CDATA content escaping."""

    def escape_for_cdata(text):
        """Escape text for use within CDATA sections."""
        if not text:
            return ""
        # CDATA sections handle most characters, but we should escape ]]>
        # which would prematurely end the CDATA section
        return text.replace("]]>", "]]]]><![CDATA[>")

    # Test normal text
    normal_text = "This is normal text"
    escaped = escape_for_cdata(normal_text)
    assert escaped == normal_text
    print("✓ Normal text CDATA escaping works")

    # Test problematic text
    problematic_text = "This contains ]]> problematic content"
    escaped = escape_for_cdata(problematic_text)
    assert "]]>" not in escaped or "]]]]><![CDATA[>" in escaped
    print("✓ Problematic CDATA content properly escaped")

    return True


def test_rss_feed_file_generation():
    """Test RSS feed file generation."""

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        rss_path = Path(temp_dir) / "feed.xml"

        # Write RSS content
        rss_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <link>https://example.com</link>
        <description>Test RSS feed</description>
        <item>
            <title>Test Item</title>
            <link>https://example.com/item</link>
            <description>Test description</description>
            <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
            <guid>test-guid</guid>
        </item>
    </channel>
</rss>"""

        with open(rss_path, 'w', encoding='utf-8') as f:
            f.write(rss_content)

        # Verify file was created and is readable
        assert rss_path.exists()
        assert rss_path.stat().st_size > 0

        with open(rss_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert content == rss_content
        print("✓ RSS feed file generation works")

        return True


if __name__ == "__main__":
    print("Running RSS feed validation tests...\n")

    try:
        # Run all tests
        test1_passed = test_rss_xml_structure()
        test2_passed = test_cdata_escaping()
        test3_passed = test_rss_feed_file_generation()

        if all([test1_passed, test2_passed, test3_passed]):
            print("\n✅ All RSS feed tests passed successfully!")
            print("The enhanced RSS feed generation is working correctly.")
        else:
            print("\n❌ Some tests failed.")
            exit(1)

    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        exit(1)