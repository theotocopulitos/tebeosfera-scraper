'''
TebeoSfera Database Adapter

This module provides database-like access to tebeosfera.com, adapting
the HTML parsing results to the standard Issue and Series model classes.

@author: Comic Scraper Enhancement Project
'''

from database.dbmodels import Issue, IssueRef, SeriesRef
from .tbconnection import TebeoSferaConnection, get_connection, build_issue_url
from .tbparser import TebeoSferaParser
from utils_compat import sstr, log


class TebeoSferaDB(object):
    '''
    Database adapter for tebeosfera.com that implements query methods
    compatible with the existing scraper architecture.
    '''

    def __init__(self, log_callback=None):
        '''
        Initialize the TebeoSfera database adapter
        
        Args:
            log_callback: Optional function to call for logging (takes a string message)
        '''
        self.connection = get_connection()
        self.parser = TebeoSferaParser(log_callback=log_callback)

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
            log.debug("No results from TebeoSfera search - HTML content is None")
            return []

        # Log HTML content info
        html_length = len(html_content) if html_content else 0
        log.debug("HTML content received: {0} bytes".format(html_length))
        
        # Save HTML to file for debugging
        if html_content:
            try:
                import tempfile
                import os
                debug_file = os.path.join(tempfile.gettempdir(), 'tebeosfera_search_debug.html')
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                log.debug("HTML saved to: {0}".format(debug_file))
            except Exception as e:
                log.debug("Could not save HTML debug file: {0}".format(str(e)))
        
        # Log a sample of the HTML to see what we're getting
        if html_content:
            #sample = html_content[:2000] if len(html_content) > 2000 else html_content
            #log.debug("HTML sample (first 2000 chars): ", sample[:2000])
            
            # Check for common patterns that indicate results
            has_numeros = '/numeros/' in html_content
            has_colecciones = '/colecciones/' in html_content
            has_results_div = 'resultados' in html_content.lower() or 'resultado' in html_content.lower()
            log.debug("HTML contains /numeros/: {0}, /colecciones/: {1}, 'resultados': {2}".format(
                has_numeros, has_colecciones, has_results_div))
            
            # Count actual occurrences
            numeros_count = html_content.count('/numeros/')
            colecciones_count = html_content.count('/colecciones/')
            log.debug("Count: /numeros/ appears {0} times, /colecciones/ appears {1} times".format(
                numeros_count, colecciones_count))

        # Parse search results
        results = self.parser.parse_search_results(html_content)
        log.debug("Parser found {0} total results (issues + collections)".format(len(results)))
        
        # Log breakdown by type
        issues_count = sum(1 for r in results if r.get('type') == 'issue')
        collections_count = sum(1 for r in results if r.get('type') == 'collection')
        sagas_count = sum(1 for r in results if r.get('type') == 'saga')
        log.debug("Breakdown: {0} issues, {1} collections, {2} sagas".format(
            issues_count, collections_count, sagas_count))
        
        # Log first few results for debugging
        if results:
            log.debug("First 5 results:")
            for i, result in enumerate(results[:5]):
                log.debug("  [{0}] type={1}, slug={2}, title={3}, series={4}".format(
                    i+1, result.get('type'), result.get('slug'), 
                    result.get('title', 'N/A')[:50], result.get('series_name', 'N/A')[:30]))

        series_refs = []
        
        # Process results - DON'T group issues, show each individually
        for result in results:
            slug = result.get('slug')
            result_type = result.get('type', 'collection')
            
            # Get thumbnail URL and ensure it's absolute
            thumb_url = result.get('thumb_url')
            if thumb_url and not thumb_url.startswith('http'):
                thumb_url = 'https://www.tebeosfera.com' + thumb_url
            image_url = result.get('image_url')
            if image_url and not image_url.startswith('http'):
                image_url = 'https://www.tebeosfera.com' + image_url
            
            if result_type in ['collection', 'saga']:
                # Collections and sagas are shown as-is (they are series/groups)
                series_name = result.get('series_name') or result.get('title', slug)
                series_key = slug
                issue_count = 0  # Unknown for collections/sagas
                
            elif result_type == 'issue':
                # Issues are shown individually with their full title
                # Use the FULL title from the result, not just the series name
                full_title = result.get('title', '')
                series_name = full_title if full_title else result.get('series_name', slug)
                series_key = slug  # Use the issue slug as the key
                issue_count = 1  # It's a single issue
            
            else:
                continue
            
            # Create SeriesRef for this result
            series_ref = SeriesRef(
                series_key=series_key,
                series_name_s=series_name,
                volume_year_n=-1,
                publisher_s='',
                issue_count_n=issue_count,
                thumb_url_s=thumb_url
            )
            # Set extended fields
            series_ref.type_s = result_type
            series_ref.extra_image_url = image_url or thumb_url
            series_refs.append(series_ref)

        log.debug("Found {0} series in TebeoSfera (from {1} results: {2} issues, {3} collections, {4} sagas)".format(
            len(series_refs), len(results),
            sum(1 for r in results if r.get('type') == 'issue'),
            sum(1 for r in results if r.get('type') == 'collection'),
            sum(1 for r in results if r.get('type') == 'saga')))
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

    def query_series_children(self, series_ref):
        '''
        Get all children for a given series/saga (collections, issues, or both).
        
        For sagas: returns both collections and issues
        For collections: returns issues only
        
        series_ref: SeriesRef object with type_s attribute indicating 'saga' or 'collection'
        Returns: Dictionary with 'collections' and 'issues' lists containing SeriesRef and IssueRef objects
        '''
        # Default to 'collection' if type_s is not set (defensive programming)
        # Collections are more common and the collection page fetch is the safer default
        series_type = getattr(series_ref, 'type_s', 'collection')
        series_key = getattr(series_ref, 'series_key', None)
        
        if not series_key:
            log.debug("ERROR: series_ref has no series_key attribute")
            return {'collections': [], 'issues': []}
        
        print(f"[DEBUG] === query_series_children called ===")
        print(f"[DEBUG] Series type: {series_type}")
        print(f"[DEBUG] Series key: {series_key}")
        print(f"[DEBUG] Series name: {getattr(series_ref, 'series_name_s', 'unknown')}")
        log.debug("=== query_series_children called ===")
        log.debug("Series type: {0}".format(series_type))
        log.debug("Series key: {0}".format(series_key))
        log.debug("Series name: {0}".format(getattr(series_ref, 'series_name_s', 'unknown')))
        
        # Fetch the appropriate page based on type
        if series_type == 'saga':
            print(f"[DEBUG] Fetching saga page for: {series_key}")
            log.debug("Fetching saga page for: {0}".format(series_key))
            html_content = self.connection.get_saga_page(series_key)
        else:
            print(f"[DEBUG] Fetching collection page for: {series_key}")
            log.debug("Fetching collection page for: {0}".format(series_key))
            html_content = self.connection.get_collection_page(series_key)
            
        if not html_content:
            print(f"[DEBUG] ERROR: Could not fetch {series_type} page for {series_key}")
            log.debug("ERROR: Could not fetch {0} page for {1}".format(series_type, series_key))
            return {'collections': [], 'issues': []}
        
        print(f"[DEBUG] Fetched HTML content: {len(html_content)} bytes")
        log.debug("Fetched HTML content: {0} bytes".format(len(html_content)))
        
        # Parse search results from the page
        print(f"[DEBUG] Parsing search results...")
        results = self.parser.parse_search_results(html_content)
        
        print(f"[DEBUG] Parser returned {len(results)} results")
        log.debug("Parser returned {0} results".format(len(results)))
        
        collections = []
        issue_refs = []
        
        # Process results based on type
        for result in results:
            result_type = result.get('type', 'unknown')
            slug = result.get('slug')
            
            log.debug("  Processing result: type={0}, slug={1}".format(result_type, slug))
            
            if result_type == 'collection':
                # Collections found in saga pages
                thumb_url = result.get('thumb_url')
                if thumb_url and not thumb_url.startswith('http'):
                    thumb_url = 'https://www.tebeosfera.com' + thumb_url
                    
                series_name = result.get('series_name') or result.get('title', slug)
                
                collection_ref = SeriesRef(
                    series_key=slug,
                    series_name_s=series_name,
                    volume_year_n=-1,
                    publisher_s='',
                    issue_count_n=0,
                    thumb_url_s=thumb_url
                )
                collection_ref.type_s = 'collection'
                collection_ref.extra_image_url = result.get('image_url')
                collections.append(collection_ref)
                log.debug("    Added collection: {0}".format(series_name))
                
            elif result_type == 'issue':
                # Issues found in both saga and collection pages
                issue_num = self._extract_issue_number(slug)
                
                thumb_url = result.get('thumb_url')
                if thumb_url and not thumb_url.startswith('http'):
                    thumb_url = 'https://www.tebeosfera.com' + thumb_url
                
                issue_ref = IssueRef(
                    issue_num_s=issue_num,
                    issue_key=slug,
                    title_s=result['title'],
                    thumb_url_s=thumb_url
                )
                issue_ref.extra_image_url = result.get('image_url')
                issue_refs.append(issue_ref)
                log.debug("    Added issue: {0}".format(result['title'][:50]))
        
        log.debug("Found {0} collections and {1} issues in {2}".format(
            len(collections), len(issue_refs), series_type))
        log.debug("=== query_series_children complete ===")
        
        return {'collections': collections, 'issues': issue_refs}

    def query_series_issues(self, series_ref):
        '''
        Get all issues for a given series.

        series_ref: SeriesRef object
        Returns: List of IssueRef objects
        
        Note: This method now uses query_series_children internally and returns only issues
        for backward compatibility. For tree expansion, use query_series_children instead.
        '''
        children = self.query_series_children(series_ref)
        return children['issues']

    def query_issue_details(self, issue_ref):
        '''
        Get detailed information about a specific issue.

        issue_ref: IssueRef object
        Returns: Issue object with full details, or None on error
        '''
        issue_key = getattr(issue_ref, 'issue_key', None)
        if not issue_key:
            # Fallback: try series_key (for SeriesRef objects representing issues)
            issue_key = getattr(issue_ref, 'series_key', None)
        
        log.debug("Querying issue details for: ", issue_key or "unknown")

        # Fetch the issue page
        if not issue_key:
            log.debug("No issue key available")
            return None
        
        html_content = self.connection.get_issue_page(issue_key)
        if not html_content:
            log.debug("Could not fetch issue page")
            return None

        # Parse the issue page
        metadata = self.parser.parse_issue_page(html_content)
        if not metadata:
            log.debug("Could not parse issue page")
            return None

        # Add page URL to metadata (constructed from issue_key)
        metadata['page_url'] = build_issue_url(issue_key)

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
                issue_ref.extra_image_url = result.get('image_url')
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
        elif isinstance(ref_or_url, str):
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
        elif isinstance(ref_or_url, str):
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
