'''
HTML Parser Module for Tebeosfera.com

Parses HTML pages from tebeosfera.com to extract comic book metadata.
Uses BeautifulSoup-like approach with basic HTML parsing.

@author: Comic Scraper Enhancement Project
'''

import re
from html.parser import HTMLParser
from html.entities import name2codepoint
from utils_compat import sstr


class TebeoSferaParser(object):
    '''
    Parser for tebeosfera.com HTML pages.
    Extracts comic book metadata from issue detail pages.
    '''

    def __init__(self):
        '''Initialize the parser'''
        pass

    def parse_issue_page(self, html_content):
        '''
        Parse an issue detail page and extract all metadata.

        html_content: HTML string from tebeosfera.com issue page
        Returns: Dictionary with extracted metadata, or None on error
        '''
        if not html_content:
            return None

        metadata = {
            # Basic info
            'title': None,
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
        title_match = re.search(
            r'<div id="titulo_ficha"[^>]*>.*?<div class="titulo">.*?'
            r'<span[^>]*>(.*?)</span><br>(.*?)</div>',
            html_content, re.DOTALL | re.IGNORECASE
        )
        if title_match:
            series_title = self._clean_text(title_match.group(1))
            issue_title = self._clean_text(title_match.group(2))
            metadata['series'] = series_title
            metadata['title'] = issue_title
        else:
            # Fallback: try simpler pattern
            title_match = re.search(
                r'<div class="titulo">(.*?)</div>',
                html_content, re.DOTALL | re.IGNORECASE
            )
            if title_match:
                full_title = self._clean_text(title_match.group(1))
                metadata['title'] = full_title

        # Extract issue number and collection info
        number_match = re.search(
            r'<strong><span[^>]*>Nº</span></strong>\s*(\d+)\s*<strong>de</strong>.*?'
            r'<a href="(/colecciones/[^"]+)"[^>]*>([^<]+)</a>.*?'
            r'\[de (\d+)\]',
            html_content, re.DOTALL | re.IGNORECASE
        )
        if number_match:
            metadata['number'] = number_match.group(1)
            metadata['collection_url'] = number_match.group(2)
            metadata['series'] = self._clean_text(number_match.group(3))
            metadata['count'] = int(number_match.group(4))

        # Extract publisher, location, and country
        publisher_match = re.search(
            r'<a href="/entidades/[^"]+"\s*>([^<]+)</a>\s*<strong>\s*·\s*</strong>\s*'
            r'<span[^>]*>([^<]*)</span>\s*<strong>\s*·\s*</strong>\s*'
            r'<img[^>]*alt="([^"]+)"',
            html_content, re.IGNORECASE
        )
        if publisher_match:
            metadata['publisher'] = self._clean_text(publisher_match.group(1))
            metadata['publisher_location'] = self._clean_text(publisher_match.group(2))
            metadata['publisher_country'] = self._clean_text(publisher_match.group(3))

        # Extract all row-fluid dato fields using a more robust approach
        self._extract_field_rows(html_content, metadata)

        # Extract authors section
        self._extract_authors(html_content, metadata)

        # Extract genres
        genres_match = re.search(
            r'<div class="tab-pane active" id="tab1"><p>(.*?)</p></div>',
            html_content, re.DOTALL | re.IGNORECASE
        )
        if genres_match:
            genres_html = genres_match.group(1)
            genres = re.findall(r'<a[^>]*>([^<]+)</a>', genres_html)
            metadata['genres'] = [self._clean_text(g) for g in genres]

        # Extract cover image (the first/main one)
        cover_match = re.search(
            r'<img id="img_principal"\s+src="([^"]+)"',
            html_content, re.IGNORECASE
        )
        if cover_match:
            cover_url = cover_match.group(1)
            # Ensure it's a full URL
            if not cover_url.startswith('http'):
                cover_url = 'https://www.tebeosfera.com' + cover_url
            metadata['cover_image_url'] = cover_url
            metadata['image_urls'].append(cover_url)

        # Extract all additional images from the page
        all_images_pattern = r'<img[^>]*src="([^"]*T3_numeros[^"]*)"[^>]*>'
        for img_match in re.finditer(all_images_pattern, html_content, re.IGNORECASE):
            img_url = img_match.group(1)
            if not img_url.startswith('http'):
                img_url = 'https://www.tebeosfera.com' + img_url
            if img_url not in metadata['image_urls']:
                metadata['image_urls'].append(img_url)

        # Parse dates from the date field
        if metadata['date']:
            date_parts = self._parse_date(metadata['date'])
            if date_parts:
                metadata['day'], metadata['month'], metadata['year'] = date_parts

        # Extract volume year from series name if present
        series_year_match = re.search(r'\((\d{4})', metadata.get('series', ''))
        if series_year_match:
            metadata['volume_year'] = int(series_year_match.group(1))

        return metadata

    def _extract_field_rows(self, html_content, metadata):
        '''
        Extract data from row-fluid sections with etiqueta/dato structure.

        html_content: HTML string
        metadata: Dictionary to update with extracted data
        '''
        # Find all row-fluid sections with etiqueta and dato
        pattern = r'<div class="row-fluid">.*?' \
                  r'<div class="span3 etiqueta[^"]*">([^<]+)</div>.*?' \
                  r'<div class="span9 dato">(.*?)</div>.*?</div>'

        matches = re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE)

        for match in matches:
            label = self._clean_text(match.group(1)).lower()
            value_html = match.group(2)
            value_text = self._clean_text(self._strip_tags(value_html))

            # Distribution info (date, price, countries)
            if 'distribuci' in label:
                # Extract date
                date_match = re.search(r'(\d{1,2}-[IVX]+-\d{4})', value_html)
                if date_match:
                    metadata['date'] = date_match.group(1)

                # Extract price
                price_match = re.search(r'([\d.,]+)\s*<strong>&nbsp;(&euro;|\$|€)</strong>', value_html)
                if price_match:
                    metadata['price'] = price_match.group(1)
                    currency_symbol = price_match.group(2)
                    if 'euro' in currency_symbol or '€' in currency_symbol:
                        metadata['currency'] = 'EUR'
                    elif '$' in currency_symbol:
                        metadata['currency'] = 'USD'

                # Extract distribution countries
                countries = re.findall(r'alt="([^"]+)"', value_html)
                metadata['distribution_countries'] = [self._clean_text(c) for c in countries]

            # Edition type
            elif 'edici' in label:
                types = re.findall(r'<a[^>]*>([^<]+)</a>', value_html)
                if len(types) >= 1:
                    metadata['edition'] = self._clean_text(types[0])
                if len(types) >= 2:
                    metadata['type'] = self._clean_text(types[1])
                if len(types) >= 3:
                    metadata['format'] = self._clean_text(types[2])

            # Origin information
            elif 'origen' in label:
                metadata['origin_title'] = value_text

                # Extract origin publisher
                pub_match = re.search(r'<a href="/entidades/[^"]+"\s*>([^<]+)</a>', value_html)
                if pub_match:
                    metadata['origin_publisher'] = self._clean_text(pub_match.group(1))

                # Extract origin country
                country_match = re.search(r'alt="([^"]+)"', value_html)
                if country_match:
                    metadata['origin_country'] = self._clean_text(country_match.group(1))

            # Language
            elif 'lengua' in label:
                metadata['language'] = value_text

            # Format details (binding, etc.)
            elif 'formato' in label:
                format_types = re.findall(r'<a[^>]*>([^<]+)</a>', value_html)
                if format_types:
                    if not metadata['format']:
                        metadata['format'] = self._clean_text(format_types[0])
                    if len(format_types) > 1:
                        metadata['binding'] = self._clean_text(format_types[1])

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
                isbn_match = re.search(r'ISBN:\s*([\d\-]+)', value_html, re.IGNORECASE)
                if isbn_match:
                    metadata['isbn'] = isbn_match.group(1)

                deposit_match = re.search(r'(?:Dep(?:ósito)?|D\.L\.)[:\.]?\s*([^\s<]+)', value_html, re.IGNORECASE)
                if deposit_match:
                    metadata['legal_deposit'] = self._clean_text(deposit_match.group(1))

    def _extract_authors(self, html_content, metadata):
        '''
        Extract author information from the authors section.

        html_content: HTML string
        metadata: Dictionary to update with extracted data
        '''
        # Pattern for author sections
        pattern = r'<span class="tab_subtitulo">([^<]+)<span[^>]*>\d+</span></span>:\s*' \
                  r'.*?<a href="[^"]*"\s*[^>]*>([^<]+)</a>'

        matches = re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE)

        for match in matches:
            role = self._clean_text(match.group(1)).lower()
            name = self._clean_text(match.group(2))

            if 'guion' in role:
                metadata['writers'].append(name)
            elif 'dibuj' in role:
                metadata['pencillers'].append(name)
            elif 'tint' in role:
                metadata['inkers'].append(name)
            elif 'color' in role:
                metadata['colorists'].append(name)
            elif 'letr' in role or 'rotul' in role:
                metadata['letterers'].append(name)
            elif 'portad' in role or 'cubierta' in role:
                metadata['cover_artists'].append(name)
            elif 'editor' in role:
                metadata['editors'].append(name)
            elif 'traduc' in role:
                metadata['translators'].append(name)
            elif 'adapt' in role:
                metadata['adapted_authors'].append(name)

    def parse_search_results(self, html_content):
        '''
        Parse search results page to extract issue links.

        html_content: HTML string from search results page
        Returns: List of dictionaries with {slug, title, url, thumb_url, series_name, type}
        '''
        if not html_content:
            return []

        results = []
        from utils_compat import log

        # Parse each result line: <div class="linea_resultados">...</div>
        # This is the most reliable way to get complete result information
        # Need to match the opening div and find the matching closing div (handling nested divs)
        lineas = []
        pos = 0
        while True:
            # Find next opening div with class="linea_resultados"
            start_match = re.search(r'<div[^>]*class="[^"]*linea_resultados[^"]*"[^>]*>', html_content[pos:], re.IGNORECASE)
            if not start_match:
                break
            
            start_pos = pos + start_match.end()
            # Find matching closing </div> by counting nested divs
            depth = 1
            search_pos = start_pos
            end_pos = None
            
            while depth > 0 and search_pos < len(html_content):
                # Look for next <div or </div>
                next_tag = re.search(r'</?div[^>]*>', html_content[search_pos:], re.IGNORECASE)
                if not next_tag:
                    break
                
                tag_pos = search_pos + next_tag.start()
                tag = next_tag.group(0).lower()
                
                if tag.startswith('</div'):
                    depth -= 1
                    if depth == 0:
                        end_pos = tag_pos
                        break
                elif tag.startswith('<div'):
                    depth += 1
                
                search_pos = tag_pos + next_tag.end()
            
            if end_pos:
                linea_content = html_content[start_pos:end_pos]
                lineas.append((start_pos, end_pos, linea_content))
                pos = end_pos + 6  # Move past </div>
            else:
                # Fallback: use simple pattern if matching fails
                break
        
        # Fallback to simple pattern if nested matching failed
        if not lineas:
            linea_pattern = r'<div[^>]*class="[^"]*linea_resultados[^"]*"[^>]*>(.*?)</div>'
            simple_lineas = list(re.finditer(linea_pattern, html_content, re.DOTALL | re.IGNORECASE))
            lineas = [(m.start(), m.end(), m.group(1)) for m in simple_lineas]
        
        log.debug("Found {0} result lines (linea_resultados)".format(len(lineas)))
        
        for linea_info in lineas:
            if isinstance(linea_info, tuple):
                _, _, linea_content = linea_info
            else:
                linea_content = linea_info.group(1)
            
            # Extract image URL (thumbnail) - look for img with id="img_principal"
            # The img can be directly in the div or inside an <a> tag
            img_match = re.search(r'<img[^>]*id="img_principal"[^>]*src="([^"]+)"', linea_content, re.IGNORECASE)
            thumb_url = img_match.group(1) if img_match else None
            if thumb_url and not thumb_url.startswith('http'):
                thumb_url = 'https://www.tebeosfera.com' + thumb_url

            full_image_match = re.search(
                r'<a[^>]*href="([^"]+)"[^>]*>\s*<img[^>]*id="img_principal"',
                linea_content,
                re.IGNORECASE
            )
            full_image_url = full_image_match.group(1) if full_image_match else None
            if full_image_url and not full_image_url.startswith('http'):
                full_image_url = 'https://www.tebeosfera.com' + full_image_url
            
            # Extract issue link and slug - need to handle nested tags in link text
            link_match = re.search(r'<a[^>]*href="(/numeros/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
            if not link_match:
                # Try collection link
                link_match = re.search(r'<a[^>]*href="(/colecciones/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
                if link_match:
                    url = link_match.group(1)
                    slug = link_match.group(2)
                    # Extract link text (everything between <a> and </a>, handling nested tags)
                    link_start = link_match.end()
                    link_end_match = re.search(r'</a>', linea_content[link_start:], re.IGNORECASE)
                    if link_end_match:
                        link_text = linea_content[link_start:link_start+link_end_match.start()]
                        title = self._clean_text(self._strip_tags(link_text))
                        
                        results.append({
                            'slug': slug,
                            'title': title,
                            'url': url,
                            'thumb_url': thumb_url,
                            'image_url': full_image_url or thumb_url,
                            'series_name': title,  # For collections, title is the series name
                            'type': 'collection'
                        })
                continue
            
            url = link_match.group(1)
            slug = link_match.group(2)
            
            # Extract link text (everything between <a> and </a>, handling nested tags)
            link_start = link_match.end()
            link_end_match = re.search(r'</a>', linea_content[link_start:], re.IGNORECASE)
            if not link_end_match:
                continue
            link_text = linea_content[link_start:link_start+link_end_match.start()]
            
            # Extract full title from link text
            full_title = self._clean_text(self._strip_tags(link_text))
            
            # Parse series name from format: "SERIE (AÑO, EDITORIAL) NÚMERO : TÍTULO"
            # Or: "SERIE (AÑO, EDITORIAL) NÚMERO"
            # Or: "SERIE (AÑO, EDITORIAL) : TÍTULO"
            # Or: "SERIE -SUBTÍTULO- NÚMERO : TÍTULO"
            series_name = None
            issue_title = None
            
            # Try pattern: "SERIE (AÑO, EDITORIAL) NÚMERO : TÍTULO"
            series_match = re.match(r'^(.+?)\s*\([^)]+\)\s*([^:]*?)\s*:\s*(.+)$', full_title)
            if series_match:
                series_name = self._clean_text(series_match.group(1))
                issue_title = self._clean_text(series_match.group(3))
            else:
                # Try pattern: "SERIE -SUBTÍTULO- NÚMERO : TÍTULO"
                series_match = re.match(r'^(.+?)\s*-\s*([^-]+)\s*-\s*([^:]*?)\s*:\s*(.+)$', full_title)
                if series_match:
                    series_name = self._clean_text(series_match.group(1))
                    issue_title = self._clean_text(series_match.group(4))
                else:
                    # Try pattern: "SERIE (AÑO, EDITORIAL) NÚMERO"
                    series_match = re.match(r'^(.+?)\s*\([^)]+\)\s*([^:]+)$', full_title)
                    if series_match:
                        series_name = self._clean_text(series_match.group(1))
                        issue_title = self._clean_text(series_match.group(2))
                    else:
                        # Try pattern: "SERIE (AÑO, EDITORIAL) : TÍTULO"
                        series_match = re.match(r'^(.+?)\s*\([^)]+\)\s*:\s*(.+)$', full_title)
                        if series_match:
                            series_name = self._clean_text(series_match.group(1))
                            issue_title = self._clean_text(series_match.group(2))
                        else:
                            # Try pattern: "SERIE -SUBTÍTULO- NÚMERO"
                            series_match = re.match(r'^(.+?)\s*-\s*([^-]+)\s*-\s*([^:]+)$', full_title)
                            if series_match:
                                series_name = self._clean_text(series_match.group(1))
                                issue_title = self._clean_text(series_match.group(3))
                            else:
                                # Fallback: use first part before parentheses or dash
                                series_match = re.match(r'^(.+?)(?:\s*\(|\s*-)', full_title)
                                if series_match:
                                    series_name = self._clean_text(series_match.group(1))
                                else:
                                    # Last resort: use slug to guess series name
                                    # Take first 2-3 parts of slug as series name
                                    slug_parts = slug.split('_')
                                    if len(slug_parts) >= 2:
                                        series_name = ' '.join(slug_parts[:2]).replace('_', ' ').title()
                                    else:
                                        series_name = slug.split('_')[0].replace('_', ' ').title()
            
            if series_name:
                results.append({
                    'slug': slug,
                    'title': full_title,
                    'url': url,
                    'thumb_url': thumb_url,
                    'image_url': full_image_url or thumb_url,
                    'series_name': series_name.strip(),
                    'issue_title': issue_title.strip() if issue_title else None,
                    'type': 'issue'
                })

        log.debug("Parser returning {0} total results".format(len(results)))
        return results

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
