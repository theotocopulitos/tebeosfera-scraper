#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
TebeoSfera Standalone Scraper

A standalone script to scrape comic metadata from tebeosfera.com
and generate ComicInfo.xml files for Spanish comics.

Usage:
    python tebeosfera_scraper.py search "Thorgal"
    python tebeosfera_scraper.py issue "leyendas_de_los_otori_2021_tengu_5"
    python tebeosfera_scraper.py series "thorgal_1977_rosinski"
    python tebeosfera_scraper.py inject "comic.cbz" "issue_slug"

@author: Comic Scraper Enhancement Project
'''

import sys
import os
import argparse
import json

# Add src/py to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'py'))

try:
    from database.tebeosfera.tbdb import TebeoSferaDB
    from comicinfo_xml import ComicInfoGenerator
    import zipfile
    import tempfile
    import shutil
except ImportError as e:
    print("Error importing modules: {0}".format(e))
    print("Make sure all required modules are in src/py/")
    sys.exit(1)


class TebeoSferaScraper(object):
    '''Main scraper class'''

    def __init__(self):
        '''Initialize the scraper'''
        self.db = TebeoSferaDB()
        self.xml_generator = ComicInfoGenerator()

    def search_series(self, search_terms):
        '''
        Search for series matching the search terms.

        search_terms: String with search keywords
        Returns: List of series dictionaries
        '''
        print("Searching for: {0}".format(search_terms))
        series_list = self.db.search_series(search_terms)

        results = []
        for series_ref in series_list:
            result = {
                'key': series_ref.series_key,
                'name': series_ref.series_name_s,
                'year': series_ref.volume_year_n if series_ref.volume_year_n > 0 else None,
                'publisher': series_ref.publisher_s,
                'issue_count': series_ref.issue_count_n
            }
            results.append(result)

        return results

    def get_series_issues(self, series_key):
        '''
        Get all issues for a series.

        series_key: Series slug/key
        Returns: List of issue dictionaries
        '''
        print("Getting issues for series: {0}".format(series_key))

        from database.dbmodels import SeriesRef
        series_ref = SeriesRef(
            series_key=series_key,
            series_name_s=series_key,
            volume_year_n=-1,
            publisher_s='',
            issue_count_n=0,
            thumb_url_s=None
        )

        issue_list = self.db.query_series_issues(series_ref)

        results = []
        for issue_ref in issue_list:
            result = {
                'key': issue_ref.issue_key,
                'number': issue_ref.issue_num_s,
                'title': issue_ref.title_s
            }
            results.append(result)

        return results

    def get_issue_details(self, issue_key):
        '''
        Get detailed information for an issue.

        issue_key: Issue slug/key
        Returns: Dictionary with issue details
        '''
        print("Getting details for issue: {0}".format(issue_key))

        from database.dbmodels import IssueRef
        issue_ref = IssueRef(
            issue_num_s="1",
            issue_key=issue_key,
            title_s="",
            thumb_url_s=None
        )

        issue = self.db.query_issue_details(issue_ref)
        if not issue:
            return None

        # Convert Issue object to dictionary
        result = {
            'key': issue.issue_key,
            'series': issue.series_name_s or issue.collection_s,
            'number': issue.issue_num_s,
            'title': issue.title_s,
            'publisher': issue.publisher_s,
            'year': issue.pub_year_n if issue.pub_year_n > 0 else None,
            'month': issue.pub_month_n if issue.pub_month_n > 0 else None,
            'day': issue.pub_day_n if issue.pub_day_n > 0 else None,
            'summary': issue.summary_s,
            'writers': issue.writers_sl,
            'pencillers': issue.pencillers_sl,
            'inkers': issue.inkers_sl,
            'colorists': issue.colorists_sl,
            'letterers': issue.letterers_sl,
            'cover_artists': issue.cover_artists_sl,
            'translators': issue.translators_sl,
            'isbn': issue.isbn_s,
            'price': issue.price_s,
            'format': issue.format_s,
            'binding': issue.binding_s,
            'dimensions': issue.dimensions_s,
            'page_count': issue.page_count_n if issue.page_count_n > 0 else None,
            'color': issue.color_s,
            'language': issue.language_s,
            'origin_title': issue.origin_title_s,
            'origin_publisher': issue.origin_publisher_s,
            'origin_country': issue.origin_country_s,
            'collection': issue.collection_s,
            'genres': issue.crossovers_sl,
            'characters': issue.characters_sl,
            'images': issue.image_urls_sl,
            'webpage': issue.webpage_s
        }

        return result

    def generate_comicinfo_xml(self, issue_key, output_file=None):
        '''
        Generate ComicInfo.xml for an issue.

        issue_key: Issue slug/key
        output_file: Path to save XML file (optional)
        Returns: XML string
        '''
        print("Generating ComicInfo.xml for: {0}".format(issue_key))

        from database.dbmodels import IssueRef
        issue_ref = IssueRef(
            issue_num_s="1",
            issue_key=issue_key,
            title_s="",
            thumb_url_s=None
        )

        issue = self.db.query_issue_details(issue_ref)
        if not issue:
            print("ERROR: Could not fetch issue details")
            return None

        # Create comic_data dictionary for XML generator
        comic_data = {
            'series': issue.series_name_s or issue.collection_s,
            'number': issue.issue_num_s,
            'title': issue.title_s,
            'summary': issue.summary_s,
            'publisher': issue.publisher_s,
            'year': issue.pub_year_n if issue.pub_year_n > 0 else None,
            'month': issue.pub_month_n if issue.pub_month_n > 0 else None,
            'day': issue.pub_day_n if issue.pub_day_n > 0 else None,
            'writer': issue.writers_sl,
            'penciller': issue.pencillers_sl,
            'inker': issue.inkers_sl,
            'colorist': issue.colorists_sl,
            'letterer': issue.letterers_sl,
            'cover_artist': issue.cover_artists_sl,
            'translator': issue.translators_sl,
            'characters': issue.characters_sl,
            'genre': ', '.join(issue.crossovers_sl) if issue.crossovers_sl else None,
            'web': issue.webpage_s,
            'isbn': issue.isbn_s,
            'price': issue.price_s,
            'format': issue.format_s,
            'binding': issue.binding_s,
            'dimensions': issue.dimensions_s,
            'page_count': issue.page_count_n if issue.page_count_n > 0 else None,
            'original_title': issue.origin_title_s,
            'original_publisher': issue.origin_publisher_s,
            'collection': issue.collection_s,
            'language_iso': 'es'  # Spanish by default
        }

        # Detect if black and white
        if issue.color_s:
            if 'B/N' in issue.color_s or 'BLANCO Y NEGRO' in issue.color_s.upper():
                comic_data['black_and_white'] = 'Yes'
            else:
                comic_data['black_and_white'] = 'No'

        # Count
        if issue.issue_count_n > 0:
            comic_data['count'] = issue.issue_count_n

        # Volume
        if issue.volume_year_n > 0:
            comic_data['volume'] = issue.volume_year_n

        # Generate XML
        xml_content = self.xml_generator.generate_xml(comic_data)

        # Save to file if requested
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            print("ComicInfo.xml saved to: {0}".format(output_file))

        return xml_content

    def inject_comicinfo_to_cbz(self, cbz_path, issue_key):
        '''
        Inject ComicInfo.xml into a CBZ file.

        cbz_path: Path to CBZ file
        issue_key: Issue slug/key
        Returns: True if successful, False otherwise
        '''
        print("Injecting ComicInfo.xml into: {0}".format(cbz_path))

        # Check if file exists
        if not os.path.exists(cbz_path):
            print("ERROR: File not found: {0}".format(cbz_path))
            return False

        # Check if file is a zip
        if not zipfile.is_zipfile(cbz_path):
            print("ERROR: File is not a valid ZIP/CBZ: {0}".format(cbz_path))
            return False

        # Generate ComicInfo.xml content
        xml_content = self.generate_comicinfo_xml(issue_key)
        if not xml_content:
            return False

        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        temp_cbz = os.path.join(temp_dir, 'temp.cbz')

        try:
            # Extract existing CBZ
            with zipfile.ZipFile(cbz_path, 'r') as zip_in:
                # Copy all files except ComicInfo.xml (if it exists)
                with zipfile.ZipFile(temp_cbz, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                    for item in zip_in.infolist():
                        if item.filename != 'ComicInfo.xml':
                            data = zip_in.read(item.filename)
                            zip_out.writestr(item, data)

                    # Add new ComicInfo.xml
                    zip_out.writestr('ComicInfo.xml', xml_content.encode('utf-8'))

            # Replace original file
            shutil.move(temp_cbz, cbz_path)
            print("SUCCESS: ComicInfo.xml injected into {0}".format(cbz_path))
            return True

        except Exception as e:
            print("ERROR: Failed to inject ComicInfo.xml: {0}".format(e))
            return False

        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

    def close(self):
        '''Close database connections'''
        self.db.close()


def main():
    '''Main entry point'''
    parser = argparse.ArgumentParser(
        description='TebeoSfera Scraper - Scrape Spanish comic metadata and generate ComicInfo.xml',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Search for a series:
    python tebeosfera_scraper.py search "Thorgal"

  Get issues from a series:
    python tebeosfera_scraper.py series "leyendas_de_los_otori_2021_tengu"

  Get details for an issue:
    python tebeosfera_scraper.py issue "leyendas_de_los_otori_2021_tengu_5"

  Generate ComicInfo.xml:
    python tebeosfera_scraper.py xml "leyendas_de_los_otori_2021_tengu_5" -o ComicInfo.xml

  Inject ComicInfo.xml into CBZ:
    python tebeosfera_scraper.py inject "comic.cbz" "leyendas_de_los_otori_2021_tengu_5"
        '''
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search for series')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Series command
    series_parser = subparsers.add_parser('series', help='Get issues from a series')
    series_parser.add_argument('series_key', help='Series slug/key')
    series_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Issue command
    issue_parser = subparsers.add_parser('issue', help='Get issue details')
    issue_parser.add_argument('issue_key', help='Issue slug/key')
    issue_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # XML command
    xml_parser = subparsers.add_parser('xml', help='Generate ComicInfo.xml')
    xml_parser.add_argument('issue_key', help='Issue slug/key')
    xml_parser.add_argument('-o', '--output', help='Output file path')

    # Inject command
    inject_parser = subparsers.add_parser('inject', help='Inject ComicInfo.xml into CBZ')
    inject_parser.add_argument('cbz_file', help='Path to CBZ file')
    inject_parser.add_argument('issue_key', help='Issue slug/key')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Create scraper
    scraper = TebeoSferaScraper()

    try:
        if args.command == 'search':
            results = scraper.search_series(args.query)
            if args.json:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print("\nFound {0} series:\n".format(len(results)))
                for i, result in enumerate(results, 1):
                    print("{0}. {1}".format(i, result['name']))
                    print("   Key: {0}".format(result['key']))
                    if result.get('year'):
                        print("   Year: {0}".format(result['year']))
                    if result.get('publisher'):
                        print("   Publisher: {0}".format(result['publisher']))
                    print()

        elif args.command == 'series':
            results = scraper.get_series_issues(args.series_key)
            if args.json:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print("\nFound {0} issues:\n".format(len(results)))
                for i, result in enumerate(results, 1):
                    print("{0}. #{1} - {2}".format(i, result['number'], result['title']))
                    print("   Key: {0}".format(result['key']))
                    print()

        elif args.command == 'issue':
            result = scraper.get_issue_details(args.issue_key)
            if result:
                if args.json:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    print("\nIssue Details:\n")
                    print("Series: {0}".format(result.get('series', 'N/A')))
                    print("Number: {0}".format(result.get('number', 'N/A')))
                    print("Title: {0}".format(result.get('title', 'N/A')))
                    print("Publisher: {0}".format(result.get('publisher', 'N/A')))
                    if result.get('year'):
                        date_str = str(result['year'])
                        if result.get('month'):
                            date_str += "-{0:02d}".format(result['month'])
                        if result.get('day'):
                            date_str += "-{0:02d}".format(result['day'])
                        print("Date: {0}".format(date_str))
                    if result.get('writers'):
                        print("Writers: {0}".format(', '.join(result['writers'])))
                    if result.get('pencillers'):
                        print("Artists: {0}".format(', '.join(result['pencillers'])))
                    if result.get('isbn'):
                        print("ISBN: {0}".format(result['isbn']))
                    if result.get('format'):
                        print("Format: {0}".format(result['format']))
                    if result.get('page_count'):
                        print("Pages: {0}".format(result['page_count']))
                    if result.get('summary'):
                        print("\nSummary:\n{0}".format(result['summary']))
            else:
                print("ERROR: Could not fetch issue details")
                return 1

        elif args.command == 'xml':
            xml_content = scraper.generate_comicinfo_xml(args.issue_key, args.output)
            if xml_content and not args.output:
                print(xml_content)
            elif not xml_content:
                return 1

        elif args.command == 'inject':
            success = scraper.inject_comicinfo_to_cbz(args.cbz_file, args.issue_key)
            return 0 if success else 1

        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        print("ERROR: {0}".format(e))
        import traceback
        traceback.print_exc()
        return 1
    finally:
        scraper.close()


if __name__ == '__main__':
    sys.exit(main())
