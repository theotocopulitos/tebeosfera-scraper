#!/usr/bin/env python3
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
import subprocess
import platform

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

    def __init__(self, show_covers=True):
        '''Initialize the scraper'''
        self.db = TebeoSferaDB()
        self.xml_generator = ComicInfoGenerator()
        self.show_covers = show_covers
        self.temp_dir = tempfile.mkdtemp(prefix='tebeosfera_')

    def _open_image(self, filepath):
        '''
        Open an image file with the system default viewer.

        filepath: Path to image file
        '''
        if not self.show_covers:
            return

        try:
            system = platform.system()
            if system == 'Darwin':  # macOS
                subprocess.call(['open', filepath])
            elif system == 'Windows':
                os.startfile(filepath)
            else:  # Linux and others
                subprocess.call(['xdg-open', filepath])
        except Exception as e:
            print("Could not open image: {0}".format(e))
            print("Image saved at: {0}".format(filepath))

    def _show_cover(self, ref_or_url, label="Cover"):
        '''
        Download and display a cover image.

        ref_or_url: IssueRef, SeriesRef, or URL string
        label: Label for the image file
        Returns: Path to saved image, or None
        '''
        if not self.show_covers:
            return None

        # Create safe filename from label
        safe_label = "".join(c for c in label if c.isalnum() or c in (' ', '-', '_'))
        filepath = os.path.join(self.temp_dir, "{0}.jpg".format(safe_label))

        # Download and save image
        if self.db.save_image(ref_or_url, filepath):
            print("  [Opening cover image...]")
            self._open_image(filepath)
            return filepath
        else:
            print("  [No cover image available]")
            return None

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

    def show_series_covers(self, series_list, interactive=False):
        '''
        Show covers for a list of series.

        series_list: List of SeriesRef objects or series dictionaries
        interactive: If True, prompt user to select which covers to view
        '''
        if not self.show_covers or not series_list:
            return

        print("\n=== Series Covers ===")
        for i, series in enumerate(series_list, 1):
            if hasattr(series, 'series_name_s'):
                # SeriesRef object
                name = series.series_name_s
                ref = series
            else:
                # Dictionary
                name = series.get('name', 'Unknown')
                # Create a simple object with thumb_url_s
                class RefWrapper:
                    def __init__(self, url):
                        self.thumb_url_s = url
                ref = RefWrapper(series.get('thumb_url'))

            if ref.thumb_url_s:
                print("{0}. {1}".format(i, name))
                if interactive:
                    response = raw_input("   View cover? (y/N): ")
                    if response.lower() == 'y':
                        self._show_cover(ref, "series_{0}".format(i))
                else:
                    # Auto-show only the first few
                    if i <= 3:
                        self._show_cover(ref, "series_{0}".format(i))

    def show_issue_covers(self, issue_list, interactive=False):
        '''
        Show covers for a list of issues.

        issue_list: List of IssueRef objects or issue dictionaries
        interactive: If True, prompt user to select which covers to view
        '''
        if not self.show_covers or not issue_list:
            return

        print("\n=== Issue Covers ===")
        for i, issue in enumerate(issue_list, 1):
            if hasattr(issue, 'title_s'):
                # IssueRef object
                name = issue.title_s or "Issue {0}".format(issue.issue_num_s)
                ref = issue
            else:
                # Dictionary
                name = issue.get('title', 'Unknown')
                class RefWrapper:
                    def __init__(self, url):
                        self.thumb_url_s = url
                ref = RefWrapper(issue.get('thumb_url'))

            if ref.thumb_url_s:
                print("{0}. {1}".format(i, name))
                if interactive:
                    response = raw_input("   View cover? (y/N): ")
                    if response.lower() == 'y':
                        self._show_cover(ref, "issue_{0}".format(i))
                else:
                    # Auto-show only the first few
                    if i <= 3:
                        self._show_cover(ref, "issue_{0}".format(i))

    def cleanup(self):
        '''Clean up temporary files'''
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except:
            pass

    def close(self):
        '''Close database connections and clean up'''
        self.db.close()
        self.cleanup()


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

    # Global options
    parser.add_argument('--no-covers', action='store_true',
                        help='Do not show cover images')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search for series')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--json', action='store_true', help='Output as JSON')
    search_parser.add_argument('--interactive', '-i', action='store_true',
                              help='Interactively choose which covers to view')

    # Series command
    series_parser = subparsers.add_parser('series', help='Get issues from a series')
    series_parser.add_argument('series_key', help='Series slug/key')
    series_parser.add_argument('--json', action='store_true', help='Output as JSON')
    series_parser.add_argument('--interactive', '-i', action='store_true',
                              help='Interactively choose which covers to view')

    # Issue command
    issue_parser = subparsers.add_parser('issue', help='Get issue details')
    issue_parser.add_argument('issue_key', help='Issue slug/key')
    issue_parser.add_argument('--json', action='store_true', help='Output as JSON')
    issue_parser.add_argument('--show-cover', action='store_true',
                            help='Show cover image')

    # XML command
    xml_parser = subparsers.add_parser('xml', help='Generate ComicInfo.xml')
    xml_parser.add_argument('issue_key', help='Issue slug/key')
    xml_parser.add_argument('-o', '--output', help='Output file path')
    xml_parser.add_argument('--show-cover', action='store_true',
                          help='Show cover image')

    # Inject command
    inject_parser = subparsers.add_parser('inject', help='Inject ComicInfo.xml into CBZ')
    inject_parser.add_argument('cbz_file', help='Path to CBZ file')
    inject_parser.add_argument('issue_key', help='Issue slug/key')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Create scraper (with covers enabled unless --no-covers)
    scraper = TebeoSferaScraper(show_covers=not args.no_covers)

    try:
        if args.command == 'search':
            # Get series results
            series_list = scraper.db.search_series(args.query)

            # Convert to dictionaries for display
            results = []
            for series_ref in series_list:
                result = {
                    'key': series_ref.series_key,
                    'name': series_ref.series_name_s,
                    'year': series_ref.volume_year_n if series_ref.volume_year_n > 0 else None,
                    'publisher': series_ref.publisher_s,
                    'issue_count': series_ref.issue_count_n,
                    'thumb_url': series_ref.thumb_url_s
                }
                results.append(result)

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
                    if result.get('thumb_url'):
                        print("   Cover: Available")
                    print()

                # Show covers
                if series_list:
                    interactive = hasattr(args, 'interactive') and args.interactive
                    scraper.show_series_covers(series_list, interactive=interactive)

        elif args.command == 'series':
            # Get issues from series
            from database.dbmodels import SeriesRef
            series_ref = SeriesRef(
                series_key=args.series_key,
                series_name_s=args.series_key,
                volume_year_n=-1,
                publisher_s='',
                issue_count_n=0,
                thumb_url_s=None
            )

            issue_list = scraper.db.query_series_issues(series_ref)

            # Convert to dictionaries
            results = []
            for issue_ref in issue_list:
                result = {
                    'key': issue_ref.issue_key,
                    'number': issue_ref.issue_num_s,
                    'title': issue_ref.title_s,
                    'thumb_url': issue_ref.thumb_url_s
                }
                results.append(result)

            if args.json:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print("\nFound {0} issues:\n".format(len(results)))
                for i, result in enumerate(results, 1):
                    print("{0}. #{1} - {2}".format(i, result['number'], result['title']))
                    print("   Key: {0}".format(result['key']))
                    if result.get('thumb_url'):
                        print("   Cover: Available")
                    print()

                # Show covers
                if issue_list:
                    interactive = hasattr(args, 'interactive') and args.interactive
                    scraper.show_issue_covers(issue_list, interactive=interactive)

        elif args.command == 'issue':
            result = scraper.get_issue_details(args.issue_key)
            if result:
                # Show cover if requested
                if hasattr(args, 'show_cover') and args.show_cover and result.get('images'):
                    scraper._show_cover(result['images'][0], "issue_cover")

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
                    if result.get('images'):
                        print("Cover URL: {0}".format(result['images'][0]))
                    if result.get('summary'):
                        print("\nSummary:\n{0}".format(result['summary']))
            else:
                print("ERROR: Could not fetch issue details")
                return 1

        elif args.command == 'xml':
            xml_content = scraper.generate_comicinfo_xml(args.issue_key, args.output)

            # Show cover if requested
            if hasattr(args, 'show_cover') and args.show_cover:
                from database.dbmodels import IssueRef
                issue_ref = IssueRef(
                    issue_num_s="1",
                    issue_key=args.issue_key,
                    title_s="",
                    thumb_url_s=None
                )
                issue = scraper.db.query_issue_details(issue_ref)
                if issue and issue.image_urls_sl:
                    scraper._show_cover(issue.image_urls_sl[0], "xml_cover")

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
