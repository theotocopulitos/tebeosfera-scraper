'''
TebeoSfera Database Adapter

This module provides database-like access to tebeosfera.com, adapting
the HTML parsing results to the standard Issue and Series model classes.

@author: Comic Scraper Enhancement Project
'''

from dbmodels import Issue, IssueRef, SeriesRef
from tbconnection import TebeoSferaConnection, get_connection
from tbparser import TebeoSferaParser
from utils import sstr
import log


class TebeoSferaDB(object):
    '''
    Database adapter for tebeosfera.com that implements query methods
    compatible with the existing scraper architecture.
    '''

    def __init__(self):
        '''Initialize the TebeoSfera database adapter'''
        self.connection = get_connection()
        self.parser = TebeoSferaParser()

    def search_series(self, search_terms):
        '''
        Search for series matching the given search terms.

        search_terms: String with search keywords
        Returns: List of SeriesRef objects
        '''
        log.debug("Searching TebeoSfera for: ", search_terms)

        # Perform search
        html_content = self.connection.search(search_terms)
        if not html_content:
            log.debug("No results from TebeoSfera search")
            return []

        # Parse search results
        results = self.parser.parse_search_results(html_content)

        series_refs = []
        seen_slugs = set()

        # Convert collection results to SeriesRef objects
        for result in results:
            if result['type'] == 'collection':
                slug = result['slug']
                if slug not in seen_slugs:
                    seen_slugs.add(slug)

                    # Get thumbnail URL and ensure it's absolute
                    thumb_url = result.get('thumb_url')
                    if thumb_url and not thumb_url.startswith('http'):
                        thumb_url = 'https://www.tebeosfera.com' + thumb_url

                    # Create SeriesRef with collection slug as key
                    series_ref = SeriesRef(
                        series_key=slug,
                        series_name_s=result['title'],
                        volume_year_n=-1,  # Will be populated when querying series details
                        publisher_s='',
                        issue_count_n=0,
                        thumb_url_s=thumb_url
                    )
                    series_refs.append(series_ref)

        log.debug("Found {0} series in TebeoSfera".format(len(series_refs)))
        return series_refs

    def query_series_details(self, series_ref):
        '''
        Get detailed information about a series.

        series_ref: SeriesRef object
        Returns: Updated SeriesRef with more details, or None on error
        '''
        log.debug("Querying series details for: ", series_ref.series_key)

        # For now, return the series_ref as-is
        # In a full implementation, we would fetch the collection page
        # and extract additional details
        return series_ref

    def query_series_issues(self, series_ref):
        '''
        Get all issues for a given series.

        series_ref: SeriesRef object
        Returns: List of IssueRef objects
        '''
        log.debug("Querying issues for series: ", series_ref.series_key)

        # Fetch the collection page
        html_content = self.connection.get_collection_page(series_ref.series_key)
        if not html_content:
            log.debug("Could not fetch collection page")
            return []

        # Parse search results from collection page
        results = self.parser.parse_search_results(html_content)

        issue_refs = []

        # Convert issue results to IssueRef objects
        for result in results:
            if result['type'] == 'issue':
                # Extract issue number from slug if possible
                slug = result['slug']
                issue_num = self._extract_issue_number(slug)

                # Get thumbnail URL and ensure it's absolute
                thumb_url = result.get('thumb_url')
                if thumb_url and not thumb_url.startswith('http'):
                    thumb_url = 'https://www.tebeosfera.com' + thumb_url

                issue_ref = IssueRef(
                    issue_num_s=issue_num,
                    issue_key=slug,
                    title_s=result['title'],
                    thumb_url_s=thumb_url
                )
                issue_refs.append(issue_ref)

        log.debug("Found {0} issues in series".format(len(issue_refs)))
        return issue_refs

    def query_issue_details(self, issue_ref):
        '''
        Get detailed information about a specific issue.

        issue_ref: IssueRef object
        Returns: Issue object with full details, or None on error
        '''
        log.debug("Querying issue details for: ", issue_ref.issue_key)

        # Fetch the issue page
        html_content = self.connection.get_issue_page(issue_ref.issue_key)
        if not html_content:
            log.debug("Could not fetch issue page")
            return None

        # Parse the issue page
        metadata = self.parser.parse_issue_page(html_content)
        if not metadata:
            log.debug("Could not parse issue page")
            return None

        # Create Issue object from parsed metadata
        issue = self._create_issue_from_metadata(issue_ref, metadata)

        return issue

    def search_issues(self, search_terms):
        '''
        Search for issues matching the given search terms.

        search_terms: String with search keywords
        Returns: List of IssueRef objects
        '''
        log.debug("Searching TebeoSfera issues for: ", search_terms)

        # Perform search
        html_content = self.connection.search(search_terms)
        if not html_content:
            log.debug("No results from TebeoSfera search")
            return []

        # Parse search results
        results = self.parser.parse_search_results(html_content)

        issue_refs = []

        # Convert issue results to IssueRef objects
        for result in results:
            if result['type'] == 'issue':
                slug = result['slug']
                issue_num = self._extract_issue_number(slug)

                # Get thumbnail URL and ensure it's absolute
                thumb_url = result.get('thumb_url')
                if thumb_url and not thumb_url.startswith('http'):
                    thumb_url = 'https://www.tebeosfera.com' + thumb_url

                issue_ref = IssueRef(
                    issue_num_s=issue_num,
                    issue_key=slug,
                    title_s=result['title'],
                    thumb_url_s=thumb_url
                )
                issue_refs.append(issue_ref)

        log.debug("Found {0} issues in TebeoSfera".format(len(issue_refs)))
        return issue_refs

    def _create_issue_from_metadata(self, issue_ref, metadata):
        '''
        Create an Issue object from parsed metadata dictionary.

        issue_ref: IssueRef object
        metadata: Dictionary with parsed metadata
        Returns: Issue object
        '''
        issue = Issue(issue_ref)

        # Basic info
        issue.issue_num_s = metadata.get('number', issue_ref.issue_num_s)
        issue.title_s = metadata.get('title', '')
        issue.series_name_s = metadata.get('series', '')

        # Use series from metadata or from collection name
        if not issue.series_name_s and metadata.get('collection_s'):
            issue.series_name_s = metadata.get('collection_s', '')

        # Publishing info
        issue.publisher_s = metadata.get('publisher', '')
        issue.imprint_s = ''  # TebeoSfera doesn't clearly separate imprints

        # Dates
        if metadata.get('year'):
            issue.pub_year_n = metadata['year']
        if metadata.get('month'):
            issue.pub_month_n = metadata['month']
        if metadata.get('day'):
            issue.pub_day_n = metadata['day']

        # Volume year
        if metadata.get('volume_year'):
            issue.volume_year_n = metadata['volume_year']

        # Summary/description
        issue.summary_s = metadata.get('summary', '') or metadata.get('synopsis', '')

        # People
        issue.writers_sl = metadata.get('writers', [])
        issue.pencillers_sl = metadata.get('pencillers', [])
        issue.inkers_sl = metadata.get('inkers', [])
        issue.colorists_sl = metadata.get('colorists', [])
        issue.letterers_sl = metadata.get('letterers', [])
        issue.cover_artists_sl = metadata.get('cover_artists', [])
        issue.editors_sl = metadata.get('editors', [])

        # Spanish-specific fields
        issue.translators_sl = metadata.get('translators', [])
        issue.adapted_authors_sl = metadata.get('adapted_authors', [])
        issue.isbn_s = metadata.get('isbn', '')
        issue.legal_deposit_s = metadata.get('legal_deposit', '')

        # Price
        price = metadata.get('price', '')
        currency = metadata.get('currency', '')
        if price and currency:
            issue.price_s = "{0} {1}".format(price, currency)
        elif price:
            issue.price_s = price

        issue.format_s = metadata.get('format', '')
        issue.binding_s = metadata.get('binding', '')
        issue.dimensions_s = metadata.get('dimensions', '')

        if metadata.get('page_count'):
            issue.page_count_n = metadata['page_count']

        issue.color_s = metadata.get('color', '')
        issue.origin_title_s = metadata.get('origin_title', '')
        issue.origin_publisher_s = metadata.get('origin_publisher', '')
        issue.origin_country_s = metadata.get('origin_country', '')
        issue.language_s = metadata.get('language', '')

        # Collection info
        if metadata.get('series'):
            issue.collection_s = metadata['series']
        if metadata.get('collection_url'):
            issue.collection_url_s = metadata['collection_url']
        if metadata.get('count'):
            issue.issue_count_n = metadata['count']

        # Story elements
        issue.characters_sl = metadata.get('characters', [])

        # Genres (stored in crossovers for compatibility)
        if metadata.get('genres'):
            issue.crossovers_sl = metadata['genres']

        # Images
        issue.image_urls_sl = metadata.get('image_urls', [])

        # Webpage
        if metadata.get('page_url'):
            issue.webpage_s = metadata['page_url']
        else:
            issue.webpage_s = "https://www.tebeosfera.com/numeros/{0}.html".format(
                issue_ref.issue_key)

        return issue

    def _extract_issue_number(self, slug):
        '''
        Try to extract issue number from slug.

        slug: Issue slug (e.g., "thorgal_1977_rosinski_12")
        Returns: Issue number as string, or "1" if not found
        '''
        # Try to find a number at the end of the slug
        import re
        match = re.search(r'_(\d+)$', slug)
        if match:
            return match.group(1)

        # Default to "1" if we can't extract a number
        return "1"

    def query_image(self, ref_or_url):
        '''
        Download an image from tebeosfera.com.
        Compatible with the existing scraper architecture.

        ref_or_url: IssueRef, SeriesRef, or URL string
        Returns: Binary image data, or None on error
        '''
        # Extract URL from ref or use directly
        if hasattr(ref_or_url, 'thumb_url_s'):
            url = ref_or_url.thumb_url_s
        elif isinstance(ref_or_url, basestring):
            url = ref_or_url
        else:
            log.debug("Invalid ref or URL for image query")
            return None

        if not url:
            log.debug("No URL available for image")
            return None

        # Download the image
        return self.connection.download_image(url)

    def save_image(self, ref_or_url, filepath):
        '''
        Download and save an image to a file.

        ref_or_url: IssueRef, SeriesRef, or URL string
        filepath: Path where to save the image
        Returns: True if successful, False otherwise
        '''
        # Extract URL
        if hasattr(ref_or_url, 'thumb_url_s'):
            url = ref_or_url.thumb_url_s
        elif isinstance(ref_or_url, basestring):
            url = ref_or_url
        else:
            return False

        if not url:
            return False

        return self.connection.save_image(url, filepath)

    def close(self):
        '''Close the database connection'''
        if self.connection:
            self.connection.close()
