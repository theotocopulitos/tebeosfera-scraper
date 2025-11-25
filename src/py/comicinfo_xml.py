'''
ComicInfo.xml Generator Module

This module generates ComicInfo.xml files according to the ComicRack standard schema.
ComicInfo.xml is embedded in CBZ/CBR files to provide metadata for comic readers.

Standard fields reference: https://anansi-project.github.io/docs/comicinfo/schemas/v2.0

@author: Comic Scraper Enhancement Project
'''

import xml.etree.ElementTree as ET
from xml.dom import minidom
from utils_compat import sstr


class ComicInfoGenerator(object):
    '''
    Generates ComicInfo.xml files from comic book metadata.
    Supports both standard ComicRack fields and Spanish-specific extensions.
    '''

    # Supported manga reading directions
    MANGA_NO = "No"
    MANGA_YES = "Yes"
    MANGA_YESANDRIGHTTOLEFT = "YesAndRightToLeft"

    # Age ratings
    AGE_RATING_UNKNOWN = "Unknown"
    AGE_RATING_ADULTS_ONLY = "Adults Only 18+"
    AGE_RATING_MATURE = "Mature 17+"
    AGE_RATING_TEEN = "Teen"
    AGE_RATING_EVERYONE_10 = "Everyone 10+"
    AGE_RATING_EVERYONE = "Everyone"

    def __init__(self):
        '''Initialize the ComicInfo generator'''
        pass

    def generate_xml(self, comic_data):
        '''
        Generate ComicInfo.xml from comic data dictionary.

        comic_data: dictionary with comic metadata. Supported keys:
            # Basic Info
            - 'title': Issue title
            - 'series': Series name
            - 'number': Issue number (string, can be "1", "1.5", "Annual 1", etc.)
            - 'count': Total number of issues in series (integer)
            - 'volume': Volume number (integer)
            - 'alternate_series': Alternate series name
            - 'alternate_number': Alternate issue number
            - 'alternate_count': Alternate issue count
            - 'summary': Story summary/synopsis
            - 'notes': Additional notes

            # Publishing Info
            - 'publisher': Publisher name
            - 'imprint': Imprint/label
            - 'genre': Genre (comma-separated string)
            - 'web': Web URL
            - 'page_count': Number of pages (integer)
            - 'language_iso': Language code (e.g., 'es', 'en', 'fr')

            # Dates (integers)
            - 'year': Publication year
            - 'month': Publication month (1-12)
            - 'day': Publication day (1-31)

            # People (comma-separated strings or lists)
            - 'writer': Writer(s)
            - 'penciller': Penciller(s)
            - 'inker': Inker(s)
            - 'colorist': Colorist(s)
            - 'letterer': Letterer(s)
            - 'cover_artist': Cover artist(s)
            - 'editor': Editor(s)
            - 'translator': Translator(s) [Spanish extension]

            # Story elements (comma-separated strings or lists)
            - 'characters': Character names
            - 'teams': Team names
            - 'locations': Location names
            - 'story_arc': Story arc name
            - 'series_group': Series group

            # Format info
            - 'format': Format (e.g., "Album", "Grapa", "Tomo")
            - 'black_and_white': "Yes" or "No"
            - 'manga': "Yes", "No", or "YesAndRightToLeft"
            - 'age_rating': Age rating string

            # Spanish-specific fields (extensions)
            - 'isbn': ISBN number
            - 'legal_deposit': Depósito Legal
            - 'price': Price with currency
            - 'original_title': Original title if translation
            - 'original_publisher': Original publisher
            - 'collection': Collection/serie name
            - 'binding': Binding type (Cartoné, Rústica, etc.)
            - 'dimensions': Physical dimensions

        Returns: XML string with proper formatting
        '''

        # Create root element
        root = ET.Element('ComicInfo')
        root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        root.set('xmlns:xsd', 'http://www.w3.org/2001/XMLSchema')

        # Add elements in standard order
        self._add_element(root, 'Title', comic_data.get('title'))
        self._add_element(root, 'Series', comic_data.get('series'))
        self._add_element(root, 'Number', comic_data.get('number'))
        self._add_element(root, 'Count', comic_data.get('count'))
        self._add_element(root, 'Volume', comic_data.get('volume'))
        self._add_element(root, 'AlternateSeries', comic_data.get('alternate_series'))
        self._add_element(root, 'AlternateNumber', comic_data.get('alternate_number'))
        self._add_element(root, 'AlternateCount', comic_data.get('alternate_count'))
        self._add_element(root, 'Summary', comic_data.get('summary'))
        self._add_element(root, 'Notes', comic_data.get('notes'))

        # Publishing info
        self._add_element(root, 'Publisher', comic_data.get('publisher'))
        self._add_element(root, 'Imprint', comic_data.get('imprint'))
        self._add_element(root, 'Genre', comic_data.get('genre'))
        self._add_element(root, 'Web', comic_data.get('web'))
        self._add_element(root, 'PageCount', comic_data.get('page_count'))
        self._add_element(root, 'LanguageISO', comic_data.get('language_iso'))
        self._add_element(root, 'Format', comic_data.get('format'))
        self._add_element(root, 'BlackAndWhite', comic_data.get('black_and_white'))
        self._add_element(root, 'Manga', comic_data.get('manga'))
        self._add_element(root, 'AgeRating', comic_data.get('age_rating'))

        # Dates
        year = comic_data.get('year')
        month = comic_data.get('month')
        day = comic_data.get('day')
        if year and year > 0:
            self._add_element(root, 'Year', year)
        if month and month > 0:
            self._add_element(root, 'Month', month)
        if day and day > 0:
            self._add_element(root, 'Day', day)

        # People (convert lists to comma-separated strings)
        self._add_element(root, 'Writer', self._list_to_string(comic_data.get('writer')))
        self._add_element(root, 'Penciller', self._list_to_string(comic_data.get('penciller')))
        self._add_element(root, 'Inker', self._list_to_string(comic_data.get('inker')))
        self._add_element(root, 'Colorist', self._list_to_string(comic_data.get('colorist')))
        self._add_element(root, 'Letterer', self._list_to_string(comic_data.get('letterer')))
        self._add_element(root, 'CoverArtist', self._list_to_string(comic_data.get('cover_artist')))
        self._add_element(root, 'Editor', self._list_to_string(comic_data.get('editor')))
        self._add_element(root, 'Translator', self._list_to_string(comic_data.get('translator')))

        # Story elements
        self._add_element(root, 'Characters', self._list_to_string(comic_data.get('characters')))
        self._add_element(root, 'Teams', self._list_to_string(comic_data.get('teams')))
        self._add_element(root, 'Locations', self._list_to_string(comic_data.get('locations')))
        self._add_element(root, 'StoryArc', comic_data.get('story_arc'))
        self._add_element(root, 'SeriesGroup', comic_data.get('series_group'))

        # GTIN field (ISBN) - according to ComicInfo v2.1 schema
        self._add_element(root, 'GTIN', comic_data.get('isbn'))
        
        # Spanish-specific extensions (stored in Notes if not empty)
        spanish_notes = []
        if comic_data.get('legal_deposit'):
            spanish_notes.append(f"Depósito Legal: {comic_data.get('legal_deposit')}")
        if comic_data.get('price'):
            spanish_notes.append(f"Precio: {comic_data.get('price')}")
        if comic_data.get('original_title'):
            spanish_notes.append(f"Título Original: {comic_data.get('original_title')}")
        if comic_data.get('original_publisher'):
            spanish_notes.append(f"Editorial Original: {comic_data.get('original_publisher')}")
        if comic_data.get('collection'):
            spanish_notes.append(f"Colección: {comic_data.get('collection')}")
        if comic_data.get('binding'):
            spanish_notes.append(f"Encuadernación: {comic_data.get('binding')}")
        if comic_data.get('dimensions'):
            spanish_notes.append(f"Dimensiones: {comic_data.get('dimensions')}")

        # Append Spanish notes to existing notes
        if spanish_notes:
            existing_notes = comic_data.get('notes', '')
            if existing_notes:
                spanish_notes.insert(0, existing_notes)
            notes_element = root.find('Notes')
            if notes_element is not None:
                notes_element.text = '\n'.join(spanish_notes)
            else:
                self._add_element(root, 'Notes', '\n'.join(spanish_notes))

        # Convert to pretty XML string
        return self._prettify_xml(root)

    def _add_element(self, parent, tag, value):
        '''
        Add an XML element only if value is not None/empty.

        parent: parent XML element
        tag: tag name
        value: value to set (string or number)
        '''
        if value is not None and value != '' and value != -1:
            element = ET.SubElement(parent, tag)
            element.text = sstr(value)

    def _list_to_string(self, value):
        '''
        Convert a list to comma-separated string, or return as-is if already string.

        value: list or string
        Returns: comma-separated string or None
        '''
        if value is None:
            return None
        if isinstance(value, list):
            # Filter out None and empty strings
            filtered = [sstr(v).strip() for v in value if v]
            return ', '.join(filtered) if filtered else None
        return sstr(value).strip() if value else None

    def _prettify_xml(self, elem):
        '''
        Return a pretty-printed XML string.

        elem: XML element
        Returns: formatted XML string
        '''
        rough_string = ET.tostring(elem, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')

    def save_to_file(self, comic_data, filepath):
        '''
        Generate and save ComicInfo.xml to file.

        comic_data: dictionary with comic metadata
        filepath: path where to save the XML file
        '''
        xml_content = self.generate_xml(comic_data)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml_content)


def generate_comicinfo_from_bookdata(bookdata):
    '''
    Helper function to generate ComicInfo.xml from a BookData object.

    bookdata: BookData instance
    Returns: XML string
    '''
    generator = ComicInfoGenerator()

    # Map BookData fields to ComicInfo fields
    comic_data = {
        'title': bookdata.title_s,
        'series': bookdata.series_s,
        'number': bookdata.issue_num_s,
        'volume': bookdata.volume_year_n if bookdata.volume_year_n > 0 else None,
        'summary': bookdata.summary_s,
        'notes': bookdata.notes_s,
        'publisher': bookdata.publisher_s,
        'imprint': bookdata.imprint_s,
        'web': bookdata.webpage_s,
        'page_count': bookdata.page_count_n if bookdata.page_count_n > 0 else None,
        'format': bookdata.format_s,
        'year': bookdata.pub_year_n if bookdata.pub_year_n > 0 else None,
        'month': bookdata.pub_month_n if bookdata.pub_month_n > 0 else None,
        'day': bookdata.pub_day_n if bookdata.pub_day_n > 0 else None,
        'writer': bookdata.writers_sl,
        'penciller': bookdata.pencillers_sl,
        'inker': bookdata.inkers_sl,
        'colorist': bookdata.colorists_sl,
        'letterer': bookdata.letterers_sl,
        'cover_artist': bookdata.cover_artists_sl,
        'editor': bookdata.editors_sl,
        'characters': bookdata.characters_sl,
        'teams': bookdata.teams_sl,
        'locations': bookdata.locations_sl,
        'story_arc': ', '.join(bookdata.crossovers_sl) if bookdata.crossovers_sl else None,
    }

    return generator.generate_xml(comic_data)
