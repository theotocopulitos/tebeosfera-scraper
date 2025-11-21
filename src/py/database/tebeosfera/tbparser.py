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
        
        # Extract promotional description / synopsis (multiple patterns)
        # Pattern 0: "Comentario de la editorial:" - very specific and reliable
        # This usually contains the actual synopsis/plot description
        # Also capture relevant technical info (pages, translation) that comes before it
        comentario_match = re.search(r'Comentario\s+de\s+la\s+editorial:', html_content, re.IGNORECASE)
        if comentario_match:
            comentario_start = comentario_match.start()
            
            # Look backwards to find relevant technical info (pages, translation, etc.)
            # Search for paragraphs before "Comentario" that contain book info but not paper/printing info
            before_text = html_content[max(0, comentario_start - 2000):comentario_start]
            before_paras = re.findall(r'<p[^>]*>(.*?)</p>', before_text, re.DOTALL | re.IGNORECASE)
            
            relevant_before = []
            skip_after_keywords = ['papel', 'bosques', 'gestionados', 'sostenible', 'impreso', 'italia', 'spa', 'leg']
            good_before_keywords = ['páginas', 'traducción', 'encuadernado', 'tapa', 'cartoné', 'editorial', 'rotulación', 'editor']
            
            for para in reversed(before_paras):  # Start from closest to comentario
                text = self._clean_text(self._strip_tags(para))
                if text and len(text) > 30:
                    text_lower = text.lower()
                    # Skip if it's about paper/printing (comes after comentario)
                    if any(skip in text_lower for skip in skip_after_keywords):
                        break  # Stop looking backwards if we hit paper info
                    # Include if it has book info keywords
                    if any(good in text_lower for good in good_before_keywords):
                        relevant_before.insert(0, text)  # Add at beginning to maintain order
                        if len(relevant_before) >= 3:  # Limit to 3 paragraphs max
                            break
            
            # Now capture content after "Comentario de la editorial:"
            start_pos = comentario_match.end()
            # Find the end: look for common delimiters
            end_markers = [
                (r'<div[^>]*class="[^"]*tebeoafines', 'tebeoafines div'),
                (r'TEBEOAFINES', 'TEBEOAFINES text'),
                (r'<div[^>]*class="[^"]*(?:row|tab|datos)', 'row/tab div'),
                (r'<h[234]', 'heading tag'),
                (r'</body>', 'body end'),
            ]
            
            # Find the earliest end marker
            end_pos = len(html_content)
            found_marker = None
            for marker_pattern, marker_name in end_markers:
                end_match = re.search(marker_pattern, html_content[start_pos:], re.IGNORECASE)
                if end_match:
                    candidate_end = start_pos + end_match.start()
                    if candidate_end < end_pos:
                        end_pos = candidate_end
                        found_marker = marker_name
            
            # Extract the content after comentario
            if end_pos > start_pos:
                content = html_content[start_pos:end_pos]
                synopsis_after = self._strip_tags(content)
                cleaned_after = self._clean_text_preserve_newlines(synopsis_after)
                
                # Combine: technical info + "Comentario de la editorial:" + synopsis
                all_parts = relevant_before + [cleaned_after] if cleaned_after else relevant_before
                combined = '\n\n'.join(all_parts)
                
                # Only use if it's substantial text (> 100 chars)
                if combined and len(combined) > 100:
                    metadata['synopsis'] = combined
        
        # Pattern 1: "Información de la editorial:" section - capture ALL content including promo
        # This is the most complete source, capturing everything from the description to the end
        
        # Find the start position of "Información de la editorial:" (try multiple formats)
        if not metadata.get('synopsis'):
            # Try different formats
            info_patterns = [
                (r'Información\s+de\s+la\s+editorial:', 'standard'),
                (r'<strong>Información\s+de\s+la\s+editorial:</strong>', 'strong tag'),
                (r'<h[234][^>]*>Información\s+de\s+la\s+editorial:', 'heading'),
            ]
            info_start = None
            pattern_used = None
            for pattern, pattern_name in info_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    info_start = match
                    pattern_used = pattern_name
                    break
            
            if info_start:
                start_pos = info_start.end()
                
                # Find the end: look for common delimiters
                end_markers = [
                    (r'<div[^>]*class="[^"]*tebeoafines', 'tebeoafines div'),
                    (r'TEBEOAFINES', 'TEBEOAFINES text'),
                    (r'Muestras', 'Muestras'),
                    (r'<h[234]', 'heading tag'),
                    (r'</body>', 'body end'),
                ]
                
                # Find the earliest end marker
                end_pos = len(html_content)
                found_marker = None
                for marker_pattern, marker_name in end_markers:
                    end_match = re.search(marker_pattern, html_content[start_pos:], re.IGNORECASE)
                    if end_match:
                        candidate_end = start_pos + end_match.start()
                        if candidate_end < end_pos:
                            end_pos = candidate_end
                            found_marker = marker_name
                
                # Extract the content
                if end_pos > start_pos:
                    content = html_content[start_pos:end_pos]
                    synopsis = self._strip_tags(content)
                    cleaned = self._clean_text_preserve_newlines(synopsis)
                    # Only use if it's substantial text (> 100 chars)
                    if cleaned and len(cleaned) > 100:
                        metadata['synopsis'] = cleaned
        
        # Pattern 1.5: Look for long paragraphs that combine technical info + synopsis
        # These often start with book details but contain the actual synopsis
        if not metadata.get('synopsis'):
            paragraphs = re.findall(
                r'<p[^>]*>(.*?)</p>',
                html_content, re.DOTALL | re.IGNORECASE
            )
            
            for para in paragraphs:
                text = self._clean_text_preserve_newlines(self._strip_tags(para))
                if text and len(text) > 200:  # Must be long (likely combined)
                    text_lower = text.lower()
                    
                    # Check if it has technical info at the start
                    has_tech_start = any(tech in text_lower[:200] for tech in ['libro', 'encuadernado', 'páginas', 'traducción', 'original'])
                    
                    # Check if it has narrative content (quotes, narrative keywords)
                    has_quotes = '"' in text or '&ldquo;' in text or '&rdquo;' in text
                    narrative_keywords = ['muerte', 'vida', 'dios', 'personaje', 'descubrir', 'mundo', 'enfermedad', 'herencia', 'monasterio']
                    has_narrative = any(keyword in text_lower for keyword in narrative_keywords) or has_quotes
                    
                    if has_tech_start and has_narrative:
                        # This is likely a combined paragraph - use it!
                        metadata['synopsis'] = text
                        break
        
        # Pattern 2: "Promoción editorial:" - capture until next section or end
        if not metadata.get('synopsis'):
            promo_patterns = [
                (r'<strong>Promoción editorial:</strong>\s*</p>(.*?)(?:<h[234]|<div[^>]*class="[^"]*(?:row|tab|datos|tebeoafines)|Muestras|$)', 'strong tag'),
                (r'Promoción\s+editorial:\s*</p>(.*?)(?:<h[234]|<div[^>]*class="[^"]*(?:row|tab|datos)|$)', 'text only'),
            ]
            for pattern, pattern_name in promo_patterns:
                promo_match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
                if promo_match:
                    synopsis = self._strip_tags(promo_match.group(1))
                    cleaned = self._clean_text_preserve_newlines(synopsis)
                    if cleaned and len(cleaned) > 50:
                        metadata['synopsis'] = cleaned
                        break
        
        # Pattern 3: "Argumento:" label - capture until next section
        if not metadata.get('synopsis'):
            arg_match = re.search(
                r'<strong>Argumento:</strong>\s*</p>(.*?)(?:<h[234]|<div[^>]*class="[^"]*(?:row|tab|datos))',
                html_content, re.DOTALL | re.IGNORECASE
            )
            if arg_match:
                synopsis = self._strip_tags(arg_match.group(1))
                cleaned = self._clean_text_preserve_newlines(synopsis)
                if cleaned and len(cleaned) > 50:
                    metadata['synopsis'] = cleaned
        
        # Pattern 4: Text in <p class="texto"> (main description) - capture ALL paragraphs
        if not metadata.get('synopsis'):
            # First, find the container that holds the description paragraphs
            # Look for a div or section that contains multiple <p class="texto"> tags
            texto_container = re.search(
                r'(<div[^>]*>.*?<p class="texto"[^>]*>.*?</p>(?:.*?<p[^>]*>.*?</p>)*)',
                html_content, re.DOTALL | re.IGNORECASE
            )
            if texto_container:
                # Extract all paragraphs from this container
                paragraphs = re.findall(
                    r'<p[^>]*>(.*?)</p>',
                    texto_container.group(1), re.DOTALL | re.IGNORECASE
                )
                all_text = []
                for para in paragraphs:
                    text = self._clean_text_preserve_newlines(self._strip_tags(para))
                    if text and len(text) > 10:  # Skip very short paragraphs
                        all_text.append(text)
                
                if all_text:
                    combined = '\n\n'.join(all_text)
                    if len(combined) > 50:
                        metadata['synopsis'] = combined
            else:
                # Fallback: single <p class="texto">
                desc_match = re.search(
                    r'<p class="texto"[^>]*>(.*?)</p>',
                    html_content, re.DOTALL | re.IGNORECASE
                )
                if desc_match:
                    description = self._strip_tags(desc_match.group(1))
                    cleaned_desc = self._clean_text_preserve_newlines(description)
                    if cleaned_desc and len(cleaned_desc) > 20:
                        metadata['synopsis'] = cleaned_desc
        
        # Pattern 5: Look for description section - capture everything between title and next major section
        if not metadata.get('synopsis'):
            # Look for a section that contains substantial descriptive text
            # Common patterns: after "Información" or before "Datos técnicos"
            desc_section = re.search(
                r'(?:Información|Descripción|Argumento)[^<]*:.*?<p[^>]*>(.*?)(?:<h[234]|<div[^>]*class="[^"]*(?:datos|tab|row|tebeoafines)|</body>)',
                html_content, re.DOTALL | re.IGNORECASE
            )
            if desc_section:
                # Extract all paragraphs from this section
                section_content = desc_section.group(1)
                paragraphs = re.findall(
                    r'<p[^>]*>(.*?)</p>',
                    section_content, re.DOTALL | re.IGNORECASE
                )
                all_text = []
                for para in paragraphs:
                    text = self._clean_text_preserve_newlines(self._strip_tags(para))
                    # Skip metadata-like content
                    if text and len(text) > 20 and not any(skip in text.lower() for skip in ['isbn', 'depósito', 'precio', 'páginas', 'formato', 'tamaño']):
                        all_text.append(text)
                
                if all_text:
                    combined = '\n\n'.join(all_text)
                    if len(combined) > 50:
                        metadata['synopsis'] = combined
        
        # Pattern 6: Fallback - find the LONGEST substantial paragraph (not just the first)
        if not metadata.get('synopsis'):
            paragraphs = re.findall(
                r'<p[^>]*>(.*?)</p>',
                html_content, re.DOTALL | re.IGNORECASE
            )
            best_para = None
            best_score = 0
            # Keywords that indicate technical/metadata content (should be skipped)
            skip_keywords = [
                'isbn', 'depósito', 'precio', 'páginas', 'formato', 'tamaño', 'color', 'lengua', 
                'traducción', 'original', 'papel', 'bosques', 'gestionados', 'sostenible', 'impreso',
                'encuadernado', 'tapa', 'semirígida', 'cartoné', 'ediciones', 'editorial', 'traducción',
                'rotulación', 'editor', 'italia', 'spa', 'leg', 'proveniente'
            ]
            # Keywords that indicate a good synopsis (narrative content)
            good_keywords = [
                'historia', 'colección', 'descubrir', 'personajes', 'aventura', 'argumento', 'sinopsis', 
                'narra', 'cuenta', 'viaje', 'embarcan', 'misterioso', 'personaje', 'recorrido', 'gesta',
                'iniciático', 'místico', 'pintados', 'colores', 'inspirad', 'ruedan', 'carreteras',
                'autoestopista', 'veterano', 'silla', 'ruedas', 'mago', 'piernas', 'accidente', 'helicóptero',
                'muerte', 'dios', 'vida', 'soledad', 'silencio', 'monasterio', 'herencia', 'parís', 'mundo',
                'cuestion', 'reencontr', 'enfermedad', 'incurable', 'confront', 'preguntas', 'elecciones',
                'cartujana', 'william', 'méry', 'abandonar', 'descubrirá', 'forjadas', 'antigua'
            ]
            
            for para in paragraphs:
                text = self._clean_text_preserve_newlines(self._strip_tags(para))
                # Look for substantial paragraphs (> 50 chars, not just metadata)
                if text and len(text) > 50:
                    text_lower = text.lower()
                    
                    # Count technical keywords (metadata)
                    skip_count = sum(1 for skip in skip_keywords if skip in text_lower)
                    
                    # Count good keywords (narrative content)
                    good_count = sum(1 for keyword in good_keywords if keyword in text_lower)
                    
                    # Check for quotes (citations) - often indicate synopsis
                    has_quotes = '"' in text or '&ldquo;' in text or '&rdquo;' in text or "'" in text
                    if has_quotes:
                        good_count += 2  # Quotes are a strong indicator of synopsis
                    
                    # IMPORTANT: If paragraph has BOTH technical AND narrative keywords,
                    # it's likely a combined paragraph (technical info + synopsis) - DON'T skip it!
                    # Only skip if it has technical keywords BUT NO narrative keywords AND no quotes
                    if skip_count >= 2 and good_count == 0 and not has_quotes:
                        # Pure technical/metadata paragraph - skip it
                        continue
                    
                    # Score: length + strong bonus for narrative keywords and quotes
                    # If it has narrative keywords or quotes, it's valuable even if it has some technical info
                    score = len(text)
                    if good_count > 0 or has_quotes:
                        score += 500 * good_count  # Very strong bonus for narrative keywords
                        if has_quotes:
                            score += 300  # Bonus for quotes
                        # If it has narrative content, reduce penalty for technical keywords
                        if skip_count > 0:
                            score -= 50 * skip_count  # Small penalty (it's a combined paragraph)
                    else:
                        # No narrative keywords or quotes - apply full penalty for technical keywords
                        if skip_count > 0:
                            score -= 150 * skip_count  # Stronger penalty
                    
                    if score > best_score:
                        best_score = score
                        best_para = text
            
            if best_para:
                metadata['synopsis'] = best_para

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
        series_name = metadata.get('series') or ''
        if series_name:
            series_year_match = re.search(r'\((\d{4})', series_name)
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

            # Historietista = guionista + dibujante
            if 'historietista' in role:
                if name not in metadata['writers']:
                    metadata['writers'].append(name)
                if name not in metadata['pencillers']:
                    metadata['pencillers'].append(name)
            elif 'guion' in role:
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

        # New approach: Parse by sections marked with <div class="help-block">
        # Sections are: Colecciones, Sagas, Números, Autores, etc.
        # Everything between a section header and the next one belongs to that section
        
        # Find all section headers
        section_pattern = r'<div[^>]*class="[^"]*help-block[^"]*"[^>]*>([^<]+)</div>'
        section_matches = list(re.finditer(section_pattern, html_content, re.IGNORECASE))
        
        log.debug("Found {0} section headers".format(len(section_matches)))
        
        # Process each section
        for i, section_match in enumerate(section_matches):
            section_title = self._clean_text(section_match.group(1)).strip()
            section_start = section_match.end()
            
            # Find end of section (start of next section or end of content)
            section_end = len(html_content)
            if i + 1 < len(section_matches):
                section_end = section_matches[i + 1].start()
            
            section_content = html_content[section_start:section_end]
            
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
            
            # Parse results in this section
            section_results = self._parse_section_results(section_content, section_type)
            results.extend(section_results)
            log.debug("Found {0} results in section '{1}'".format(len(section_results), section_title))
        
        # Fallback: if no sections found, use old method
        if not results:
            log.debug("No sections found, falling back to linea_resultados parsing")
            lineas = []
            pos = 0
            while True:
                start_match = re.search(r'<div[^>]*class="[^"]*linea_resultados[^"]*"[^>]*>', html_content[pos:], re.IGNORECASE)
                if not start_match:
                    break
                
                start_pos = pos + start_match.end()
                depth = 1
                search_pos = start_pos
                end_pos = None
                
                while depth > 0 and search_pos < len(html_content):
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
                    pos = end_pos + 6
                else:
                    break
            
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
                
                # Extract link and slug - can be issue, collection, or saga
                # Search for ALL types and prioritize collections/sagas over issues
                # (since a result might have multiple links, we want the main one)
                link_match = None
                result_type = None
                url = None
                slug = None
                
                # Try saga link first (highest priority)
                saga_match = re.search(r'<a[^>]*href="(/sagas/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
                if saga_match:
                    link_match = saga_match
                    result_type = 'saga'
                    url = saga_match.group(1)
                    slug = saga_match.group(2)
                
                # Try collection link (second priority)
                if not link_match:
                    collection_match = re.search(r'<a[^>]*href="(/colecciones/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
                    if collection_match:
                        link_match = collection_match
                        result_type = 'collection'
                        url = collection_match.group(1)
                        slug = collection_match.group(2)
                
                # Try issue link last (lowest priority)
                if not link_match:
                    issue_match = re.search(r'<a[^>]*href="(/numeros/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
                    if issue_match:
                        link_match = issue_match
                        result_type = 'issue'
                        url = issue_match.group(1)
                        slug = issue_match.group(2)
                
                if not link_match:
                    # No recognized link type found
                    continue
                
                # Extract link text (everything between <a> and </a>, handling nested tags)
                link_start = link_match.end()
                link_end_match = re.search(r'</a>', linea_content[link_start:], re.IGNORECASE)
                if not link_end_match:
                    continue
                link_text = linea_content[link_start:link_start+link_end_match.start()]
                title = self._clean_text(self._strip_tags(link_text))
                
                # For collections and sagas, they are series/groups, not individual issues
                if result_type in ['collection', 'saga']:
                    results.append({
                        'slug': slug,
                        'title': title,
                        'url': url,
                        'thumb_url': thumb_url,
                        'image_url': full_image_url or thumb_url,
                        'series_name': title,  # For collections/sagas, title IS the series name
                        'type': result_type
                    })
                    continue
                
                # If we get here, it's an issue (/numeros/)
                # The url, slug, and title were already extracted above
                full_title = title
                
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

    def _parse_section_results(self, section_content, section_type):
        '''
        Parse results from a section (Colecciones, Sagas, Números, etc.)
        
        section_content: HTML content of the section
        section_type: 'collection', 'saga', or 'issue'
        Returns: List of result dictionaries
        '''
        results = []
        from utils_compat import log
        
        # Find all linea_resultados in this section
        lineas = []
        pos = 0
        while True:
            start_match = re.search(r'<div[^>]*class="[^"]*linea_resultados[^"]*"[^>]*>', section_content[pos:], re.IGNORECASE)
            if not start_match:
                break
            
            start_pos = pos + start_match.end()
            depth = 1
            search_pos = start_pos
            end_pos = None
            
            while depth > 0 and search_pos < len(section_content):
                next_tag = re.search(r'</?div[^>]*>', section_content[search_pos:], re.IGNORECASE)
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
                linea_content = section_content[start_pos:end_pos]
                lineas.append(linea_content)
                pos = end_pos + 6
            else:
                break
        
        # Fallback to simple pattern
        if not lineas:
            linea_pattern = r'<div[^>]*class="[^"]*linea_resultados[^"]*"[^>]*>(.*?)</div>'
            simple_lineas = re.finditer(linea_pattern, section_content, re.DOTALL | re.IGNORECASE)
            lineas = [m.group(1) for m in simple_lineas]
        
        # Parse each result in this section
        for linea_content in lineas:
            # Extract image URL (thumbnail)
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
            
            # Find the main link - use the section type to determine which link to look for
            link_match = None
            url = None
            slug = None
            
            if section_type == 'saga':
                link_match = re.search(r'<a[^>]*href="(/sagas/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
            elif section_type == 'collection':
                link_match = re.search(r'<a[^>]*href="(/colecciones/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
            else:  # issue
                link_match = re.search(r'<a[^>]*href="(/numeros/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
            
            if not link_match:
                # Try any link as fallback
                any_link = re.search(r'<a[^>]*href="(/(?:numeros|colecciones|sagas)/([^"]+)\.html)"[^>]*>', linea_content, re.IGNORECASE)
                if any_link:
                    link_match = any_link
                    url = any_link.group(1)
                    slug = any_link.group(2)
            else:
                url = link_match.group(1)
                slug = link_match.group(2)
            
            if not link_match:
                continue
            
            # Extract link text
            link_start = link_match.end()
            link_end_match = re.search(r'</a>', linea_content[link_start:], re.IGNORECASE)
            if not link_end_match:
                continue
            link_text = linea_content[link_start:link_start+link_end_match.start()]
            title = self._clean_text(self._strip_tags(link_text))
            
            # For collections and sagas, title IS the series name
            if section_type in ['collection', 'saga']:
                results.append({
                    'slug': slug,
                    'title': title,
                    'url': url,
                    'thumb_url': thumb_url,
                    'image_url': full_image_url or thumb_url,
                    'series_name': title,
                    'type': section_type
                })
            else:
                # For issues, parse series name from title
                full_title = title
                series_name = None
                issue_title = None
                
                # Try same patterns as before
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
                        series_match = re.match(r'^(.+?)\s*\([^)]+\)\s*([^:]+)$', full_title)
                        if series_match:
                            series_name = self._clean_text(series_match.group(1))
                            issue_title = self._clean_text(series_match.group(2))
                        else:
                            series_match = re.match(r'^(.+?)\s*\([^)]+\)\s*:\s*(.+)$', full_title)
                            if series_match:
                                series_name = self._clean_text(series_match.group(1))
                                issue_title = self._clean_text(series_match.group(2))
                            else:
                                series_match = re.match(r'^(.+?)\s*-\s*([^-]+)\s*-\s*([^:]+)$', full_title)
                                if series_match:
                                    series_name = self._clean_text(series_match.group(1))
                                    issue_title = self._clean_text(series_match.group(3))
                                else:
                                    series_match = re.match(r'^(.+?)(?:\s*\(|\s*-)', full_title)
                                    if series_match:
                                        series_name = self._clean_text(series_match.group(1))
                                    else:
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
