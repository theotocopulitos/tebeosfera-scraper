'''
HTTP Connection Module for Tebeosfera.com

Handles all HTTP requests to tebeosfera.com with proper rate limiting,
error handling, and session management.

@author: Comic Scraper Enhancement Project
'''

import time
import urllib.request
import urllib.parse
import urllib.error
import re
from utils import sstr


class TebeoSferaConnection(object):
    '''
    Manages HTTP connections to tebeosfera.com with rate limiting and error handling.
    '''

    # Base URL for tebeosfera.com
    BASE_URL = "https://www.tebeosfera.com"

    # Delay between queries to be respectful (in milliseconds)
    __QUERY_DELAY_MS = 1500  # 1.5 seconds between requests

    # User agent string
    USER_AGENT = "Mozilla/5.0 (compatible; TebeoSferaBot/1.0; +Comic-Scraper)"

    # Timeout for requests (in seconds)
    TIMEOUT_SECS = 30

    def __init__(self):
        '''Initialize the connection manager'''
        self.__last_query_time = 0
        self.__session_opener = None
        self._init_session()

    def _init_session(self):
        '''Initialize HTTP session with cookies and headers'''
        # Create cookie handler
        cookie_handler = urllib.request.HTTPCookieProcessor()

        # Create opener with cookie support
        self.__session_opener = urllib.request.build_opener(cookie_handler)

        # Set user agent
        self.__session_opener.addheaders = [
            ('User-Agent', TebeoSferaConnection.USER_AGENT),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
            ('Accept-Language', 'es-ES,es;q=0.9,en;q=0.8'),
            ('Accept-Encoding', 'gzip, deflate'),
            ('Connection', 'keep-alive'),
        ]

    def _enforce_rate_limit(self):
        '''
        Enforce rate limiting between queries to be respectful to the server.
        '''
        now = time.time()
        time_since_last = (now - self.__last_query_time) * 1000  # Convert to ms

        if time_since_last < TebeoSferaConnection.__QUERY_DELAY_MS:
            sleep_time = (TebeoSferaConnection.__QUERY_DELAY_MS - time_since_last) / 1000.0
            time.sleep(sleep_time)

        self.__last_query_time = time.time()

    def get_page(self, url):
        '''
        Fetch a page from tebeosfera.com.

        url: Full URL or path (if path, BASE_URL is prepended)
        Returns: HTML content as string, or None on error
        '''
        # Ensure we have the full URL
        if not url.startswith('http'):
            url = TebeoSferaConnection.BASE_URL + url

        # Enforce rate limiting
        self._enforce_rate_limit()

        try:
            response = self.__session_opener.open(url, timeout=TebeoSferaConnection.TIMEOUT_SECS)
            html_content = response.read()

            # Handle gzip encoding if present
            if response.info().get('Content-Encoding') == 'gzip':
                import io
                import gzip
                buf = io.BytesIO(html_content)
                f = gzip.GzipFile(fileobj=buf)
                html_content = f.read()

            # Decode to unicode
            charset = self._get_charset(response)
            if charset:
                html_content = html_content.decode(charset)
            else:
                # Try UTF-8 first, then latin-1
                try:
                    html_content = html_content.decode('utf-8')
                except:
                    html_content = html_content.decode('latin-1')

            return html_content

        except urllib.error.HTTPError as e:
            print("HTTP Error {0}: {1}".format(e.code, e.reason))
            return None
        except urllib.error.URLError as e:
            print("URL Error: {0}".format(e.reason))
            return None
        except Exception as e:
            print("Error fetching page: {0}".format(sstr(e)))
            return None

    def search(self, query):
        '''
        Search tebeosfera.com for comics.

        query: Search term (series name, author, etc.)
        Returns: HTML content of search results page, or None on error
        '''
        # Clean and encode the query
        query = query.strip()
        query = query.replace(' ', '_')

        # Build search URL
        search_url = "/buscador/{0}/".format(query)

        return self.get_page(search_url)

    def get_issue_page(self, issue_slug):
        '''
        Get the detail page for a specific issue.

        issue_slug: The slug identifier for the issue (e.g., "thorgal_1977_rosinski_1")
        Returns: HTML content of issue page, or None on error
        '''
        issue_url = "/numeros/{0}.html".format(issue_slug)
        return self.get_page(issue_url)

    def get_collection_page(self, collection_slug):
        '''
        Get the detail page for a collection/series.

        collection_slug: The slug identifier for the collection
        Returns: HTML content of collection page, or None on error
        '''
        collection_url = "/colecciones/{0}.html".format(collection_slug)
        return self.get_page(collection_url)

    def get_author_page(self, author_slug):
        '''
        Get the detail page for an author.

        author_slug: The slug identifier for the author
        Returns: HTML content of author page, or None on error
        '''
        author_url = "/autores/{0}.html".format(author_slug)
        return self.get_page(author_url)

    def download_image(self, image_url):
        '''
        Download an image (cover art, etc.) from tebeosfera.com.

        image_url: URL of the image (full URL or path)
        Returns: Binary image data, or None on error
        '''
        # Ensure we have the full URL
        if not image_url.startswith('http'):
            image_url = TebeoSferaConnection.BASE_URL + image_url

        # Enforce rate limiting
        self._enforce_rate_limit()

        try:
            response = self.__session_opener.open(image_url, timeout=TebeoSferaConnection.TIMEOUT_SECS)
            image_data = response.read()
            return image_data
        except Exception as e:
            print("Error downloading image: {0}".format(sstr(e)))
            return None

    def save_image(self, image_url, filepath):
        '''
        Download and save an image to a file.

        image_url: URL of the image
        filepath: Path where to save the image
        Returns: True if successful, False otherwise
        '''
        image_data = self.download_image(image_url)
        if not image_data:
            return False

        try:
            with open(filepath, 'wb') as f:
                f.write(image_data)
            return True
        except Exception as e:
            print("Error saving image: {0}".format(sstr(e)))
            return False

    def _get_charset(self, response):
        '''
        Extract charset from HTTP response headers.

        response: urllib2 response object
        Returns: charset string or None
        '''
        content_type = response.info().get('Content-Type', '')
        match = re.search(r'charset=([^;\s]+)', content_type, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def close(self):
        '''Close the connection and clean up resources'''
        # Nothing to explicitly close with urllib2
        pass


# Module-level convenience function
_connection = None

def get_connection():
    '''
    Get a singleton connection instance.

    Returns: TebeoSferaConnection instance
    '''
    global _connection
    if _connection is None:
        _connection = TebeoSferaConnection()
    return _connection
