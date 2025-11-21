#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Test script for TebeoSfera Scraper

Simple tests to verify the scraper is working correctly.

@author: Comic Scraper Enhancement Project
'''

import sys
import os

# Add src/py to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'py'))

def test_connection():
    '''Test connection to tebeosfera.com'''
    print("\n=== Test 1: Connection ===")
    try:
        from database.tebeosfera.tbconnection import TebeoSferaConnection
        conn = TebeoSferaConnection()
        print("✓ Connection module loaded")

        # Try to fetch home page
        html = conn.get_page("/")
        if html and len(html) > 0:
            print("✓ Successfully fetched homepage ({0} bytes)".format(len(html)))
            return True
        else:
            print("✗ Failed to fetch homepage")
            return False
    except Exception as e:
        print("✗ Connection test failed: {0}".format(e))
        return False

def test_parser():
    '''Test HTML parser'''
    print("\n=== Test 2: Parser ===")
    try:
        from database.tebeosfera.tbparser import TebeoSferaParser
        parser = TebeoSferaParser()
        print("✓ Parser module loaded")

        # Test date parsing
        dates = [
            ("18-XI-2025", (18, 11, 2025)),
            ("20-04-1998", (20, 4, 1998)),
            ("1-I-2000", (1, 1, 2000))
        ]

        all_passed = True
        for date_str, expected in dates:
            result = parser._parse_date(date_str)
            if result == expected:
                print("✓ Date parsing: {0} -> {1}".format(date_str, result))
            else:
                print("✗ Date parsing failed: {0} (expected {1}, got {2})".format(
                    date_str, expected, result))
                all_passed = False

        return all_passed
    except Exception as e:
        print("✗ Parser test failed: {0}".format(e))
        import traceback
        traceback.print_exc()
        return False

def test_comicinfo_generator():
    '''Test ComicInfo.xml generator'''
    print("\n=== Test 3: ComicInfo.xml Generator ===")
    try:
        from comicinfo_xml import ComicInfoGenerator
        generator = ComicInfoGenerator()
        print("✓ Generator module loaded")

        # Create test data
        test_data = {
            'title': 'Test Issue',
            'series': 'Test Series',
            'number': '1',
            'publisher': 'Test Publisher',
            'year': 2025,
            'month': 1,
            'writer': ['Test Writer'],
            'penciller': ['Test Artist'],
            'isbn': '978-84-12345-67-8',
            'price': '15.00 EUR'
        }

        xml = generator.generate_xml(test_data)

        # Verify XML contains expected elements
        checks = [
            ('<Title>Test Issue</Title>', 'Title'),
            ('<Series>Test Series</Series>', 'Series'),
            ('<Number>1</Number>', 'Number'),
            ('<Publisher>Test Publisher</Publisher>', 'Publisher'),
            ('<Writer>Test Writer</Writer>', 'Writer'),
            ('ISBN: 978-84-12345-67-8', 'ISBN in Notes')
        ]

        all_passed = True
        for check_str, description in checks:
            if check_str in xml:
                print("✓ XML contains {0}".format(description))
            else:
                print("✗ XML missing {0}".format(description))
                all_passed = False

        return all_passed

    except Exception as e:
        print("✗ ComicInfo generator test failed: {0}".format(e))
        import traceback
        traceback.print_exc()
        return False

def test_database():
    '''Test database adapter'''
    print("\n=== Test 4: Database Adapter ===")
    try:
        from database.tebeosfera.tbdb import TebeoSferaDB
        db = TebeoSferaDB()
        print("✓ Database adapter loaded")

        # Note: We don't actually query tebeosfera.com in this test
        # to avoid making unnecessary requests

        print("✓ Database adapter initialized successfully")
        db.close()
        return True

    except Exception as e:
        print("✗ Database adapter test failed: {0}".format(e))
        import traceback
        traceback.print_exc()
        return False

def test_models():
    '''Test extended Issue model with Spanish fields'''
    print("\n=== Test 5: Extended Data Models ===")
    try:
        from database.dbmodels import Issue, IssueRef

        # Create test IssueRef
        issue_ref = IssueRef(
            issue_num_s="1",
            issue_key="test_issue_key",
            title_s="Test Issue",
            thumb_url_s=None
        )
        print("✓ IssueRef created")

        # Create Issue with Spanish fields
        issue = Issue(issue_ref)
        issue.isbn_s = "978-84-12345-67-8"
        issue.legal_deposit_s = "M-12345-2025"
        issue.price_s = "15.00 EUR"
        issue.format_s = "ÁLBUM"
        issue.binding_s = "CARTONÉ"
        issue.dimensions_s = "31 x 23 cm"
        issue.page_count_n = 80
        issue.translators_sl = ["Test Translator"]
        issue.origin_title_s = "Original Title"
        issue.origin_publisher_s = "Original Publisher"
        issue.language_s = "Traducción del francés"
        issue.collection_s = "Test Collection"

        # Verify fields
        checks = [
            (issue.isbn_s == "978-84-12345-67-8", "ISBN"),
            (issue.legal_deposit_s == "M-12345-2025", "Legal Deposit"),
            (issue.price_s == "15.00 EUR", "Price"),
            (issue.format_s == "ÁLBUM", "Format"),
            (issue.binding_s == "CARTONÉ", "Binding"),
            (issue.dimensions_s == "31 x 23 cm", "Dimensions"),
            (issue.page_count_n == 80, "Page Count"),
            (len(issue.translators_sl) == 1, "Translators"),
            (issue.origin_title_s == "Original Title", "Original Title"),
            (issue.language_s == "Traducción del francés", "Language")
        ]

        all_passed = True
        for check, description in checks:
            if check:
                print("✓ {0} field working".format(description))
            else:
                print("✗ {0} field failed".format(description))
                all_passed = False

        return all_passed

    except Exception as e:
        print("✗ Models test failed: {0}".format(e))
        import traceback
        traceback.print_exc()
        return False

def main():
    '''Run all tests'''
    print("=" * 60)
    print("TebeoSfera Scraper - Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Connection", test_connection()))
    results.append(("Parser", test_parser()))
    results.append(("ComicInfo Generator", test_comicinfo_generator()))
    results.append(("Database Adapter", test_database()))
    results.append(("Extended Models", test_models()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, result in results:
        status = "PASSED" if result else "FAILED"
        symbol = "✓" if result else "✗"
        print("{0} {1}: {2}".format(symbol, name, status))
        if result:
            passed += 1
        else:
            failed += 1

    print("\n{0}/{1} tests passed".format(passed, len(results)))

    if failed == 0:
        print("\n🎉 All tests passed! The scraper is ready to use.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
