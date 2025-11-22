'''
HTML Parser Module for Tebeosfera.com

Parses HTML pages from tebeosfera.com to extract comic book metadata.
Uses BeautifulSoup4 for robust HTML parsing.

@author: Comic Scraper Enhancement Project
'''

import re
from html.entities import name2codepoint
from bs4 import BeautifulSoup
from utils_compat import sstr


class TebeoSferaParser(object):
    '''
    Parser for tebeosfera.com HTML pages.
    Extracts comic book metadata from issue detail pages.
    '''

    def __init__(self, log_callback=None):
        '''
        Initialize the parser
        
        Args:
            log_callback: Optional function to call for logging (takes a string message)
        '''
        self.log_callback = log_callback
    
    def _log(self, message):
        '''Log a message using callback if available, otherwise use utils_compat.log'''
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception as e:
                # Fallback to console if callback fails
                from utils_compat import log
                log.debug(f"[CALLBACK ERROR] {e}: {message}")
        else:
            from utils_compat import log
            log.debug(message)

    def parse_issue_page(self, html_content):
        '''
        Parse an issue detail page and extract all metadata.

        html_content: HTML string from tebeosfera.com issue page
        Returns: Dictionary with extracted metadata, or None on error
        '''
        if not html_content:
            return None

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        metadata = {
            # Basic info
            'title': None,
            'synopsis': None,
            'series': None,
            'number': None,
            'count': None,
            'volume_year': None,

            # Publishing info
            'publisher': None,
            'publisher_location': None,
            'publisher_country': None,
            'imprint': None,
            'date': None,  # Format: DD-MM-YYYY
            'year': None,
            'month': None,
            'day': None,
            'price': None,
            'currency': None,

            # Format info
            'edition': None,  # NUEVA, PRIMERA, etc.
            'type': None,  # TEBEO, LIBRO, etc.
            'format': None,  # LIBRO DE HISTORIETA, ALBUM, etc.
            'binding': None,  # CARTONÉ, RÚSTICA, etc.
            'dimensions': None,  # e.g., "31 x 23 cm"
            'page_count': None,
            'color': None,  # COLOR, B/N

            # Origin/Translation info
            'origin_title': None,
            'origin_publisher': None,
            'origin_country': None,
            'origin_date': None,
            'language': None,  # e.g., "Traducción del francés"

            # Identifiers
            'isbn': None,
            'legal_deposit': None,
            'barcode': None,

            # People
            'writers': [],
            'pencillers': [],
            'inkers': [],
            'colorists': [],
            'letterers': [],
            'cover_artists': [],
            'editors': [],
            'translators': [],
            'adapted_authors': [],  # Original authors for adaptations

            # Content
            'genres': [],
            'summary': None,
            'synopsis': None,

            # Characters and story
            'characters': [],
            'story_arcs': [],

            # Images
            'cover_image_url': None,
            'image_urls': [],

            # URLs
            'page_url': None,
            'collection_url': None,

            # Distribution
            'distribution_countries': [],
        }

        # Extract title (in div with id="titulo_ficha")
        titulo_ficha = soup.find('div', id='titulo_ficha')
        if titulo_ficha:
            titulo_div = titulo_ficha.find('div', class_='titulo')
            if titulo_div:
                # Try to extract series and issue title separately
                span = titulo_div.find('span')
                if span:
                    series_title = self._clean_text(span.get_text())
                    # Get text after the span and <br> tag
                    remaining_text = []
                    span_found = False
                    for content in titulo_div.children:
                        # Track if we've passed the span element
                        if hasattr(content, 'name') and content.name == 'span':
                            span_found = True
                            continue
                        # Skip <br> tags
                        if hasattr(content, 'name') and content.name == 'br':
                            continue
                        # Only collect content after the span
                        if span_found:
                            if hasattr(content, 'get_text'):
                                remaining_text.append(content.get_text())
                            elif isinstance(content, str):
                                remaining_text.append(content)
                    issue_title = self._clean_text(''.join(remaining_text))
                    metadata['series'] = series_title
                    metadata['title'] = issue_title
                else:
                    # Fallback: use entire text
                    full_title = self._clean_text(titulo_div.get_text())
                    metadata['title'] = full_title
        else:
            # Fallback: try simpler pattern
            titulo_div = soup.find('div', class_='titulo')
            if titulo_div:
                full_title = self._clean_text(titulo_div.get_text())
                metadata['title'] = full_title

        # Extract issue number and collection info
        # Look for pattern: "Nº X de <link>SERIES</link> [de Y]"
        for strong in soup.find_all('strong'):
            text = strong.get_text().strip()
            if 'Nº' in text or 'N°' in text:
                # Navigate to find number and collection
                parent = strong.parent
                if parent:
                    parent_text = parent.get_text()
                    # Extract number
                    num_match = re.search(r'Nº\s*(\d+)', parent_text, re.IGNORECASE)
                    if num_match:
                        metadata['number'] = num_match.group(1)
                    
                    # Extract collection link
                    coll_link = parent.find('a', href=re.compile(r'/colecciones/'))
                    if coll_link:
                        metadata['collection_url'] = coll_link.get('href', '')
                        metadata['series'] = self._clean_text(coll_link.get_text())
                    
                    # Extract count
                    count_match = re.search(r'\[de\s+(\d+)\]', parent_text)
                    if count_match:
                        metadata['count'] = int(count_match.group(1))
                break

        # Extract publisher, location, and country
        # Look for pattern: <a>PUBLISHER</a> · <span>LOCATION</span> · <img alt="COUNTRY">
        publisher_links = soup.find_all('a', href=re.compile(r'/entidades/'))
        for link in publisher_links:
            publisher_text = self._clean_text(link.get_text())
            if publisher_text:
                metadata['publisher'] = publisher_text
        
                # Use find_next_sibling for robust traversal
                location_span = link.find_next_sibling('span')
                if location_span:
                    metadata['publisher_location'] = self._clean_text(location_span.get_text())

                country_img = link.find_next_sibling('img')
                if country_img and country_img.get('alt'):
                    metadata['publisher_country'] = self._clean_text(country_img['alt'])
        
                break

        # Extract all row-fluid dato fields using BeautifulSoup
        self._extract_field_rows_bs(soup, metadata)

        # Extract authors section using BeautifulSoup
        self._extract_authors_bs(soup, metadata)

        # Extract genres using BeautifulSoup
        genres_tab = soup.find('div', class_='tab-pane active', id='tab1')
        if genres_tab:
            genre_links = genres_tab.find_all('a')
            metadata['genres'] = [self._clean_text(link.get_text()) for link in genre_links if link.get_text().strip()]
        
        # Extract synopsis using BeautifulSoup
        self._extract_synopsis_bs(soup, metadata)

        # Extract cover image (the first/main one)
        cover_img = soup.find('img', id='img_principal')
        if cover_img:
            cover_url = cover_img.get('src', '')
            # Ensure it's a full URL
            if cover_url and not cover_url.startswith('http'):
                cover_url = 'https://www.tebeosfera.com' + cover_url
            if cover_url:
                metadata['cover_image_url'] = cover_url
                metadata['image_urls'].append(cover_url)

        # Extract all additional images from the page
        all_images = soup.find_all('img', src=re.compile(r'T3_numeros'))
        for img in all_images:
            img_url = img.get('src', '')
            if img_url and not img_url.startswith('http'):
                img_url = 'https://www.tebeosfera.com' + img_url
            if img_url and img_url not in metadata['image_urls']:
                metadata['image_urls'].append(img_url)

        # Parse dates from the date field
        if metadata['date']:
            date_parts = self._parse_date(metadata['date'])
            if date_parts:
                metadata['day'], metadata['month'], metadata['year'] = date_parts

        # Extract volume year from series name if present
        series_name = metadata.get('series') or ''
        if series_name:
            series_year_match = re.search(r'\((\d{4})', series_name)
            if series_year_match:
                metadata['volume_year'] = int(series_year_match.group(1))


        return metadata

    def _extract_field_rows_bs(self, soup, metadata):
        '''
        Extract data from row-fluid sections with etiqueta/dato structure using BeautifulSoup.

        soup: BeautifulSoup object
        metadata: Dictionary to update with extracted data
        '''
        # Find all row-fluid sections with etiqueta and dato
        row_fluid_divs = soup.find_all('div', class_='row-fluid')
        
        for row_div in row_fluid_divs:
            etiqueta = row_div.find('div', class_=re.compile(r'etiqueta'))
            dato = row_div.find('div', class_='dato')
            
            if not etiqueta or not dato:
                continue
            
            label = self._clean_text(etiqueta.get_text()).lower()
            value_text = self._clean_text(dato.get_text())

            # Distribution info (date, price, countries)
            if 'distribuci' in label:
                # Extract date
                date_match = re.search(r'(\d{1,2}-[IVX]+-\d{4})', dato.get_text())
                if date_match:
                    metadata['date'] = date_match.group(1)

                # Extract price
                for strong in dato.find_all('strong'):
                    strong_text = strong.get_text()
                    if '€' in strong_text or 'euro' in strong_text:
                        # Look for price before this
                        prev = strong.previous_sibling
                        if prev and isinstance(prev, str):
                            price_match = re.search(r'([\d.,]+)\s*$', prev)
                            if price_match:
                                metadata['price'] = price_match.group(1)
                                metadata['currency'] = 'EUR'
                    elif '$' in strong_text:
                        prev = strong.previous_sibling
                        if prev and isinstance(prev, str):
                            price_match = re.search(r'([\d.,]+)\s*$', prev)
                            if price_match:
                                metadata['price'] = price_match.group(1)
                                metadata['currency'] = 'USD'

                # Extract distribution countries
                country_imgs = dato.find_all('img', alt=True)
                metadata['distribution_countries'] = [self._clean_text(img.get('alt', '')) for img in country_imgs if img.get('alt')]

            # Edition type
            elif 'edici' in label:
                links = dato.find_all('a')
                link_texts = [self._clean_text(link.get_text()) for link in links]
                if len(link_texts) >= 1:
                    metadata['edition'] = link_texts[0]
                if len(link_texts) >= 2:
                    metadata['type'] = link_texts[1]
                if len(link_texts) >= 3:
                    metadata['format'] = link_texts[2]

            # Origin information
            elif 'origen' in label:
                metadata['origin_title'] = value_text

                # Extract origin publisher
                pub_link = dato.find('a', href=re.compile(r'/entidades/'))
                if pub_link:
                    metadata['origin_publisher'] = self._clean_text(pub_link.get_text())

                # Extract origin country
                country_img = dato.find('img', alt=True)
                if country_img:
                    metadata['origin_country'] = self._clean_text(country_img.get('alt', ''))

            # Language
            elif 'lengua' in label:
                metadata['language'] = value_text

            # Format details (binding, etc.)
            elif 'formato' in label:
                format_links = dato.find_all('a')
                format_texts = [self._clean_text(link.get_text()) for link in format_links]
                if format_texts:
                    if not metadata['format']:
                        metadata['format'] = format_texts[0]
                    if len(format_texts) > 1:
                        metadata['binding'] = format_texts[1]

            # Dimensions
            elif 'tama' in label:
                metadata['dimensions'] = value_text

            # Page count
            elif 'paginaci' in label:
                page_match = re.search(r'(\d+)\s*p', value_text, re.IGNORECASE)
                if page_match:
                    metadata['page_count'] = int(page_match.group(1))

            # Color
            elif 'color' in label:
                metadata['color'] = value_text

            # Registros (ISBN, Legal Deposit, etc.)
            elif 'registros' in label:
                dato_text = dato.get_text()
                isbn_match = re.search(r'ISBN:\s*([\d\-]+)', dato_text, re.IGNORECASE)
                if isbn_match:
                    metadata['isbn'] = isbn_match.group(1)

                deposit_match = re.search(r'(?:Dep(?:ósito)?|D\.L\.)[:\.]?\s*([^\s]+)', dato_text, re.IGNORECASE)
                if deposit_match:
                    metadata['legal_deposit'] = self._clean_text(deposit_match.group(1))

    def _extract_authors_bs(self, soup, metadata):
        '''
        Extract author information from the authors section using BeautifulSoup.

        soup: BeautifulSoup object
        metadata: Dictionary to update with extracted data
        '''
        # Find all author sections
        author_spans = soup.find_all('span', class_='tab_subtitulo')
        
        for span in author_spans:
            role_text = span.get_text()
            # Extract role (ignore the number in <span>)
            role = re.sub(r'\d+', '', role_text).strip()
            role = self._clean_text(role).lower()
            
            # Find associated author link
            # The link usually comes after the colon following this span
            parent = span.parent
            if parent:
                # Look for links in the parent or next siblings
                links = []
                next_elem = span.next_sibling
                # Limit search to 5 links to avoid scanning too much of the DOM
                MAX_AUTHOR_LINKS = 5
                while next_elem and len(links) < MAX_AUTHOR_LINKS:
                    if hasattr(next_elem, 'name'):
                        if next_elem.name == 'a':
                            links.append(next_elem)
                        elif next_elem.name in ['div', 'p']:
                            # Stop at major structural elements
                            break
                    next_elem = next_elem.next_sibling
                
                for link in links:
                    name = self._clean_text(link.get_text())
                    if not name:
                        continue
                    
                    # Historietista = guionista + dibujante
                    if 'historietista' in role:
                        if name not in metadata['writers']:
                            metadata['writers'].append(name)
                        if name not in metadata['pencillers']:
                            metadata['pencillers'].append(name)
                    elif 'guion' in role:
                        if name not in metadata['writers']:
                            metadata['writers'].append(name)
                    elif 'dibuj' in role:
                        if name not in metadata['pencillers']:
                            metadata['pencillers'].append(name)
                    elif 'tint' in role:
                        if name not in metadata['inkers']:
                            metadata['inkers'].append(name)
                    elif 'color' in role:
                        if name not in metadata['colorists']:
                            metadata['colorists'].append(name)
                    elif 'letr' in role or 'rotul' in role:
                        if name not in metadata['letterers']:
                            metadata['letterers'].append(name)
                    elif 'portad' in role or 'cubierta' in role:
                        if name not in metadata['cover_artists']:
                            metadata['cover_artists'].append(name)
                    elif 'editor' in role:
                        if name not in metadata['editors']:
                            metadata['editors'].append(name)
                    elif 'traduc' in role:
                        if name not in metadata['translators']:
                            metadata['translators'].append(name)
                    elif 'adapt' in role:
                        if name not in metadata['adapted_authors']:
                            metadata['adapted_authors'].append(name)

    def _extract_synopsis_bs(self, soup, metadata):
        '''
        Extract synopsis/description using BeautifulSoup with multiple fallback patterns.

        soup: BeautifulSoup object
        metadata: Dictionary to update with extracted data
        '''
        # Pattern 1: Look for "Comentario de la editorial:" or "Información de la editorial:"
        for pattern in ['Comentario de la editorial', 'Información de la editorial', 'Promoción editorial', 'Argumento']:
            # Find all text nodes or elements containing this pattern
            for element in soup.find_all(string=re.compile(pattern, re.IGNORECASE)):
                # Get parent and following paragraphs
                parent = element.parent
                if parent:
                    # Collect paragraphs after this marker
                    # Limit to 10 paragraphs to avoid collecting unrelated content
                    MAX_SYNOPSIS_PARAGRAPHS = 10
                    paragraphs = []
                    next_elem = parent.next_sibling
                    while next_elem and len(paragraphs) < MAX_SYNOPSIS_PARAGRAPHS:
                        if hasattr(next_elem, 'name'):
                            if next_elem.name == 'p':
                                text = self._clean_text_preserve_newlines(next_elem.get_text())
                                if text and len(text) > 20:
                                    paragraphs.append(text)
                            elif next_elem.name in ['h2', 'h3', 'h4', 'div']:
                                # Stop at major sections
                                break
                        next_elem = next_elem.next_sibling
                    
                    if paragraphs:
                        combined = '\n\n'.join(paragraphs)
                        if len(combined) > 50:
                            metadata['synopsis'] = combined
                            return

        # Pattern 2: Look for <p class="texto">
        texto_paras = soup.find_all('p', class_='texto')
        if texto_paras:
            all_text = []
            for para in texto_paras:
                text = self._clean_text_preserve_newlines(para.get_text())
                if text and len(text) > 10:
                    all_text.append(text)
            if all_text:
                combined = '\n\n'.join(all_text)
                if len(combined) > 50:
                    metadata['synopsis'] = combined
                    return

        # Pattern 3: Find longest substantial paragraph (fallback)
        all_paragraphs = soup.find_all('p')
        best_para = None
        best_score = 0
        
        skip_keywords = ['isbn', 'depósito', 'precio', 'páginas', 'formato', 'tamaño', 'color', 'lengua']
        good_keywords = ['historia', 'personaje', 'aventura', 'narra', 'cuenta', 'viaje', 'muerte', 'vida']
        
        for para in all_paragraphs:
            text = self._clean_text_preserve_newlines(para.get_text())
            if text and len(text) > 50:
                text_lower = text.lower()
                
                # Count keywords
                skip_count = sum(1 for skip in skip_keywords if skip in text_lower)
                good_count = sum(1 for keyword in good_keywords if keyword in text_lower)
                has_quotes = '"' in text or '\u201c' in text or '\u201d' in text
                
                if skip_count >= 2 and good_count == 0 and not has_quotes:
                    continue
                
                # Score based on length and narrative content
                score = len(text)
                if good_count > 0 or has_quotes:
                    score += 500 * good_count
                    if has_quotes:
                        score += 300
                    if skip_count > 0:
                        score -= 50 * skip_count
                else:
                    if skip_count > 0:
                        score -= 150 * skip_count
                
                if score > best_score:
                    best_score = score
                    best_para = text
        
        if best_para:
            metadata['synopsis'] = best_para

    def parse_search_results(self, html_content):
        '''
        Parse search results page to extract issue links using BeautifulSoup.

        html_content: HTML string from search results page
        Returns: List of dictionaries with {slug, title, url, thumb_url, series_name, type}
        '''
        if not html_content:
            return []

        results = []
        from utils_compat import log
        
        log.debug("=== PARSER STARTING: parse_search_results called with {0} bytes of HTML ===".format(len(html_content)))

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all section headers (help-block divs)
        section_headers = soup.find_all('div', class_=re.compile(r'help-block'))
        
        log.debug("Found {0} section headers".format(len(section_headers)))
        
        # Process each section
        for i, header in enumerate(section_headers):
            section_title = self._clean_text(header.get_text()).strip()
            log.debug("  Section {0}: '{1}'".format(i+1, section_title))
            
            # Determine section type
            section_type = None
            if 'coleccion' in section_title.lower():
                section_type = 'collection'
            elif 'saga' in section_title.lower():
                section_type = 'saga'
            elif 'número' in section_title.lower() or 'numero' in section_title.lower():
                section_type = 'issue'
            elif 'autor' in section_title.lower():
                # Skip autores section
                continue
            else:
                # Unknown section, skip
                log.debug("Unknown section type: {0}".format(section_title))
                continue
            
            log.debug("Processing section: {0} (type: {1})".format(section_title, section_type))
            
            # Find all result lines in this section
            # Get the next sibling elements until we hit another section header
            section_results = []
            next_elem = header.next_sibling
            while next_elem:
                if hasattr(next_elem, 'name'):
                    if next_elem.name == 'div' and next_elem.get('class') and 'help-block' in next_elem.get('class', []):
                        # Hit next section header
                        break
                    elif next_elem.name == 'div' and next_elem.get('class') and 'linea_resultados' in ' '.join(next_elem.get('class', [])):
                        # Found a result line
                        result = self._parse_result_line_bs(next_elem, section_type)
                        if result:
                            section_results.append(result)
                next_elem = next_elem.next_sibling
            
            results.extend(section_results)
            log.debug("Found {0} results in section '{1}'".format(len(section_results), section_title))
        
        # Fallback: if no results found, try direct scan for linea_resultados
        if not results:
            log.debug("No results found in sections, trying direct link scan")
            
            # Find all linea_resultados divs
            all_lines = soup.find_all('div', class_=re.compile(r'linea_resultados'))
            log.debug("Found {0} linea_resultados divs via fallback".format(len(all_lines)))
            
            for line in all_lines:
                # Try to determine type from link
                result = self._parse_result_line_bs(line, None)  # Type will be auto-detected
                if result:
                    results.append(result)
        
        log.debug("Parser returning {0} total results".format(len(results)))
        return results

    def _parse_result_line_bs(self, line_div, section_type=None):
        '''
        Parse a single result line using BeautifulSoup.

        line_div: BeautifulSoup element (div with class linea_resultados)
        section_type: Expected type ('collection', 'saga', 'issue') or None to auto-detect
        Returns: Dictionary with result data, or None if parsing fails
        '''
        # Extract thumbnail
        thumb_url = None
        cover_img = line_div.find('img', id='img_principal')
        if cover_img:
            thumb_url = cover_img.get('src', '')
            if thumb_url and not thumb_url.startswith('http'):
                thumb_url = 'https://www.tebeosfera.com' + thumb_url
        
        # Extract full image URL (from <a> wrapping the img)
        full_image_url = None
        if cover_img:
            parent_link = cover_img.find_parent('a')
            if parent_link:
                full_image_url = parent_link.get('href', '')
                if full_image_url and not full_image_url.startswith('http'):
                    full_image_url = 'https://www.tebeosfera.com' + full_image_url
        
        # Find the main content link (not image link)
        url = None
        slug = None
        title = None
        result_type = section_type
        
        # Try different link types based on section type
        link_patterns = []
        if section_type == 'saga' or not section_type:
            link_patterns.append(('saga', re.compile(r'/sagas/([^/]+)\.html')))
        if section_type == 'collection' or not section_type:
            link_patterns.append(('collection', re.compile(r'/colecciones/([^/]+)\.html')))
        if section_type == 'issue' or not section_type:
            link_patterns.append(('issue', re.compile(r'/numeros/([^/]+)\.html')))
        
        # Find links with text content (not just images)
        for link_type, href_pattern in link_patterns:
            links = line_div.find_all('a', href=href_pattern)
            for link in links:
                link_text = self._clean_text(link.get_text())
                if link_text:  # Has actual text content
                    href = link.get('href', '')
                    match = href_pattern.search(href)
                    if match:
                        url = href
                        slug = match.group(1)
                        title = link_text
                        result_type = link_type
                        break
            if title:
                break
        
        if not url or not slug or not title:
            return None
        
        # For collections and sagas, title IS the series name
        if result_type in ['collection', 'saga']:
            return {
                'slug': slug,
                'title': title,
                'url': url,
                'thumb_url': thumb_url,
                'image_url': full_image_url or thumb_url,
                'series_name': title,
                'type': result_type
            }
        
        # For issues, parse series name from title
        full_title = title
        series_name = None
        issue_title = None
        
        # Try various patterns to extract series name
        series_match = re.match(r'^(.+?)\s*\([^)]+\)\s*([^:]*?)\s*:\s*(.+)$', full_title)
        if series_match:
            series_name = self._clean_text(series_match.group(1))
            issue_title = self._clean_text(series_match.group(3))
        else:
            series_match = re.match(r'^(.+?)\s*-\s*([^-]+)\s*-\s*([^:]*?)\s*:\s*(.+)$', full_title)
            if series_match:
                series_name = self._clean_text(series_match.group(1))
                issue_title = self._clean_text(series_match.group(4))
            else:
                series_match = re.match(r'^(.+?)\s*\([^)]+\)', full_title)
                if series_match:
                    series_name = self._clean_text(series_match.group(1))
                else:
                    # Fallback: use first part of slug
                    slug_parts = slug.split('_')
                    if len(slug_parts) >= 2:
                        series_name = ' '.join(slug_parts[:2]).replace('_', ' ').title()
                    else:
                        series_name = slug.split('_')[0].replace('_', ' ').title()
        
        if series_name:
            return {
                'slug': slug,
                'title': full_title,
                'url': url,
                'thumb_url': thumb_url,
                'image_url': full_image_url or thumb_url,
                'series_name': series_name.strip(),
                'issue_title': issue_title.strip() if issue_title else None,
                'type': 'issue'
            }
        
        return None

    def _parse_date(self, date_string):
        '''
        Parse Spanish date format (DD-MM-YYYY or DD-MON-YYYY with Roman numerals).

        date_string: Date string (e.g., "18-XI-2025", "20-04-1998")
        Returns: Tuple (day, month, year) or None
        '''
        if not date_string:
            return None

        # Map Roman numerals to month numbers
        roman_months = {
            'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6,
            'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12
        }

        # Try DD-MON-YYYY format with Roman numerals
        match = re.match(r'(\d{1,2})-([IVX]+)-(\d{4})', date_string)
        if match:
            day = int(match.group(1))
            month_roman = match.group(2)
            year = int(match.group(3))
            month = roman_months.get(month_roman)
            if month:
                return (day, month, year)

        # Try DD-MM-YYYY format
        match = re.match(r'(\d{1,2})-(\d{1,2})-(\d{4})', date_string)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            return (day, month, year)

        return None

    def _clean_text(self, text):
        '''
        Clean HTML text by removing extra whitespace and decoding entities.

        text: Text string
        Returns: Cleaned text
        '''
        if not text:
            return ''

        # Decode HTML entities
        text = self._decode_entities(text)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text
    
    def _clean_text_preserve_newlines(self, text):
        '''
        Clean HTML text preserving newlines and blank lines (for synopsis).
        
        text: Text string
        Returns: Cleaned text with preserved newlines
        '''
        if not text:
            return ''
        
        # Decode HTML entities
        text = self._decode_entities(text)
        
        # Replace <br> and <br/> with newlines
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        
        # Replace </p> with newline (paragraph breaks)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        
        # Strip HTML tags
        text = self._strip_tags(text)
        
        # Normalize whitespace: preserve newlines, collapse multiple spaces to single space
        # But preserve blank lines (multiple consecutive newlines)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Collapse multiple spaces within a line
            cleaned_line = re.sub(r'[ \t]+', ' ', line.strip())
            cleaned_lines.append(cleaned_line)
        
        # Join lines, preserving blank lines
        text = '\n'.join(cleaned_lines)
        
        # Remove trailing whitespace from each line but keep blank lines
        # Remove excessive blank lines (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def _strip_tags(self, html):
        '''
        Remove HTML tags from string.

        html: HTML string
        Returns: Text without tags
        '''
        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        return text

    def _decode_entities(self, text):
        '''
        Decode HTML entities in text.

        text: Text with HTML entities
        Returns: Text with entities decoded
        '''
        # Decode numeric entities
        text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
        text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)

        # Decode named entities
        def replace_entity(match):
            entity = match.group(1)
            if entity in name2codepoint:
                return chr(name2codepoint[entity])
            return match.group(0)

        text = re.sub(r'&([a-zA-Z]+);', replace_entity, text)

        return text
