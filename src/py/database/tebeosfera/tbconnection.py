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
import gzip
import os
import ssl
import tempfile
import traceback
from utils_compat import sstr


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
        self.last_request_url = None
        self.last_status_code = None
        self.last_response_size = 0
        self.last_elapsed_ms = 0
        # Cache for successful AJAX endpoints to avoid repeatedly trying failed endpoints
        self._successful_endpoints = {}
        self._init_session()

    def _init_session(self):
        '''Initialize HTTP session with cookies and headers'''
        # Create cookie handler
        cookie_handler = urllib.request.HTTPCookieProcessor()
        
        handlers = [cookie_handler]
        
        # Create unverified SSL context to avoid certificate errors
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            https_handler = urllib.request.HTTPSHandler(context=ctx)
            handlers.append(https_handler)
        except Exception as e:
            print("Warning: Could not setup SSL context: {0}".format(e))

        # Create opener with cookie support and SSL handler
        self.__session_opener = urllib.request.build_opener(*handlers)

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

        # Track request metadata
        self.last_request_url = url
        self.last_status_code = None
        self.last_response_size = 0
        self.last_elapsed_ms = 0

        # Enforce rate limiting
        self._enforce_rate_limit()

        try:
            start_time = time.time()
            response = self.__session_opener.open(url, timeout=TebeoSferaConnection.TIMEOUT_SECS)
            self.last_status_code = getattr(response, 'status', None) or response.getcode()
            html_content = response.read()
            elapsed = (time.time() - start_time) * 1000.0
            self.last_elapsed_ms = elapsed
            # Handle gzip encoding if present
            if response.info().get('Content-Encoding') == 'gzip':
                import io
                buf = io.BytesIO(html_content)
                f = gzip.GzipFile(fileobj=buf)
                html_content = f.read()

            self.last_response_size = len(html_content)
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
            self.last_status_code = e.code
            print("HTTP Error {0}: {1}".format(e.code, e.reason))
            return None
        except urllib.error.URLError as e:
            self.last_status_code = None
            print("URL Error: {0}".format(e.reason))
            return None
        except Exception as e:
            self.last_status_code = None
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
        original_query = query
        query_encoded = query.replace(' ', '_')
        query_encoded = urllib.parse.quote(query_encoded, safe='_')

        # Build search URL (for reference, though we'll use AJAX calls)
        search_url = "/buscador/{0}/".format(query_encoded)
        
        # Initialize initial_html to empty string as fallback
        initial_html = ""
        
        from utils_compat import log
        
        # All search results are loaded via AJAX calls, not in the initial page
        # We need to make separate AJAX calls for each type of result
        all_results_html = []
        
        # Search in collections (T3_publicaciones table)
        try:
            collections_data = urllib.parse.urlencode({
                'tabla': 'T3_publicaciones',
                'busqueda': original_query
            }).encode('utf-8')
            
            collections_url = TebeoSferaConnection.BASE_URL + "/neko/templates/ajax/buscador_txt_post.php"
            request = urllib.request.Request(collections_url, data=collections_data, method='POST')
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.add_header('User-Agent', TebeoSferaConnection.USER_AGENT)
            request.add_header('Referer', TebeoSferaConnection.BASE_URL + search_url)
            
            self._enforce_rate_limit()
            response = self.__session_opener.open(request, timeout=TebeoSferaConnection.TIMEOUT_SECS)
            collections_html = response.read()
            
            # Check if response is gzipped
            if collections_html.startswith(b'\x1f\x8b'):  # gzip magic number
                collections_html = gzip.decompress(collections_html)
            
            # Decode response
            charset = self._get_charset(response)
            if charset:
                collections_html = collections_html.decode(charset)
            else:
                try:
                    collections_html = collections_html.decode('utf-8')
                except:
                    collections_html = collections_html.decode('latin-1')
            
            if collections_html and collections_html.strip() and not collections_html.startswith('Error'):
                # Add section header for collections
                collections_with_header = '<div class="help-block" style="clear:both; margin-top: -2px; font-size: 16px; color: #FD8F01; font-weight: bold; margin-bottom: 0px;">Colecciones</div>\n' + collections_html
                all_results_html.append(collections_with_header)
                log.debug("Collections AJAX returned {0} bytes".format(len(collections_html)))
            else:
                if not collections_html:
                    log.debug("Collections AJAX returned empty response")
                elif not collections_html.strip():
                    log.debug("Collections AJAX returned whitespace-only response ({0} bytes)".format(len(collections_html)))
                elif collections_html.startswith('Error'):
                    log.debug("Collections AJAX returned error: {0}".format(collections_html[:200]))
        except Exception as e:
            log.debug("Error fetching collections via AJAX: {0}".format(sstr(e)))
        
        # Search in sagas (T3_series table)
        try:
            sagas_data = urllib.parse.urlencode({
                'tabla': 'T3_series',
                'busqueda': original_query
            }).encode('utf-8')
            
            sagas_url = TebeoSferaConnection.BASE_URL + "/neko/templates/ajax/buscador_txt_post.php"
            request = urllib.request.Request(sagas_url, data=sagas_data, method='POST')
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.add_header('User-Agent', TebeoSferaConnection.USER_AGENT)
            request.add_header('Referer', TebeoSferaConnection.BASE_URL + search_url)
            
            self._enforce_rate_limit()
            response = self.__session_opener.open(request, timeout=TebeoSferaConnection.TIMEOUT_SECS)
            sagas_html = response.read()
            
            # Check if response is gzipped
            if sagas_html.startswith(b'\x1f\x8b'):  # gzip magic number
                sagas_html = gzip.decompress(sagas_html)
            
            # Decode response
            charset = self._get_charset(response)
            if charset:
                sagas_html = sagas_html.decode(charset)
            else:
                try:
                    sagas_html = sagas_html.decode('utf-8')
                except:
                    sagas_html = sagas_html.decode('latin-1')
            
            if sagas_html and sagas_html.strip() and not sagas_html.startswith('Error'):
                # Add section header for sagas
                sagas_with_header = '<div class="help-block" style="clear:both; margin-top: -2px; font-size: 16px; color: #FD8F01; font-weight: bold; margin-bottom: 0px;">Sagas</div>\n' + sagas_html
                all_results_html.append(sagas_with_header)
                log.debug("Sagas AJAX returned {0} bytes".format(len(sagas_html)))
            else:
                if not sagas_html:
                    log.debug("Sagas AJAX returned empty response")
                elif not sagas_html.strip():
                    log.debug("Sagas AJAX returned whitespace-only response ({0} bytes)".format(len(sagas_html)))
                elif sagas_html.startswith('Error'):
                    log.debug("Sagas AJAX returned error: {0}".format(sagas_html[:200]))
        except Exception as e:
            log.debug("Error fetching sagas via AJAX: {0}".format(sstr(e)))
        
        # Search in numbers (issues) using megaAjax.php endpoint (finds all 56 issues vs 52 with buscador_txt_post.php)
        try:
            numbers_data = urllib.parse.urlencode({
                'action': 'buscador_simple_numeros',
                'busqueda': original_query
            }).encode('utf-8')
            
            numbers_url = TebeoSferaConnection.BASE_URL + "/neko/php/ajax/megaAjax.php"
            request = urllib.request.Request(numbers_url, data=numbers_data, method='POST')
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.add_header('User-Agent', TebeoSferaConnection.USER_AGENT)
            request.add_header('Referer', TebeoSferaConnection.BASE_URL + search_url)
            
            self._enforce_rate_limit()
            response = self.__session_opener.open(request, timeout=TebeoSferaConnection.TIMEOUT_SECS)
            numbers_html = response.read()
            
            # Check if response is gzipped
            if numbers_html.startswith(b'\x1f\x8b'):  # gzip magic number
                numbers_html = gzip.decompress(numbers_html)
            
            # Decode response
            charset = self._get_charset(response)
            if charset:
                numbers_html = numbers_html.decode(charset)
            else:
                try:
                    numbers_html = numbers_html.decode('utf-8')
                except:
                    numbers_html = numbers_html.decode('latin-1')
            
            if numbers_html and numbers_html.strip() and not numbers_html.startswith('Error'):
                # Add section header for numbers
                numbers_with_header = '<div class="help-block" style="clear:both; margin-top: -2px; font-size: 16px; color: #FD8F01; font-weight: bold; margin-bottom: 0px;">Números</div>\n' + numbers_html
                all_results_html.append(numbers_with_header)
                log.debug("Numbers AJAX returned {0} bytes".format(len(numbers_html)))
        except Exception as e:
            log.debug("Error fetching numbers via AJAX: {0}".format(sstr(e)))
        
        # Combine all results into a single HTML string
        # Section headers are already added to each chunk
        if all_results_html:
            combined_html = '\n'.join(all_results_html)
            log.debug("Combined AJAX results: {0} bytes".format(len(combined_html)))
            return combined_html
        
        # Fallback: return initial page (though it won't have results)
        return initial_html

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
        This includes fetching the numbers via AJAX, similar to search results.

        collection_slug: The slug identifier for the collection
        Returns: HTML content of collection page with numbers loaded, or None on error
        '''
        from utils_compat import log
        
        collection_url = "/colecciones/{0}.html".format(collection_slug)
        initial_html = self.get_page(collection_url)
        
        if not initial_html:
            return None
        
        # Collection pages load numbers via AJAX
        log.debug("get_collection_page called for: {0}".format(collection_slug))
        log.debug("Initial HTML size: {0} bytes".format(len(initial_html) if initial_html else 0))
        
        # First, check if numbers are already in the HTML (early exit)
        if initial_html:
            numeros_count = initial_html.count('/numeros/')
            linea_resultados_count = initial_html.count('linea_resultados')
            log.debug("HTML contains: {0} /numeros/ links, {1} linea_resultados divs".format(numeros_count, linea_resultados_count))
            
            # If we already have numbers in the HTML, return it as-is
            if numeros_count > 0 or linea_resultados_count > 0:
                log.debug("HTML already contains numbers, returning as-is")
                return initial_html
        
        # Try to find collection ID in the HTML (might be in data attributes, scripts, etc.)
        collection_id = None
        collection_id_match = re.search(r'coleccion[_-]?id["\']?\s*[:=]\s*["\']?(\d+)', initial_html, re.IGNORECASE)
        if collection_id_match:
            collection_id = collection_id_match.group(1)
            log.debug("Found collection ID in HTML: {0}".format(collection_id))
        
        # Try to extract collection name from page title for fallback
        title_match = re.search(r'<title>([^<]+)</title>', initial_html, re.IGNORECASE)
        collection_name = collection_slug.replace('_', ' ') if not title_match else title_match.group(1).strip()
        # Clean title (remove " - TebeoSfera" or similar)
        collection_name = re.sub(r'\s*[-–]\s*TebeoSfera.*$', '', collection_name, flags=re.IGNORECASE).strip()
        
        # Check if we have a cached successful endpoint for this type of request
        cache_key = 'collection_numbers'
        cached_endpoint = self._successful_endpoints.get(cache_key)
        
        # Build list of endpoints to try, prioritizing cached successful endpoint
        all_endpoints = []
        
        if collection_id:
            all_endpoints.extend([
                {
                    'url': '/neko/php/ajax/megaAjax.php',
                    'data': {'action': 'numeros_coleccion', 'coleccion_id': collection_id},
                    'name': 'collection_id_method'
                },
                {
                    'url': '/neko/templates/ajax/buscador_txt_post.php',
                    'data': {'tabla': 'T3_numeros', 'coleccion_id': collection_id},
                    'name': 'collection_id_alt'
                },
                {
                    'url': '/neko/php/ajax/megaAjax.php',
                    'data': {'coleccion_id': collection_id, 'ajax': '1'},
                    'name': 'collection_id_ajax'
                }
            ])
        
        # Add slug-based endpoint
        all_endpoints.append({
            'url': '/neko/php/ajax/megaAjax.php',
            'data': {'action': 'numeros_coleccion', 'coleccion': collection_slug},
            'name': 'slug_method'
        })
        
        # Add name-based fallback
        all_endpoints.append({
            'url': '/neko/php/ajax/megaAjax.php',
            'data': {'action': 'buscador_simple_numeros', 'busqueda': collection_name},
            'name': 'name_search'
        })
        
        # Reorder to prioritize cached endpoint
        if cached_endpoint:
            # Move cached endpoint to front
            for i, ep in enumerate(all_endpoints):
                if ep['name'] == cached_endpoint:
                    all_endpoints.insert(0, all_endpoints.pop(i))
                    break
        
        # Try endpoints
        for endpoint in all_endpoints:
            result = self._try_ajax_endpoint(endpoint, collection_url, collection_slug)
            if result:
                # Cache this successful endpoint
                self._successful_endpoints[cache_key] = endpoint['name']
                numbers_with_header = '<div class="help-block" style="clear:both; margin-top: -2px; font-size: 16px; color: #FD8F01; font-weight: bold; margin-bottom: 0px;">Números</div>\n' + result
                return initial_html + '\n' + numbers_with_header
        
        log.debug("All methods failed, returning initial HTML only")
        
        # Fallback: return initial page (may not have numbers loaded)
        return initial_html
    
    def _try_ajax_endpoint(self, endpoint, referer_url, collection_slug):
        '''
        Try a single AJAX endpoint and return the result if successful.
        
        Returns: HTML content if successful, None otherwise
        
        Note: For name_search endpoint, results are filtered by collection_slug to avoid
        returning issues from unrelated collections with similar names.
        '''
        from utils_compat import log
        
        try:
            numbers_data = urllib.parse.urlencode(endpoint['data']).encode('utf-8')
            numbers_url = TebeoSferaConnection.BASE_URL + endpoint['url']
            log.debug("Trying endpoint: {0} with {1}".format(endpoint['url'], endpoint['data']))
            
            request = urllib.request.Request(numbers_url, data=numbers_data, method='POST')
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.add_header('User-Agent', TebeoSferaConnection.USER_AGENT)
            request.add_header('Referer', TebeoSferaConnection.BASE_URL + referer_url)
            
            self._enforce_rate_limit()
            response = self.__session_opener.open(request, timeout=TebeoSferaConnection.TIMEOUT_SECS)
            
            # Early exit: check content type more flexibly
            content_type = (response.info().get('Content-Type') or '').lower()
            if not any(token in content_type for token in ('html', 'application/json', 'text/plain')):
                log.debug("Unexpected content type: {0}, skipping".format(content_type))
                return None
            
            numbers_html = response.read()
            
            # Early exit: empty response
            if not numbers_html or len(numbers_html) < 10:
                log.debug("Empty or too short response, skipping")
                return None
            
            if numbers_html.startswith(b'\x1f\x8b'):
                numbers_html = gzip.decompress(numbers_html)
            
            charset = self._get_charset(response)
            if charset:
                numbers_html = numbers_html.decode(charset)
            else:
                try:
                    numbers_html = numbers_html.decode('utf-8')
                except UnicodeDecodeError:
                    numbers_html = numbers_html.decode('latin-1')
            
            log.debug("Response: {0} bytes".format(len(numbers_html)))
            
            # Check if this looks like actual results (not a search form)
            is_search_form = 'Nombre real' in numbers_html or 'Carácteres disponibles' in numbers_html
            
            # Early exit: response is a search form, not results
            if is_search_form:
                log.debug("Response is a search form, not results - skipping")
                return None
            
            if numbers_html and ('linea_resultados' in numbers_html or '/numeros/' in numbers_html):
                # For name_search endpoint, filter results to only include issues
                # that belong to this specific collection (to avoid showing unrelated results)
                if endpoint['name'] == 'name_search' and collection_slug:
                    filtered_html = self._filter_results_by_collection(numbers_html, collection_slug)
                    if filtered_html:
                        log.debug("Endpoint {0} succeeded after filtering!".format(endpoint['name']))
                        return filtered_html
                    else:
                        log.debug("No matching results after filtering by collection slug")
                        return None
                else:
                    log.debug("Endpoint {0} succeeded!".format(endpoint['name']))
                    return numbers_html
                
        except Exception as e:
            log.debug("Endpoint {0} failed: {1}".format(endpoint['name'], sstr(e)))
        
        return None
    
    def _filter_results_by_collection(self, html_content, collection_slug):
        '''
        Filter search results to only include entries that match the collection slug.
        
        This prevents name-based searches from returning issues from unrelated collections
        that happen to have similar names.
        
        Args:
            html_content: HTML with search results
            collection_slug: The slug to filter by (e.g., "gaston_elgafe_2015_norma")
            
        Returns: Filtered HTML or None if no matches found
        '''
        from utils_compat import log
        
        if not collection_slug:
            return html_content
        
        # Build pattern to match URLs that contain this collection slug
        # Collection slugs appear in URLs like /numeros/gaston_elgafe_2015_norma_1.html
        slug_pattern = collection_slug.lower().replace(' ', '_')
        
        # Parse the HTML and filter results
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all result rows
            result_rows = soup.find_all('div', class_='linea_resultados')
            
            if not result_rows:
                # Try finding individual links
                links = soup.find_all('a', href=re.compile(r'/numeros/'))
                if not links:
                    return html_content  # No results to filter
                
                # Filter links by collection slug
                matching_links = []
                for link in links:
                    href = link.get('href', '').lower()
                    if slug_pattern in href:
                        matching_links.append(link)
                
                if not matching_links:
                    log.debug("No links matching slug pattern: {0}".format(slug_pattern))
                    return None
                
                log.debug("Filtered {0} links down to {1} matching collection slug".format(
                    len(links), len(matching_links)))
                return html_content  # Return full content if we have any matches
            
            # Filter result rows by collection slug
            matching_rows = []
            for row in result_rows:
                row_html = str(row).lower()
                if slug_pattern in row_html:
                    matching_rows.append(row)
            
            if not matching_rows:
                log.debug("No rows matching slug pattern: {0}".format(slug_pattern))
                return None
            
            log.debug("Filtered {0} rows down to {1} matching collection slug".format(
                len(result_rows), len(matching_rows)))
            
            # Rebuild HTML with only matching rows
            filtered_html_parts = []
            for row in matching_rows:
                filtered_html_parts.append(str(row))
            
            return '\n'.join(filtered_html_parts)
            
        except ImportError:
            log.debug("BeautifulSoup not available, returning unfiltered results")
            return html_content
        except Exception as e:
            log.debug("Error filtering results: {0}".format(sstr(e)))
            return html_content

    def get_saga_page(self, saga_slug):
        '''
        Get the detail page for a saga.

        saga_slug: The slug identifier for the saga
        Returns: HTML content of saga page, or None on error
        '''
        saga_url = "/sagas/{0}.html".format(saga_slug)
        return self.get_page(saga_url)

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

    def get_request_info(self):
        '''Return metadata about the most recent HTTP request'''
        return {
            'url': self.last_request_url,
            'status': self.last_status_code,
            'bytes': self.last_response_size,
            'elapsed_ms': self.last_elapsed_ms
        }


# Module-level convenience functions
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


def build_series_url(series_key_or_path):
    '''
    Build absolute URL for a series page.
    
    Args:
        series_key_or_path: Series key (e.g., 'tintin_1958_juventud') or path
        
    Returns:
        Full URL to the series page on tebeosfera.com
    '''
    if not series_key_or_path:
        return None
    
    path = series_key_or_path.strip()
    
    # If already a full URL, return as-is
    if path.startswith('http'):
        return path
    
    # If not starting with /, assume it's a slug and prepend /colecciones/
    if not path.startswith('/'):
        path = f"/colecciones/{path}"
    
    # If starts with /, just append to base URL
    if not path.endswith('.html'):
        path += '.html'
    
    return TebeoSferaConnection.BASE_URL + path


def build_issue_url(issue_key_or_path):
    '''
    Build absolute URL for an issue page.
    
    Args:
        issue_key_or_path: Issue key (e.g., 'tintin_1958_juventud_1') or path
        
    Returns:
        Full URL to the issue page on tebeosfera.com
    '''
    if not issue_key_or_path:
        return None
    
    path = issue_key_or_path.strip()
    
    # If already a full URL, return as-is
    if path.startswith('http'):
        return path
    
    # If not starting with /, assume it's a slug and prepend /numeros/
    if not path.startswith('/'):
        path = f"/numeros/{path}"
    
    # Ensure .html extension
    if not path.endswith('.html'):
        path += '.html'
    
    return TebeoSferaConnection.BASE_URL + path
