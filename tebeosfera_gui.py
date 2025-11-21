#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
TebeoSfera GUI - Graphical interface for comic metadata scraper

A user-friendly GUI application for scraping Spanish comic metadata
from tebeosfera.com and generating ComicInfo.xml files.

Features:
- Browse and select comic files (CBZ/CBR) or directories
- Recursive directory scanning
- Visual cover preview from comic files
- Search tebeosfera.com with cover previews
- Batch processing of multiple comics
- Progress tracking and logging

@author: Comic Scraper Enhancement Project
'''

import sys
import os
import threading
import queue
import re
import shutil
import webbrowser
from time import strftime

TEBEOSFERA_BASE_URL = "https://www.tebeosfera.com"


def build_series_url(series_key_or_path):
    """Build absolute URL for a series."""
    if not series_key_or_path:
        return None

    path = series_key_or_path.strip()
    if path.startswith('http'):
        return path

    if not path.startswith('/'):
        # assume slug
        path = f"/colecciones/{path}"

    if not path.endswith('.html'):
        path = f"{path}.html"

    return f"{TEBEOSFERA_BASE_URL}{path}"


def build_issue_url(issue_key_or_path):
    """Build absolute URL for an issue."""
    if not issue_key_or_path:
        return None

    path = issue_key_or_path.strip()
    if path.startswith('http'):
        return path

    if not path.startswith('/'):
        path = f"/numeros/{path}"

    if not path.endswith('.html'):
        path = f"{path}.html"

    return f"{TEBEOSFERA_BASE_URL}{path}"


def resize_image_for_preview(image, max_size):
    """Resize image to fit within max_size, allowing upscale."""
    if image is None:
        return None

    max_w, max_h = max_size
    width, height = image.size

    if width == 0 or height == 0:
        return image

    scale = min(float(max_w) / width, float(max_h) / height)
    if scale <= 0:
        return image

    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))

    if new_width == width and new_height == height:
        return image.copy()

    return image.resize((new_width, new_height), ANTIALIAS)

# Add src/py to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'py'))

# Tkinter imports (Python 3)
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from PIL import Image, ImageTk
except ImportError as e:
    print("Error: This GUI requires tkinter and PIL/Pillow")
    print("Install with: pip install pillow")
    sys.exit(1)

MAIN_PREVIEW_SIZE = (480, 720)   # Aspect ratio ~2:3
SEARCH_PREVIEW_SIZE = (460, 690)

try:
    from database.tebeosfera.tbdb import TebeoSferaDB
    from comicinfo_xml import ComicInfoGenerator
    import zipfile
    import tempfile
    from io import BytesIO
except ImportError as e:
    print("Error importing modules: {0}".format(e))
    sys.exit(1)

try:
    import rarfile
except ImportError:
    rarfile = None

# Compatibility for Image.ANTIALIAS
try:
    from PIL.Image import Resampling
    ANTIALIAS = Resampling.LANCZOS
except ImportError:
    # Pillow < 10.0.0
    try:
        from PIL import Image  # ensure Image is available
        ANTIALIAS = Image.ANTIALIAS
    except (AttributeError, ImportError):
        ANTIALIAS = Image.LANCZOS


def extract_title_from_filename(filename):
    '''
    Extract series title from filename using improved parsing.
    Returns the extracted title string.
    '''
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    # Remove content in brackets and parentheses (tags, metadata, etc.)
    # Examples: [Editorial], (2020), [Digital], (c2c)
    name = re.sub(r'\[.*?\]', '', name)  # Remove [anything]
    name = re.sub(r'\(.*?\)', '', name)  # Remove (anything)
    
    # Remove common patterns
    # Remove leading numbers (reading order)
    name = re.sub(r'^\d+[.\s\-_]+', '', name)
    
    # Remove issue numbers at the end (various formats)
    name = re.sub(r'[#\s]*\d+[.\d]*\s*$', '', name)
    name = re.sub(r'[#\s]*\d+[.\d]*\s*[-_]\s*.*$', '', name)
    
    # Remove year patterns
    name = re.sub(r'\b(19|20)\d{2}\b', '', name)
    
    # Replace separators with spaces
    name = re.sub(r'[_\-.]', ' ', name)
    
    # Remove multiple spaces
    name = re.sub(r'\s+', ' ', name)
    
    # Remove trailing/leading separators and numbers
    name = name.strip(' ,-_0123456789')
    
    return name.strip() if name.strip() else os.path.splitext(filename)[0]


class ImageComparator(object):
    '''Compares images to find visual similarity'''

    @staticmethod
    def calculate_dhash(image, hash_size=8):
        '''Calculate difference hash (dHash) for an image'''
        # Resize to hash_size + 1 width, hash_size height
        resized = image.convert('L').resize((hash_size + 1, hash_size), ANTIALIAS)
        pixels = list(resized.getdata())

        # Calculate differences between adjacent pixels
        difference = []
        for row in range(hash_size):
            for col in range(hash_size):
                pixel_left = pixels[row * (hash_size + 1) + col]
                pixel_right = pixels[row * (hash_size + 1) + col + 1]
                difference.append(pixel_left > pixel_right)

        # Convert to hexadecimal hash
        return difference

    @staticmethod
    def hamming_distance(hash1, hash2):
        '''Calculate Hamming distance between two hashes'''
        if len(hash1) != len(hash2):
            return -1
        return sum(h1 != h2 for h1, h2 in zip(hash1, hash2))

    @staticmethod
    def compare_images(image1, image2):
        '''
        Compare two images and return similarity score (0-100)
        100 = identical, 0 = completely different
        '''
        if not image1 or not image2:
            return 0

        try:
            # Calculate dHash for both images
            hash1 = ImageComparator.calculate_dhash(image1)
            hash2 = ImageComparator.calculate_dhash(image2)

            # Calculate Hamming distance
            distance = ImageComparator.hamming_distance(hash1, hash2)

            # Convert to similarity percentage (lower distance = higher similarity)
            max_distance = len(hash1)
            similarity = 100.0 * (1.0 - float(distance) / max_distance)

            return similarity
        except Exception as e:
            print("Error comparing images: {0}".format(e))
            return 0

    @staticmethod
    def compare_histograms(image1, image2):
        '''
        Compare images using histogram correlation (backup method)
        Returns similarity score 0-100
        '''
        if not image1 or not image2:
            return 0

        try:
            # Convert to RGB and resize to same size
            img1 = image1.convert('RGB').resize((100, 100), ANTIALIAS)
            img2 = image2.convert('RGB').resize((100, 100), ANTIALIAS)

            # Get histograms
            h1 = img1.histogram()
            h2 = img2.histogram()

            # Calculate correlation (simplified)
            sum1 = float(sum(h1))
            sum2 = float(sum(h2))

            if sum1 == 0 or sum2 == 0:
                return 0

            # Normalize and compare
            correlation = 0.0
            for i in range(len(h1)):
                correlation += min(h1[i] / sum1, h2[i] / sum2)

            return correlation * 100.0
        except Exception as e:
            print("Error comparing histograms: {0}".format(e))
            return 0

    @staticmethod
    def find_best_match(source_image, candidate_images):
        '''
        Find the best matching image from a list of candidates
        Returns (best_index, similarity_scores)
        '''
        if not source_image or not candidate_images:
            return -1, []

        scores = []
        for candidate in candidate_images:
            if candidate:
                # Use dHash as primary method
                score_dhash = ImageComparator.compare_images(source_image, candidate)
                # Use histogram as secondary for validation
                score_hist = ImageComparator.compare_histograms(source_image, candidate)
                # Weighted average (dHash is more reliable for similar images)
                final_score = score_dhash * 0.7 + score_hist * 0.3
                scores.append(final_score)
            else:
                scores.append(0)

        if not scores:
            return -1, []

        best_index = scores.index(max(scores))
        return best_index, scores


class ComicFile(object):
    '''Represents a comic file to be scraped'''

    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.cover_image = None
        self.metadata = None
        self.selected_issue = None
        self.status = 'pending'  # pending, searching, selected, completed, error
        self.error_msg = None
        self.image_entries = []
        self.total_pages = 0
        self.current_page_index = 0
        self.archive_type = None

    def extract_cover(self):
        '''Extract the first page (cover) from the comic file'''
        image = self.get_page_image(0)
        if image:
            self.cover_image = image
        return image

    def load_image_entries(self):
        '''Load ordered list of image entries inside archive'''
        if self.image_entries:
            return

        self.error_msg = None
        entries = []

        try:
            if rarfile and self.filepath.lower().endswith('.cbr') and rarfile.is_rarfile(self.filepath):
                self.archive_type = 'rar'
                with rarfile.RarFile(self.filepath, 'r') as rf:
                    entries = [
                        f for f in rf.namelist()
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))
                    ]
            elif zipfile.is_zipfile(self.filepath):
                self.archive_type = 'zip'
                with zipfile.ZipFile(self.filepath, 'r') as zf:
                    entries = [
                        f for f in zf.namelist()
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))
                    ]
            else:
                self.error_msg = "Formato de archivo no soportado"
                return

            entries.sort()
            self.image_entries = entries
            self.total_pages = len(entries)
            if not self.total_pages:
                self.error_msg = "No se encontraron imágenes en el archivo"
            self.current_page_index = 0
        except Exception as e:
            print("Error cargando páginas de {0}: {1}".format(self.filename, e))
            self.error_msg = "Error cargando páginas: {0}".format(str(e))
            self.image_entries = []
            self.total_pages = 0

    def _read_image_data(self, entry_name):
        try:
            if self.archive_type == 'zip':
                with zipfile.ZipFile(self.filepath, 'r') as zf:
                    return zf.read(entry_name)
            elif self.archive_type == 'rar' and rarfile:
                with rarfile.RarFile(self.filepath, 'r') as rf:
                    return rf.read(entry_name)
        except Exception as e:
            self.error_msg = "Error leyendo página: {0}".format(str(e))
        return None

    def get_page_image(self, page_index=None):
        '''Return PIL image for given page index'''
        self.load_image_entries()
        if not self.image_entries:
            return None

        if page_index is None:
            page_index = self.current_page_index

        page_index = max(0, min(page_index, len(self.image_entries) - 1))
        entry_name = self.image_entries[page_index]
        data = self._read_image_data(entry_name)
        if not data:
            return None

        try:
            image = Image.open(BytesIO(data))
            self.current_page_index = page_index
            return image
        except Exception as e:
            self.error_msg = "Error abriendo imagen: {0}".format(str(e))
            return None


class TebeoSferaGUI(tk.Tk):
    '''Main GUI application window'''

    def __init__(self):
        tk.Tk.__init__(self)

        self.title("TebeoSfera Scraper - Comic Metadata Editor")
        self.geometry("1200x800")

        # Comic files list
        self.comic_files = []
        self.current_comic_index = 0

        # Thread-safe queue for UI updates
        self.update_queue = queue.Queue()

        # Create UI first (so log_text is available)
        self._create_menu()
        self._create_toolbar()
        self._create_main_panel()
        self._create_status_bar()

        # Initialize scraper with log callback (after UI is created)
        self.db = TebeoSferaDB(log_callback=self._log)
        self.xml_generator = ComicInfoGenerator()

        # Start queue processor
        self.after(100, self._process_queue)

        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Check dependencies after UI is ready
        self.after(500, self._check_dependencies)

    def _check_dependencies(self):
        '''Check for optional dependencies and system tools'''
        # Check for rarfile and unrar
        if rarfile:
            # Check if unrar executable is in PATH
            # rarfile needs 'unrar' or 'rar' command line tool
            has_unrar = shutil.which("unrar") or shutil.which("rar")
            
            # On Windows, sometimes it's just 'UnRAR.exe' but checking 'unrar' works if in PATH
            if not has_unrar and os.name == 'nt':
                # Common default paths check (optional, but helpful)
                common_paths = [
                    r"C:\Program Files\WinRAR\UnRAR.exe",
                    r"C:\Program Files (x86)\WinRAR\UnRAR.exe"
                ]
                for path in common_paths:
                    if os.path.exists(path):
                        # If found in standard location but not in PATH, we could potentially configure rarfile
                        # rarfile.UNRAR_TOOL = path
                        # But better to warn user to add to PATH or let them know
                        has_unrar = True # It exists, just not in PATH. rarfile might not find it by default.
                        self._log(f"ℹ️ UnRAR detectado en {path} (no en PATH)")
                        # We could try to set it:
                        rarfile.UNRAR_TOOL = path
                        break

            if not has_unrar:
                msg = (
                    "Soporte CBR limitado:\n"
                    "El módulo 'rarfile' está instalado, pero no se encontró 'unrar' o 'rar'.\n\n"
                    "Para abrir archivos .cbr, necesita:\n"
                    "1. Descargar UnRAR (o WinRAR)\n"
                    "2. Añadir la carpeta de instalación al PATH del sistema\n\n"
                    "Los archivos .cbz funcionarán correctamente."
                )
                self._log("⚠️ Advertencia: 'unrar' no encontrado en el sistema.")
                messagebox.showwarning("Dependencia faltante", msg)
            else:
                self._log("✅ Soporte CBR activo (rarfile + unrar detectado)")

    def _create_menu(self):
        '''Create menu bar'''
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Abrir archivo(s)...", command=self._open_files)
        file_menu.add_command(label="Abrir directorio...", command=self._open_directory)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self._on_close)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Editar", menu=edit_menu)
        edit_menu.add_command(label="Procesar seleccionados", command=self._process_selected)
        edit_menu.add_command(label="Procesar todos", command=self._process_all)
        edit_menu.add_separator()
        edit_menu.add_command(label="Limpiar lista", command=self._clear_list)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de...", command=self._show_about)

    def _create_toolbar(self):
        '''Create toolbar with quick actions'''
        toolbar = tk.Frame(self, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="📁 Abrir archivos", command=self._open_files).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="📂 Abrir carpeta", command=self._open_directory).pack(side=tk.LEFT, padx=2, pady=2)

        tk.Frame(toolbar, width=20).pack(side=tk.LEFT)  # Spacer

        tk.Button(toolbar, text="▶ Procesar seleccionados", command=self._process_selected).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(toolbar, text="▶▶ Procesar todos", command=self._process_all).pack(side=tk.LEFT, padx=2, pady=2)

        tk.Frame(toolbar, width=20).pack(side=tk.LEFT)  # Spacer

        self.recursive_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar, text="Subdirectorios", variable=self.recursive_var).pack(side=tk.LEFT, padx=2, pady=2)

    def _create_main_panel(self):
        '''Create main content area'''
        # Main container with panedwindow for resizable split
        paned = tk.PanedWindow(self, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Top panel - Main content
        top_paned = tk.PanedWindow(paned, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        paned.add(top_paned, minsize=400)

        # Left panel - File list
        left_frame = tk.Frame(top_paned)
        top_paned.add(left_frame, minsize=300)

        tk.Label(left_frame, text="Comics encontrados:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=5)

        # Listbox with scrollbar
        list_frame = tk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind('<<ListboxSelect>>', self._on_file_select)

        scrollbar.config(command=self.file_listbox.yview)

        # Right panel - Preview and details (REORGANIZADO COMPLETAMENTE)
        right_frame = tk.Frame(top_paned)
        top_paned.add(right_frame, minsize=400)

        # ========== SECCIÓN 1: PORTADA + METADATOS (dividido verticalmente) ==========
        preview_section = tk.Frame(right_frame)
        preview_section.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(preview_section, text="Vista previa:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        # PanedWindow para dividir portada (izquierda) y metadatos (derecha)
        preview_paned = tk.PanedWindow(preview_section, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        preview_paned.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        
        # ===== IZQUIERDA: PORTADA =====
        cover_frame = tk.Frame(preview_paned, bg='gray80', relief=tk.SUNKEN, bd=2)
        preview_paned.add(cover_frame, minsize=200)
        
        self.cover_canvas = tk.Canvas(cover_frame, bg='gray90', highlightthickness=0)
        self.cover_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Placeholder text
        self.cover_canvas.create_text(
            200, 300,
            text="Selecciona un comic\npara ver su portada",
            font=('Arial', 12), fill='gray40', tags='placeholder'
        )
        
        # Keep a reference for the label (needed for image persistence)
        self.cover_label = tk.Label(self.cover_canvas)  # Dummy label for image reference
        
        # ===== DERECHA: METADATOS EXISTENTES =====
        metadata_frame = tk.Frame(preview_paned)
        preview_paned.add(metadata_frame, minsize=200)
        
        # Header con título y toggle XML/Bonito
        metadata_header = tk.Frame(metadata_frame)
        metadata_header.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(metadata_header, text="Metadatos en archivo:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
        
        self.metadata_view_mode = tk.StringVar(value="pretty")  # "xml" or "pretty"
        tk.Button(metadata_header, text="XML", command=lambda: self._toggle_metadata_view("xml"),
                 width=6, relief=tk.RAISED).pack(side=tk.RIGHT, padx=2)
        tk.Button(metadata_header, text="Bonito", command=lambda: self._toggle_metadata_view("pretty"),
                 width=6, relief=tk.SUNKEN).pack(side=tk.RIGHT, padx=2)
        
        # Store button references for styling
        self.metadata_xml_button = None
        self.metadata_pretty_button = None
        # Get references after packing
        for widget in metadata_header.winfo_children():
            if isinstance(widget, tk.Button):
                if widget['text'] == "XML":
                    self.metadata_xml_button = widget
                elif widget['text'] == "Bonito":
                    self.metadata_pretty_button = widget
        
        metadata_text_frame = tk.Frame(metadata_frame)
        metadata_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.metadata_display = tk.Text(metadata_text_frame, wrap=tk.WORD, font=('Courier', 9))
        metadata_scrollbar = tk.Scrollbar(metadata_text_frame, command=self.metadata_display.yview)
        self.metadata_display.config(yscrollcommand=metadata_scrollbar.set, state=tk.DISABLED)
        metadata_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.metadata_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Store current metadata for toggling
        self.current_metadata_xml = None
        self.current_metadata_dict = None

        # ========== SECCIÓN 2: NAVEGACIÓN DE PÁGINAS ==========
        page_nav_frame = tk.Frame(right_frame, relief=tk.GROOVE, bd=2)
        page_nav_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Spacer to center the navigation controls
        tk.Frame(page_nav_frame).pack(side=tk.LEFT, expand=True)
        
        self.prev_page_button = tk.Button(page_nav_frame, text="⬅",
                                          command=self._show_prev_page, state=tk.DISABLED,
                                          width=3, font=('Arial', 12, 'bold'))
        self.prev_page_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.page_info_label = tk.Label(page_nav_frame, text="0/0", 
                                       font=('Arial', 11, 'bold'), width=10)
        self.page_info_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.next_page_button = tk.Button(page_nav_frame, text="➡",
                                          command=self._show_next_page, state=tk.DISABLED,
                                          width=3, font=('Arial', 12, 'bold'))
        self.next_page_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Spacer to center the navigation controls
        tk.Frame(page_nav_frame).pack(side=tk.LEFT, expand=True)

        # ========== SECCIÓN 3: BOTONES DE ACCIÓN ==========
        button_frame = tk.Frame(right_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(button_frame, text="🔍 Buscar en TebeoSfera", command=self._search_current,
                 height=2).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        tk.Button(button_frame, text="💾 Generar ComicInfo.xml", command=self._generate_xml_current,
                 height=2).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        tk.Button(button_frame, text="🌐 Abrir en navegador", command=self._open_current_in_browser,
                 height=2).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # ========== PANEL INFERIOR: DETALLES + LOG (horizontal) ==========
        bottom_panel = tk.Frame(paned)
        paned.add(bottom_panel, minsize=150)
        
        # Detalles a la izquierda (ocupando todo el ancho disponible)
        details_frame = tk.Frame(bottom_panel)
        details_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=5, pady=5)

        tk.Label(details_frame, text="Detalles:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        details_text_frame = tk.Frame(details_frame)
        details_text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.details_text = tk.Text(details_text_frame, height=4, wrap=tk.WORD)
        details_scrollbar = tk.Scrollbar(details_text_frame, command=self.details_text.yview)
        self.details_text.config(yscrollcommand=details_scrollbar.set)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Log debajo de Detalles
        log_frame = tk.Frame(bottom_panel)
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=(0,5))
        
        log_header = tk.Frame(log_frame)
        log_header.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        tk.Label(log_header, text="Log:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        tk.Button(log_header, text="Limpiar", command=self._clear_log, width=8).pack(side=tk.RIGHT, padx=5)
        tk.Button(log_header, text="Guardar", command=self._save_log, width=8).pack(side=tk.RIGHT, padx=5)
        
        # Log text area with scrollbar
        log_text_frame = tk.Frame(log_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        log_scrollbar = tk.Scrollbar(log_text_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_text_frame, height=8, wrap=tk.WORD, 
                                yscrollcommand=log_scrollbar.set,
                                font=('Consolas', 9), bg='#f5f5f5')
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.log_text.yview)
        
        # Make log read-only
        self.log_text.config(state=tk.DISABLED)
        
        # Initialize log
        self._log("🚀 TebeoSfera Scraper iniciado")

    def _create_status_bar(self):
        '''Create status bar'''
        self.status_bar = tk.Label(self, text="Listo", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Progress bar
        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, mode='determinate')
        # Initially hidden

    def _open_files(self):
        '''Open file dialog to select comic files'''
        filetypes = [
            ('Archivos de comic', '*.cbz *.cbr'),
            ('CBZ files', '*.cbz'),
            ('CBR files', '*.cbr'),
            ('Todos los archivos', '*.*')
        ]

        filenames = filedialog.askopenfilenames(title="Seleccionar comics", filetypes=filetypes)

        if filenames:
            self._add_files(filenames)

    def _open_directory(self):
        '''Open directory dialog and scan for comic files'''
        directory = filedialog.askdirectory(title="Seleccionar carpeta")

        if directory:
            self._scan_directory(directory, self.recursive_var.get())

    def _add_files(self, filepaths):
        '''Add files to the list'''
        for filepath in filepaths:
            if filepath.lower().endswith(('.cbz', '.cbr')):
                comic = ComicFile(filepath)
                self.comic_files.append(comic)
                self.file_listbox.insert(tk.END, comic.filename)

        self._update_status("{0} comics cargados".format(len(self.comic_files)))

    def _scan_directory(self, directory, recursive=True):
        '''Scan directory for comic files'''
        self._update_status("Escaneando directorio...")

        comic_files = []

        if recursive:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    if filename.lower().endswith(('.cbz', '.cbr')):
                        filepath = os.path.join(root, filename)
                        comic_files.append(filepath)
        else:
            for filename in os.listdir(directory):
                if filename.lower().endswith(('.cbz', '.cbr')):
                    filepath = os.path.join(directory, filename)
                    comic_files.append(filepath)

        if comic_files:
            self._add_files(comic_files)
        else:
            messagebox.showinfo("Sin resultados", "No se encontraron archivos de comic en el directorio")

    def _clear_list(self):
        '''Clear the file list'''
        if messagebox.askyesno("Confirmar", "¿Limpiar toda la lista de comics?"):
            self.comic_files = []
            self.file_listbox.delete(0, tk.END)
            self._update_status("Lista limpiada")

    def _on_file_select(self, event):
        '''Handle file selection in listbox'''
        selection = self.file_listbox.curselection()
        if selection:
            index = selection[0]
            self.current_comic_index = index
            self._show_comic_preview(index)

    def _show_comic_preview(self, index):
        '''Show preview of selected comic'''
        if index < 0 or index >= len(self.comic_files):
            return

        comic = self.comic_files[index]
        comic.current_page_index = 0
        
        # Load all pages first
        comic.load_image_entries()
        self._log(f"📚 Cómic seleccionado: {comic.filename} ({comic.total_pages} páginas)")
        
        # Display first page (portada)
        self._display_comic_page(comic, 0)
        
        # Display existing metadata from file
        self._display_existing_metadata(comic)

        # Show details
        details = "Archivo: {0}\n".format(comic.filename)
        details += "Ruta: {0}\n".format(comic.filepath)
        details += "Páginas: {0}\n".format(comic.total_pages)
        details += "Estado: {0}\n".format(comic.status)

        if comic.metadata:
            details += "\nMetadatos encontrados:\n"
            details += "Serie: {0}\n".format(comic.metadata.get('series', 'N/A'))
            details += "Número: {0}\n".format(comic.metadata.get('number', 'N/A'))

        self.details_text.delete('1.0', tk.END)
        self.details_text.insert('1.0', details)
    
    def _display_existing_metadata(self, comic):
        '''Display existing ComicInfo.xml metadata from the comic file'''
        self.metadata_display.config(state=tk.NORMAL)
        self.metadata_display.delete('1.0', tk.END)
        
        try:
            metadata_xml = self._extract_comicinfo(comic.filepath)
            
            if metadata_xml:
                # Store for toggling
                self.current_metadata_xml = metadata_xml
                
                # Parse XML to dictionary
                self.current_metadata_dict = self._parse_comicinfo_xml(metadata_xml)
                
                # Display in current mode
                self._render_metadata_view()
                
                self._log("📋 ComicInfo.xml encontrado en el archivo")
            else:
                self.current_metadata_xml = None
                self.current_metadata_dict = None
                self.metadata_display.insert('1.0', "No se encontró ComicInfo.xml\nen este archivo.\n\nPuedes agregar metadatos\nbuscando en TebeoSfera.")
        
        except Exception as e:
            self.current_metadata_xml = None
            self.current_metadata_dict = None
            self.metadata_display.insert('1.0', f"Error leyendo metadatos:\n{str(e)}")
        
        self.metadata_display.config(state=tk.DISABLED)
    
    def _parse_comicinfo_xml(self, xml_string):
        '''Parse ComicInfo.xml to a dictionary'''
        import xml.etree.ElementTree as ET
        metadata = {}
        
        try:
            root = ET.fromstring(xml_string)
            for child in root:
                if child.text and child.text.strip():
                    metadata[child.tag] = child.text.strip()
        except:
            pass
        
        return metadata
    
    def _toggle_metadata_view(self, mode):
        '''Toggle between XML and Pretty view'''
        self.metadata_view_mode.set(mode)
        
        # Update button styles
        if self.metadata_xml_button and self.metadata_pretty_button:
            if mode == "xml":
                self.metadata_xml_button.config(relief=tk.SUNKEN)
                self.metadata_pretty_button.config(relief=tk.RAISED)
            else:
                self.metadata_xml_button.config(relief=tk.RAISED)
                self.metadata_pretty_button.config(relief=tk.SUNKEN)
        
        self._render_metadata_view()
    
    def _render_metadata_view(self):
        '''Render metadata in current view mode'''
        if not self.current_metadata_xml and not self.current_metadata_dict:
            return
        
        self.metadata_display.config(state=tk.NORMAL)
        self.metadata_display.delete('1.0', tk.END)
        
        mode = self.metadata_view_mode.get()
        
        if mode == "xml":
            # Show formatted XML
            import xml.dom.minidom as minidom
            try:
                dom = minidom.parseString(self.current_metadata_xml)
                formatted_xml = dom.toprettyxml(indent="  ")
                # Remove extra blank lines
                formatted_xml = '\n'.join([line for line in formatted_xml.split('\n') if line.strip()])
                self.metadata_display.insert('1.0', formatted_xml)
            except:
                # If parsing fails, just show raw XML
                self.metadata_display.insert('1.0', self.current_metadata_xml)
        
        else:  # pretty mode
            # Show formatted key-value pairs
            if self.current_metadata_dict:
                # Field mapping for better display
                field_labels = {
                    'Title': '📖 Título',
                    'Series': '📚 Serie',
                    'Number': '🔢 Número',
                    'Count': '📊 Total',
                    'Volume': '📙 Volumen',
                    'Summary': '📝 Resumen',
                    'Notes': '📋 Notas',
                    'Publisher': '🏢 Editorial',
                    'Imprint': '🏷️ Sello',
                    'Genre': '🎭 Género',
                    'Web': '🌐 Web',
                    'PageCount': '📄 Páginas',
                    'LanguageISO': '🌍 Idioma',
                    'Format': '📐 Formato',
                    'AgeRating': '🔞 Edad',
                    'Writer': '✍️ Guionista',
                    'Penciller': '🖊️ Dibujante',
                    'Inker': '🖋️ Entintador',
                    'Colorist': '🎨 Colorista',
                    'Letterer': '✒️ Letrista',
                    'CoverArtist': '🖼️ Portadista',
                    'Editor': '📝 Editor',
                    'Translator': '🔤 Traductor',
                    'Year': '📅 Año',
                    'Month': '📅 Mes',
                    'Day': '📅 Día',
                }
                
                output = []
                for key, value in self.current_metadata_dict.items():
                    label = field_labels.get(key, key)
                    
                    # Special handling for long fields
                    if key in ['Summary', 'Notes']:
                        output.append(f"\n{label}:\n{value}\n")
                    else:
                        output.append(f"{label}: {value}")
                
                self.metadata_display.insert('1.0', '\n'.join(output))
            else:
                self.metadata_display.insert('1.0', "No se pudieron parsear los metadatos")
        
        self.metadata_display.config(state=tk.DISABLED)
    
    def _extract_comicinfo(self, filepath):
        '''Extract ComicInfo.xml from CBZ/CBR file'''
        try:
            if filepath.lower().endswith('.cbz') and zipfile.is_zipfile(filepath):
                with zipfile.ZipFile(filepath, 'r') as zf:
                    if 'ComicInfo.xml' in zf.namelist():
                        return zf.read('ComicInfo.xml').decode('utf-8')
            
            elif rarfile and filepath.lower().endswith('.cbr') and rarfile.is_rarfile(filepath):
                with rarfile.RarFile(filepath, 'r') as rf:
                    if 'ComicInfo.xml' in rf.namelist():
                        return rf.read('ComicInfo.xml').decode('utf-8')
        
        except Exception as e:
            self._log(f"⚠️ Error extrayendo ComicInfo.xml: {e}")
        
        return None

    def _display_comic_page(self, comic, page_index=None):
        '''Display a specific page from the selected comic'''
        image = comic.get_page_image(page_index)
        if image:
            # Get canvas actual size
            self.cover_canvas.update_idletasks()
            canvas_width = self.cover_canvas.winfo_width()
            canvas_height = self.cover_canvas.winfo_height()
            
            # Use reasonable defaults if canvas not yet sized
            if canvas_width < 10:
                canvas_width = 400
            if canvas_height < 10:
                canvas_height = 600
            
            # Scale image to fit canvas while maintaining aspect ratio
            img_width, img_height = image.size
            width_ratio = canvas_width / img_width
            height_ratio = canvas_height / img_height
            scale = min(width_ratio, height_ratio)
            
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            display_img = image.resize((new_width, new_height), ANTIALIAS)
            photo = ImageTk.PhotoImage(display_img)
            
            # Center image in canvas
            x_offset = (canvas_width - new_width) // 2
            y_offset = (canvas_height - new_height) // 2
            
            # Update label with image
            self.cover_label.config(image=photo, text='')
            self.cover_label.image = photo
            
            # Position label centered in canvas
            self.cover_canvas.delete("all")
            self.cover_canvas.create_image(x_offset, y_offset, image=photo, anchor=tk.NW)
            self.cover_canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
        else:
            msg = comic.error_msg if comic.error_msg else 'No se pudo extraer la portada'
            self.cover_canvas.delete("all")
            self.cover_canvas.create_text(
                self.cover_canvas.winfo_width() // 2 if self.cover_canvas.winfo_width() > 10 else 200,
                self.cover_canvas.winfo_height() // 2 if self.cover_canvas.winfo_height() > 10 else 300,
                text=msg, font=('Arial', 12), fill='gray40'
            )
            self.cover_label.image = None

        # Update buttons and page counter
        self._update_page_buttons_state(comic)
        return image is not None

    def _update_page_buttons_state(self, comic):
        '''Update page navigation button states based on current page'''
        if not hasattr(self, 'prev_page_button') or not hasattr(self, 'next_page_button'):
            return
        
        total = comic.total_pages or len(comic.image_entries) or 0
        current = comic.current_page_index
        
        # Always show the buttons frame and update info
        if hasattr(self, 'page_info_label'):
            if total > 0:
                self.page_info_label.config(text=f"{current + 1}/{total}")
            else:
                self.page_info_label.config(text="0/0")
        
        # Enable/disable buttons based on page count and position
        if total > 1:
            # Enable prev if not on first page
            self.prev_page_button.config(
                state=tk.NORMAL if current > 0 else tk.DISABLED)
            # Enable next if not on last page
            self.next_page_button.config(
                state=tk.NORMAL if current < total - 1 else tk.DISABLED)
            self._log(f"📖 Navegación habilitada: página {current + 1} de {total}")
        else:
            # Disable both if only 1 or 0 pages
            self.prev_page_button.config(state=tk.DISABLED)
            self.next_page_button.config(state=tk.DISABLED)
            if total == 1:
                self._log(f"ℹ️ Cómic con una sola página - navegación deshabilitada")

    def _show_prev_page(self):
        '''Show previous page of current comic'''
        if self.current_comic_index < 0 or self.current_comic_index >= len(self.comic_files):
            return
        comic = self.comic_files[self.current_comic_index]
        total = comic.total_pages or len(comic.image_entries)
        if not total:
            return
        target = max(0, comic.current_page_index - 1)
        self._display_comic_page(comic, target)

    def _show_next_page(self):
        '''Show next page of current comic'''
        if self.current_comic_index < 0 or self.current_comic_index >= len(self.comic_files):
            return
        comic = self.comic_files[self.current_comic_index]
        total = comic.total_pages or len(comic.image_entries)
        if not total:
            return
        target = min(total - 1, comic.current_page_index + 1)
        self._display_comic_page(comic, target)

    def _search_current(self):
        '''Search tebeosfera for current comic'''
        if self.current_comic_index < 0 or self.current_comic_index >= len(self.comic_files):
            messagebox.showwarning("Advertencia", "Selecciona un comic primero")
            return

        comic = self.comic_files[self.current_comic_index]

        # Open search dialog
        SearchDialog(self, comic, self.db)

    def _generate_xml_current(self):
        '''Generate ComicInfo.xml for current comic'''
        if self.current_comic_index < 0 or self.current_comic_index >= len(self.comic_files):
            messagebox.showwarning("Advertencia", "Selecciona un comic primero")
            return

        comic = self.comic_files[self.current_comic_index]

        if not comic.selected_issue:
            messagebox.showwarning("Advertencia", "Primero busca y selecciona el issue en TebeoSfera")
            return

        # Generate and inject XML
        try:
            xml_content = self.xml_generator.generate_xml(comic.metadata)

            # Check if it's CBR
            if comic.filepath.lower().endswith('.cbr'):
                if not rarfile:
                    messagebox.showerror("Error", "No se puede procesar CBR sin el módulo 'rarfile'")
                    return

                if messagebox.askyesno("Confirmar conversión", 
                                      "El archivo es CBR (RAR). Para inyectar el XML es necesario convertirlo a CBZ (ZIP).\n\n"
                                      "¿Desea convertirlo ahora?\n(Se creará un nuevo archivo .cbz y se eliminará el .cbr)"):
                    new_path = self._convert_cbr_to_cbz(comic.filepath)
                    if new_path:
                        comic.filepath = new_path
                        comic.filename = os.path.basename(new_path)
                        self._inject_xml(comic.filepath, xml_content)
                        # Update listbox
                        self.file_listbox.delete(self.current_comic_index)
                        self.file_listbox.insert(self.current_comic_index, comic.filename)
                        self.file_listbox.selection_set(self.current_comic_index)
                        
                        comic.status = 'completed'
                        messagebox.showinfo("Éxito", "Conversión a CBZ e inyección de XML completada")
                    else:
                        comic.status = 'error'
                        messagebox.showerror("Error", "Falló la conversión a CBZ")
                else:
                    return
            else:
                # Inject into CBZ
                self._inject_xml(comic.filepath, xml_content)
                comic.status = 'completed'
                messagebox.showinfo("Éxito", "ComicInfo.xml generado e inyectado correctamente")

        except Exception as e:
            comic.status = 'error'
            messagebox.showerror("Error", "Error generando XML: {0}".format(e))

    def _convert_cbr_to_cbz(self, cbr_path):
        '''Convert CBR to CBZ (ZIP without compression)'''
        import shutil
        
        cbz_path = os.path.splitext(cbr_path)[0] + '.cbz'
        temp_dir = tempfile.mkdtemp()
        
        try:
            self._update_status("Convirtiendo CBR a CBZ...")
            self._log("📦 Extrayendo CBR...")
            
            # Extract CBR
            with rarfile.RarFile(cbr_path) as rf:
                rf.extractall(temp_dir)
            
            self._log("📦 Creando CBZ sin compresión...")
            # Create CBZ WITHOUT compression (ZIP_STORED)
            # CBZ files are typically uncompressed to allow direct image access
            with zipfile.ZipFile(cbz_path, 'w', zipfile.ZIP_STORED) as zip_out:
                for root, dirs, files in os.walk(temp_dir):
                    # Sort files to maintain page order
                    files.sort()
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        self._log(f"  Añadiendo: {arcname}")
                        zip_out.write(file_path, arcname)
            
            # Delete original CBR if successful
            if os.path.exists(cbz_path):
                self._log(f"✅ CBZ creado: {os.path.basename(cbz_path)}")
                self._log(f"🗑️ Eliminando CBR original...")
                os.remove(cbr_path)
                return cbz_path
                
            return None
            
        except Exception as e:
            self._log(f"❌ Error convirtiendo CBR a CBZ: {e}")
            print("Error converting CBR to CBZ: {0}".format(e))
            # Cleanup incomplete CBZ
            if os.path.exists(cbz_path):
                os.remove(cbz_path)
            return None
            
        finally:
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

    def _inject_xml(self, cbz_path, xml_content):
        '''Inject ComicInfo.xml into CBZ file (without compression)'''
        import shutil
        temp_dir = tempfile.mkdtemp()
        temp_cbz = os.path.join(temp_dir, 'temp.cbz')

        try:
            self._log("📝 Inyectando ComicInfo.xml...")
            with zipfile.ZipFile(cbz_path, 'r') as zip_in:
                # Use ZIP_STORED (no compression) for CBZ
                with zipfile.ZipFile(temp_cbz, 'w', zipfile.ZIP_STORED) as zip_out:
                    # Copy all existing files except old ComicInfo.xml
                    for item in zip_in.infolist():
                        if item.filename != 'ComicInfo.xml':
                            data = zip_in.read(item.filename)
                            # Preserve original compression info
                            zip_out.writestr(item, data)

                    # Add ComicInfo.xml without compression
                    zip_out.writestr('ComicInfo.xml', xml_content.encode('utf-8'), 
                                   compress_type=zipfile.ZIP_STORED)

            shutil.move(temp_cbz, cbz_path)
            self._log("✅ ComicInfo.xml inyectado correctamente")

        finally:
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

    def _process_selected(self):
        '''Process selected comics'''
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona al menos un comic")
            return

        indices = list(selection)
        self._process_batch(indices)

    def _process_all(self):
        '''Process all comics in list'''
        if not self.comic_files:
            messagebox.showwarning("Advertencia", "No hay comics en la lista")
            return

        indices = range(len(self.comic_files))
        self._process_batch(indices)

    def _process_batch(self, indices):
        '''Process a batch of comics'''
        if not messagebox.askyesno("Confirmar",
            "¿Procesar {0} comics?\n\nSe abrirá un diálogo de búsqueda para cada uno.".format(len(indices))):
            return

        # Show progress bar
        self.progress.pack(side=tk.BOTTOM, fill=tk.X, before=self.status_bar)
        self.progress['maximum'] = len(indices)
        self.progress['value'] = 0

        # Process comics one by one
        self._batch_process_next(indices, 0)

    def _batch_process_next(self, indices, current_index):
        '''Process next comic in batch'''
        if current_index >= len(indices):
            # Batch complete
            self.progress.pack_forget()
            messagebox.showinfo("Completado",
                "Procesamiento por lotes completado.\n\n"
                "{0} comics procesados.".format(len(indices)))
            return

        index = indices[current_index]
        self.current_comic_index = index
        comic = self.comic_files[index]

        # Update progress
        self.progress['value'] = current_index + 1
        self._update_status("Procesando {0}/{1}: {2}".format(
            current_index + 1, len(indices), comic.filename))

        # If comic already has metadata, generate XML directly
        if comic.metadata and comic.selected_issue:
            try:
                xml_content = self.xml_generator.generate_xml(comic.metadata)
                self._inject_xml(comic.filepath, xml_content)
                comic.status = 'completed'

                # Continue with next
                self.after(100, lambda: self._batch_process_next(indices, current_index + 1))
            except Exception as e:
                comic.status = 'error'
                if not messagebox.askyesno("Error",
                    "Error procesando {0}:\n{1}\n\n¿Continuar con los demás?".format(
                        comic.filename, str(e))):
                    self.progress.pack_forget()
                    return
                self.after(100, lambda: self._batch_process_next(indices, current_index + 1))
        else:
            # Show search dialog
            def on_dialog_close():
                # After dialog closes, generate XML if metadata was selected
                if comic.metadata and comic.selected_issue:
                    try:
                        xml_content = self.xml_generator.generate_xml(comic.metadata)
                        self._inject_xml(comic.filepath, xml_content)
                        comic.status = 'completed'
                    except Exception as e:
                        comic.status = 'error'
                        if not messagebox.askyesno("Error",
                            "Error procesando {0}:\n{1}\n\n¿Continuar con los demás?".format(
                                comic.filename, str(e))):
                            self.progress.pack_forget()
                            return

                # Continue with next comic
                self.after(100, lambda: self._batch_process_next(indices, current_index + 1))

            # Create search dialog
            dialog = BatchSearchDialog(self, comic, self.db, on_dialog_close)
            self.wait_window(dialog)

    def _update_status(self, message):
        '''Update status bar message'''
        self.status_bar.config(text=message)

    def _process_queue(self):
        '''Process updates from background threads'''
        try:
            while True:
                callback = self.update_queue.get_nowait()
                callback()
        except queue.Empty:
            pass

        self.after(100, self._process_queue)

    def _show_about(self):
        '''Show about dialog'''
        messagebox.showinfo("Acerca de",
            "TebeoSfera Scraper GUI\n\n"
            "Scraper de metadatos para comics españoles\n"
            "Fuente: tebeosfera.com\n\n"
            "Versión 2.0\n"
            "© 2025")

    def _on_close(self):
        '''Handle window close'''
        if messagebox.askokcancel("Salir", "¿Cerrar la aplicación?"):
            self.db.close()
            self.destroy()

    def _open_current_in_browser(self):
        '''Open the selected comic's TebeoSfera page in browser'''
        if self.current_comic_index < 0 or self.current_comic_index >= len(self.comic_files):
            messagebox.showwarning("Advertencia", "Selecciona un comic primero")
            return

        comic = self.comic_files[self.current_comic_index]
        url = None

        if comic.metadata:
            url = comic.metadata.get('webpage') or comic.metadata.get('webpage_s')
            if not url:
                collection_url = comic.metadata.get('collection_url')
                if collection_url:
                    url = build_series_url(collection_url)

        if not url and getattr(comic, 'selected_issue', None):
            url = build_issue_url(getattr(comic.selected_issue, 'issue_key', None))

        if not url and getattr(comic, 'selected_issue', None):
            # Fallback to series if available in issue metadata
            series_key = getattr(comic.selected_issue, 'series_key', None)
            if series_key:
                url = build_series_url(series_key)

        if url:
            self._log(f"🌐 Abriendo en navegador: {url}")
            webbrowser.open(url)
        else:
            messagebox.showinfo("Información", "No se pudo determinar la URL en TebeoSfera para este comic.")

    def _log(self, message):
        '''Add a message to the log (thread-safe)'''
        timestamp = strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        # Use after() to ensure we're in the main thread
        def update_log():
            try:
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, log_entry)
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
            except:
                pass  # Widget might not exist yet
        
        # Always print to console (works from any thread)
        print(log_entry.strip())
        
        # Update GUI in main thread
        try:
            self.after(0, update_log)
        except:
            # If after() fails, try direct update (we might be in main thread)
            try:
                update_log()
            except:
                pass

    def _clear_log(self):
        '''Clear the log'''
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)
        self._log("Log limpiado")

    def _save_log(self):
        '''Save log to file'''
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Guardar log"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get('1.0', tk.END))
                self._log(f"✅ Log guardado en: {filename}")
                messagebox.showinfo("Éxito", f"Log guardado en:\n{filename}")
            except Exception as e:
                self._log(f"❌ Error guardando log: {str(e)}")
                messagebox.showerror("Error", f"Error guardando log:\n{str(e)}")


class SearchDialog(tk.Toplevel):
    '''Dialog for searching and selecting issues from TebeoSfera'''

    def __init__(self, parent, comic, db):
        tk.Toplevel.__init__(self, parent)

        self.title("Buscar en TebeoSfera - {0}".format(comic.filename))
        self.geometry("1400x750")
        self.transient(parent)

        self.parent = parent  # Store parent reference for logging
        self.comic = comic
        self.db = db
        self.search_results = []
        self.selected_series = None
        self.issues_list = []
        self.selected_issue = None
        self.cover_images = {}  # Cache for PhotoImage objects
        self.mode = 'series'  # 'series' or 'issues'

        # Image comparison data
        self.downloaded_images = []  # Store PIL images for comparison
        self.similarity_scores = []  # Store similarity scores
        self.best_match_index = -1  # Index of best match

        self._create_ui()

        # Auto-search based on filename
        self._auto_search()

    def _create_ui(self):
        '''Create search dialog UI'''
        # Search frame
        search_frame = tk.Frame(self)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(search_frame, text="Buscar:").pack(side=tk.LEFT)
        self.search_entry = tk.Entry(search_frame, width=50)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<Return>', lambda e: self._search())

        tk.Button(search_frame, text="🔍 Buscar", command=self._search).pack(side=tk.LEFT)

        # Main panel - split between results and preview
        main_paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: Results tree
        left_frame = tk.Frame(main_paned)
        main_paned.add(left_frame, minsize=400)

        self.results_label = tk.Label(left_frame, text="Resultados:", font=('Arial', 10, 'bold'))
        self.results_label.pack(anchor=tk.W)

        # Treeview for results (sagas/colecciones/issues)
        tree_frame = tk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.results_tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, show='tree')
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.results_tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        self.results_tree.bind('<Double-Button-1>', self._on_tree_double_click)
        # Bind expansion event to load issues
        self.results_tree.bind('<<TreeviewOpen>>', self._on_tree_expand)

        scrollbar.config(command=self.results_tree.yview)
        
        # Store tree item data: {item_id: (type, object)}
        # type can be: 'issue', 'collection', 'saga', 'issue_item'
        self.tree_item_data = {}

        # Right: Preview panel (split: cover left, metadata right)
        right_frame = tk.Frame(main_paned)
        main_paned.add(right_frame, minsize=500)
        
        # Split preview area horizontally
        preview_paned = tk.PanedWindow(right_frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        preview_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left: Cover preview
        cover_frame = tk.Frame(preview_paned)
        preview_paned.add(cover_frame, minsize=200)
        
        tk.Label(cover_frame, text="Portada:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=5)
        
        # Canvas para la imagen
        preview_container = tk.Frame(cover_frame, bg='gray80', relief=tk.SUNKEN, bd=2)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.preview_canvas = tk.Canvas(preview_container, bg='gray90', highlightthickness=0)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Placeholder text
        self.preview_canvas.create_text(
            200, 300,
            text="Selecciona un issue\npara ver su portada",
            font=('Arial', 12), fill='gray40', tags='placeholder'
        )
        
        # Keep a reference for the label (needed for image persistence)
        self.preview_label = tk.Label(self.preview_canvas)  # Dummy label for image reference
        
        # Preview actions (browser buttons)
        preview_actions = tk.Frame(cover_frame)
        preview_actions.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.open_series_button = tk.Button(preview_actions, text="🌐 Abrir en navegador", command=self._open_selected_series, state=tk.DISABLED)
        self.open_series_button.pack(side=tk.LEFT, padx=2)
        
        # Right: Metadata display
        metadata_frame = tk.Frame(preview_paned)
        preview_paned.add(metadata_frame, minsize=400)
        
        tk.Label(metadata_frame, text="Metadatos:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=5)
        
        # Toggle buttons for metadata view
        metadata_toggle = tk.Frame(metadata_frame)
        metadata_toggle.pack(fill=tk.X, padx=5, pady=5)
        
        self.metadata_view_mode = tk.StringVar(value='pretty')
        tk.Radiobutton(metadata_toggle, text="Bonito", variable=self.metadata_view_mode, 
                      value='pretty', command=self._toggle_metadata_view).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(metadata_toggle, text="XML", variable=self.metadata_view_mode, 
                      value='xml', command=self._toggle_metadata_view).pack(side=tk.LEFT, padx=5)
        
        # Metadata display with scrollbar
        metadata_text_frame = tk.Frame(metadata_frame)
        metadata_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        metadata_scrollbar = tk.Scrollbar(metadata_text_frame)
        metadata_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.metadata_display = tk.Text(metadata_text_frame, wrap=tk.WORD, 
                                        yscrollcommand=metadata_scrollbar.set,
                                        font=('Consolas', 9))
        self.metadata_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        metadata_scrollbar.config(command=self.metadata_display.yview)
        
        # Store current metadata for toggling
        self.current_metadata_xml = None
        self.current_metadata_dict = None
        
        # Apply button
        apply_button_frame = tk.Frame(metadata_frame)
        apply_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.apply_xml_button = tk.Button(apply_button_frame, text="💾 Aplicar ComicInfo.xml", 
                                          command=self._apply_comicinfo_xml, state=tk.DISABLED,
                                          height=2, font=('Arial', 10, 'bold'))
        self.apply_xml_button.pack(fill=tk.X, padx=5, pady=5)

        # Buttons
        button_frame = tk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(button_frame, text="✗ Cerrar", command=self.destroy).pack(side=tk.RIGHT, padx=5)

        # Status label
        self.status_label = tk.Label(self, text="", fg='blue')
        self.status_label.pack(fill=tk.X, padx=10)
        self._update_open_buttons()

    def _log(self, message):
        '''Add a message to the log (delegates to parent if available)'''
        if hasattr(self, 'parent') and hasattr(self.parent, '_log'):
            self.parent._log(message)
        else:
            print(f"[LOG] {message}")

    def _fetch_reference_image_data(self, ref):
        '''Fetch high-resolution image data for a SeriesRef or IssueRef'''
        if not ref:
            return None

        extra_url = getattr(ref, 'extra_image_url', None)
        if extra_url:
            try:
                data = self.db.connection.download_image(extra_url)
                if data:
                    return data
            except Exception as e:
                self._log(f"⚠️ Error descargando imagen extra: {e}")

        try:
            return self.db.query_image(ref)
        except Exception as e:
            self._log(f"⚠️ Error obteniendo imagen desde DB: {e}")
            return None

    def _update_open_buttons(self):
        '''Enable/disable open buttons based on current selections'''
        if hasattr(self, 'open_series_button'):
            if self.selected_series:
                self.open_series_button.config(state=tk.NORMAL)
                # Cambiar texto del botón según el tipo
                result_type = getattr(self.selected_series, 'type_s', 'collection')
                if result_type == 'issue':
                    self.open_series_button.config(text="🌐 Abrir ejemplar")
                elif result_type == 'saga':
                    self.open_series_button.config(text="🌐 Abrir saga")
                else:
                    self.open_series_button.config(text="🌐 Abrir colección")
            elif self.selected_issue:
                self.open_series_button.config(state=tk.NORMAL)
                self.open_series_button.config(text="🌐 Abrir ejemplar")
            else:
                self.open_series_button.config(state=tk.DISABLED)

    def _open_selected_series(self):
        '''Open selected series/issue in browser'''
        # Check if we have a selected issue first
        if self.selected_issue:
            # Try to get issue_key from IssueRef
            issue_key = getattr(self.selected_issue, 'issue_key', None)
            # If it's a SeriesRef converted to IssueRef, try series_key
            if not issue_key:
                issue_key = getattr(self.selected_issue, 'series_key', None)
            
            if issue_key:
                url = build_issue_url(issue_key)
                if url:
                    self._log(f"🌐 Abriendo ejemplar: {url}")
                    webbrowser.open(url)
                    return
                else:
                    messagebox.showinfo("Información", "No se pudo determinar la URL del ejemplar seleccionado.")
                    return
            else:
                messagebox.showinfo("Información", "No se pudo determinar la clave del ejemplar seleccionado.")
                return
        
        # Otherwise check for selected series
        series_ref = self.selected_series
        if not series_ref:
            messagebox.showinfo("Información", "Selecciona una serie, saga o ejemplar primero")
            return

        series_key = getattr(series_ref, 'series_key', None)
        result_type = getattr(series_ref, 'type_s', 'collection')
        
        # Si es un issue individual, usar URL de issue
        if result_type == 'issue':
            url = build_issue_url(series_key)
            tipo = "ejemplar"
        elif result_type == 'saga':
            url = build_series_url(series_key)
            tipo = "saga"
        else:
            url = build_series_url(series_key)
            tipo = "colección"

        if url:
            self._log(f"🌐 Abriendo {tipo}: {url}")
            webbrowser.open(url)
        else:
            messagebox.showinfo("Información", f"No se pudo determinar la URL de la {tipo} seleccionada.")

    def _open_selected_issue(self):
        '''Open selected issue in browser'''
        issue_ref = self.selected_issue
        if not issue_ref:
            messagebox.showinfo("Información", "Selecciona un issue primero")
            return

        url = build_issue_url(getattr(issue_ref, 'issue_key', None))

        if url:
            self._log(f"🌐 Abriendo issue: {url}")
            webbrowser.open(url)
        else:
            messagebox.showinfo("Información", "No se pudo determinar la URL del issue seleccionado.")

    def _format_request_info(self, info):
        '''Format HTTP request metadata for display/logging'''
        if not info:
            return ''

        parts = []
        url = info.get('url')
        if url:
            parts.append(f"URL: {url}")

        status = info.get('status')
        if status is not None:
            parts.append(f"HTTP {status}")

        bytes_count = info.get('bytes')
        if bytes_count:
            parts.append(f"{bytes_count:,} bytes")

        elapsed = info.get('elapsed_ms')
        if elapsed:
            parts.append(f"{elapsed:.0f} ms")

        return " | ".join(parts)

    def _log_request_info(self, context, info):
        '''Log formatted request metadata'''
        info_str = self._format_request_info(info)
        if info_str:
            self._log(f"{context} {info_str}")
        else:
            self._log(f"{context} (sin metadatos de URL)")

    def _auto_search(self):
        '''Auto-search based on filename with edit option'''
        # Extract series name from filename
        filename = self.comic.filename
        extracted_title = extract_title_from_filename(filename)
        
        # Show edit dialog
        edit_dialog = tk.Toplevel(self)
        edit_dialog.title("Editar título de búsqueda")
        edit_dialog.geometry("500x150")
        edit_dialog.transient(self)
        edit_dialog.grab_set()
        
        # Center the dialog
        edit_dialog.update_idletasks()
        x = (edit_dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (edit_dialog.winfo_screenheight() // 2) - (150 // 2)
        edit_dialog.geometry(f"500x150+{x}+{y}")
        
        tk.Label(edit_dialog, text="Título extraído del archivo:", 
                 font=('Arial', 9)).pack(pady=(10, 5), padx=10, anchor=tk.W)
        
        entry_var = tk.StringVar(value=extracted_title)
        entry = tk.Entry(edit_dialog, textvariable=entry_var, width=60, font=('Arial', 10))
        entry.pack(padx=10, pady=5, fill=tk.X)
        entry.select_range(0, tk.END)
        entry.focus()
        
        def on_ok():
            title = entry_var.get().strip()
            if title:
                self.search_entry.delete(0, tk.END)
                self.search_entry.insert(0, title)
                edit_dialog.destroy()
                self._search()
            else:
                messagebox.showwarning("Advertencia", "El título no puede estar vacío")
        
        def on_cancel():
            edit_dialog.destroy()
        
        button_frame = tk.Frame(edit_dialog)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Buscar", command=on_ok, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancelar", command=on_cancel, width=12).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        entry.bind('<Return>', lambda e: on_ok())
        edit_dialog.bind('<Escape>', lambda e: on_cancel())

    def _search(self):
        '''Perform search'''
        query = self.search_entry.get().strip()
        if not query:
            return
        self.selected_series = None
        self.selected_issue = None
        self._update_open_buttons()

        self.mode = 'series'
        self.results_label.config(text="Resultados:")

        # Clear tree
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.tree_item_data = {}
        
        # Add loading placeholder
        loading_item = self.results_tree.insert('', 'end', text="Buscando...", tags=('loading',))
        self.status_label.config(text="Conectando con TebeoSfera...")
        self.update()
        
        # Log the search
        self._log(f"🔍 Iniciando búsqueda: '{query}'")

        # Perform search in background
        def search_thread():
            try:
                # Update status
                def update_status(msg):
                    self.after(0, lambda: self.status_label.config(text=msg))
                    self.after(0, lambda: self._log(msg))
                
                update_status("Conectando con TebeoSfera...")
                
                # Get URL before search
                search_url = None
                if hasattr(self.db, 'connection'):
                    # Build expected URL
                    from urllib.parse import quote
                    encoded_query = quote(query.replace(' ', '_'), safe='_')
                    search_url = f"https://www.tebeosfera.com/buscador/{encoded_query}/"
                    self._log(f"🌐 URL de búsqueda: {search_url}")
                
                results = self.db.search_series(query)
                
                request_info = {}
                if hasattr(self.db, 'connection') and hasattr(self.db.connection, 'get_request_info'):
                    request_info = self.db.connection.get_request_info() or {}
                    if request_info:
                        self._log(f"📡 Respuesta HTTP: {request_info.get('status_code', 'N/A')} - {request_info.get('size_bytes', 0)} bytes")
                        if request_info.get('url'):
                            self._log(f"🔗 URL final: {request_info.get('url')}")

                update_status(f"Búsqueda completada: {len(results)} resultados encontrados")

                def update_results(request_info=request_info):
                    # Clear tree
                    for item in self.results_tree.get_children():
                        self.results_tree.delete(item)
                    self.tree_item_data = {}
                    
                    self.search_results = results

                    info_line = self._format_request_info(request_info)
                    if info_line:
                        self._log_request_info("🌐 Solicitud completada:", request_info)

                    if not results:
                        self.results_tree.insert('', 'end', text="Sin resultados", tags=('empty',))
                        status_msg = "Sin resultados"
                        if info_line:
                            status_msg += f"\n{info_line}"
                        self.status_label.config(text=status_msg)
                        self._log("❌ Sin resultados encontrados")
                        return

                    # Group results by type and display in tree
                    # Separate into sagas, collections, and issues
                    sagas = [r for r in results if getattr(r, 'type_s', 'collection') == 'saga']
                    collections = [r for r in results if getattr(r, 'type_s', 'collection') == 'collection']
                    issues = [r for r in results if getattr(r, 'type_s', 'collection') == 'issue']
                    
                    # Debug: log types found
                    self._log(f"📊 Tipos detectados: {len(sagas)} sagas, {len(collections)} colecciones, {len(issues)} issues")
                    for i, r in enumerate(results[:5]):  # Log first 5
                        type_attr = getattr(r, 'type_s', 'unknown')
                        self._log(f"  [{i+1}] type_s='{type_attr}', name='{r.series_name_s[:50]}'")
                    
                    # Insert sagas first
                    if sagas:
                        sagas_parent = self.results_tree.insert('', 'end', text=f"🗂️ Sagas ({len(sagas)})", tags=('header',))
                        self.tree_item_data[sagas_parent] = ('header', None)
                        for result in sagas:
                            display_name = result.series_name_s
                            item_id = self.results_tree.insert(sagas_parent, 'end', text=display_name, tags=('saga',))
                            # Add placeholder child to enable expansion
                            placeholder = self.results_tree.insert(item_id, 'end', text="Cargando...", tags=('loading',))
                            self.tree_item_data[item_id] = ('saga', result)
                    
                    # Insert collections
                    if collections:
                        collections_parent = self.results_tree.insert('', 'end', text=f"📚 Colecciones ({len(collections)})", tags=('header',))
                        self.tree_item_data[collections_parent] = ('header', None)
                        for result in collections:
                            display_name = result.series_name_s
                            item_id = self.results_tree.insert(collections_parent, 'end', text=display_name, tags=('collection',))
                            # Add placeholder child to enable expansion
                            placeholder = self.results_tree.insert(item_id, 'end', text="Cargando...", tags=('loading',))
                            self.tree_item_data[item_id] = ('collection', result)
                    
                    # Insert issues
                    if issues:
                        issues_parent = self.results_tree.insert('', 'end', text=f"📖 Issues ({len(issues)})", tags=('header',))
                        self.tree_item_data[issues_parent] = ('header', None)
                        for result in issues:
                            display_name = result.series_name_s
                            item_id = self.results_tree.insert(issues_parent, 'end', text=display_name, tags=('issue',))
                            self.tree_item_data[item_id] = ('issue', result)

                    # Count by type
                    type_counts = {'issue': 0, 'collection': 0, 'saga': 0}
                    for result in results:
                        type_attr = getattr(result, 'type_s', 'collection')
                        if type_attr in type_counts:
                            type_counts[type_attr] += 1
                        else:
                            type_counts['collection'] += 1
                    
                    status_text = f"{len(results)} resultados: {type_counts['issue']} issues, {type_counts['collection']} series, {type_counts['saga']} sagas"
                    if info_line:
                        status_text += f"\n{info_line}"
                    self.status_label.config(text=status_text + " - Comparando portadas...")
                    self._log(f"✅ {len(results)} resultados encontrados")
                    self._log(f"   📖 {type_counts['issue']} issues individuales (con metadata completa)")
                    self._log(f"   📚 {type_counts['collection']} colecciones (listas de issues)")
                    self._log(f"   🗂️  {type_counts['saga']} sagas (grupos temáticos)")
                    sample_names = ", ".join(result.series_name_s[:40] for result in results[:5])
                    self._log(f"📚 Primeros resultados ({min(len(results), 5)}/{len(results)}): {sample_names}")

                    # Start image comparison if comic has a cover
                    if self.comic.cover_image:
                        self._compare_covers_with_results(results)
                    else:
                        self.status_label.config(text=f"{len(results)} series encontradas")
                        self._log("ℹ️ Sin portada disponible para comparación")

                self.after(0, update_results)
            except Exception as e:
                error_msg = f"Error en búsqueda: {str(e)}"
                self.after(0, lambda: self.status_label.config(text=error_msg))
                self.after(0, lambda: self._log(f"❌ {error_msg}"))
                self.after(0, lambda: messagebox.showerror("Error", error_msg))

        thread = threading.Thread(target=search_thread)
        thread.daemon = True
        thread.start()

    def _compare_covers_with_results(self, results):
        '''Compare comic cover with search results covers'''
        def compare_thread():
            self.downloaded_images = []
            self.similarity_scores = []
            
            def update_status(msg):
                self.after(0, lambda: self.status_label.config(text=msg))
                self.after(0, lambda: self._log(msg))

            update_status(f"Descargando {len(results)} portadas para comparar...")
            
            # Download all covers
            for i, result in enumerate(results):
                try:
                    update_status(f"Descargando portada {i+1}/{len(results)}: {result.series_name_s}")
                    image_data = self._fetch_reference_image_data(result)
                    if image_data:
                        image = Image.open(BytesIO(image_data))
                        self.downloaded_images.append(image)
                    else:
                        self.downloaded_images.append(None)
                except Exception as e:
                    self.downloaded_images.append(None)
                    self.after(0, lambda: self._log(f"⚠️ Error descargando portada {i+1}: {str(e)}"))

            update_status("Comparando portadas con el comic...")

            # Compare with comic cover
            if self.comic.cover_image and self.downloaded_images:
                self.best_match_index, self.similarity_scores = ImageComparator.find_best_match(
                    self.comic.cover_image,
                    self.downloaded_images
                )

                def update_ui():
                    # Update tree with scores, grouped by type
                    # Clear and rebuild tree with scores
                    for item in self.results_tree.get_children():
                        self.results_tree.delete(item)
                    self.tree_item_data = {}
                    
                    # Group results by type
                    sagas = [(i, r) for i, r in enumerate(results) if getattr(r, 'type_s', 'collection') == 'saga']
                    collections = [(i, r) for i, r in enumerate(results) if getattr(r, 'type_s', 'collection') == 'collection']
                    issues = [(i, r) for i, r in enumerate(results) if getattr(r, 'type_s', 'collection') == 'issue']
                    
                    best_item_id = None
                    best_score = 0
                    
                    # Insert sagas first
                    if sagas:
                        sagas_parent = self.results_tree.insert('', 'end', text=f"🗂️ Sagas ({len(sagas)})", tags=('header',))
                        self.tree_item_data[sagas_parent] = ('header', None)
                        for i, result in sagas:
                            score = self.similarity_scores[i] if i < len(self.similarity_scores) else 0
                            prefix = "⭐ " if i == self.best_match_index and score > 60 else ""
                            display_text = f"{prefix}{result.series_name_s} ({score:.0f}%)"
                            item_id = self.results_tree.insert(sagas_parent, 'end', text=display_text, tags=('saga',))
                            placeholder = self.results_tree.insert(item_id, 'end', text="Cargando...", tags=('loading',))
                            self.tree_item_data[item_id] = ('saga', result)
                            if i == self.best_match_index and score > 60:
                                best_item_id = item_id
                                best_score = score
                    
                    # Insert collections
                    if collections:
                        collections_parent = self.results_tree.insert('', 'end', text=f"📚 Colecciones ({len(collections)})", tags=('header',))
                        self.tree_item_data[collections_parent] = ('header', None)
                        for i, result in collections:
                            score = self.similarity_scores[i] if i < len(self.similarity_scores) else 0
                            prefix = "⭐ " if i == self.best_match_index and score > 60 else ""
                            display_text = f"{prefix}{result.series_name_s} ({score:.0f}%)"
                            item_id = self.results_tree.insert(collections_parent, 'end', text=display_text, tags=('collection',))
                            placeholder = self.results_tree.insert(item_id, 'end', text="Cargando...", tags=('loading',))
                            self.tree_item_data[item_id] = ('collection', result)
                            if i == self.best_match_index and score > 60:
                                best_item_id = item_id
                                best_score = score
                    
                    # Insert issues
                    if issues:
                        issues_parent = self.results_tree.insert('', 'end', text=f"📖 Issues ({len(issues)})", tags=('header',))
                        self.tree_item_data[issues_parent] = ('header', None)
                        for i, result in issues:
                            score = self.similarity_scores[i] if i < len(self.similarity_scores) else 0
                            prefix = "⭐ " if i == self.best_match_index and score > 60 else ""
                            display_text = f"{prefix}{result.series_name_s} ({score:.0f}%)"
                            item_id = self.results_tree.insert(issues_parent, 'end', text=display_text, tags=('issue',))
                            self.tree_item_data[item_id] = ('issue', result)
                            if i == self.best_match_index and score > 60:
                                best_item_id = item_id
                                best_score = score

                    # Auto-select best match if score is good enough
                    if best_item_id:
                        self.results_tree.selection_set(best_item_id)
                        self.results_tree.see(best_item_id)
                        # Trigger selection event
                        self.selected_series = self.search_results[self.best_match_index]
                        self._show_series_preview(self.selected_series)

                        status_msg = f"Mejor match encontrado: {best_score:.0f}% similar (⭐ marcado)"
                        self.status_label.config(text=status_msg)
                        self._log(f"⭐ Mejor match: {self.selected_series.series_name_s} ({best_score:.0f}% similar)")
                    else:
                        self.status_label.config(text=f"{len(results)} resultados encontrados")
                        self._log("ℹ️ Comparación completada")

                self.after(0, update_ui)

        thread = threading.Thread(target=compare_thread)
        thread.daemon = True
        thread.start()

    def _on_tree_select(self, event):
        '''Handle tree item selection'''
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        if item_id not in self.tree_item_data:
            return
        
        item_type, item_obj = self.tree_item_data[item_id]
        
        # Ignore header items
        if item_type == 'header':
            return
        
        if item_type == 'issue':
            # It's an individual issue
            self.selected_issue = item_obj
            self.selected_series = None
            self._show_issue_preview_with_metadata(item_obj)
            self._update_open_buttons()
        elif item_type in ('collection', 'saga'):
            # It's a collection/saga - show preview but don't load issues yet
            self.selected_series = item_obj
            self.selected_issue = None
            self._show_series_preview(item_obj)
            self._update_open_buttons()
        elif item_type == 'issue_item':
            # It's an issue within a collection/saga
            self.selected_issue = item_obj
            self.selected_series = None
            self._show_issue_preview_with_metadata(item_obj)
            self._update_open_buttons()

    def _on_tree_double_click(self, event):
        '''Handle double-click on tree item'''
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        if item_id not in self.tree_item_data:
            return
        
        item_type, item_obj = self.tree_item_data[item_id]
        
        if item_type == 'issue':
            # Individual issue - show metadata
            self._show_issue_preview_with_metadata(item_obj)
        elif item_type == 'issue_item':
            # Issue within collection - show metadata
            self._show_issue_preview_with_metadata(item_obj)
        # Collections and sagas expand on double-click (handled by tree expansion)
    
    def _on_tree_expand(self, event):
        '''Handle tree item expansion - load issues for collections/sagas'''
        item_id = self.results_tree.focus()
        if not item_id or item_id not in self.tree_item_data:
            return
        
        item_type, item_obj = self.tree_item_data[item_id]
        
        # Ignore headers
        if item_type == 'header':
            return
        
        # Only handle collections and sagas
        if item_type not in ('collection', 'saga'):
            return
        
        # Check if already loaded (has real children, not just placeholder)
        children = self.results_tree.get_children(item_id)
        if children and self.tree_item_data.get(children[0], (None, None))[0] != 'loading':
            return  # Already loaded
        
        # Remove placeholder
        for child in children:
            if self.tree_item_data.get(child, (None, None))[0] == 'loading':
                self.results_tree.delete(child)
                if child in self.tree_item_data:
                    del self.tree_item_data[child]
        
        # Load issues in background
        def load_issues():
            issues = self.db.query_series_issues(item_obj)
            
            def update_tree():
                # Add issues as children
                for issue in issues:
                    display_text = f"#{issue.issue_num_s} - {issue.title_s}"
                    child_id = self.results_tree.insert(item_id, 'end', text=display_text, tags=('issue_item',))
                    self.tree_item_data[child_id] = ('issue_item', issue)
                
                if not issues:
                    no_issues_id = self.results_tree.insert(item_id, 'end', text="Sin issues", tags=('empty',))
                    self.tree_item_data[no_issues_id] = ('empty', None)
            
            self.after(0, update_tree)
        
        thread = threading.Thread(target=load_issues)
        thread.daemon = True
        thread.start()

    def _show_series_preview(self, series_ref):
        '''Show preview of selected series'''
        # Clear previous preview
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
            self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
            text='Cargando portada...',
            font=('Arial', 12), fill='gray40'
        )
        self.metadata_display.config(state=tk.NORMAL)
        self.metadata_display.delete('1.0', tk.END)
        self.update()

        # Show series info - distinguir tipo
        series_type = "📂 Saga/Colección" if hasattr(series_ref, 'series_type') and series_ref.series_type == 'collection' else "📚 Serie"
        info = f"{series_type}\n"
        info += "Nombre: {0}\n".format(series_ref.series_name_s)
        info += "Clave: {0}\n".format(series_ref.series_key)
        info += "\nExpande el nodo para ver los issues."
        self.metadata_display.insert('1.0', info)
        self.metadata_display.config(state=tk.DISABLED)
        self.apply_xml_button.config(state=tk.DISABLED)

        # Load cover in background
        def load_cover():
            image_data = self._fetch_reference_image_data(series_ref)
            if image_data:
                def show_cover():
                    try:
                        image = Image.open(BytesIO(image_data))
                        self._display_preview_image(image)
                    except Exception as e:
                        self.preview_canvas.delete("all")
                        self.preview_canvas.create_text(
                            self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
                            self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
                            text='Error mostrando portada',
                            font=('Arial', 12), fill='red'
                        )
                self.after(0, show_cover)
            else:
                def show_no_cover():
                    self.preview_canvas.delete("all")
                    self.preview_canvas.create_text(
                        self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
                        self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
                        text='Sin portada disponible',
                        font=('Arial', 12), fill='gray40'
                    )
                self.after(0, show_no_cover)

        thread = threading.Thread(target=load_cover)
        thread.daemon = True
        thread.start()

    def _show_issue_preview(self, issue_ref):
        '''Show preview of selected issue'''
        # Clear previous preview
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
            self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
            text='Cargando portada...',
            font=('Arial', 12), fill='gray40'
        )
        self.info_text.delete('1.0', tk.END)
        self.update()

        # Show issue info
        info = "📖 Issue\n"
        info += "Título: {0}\n".format(issue_ref.title_s)
        info += "Número: {0}\n".format(issue_ref.issue_num_s)
        info += "Clave: {0}\n".format(issue_ref.issue_key)
        self.info_text.insert('1.0', info)

        # Load cover in background
        def load_cover():
            image_data = self._fetch_reference_image_data(issue_ref)
            if image_data:
                def show_cover():
                    try:
                        image = Image.open(BytesIO(image_data))
                        self._display_preview_image(image)
                    except Exception as e:
                        self.preview_canvas.delete("all")
                        self.preview_canvas.create_text(
                            self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
                            self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
                            text='Error mostrando portada',
                            font=('Arial', 12), fill='red'
                        )
                self.after(0, show_cover)
            else:
                def show_no_cover():
                    self.preview_canvas.delete("all")
                    self.preview_canvas.create_text(
                        self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
                        self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
                        text='Sin portada disponible',
                        font=('Arial', 12), fill='gray40'
                    )
                self.after(0, show_no_cover)

        thread = threading.Thread(target=load_cover)
        thread.daemon = True
        thread.start()

    def _show_issue_preview_with_metadata(self, issue_ref):
        '''Show preview of issue with full metadata'''
        # Clear previous preview
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
            self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
            text='Cargando portada...',
            font=('Arial', 12), fill='gray40'
        )
        self.metadata_display.delete('1.0', tk.END)
        self.metadata_display.insert('1.0', 'Cargando metadatos...')
        self.apply_xml_button.config(state=tk.DISABLED)
        self.update()
        
        # Load cover and metadata in background
        def load_data():
            # Check if issue_ref is actually a SeriesRef with type='issue'
            # If so, create a temporary IssueRef
            from database.dbmodels import IssueRef, SeriesRef
            
            actual_issue_ref = issue_ref
            if isinstance(issue_ref, SeriesRef):
                # It's a SeriesRef representing an individual issue
                # Create a temporary IssueRef
                actual_issue_ref = IssueRef(
                    issue_num_s="1",  # We don't have the real number yet
                    issue_key=issue_ref.series_key,  # Use series_key as issue_key
                    title_s=issue_ref.series_name_s,
                    thumb_url_s=getattr(issue_ref, 'thumb_url_s', None)
                )
                # Copy extra_image_url if exists
                if hasattr(issue_ref, 'extra_image_url'):
                    actual_issue_ref.extra_image_url = issue_ref.extra_image_url
            
            # Load cover
            image_data = self._fetch_reference_image_data(actual_issue_ref)
            
            # Query full issue details
            issue = self.db.query_issue_details(actual_issue_ref)
            
            def update_ui():
                # Show cover
                if image_data:
                    try:
                        image = Image.open(BytesIO(image_data))
                        self._display_preview_image(image)
                    except Exception as e:
                        self.preview_canvas.delete("all")
                        self.preview_canvas.create_text(
                            self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
                            self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
                            text='Error mostrando portada',
                            font=('Arial', 12), fill='red'
                        )
                else:
                    self.preview_canvas.delete("all")
                    self.preview_canvas.create_text(
                        self.preview_canvas.winfo_width() // 2 if self.preview_canvas.winfo_width() > 10 else 200,
                        self.preview_canvas.winfo_height() // 2 if self.preview_canvas.winfo_height() > 10 else 300,
                        text='Sin portada disponible',
                        font=('Arial', 12), fill='gray40'
                    )
                
                # Show metadata
                if issue:
                    # Convert to metadata dict (similar to main GUI)
                    metadata_dict = self._issue_to_metadata_dict(issue)
                    
                    # Generate XML
                    from comicinfo_xml import ComicInfoGenerator
                    xml_generator = ComicInfoGenerator()
                    xml_content = xml_generator.generate_xml(metadata_dict)
                    
                    # Store for toggling
                    self.current_metadata_xml = xml_content
                    self.current_metadata_dict = metadata_dict
                    self.current_issue = issue
                    
                    # Display based on current view mode
                    self._toggle_metadata_view()
                    
                    # Enable apply button
                    self.apply_xml_button.config(state=tk.NORMAL)
                else:
                    self.metadata_display.delete('1.0', tk.END)
                    self.metadata_display.insert('1.0', 'Error: No se pudieron obtener los metadatos')
                    self.current_metadata_xml = None
                    self.current_metadata_dict = None
                    self.current_issue = None
            
            self.after(0, update_ui)
        
        thread = threading.Thread(target=load_data)
        thread.daemon = True
        thread.start()
    
    def _issue_to_metadata_dict(self, issue):
        '''Convert Issue object to metadata dictionary (same as main GUI)'''
        metadata = {
            'title': issue.title_s,
            'series': issue.series_name_s,
            'number': issue.issue_num_s,
            'count': issue.issue_count_n if issue.issue_count_n > 0 else None,
            'volume': issue.volume_year_n if issue.volume_year_n > 0 else None,
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
            'editor': issue.editors_sl,
            'translator': issue.translators_sl,
            'genre': ', '.join(issue.crossovers_sl) if issue.crossovers_sl else None,
            'characters': ', '.join(issue.characters_sl) if issue.characters_sl else None,
            'page_count': issue.page_count_n if issue.page_count_n > 0 else None,
            'language_iso': 'es',
            'format': issue.format_s,
            'binding': issue.binding_s,
            'dimensions': issue.dimensions_s,
            'isbn': issue.isbn_s,
            'legal_deposit': issue.legal_deposit_s,
            'price': issue.price_s,
            'original_title': issue.origin_title_s,
            'original_publisher': issue.origin_publisher_s,
            'web': issue.webpage_s
        }
        return metadata
    
    def _toggle_metadata_view(self):
        '''Toggle between pretty and XML metadata view'''
        if not self.current_metadata_dict and not self.current_metadata_xml:
            return
        
        mode = self.metadata_view_mode.get()
        self.metadata_display.config(state=tk.NORMAL)
        self.metadata_display.delete('1.0', tk.END)
        
        if mode == 'pretty':
            # Show formatted metadata
            text = self._format_metadata_pretty(self.current_metadata_dict)
            self.metadata_display.insert('1.0', text)
        else:
            # Show XML
            if self.current_metadata_xml:
                self.metadata_display.insert('1.0', self.current_metadata_xml)
            else:
                self.metadata_display.insert('1.0', 'XML no disponible')
        
        self.metadata_display.config(state=tk.DISABLED)
    
    def _format_metadata_pretty(self, metadata):
        '''Format metadata dictionary for pretty display (same as main GUI)'''
        # Use parent's method if available
        if hasattr(self.parent, '_format_metadata_pretty'):
            return self.parent._format_metadata_pretty(metadata)
        
        # Fallback implementation
        lines = []
        if metadata.get('title'):
            lines.append(f"Título: {metadata['title']}")
        if metadata.get('series'):
            lines.append(f"Serie: {metadata['series']}")
        if metadata.get('number'):
            lines.append(f"Número: {metadata['number']}")
        if metadata.get('count'):
            lines.append(f"Total números: {metadata['count']}")
        if metadata.get('volume'):
            lines.append(f"Volumen: {metadata['volume']}")
        if metadata.get('publisher'):
            lines.append(f"Editorial: {metadata['publisher']}")
        if metadata.get('year'):
            date_parts = []
            if metadata.get('day'):
                date_parts.append(str(metadata['day']))
            if metadata.get('month'):
                date_parts.append(str(metadata['month']))
            date_parts.append(str(metadata['year']))
            lines.append(f"Fecha: {'/'.join(date_parts)}")
        if metadata.get('summary'):
            lines.append(f"\nResumen:\n{metadata['summary']}")
        if metadata.get('writer'):
            lines.append(f"\nGuionista: {metadata['writer']}")
        if metadata.get('penciller'):
            lines.append(f"Dibujante: {metadata['penciller']}")
        if metadata.get('inker'):
            lines.append(f"Entintador: {metadata['inker']}")
        if metadata.get('colorist'):
            lines.append(f"Colorista: {metadata['colorist']}")
        if metadata.get('cover_artist'):
            lines.append(f"Portadista: {metadata['cover_artist']}")
        if metadata.get('web'):
            lines.append(f"\nWeb: {metadata['web']}")
        return '\n'.join(lines) if lines else 'Sin metadatos disponibles'
    
    def _apply_comicinfo_xml(self):
        '''Apply ComicInfo.xml to the comic file'''
        if not self.current_metadata_xml or not self.current_issue:
            messagebox.showwarning("Advertencia", "No hay metadatos para aplicar")
            return
        
        if not self.comic or not self.comic.filepath:
            messagebox.showerror("Error", "No hay archivo de cómic seleccionado")
            return
        
        # Check if file is CBR and convert to CBZ first
        filepath = self.comic.filepath
        if filepath.lower().endswith('.cbr'):
            # Convert CBR to CBZ
            if hasattr(self.parent, '_convert_cbr_to_cbz'):
                try:
                    self._log("🔄 Convirtiendo CBR a CBZ...")
                    filepath = self.parent._convert_cbr_to_cbz(filepath)
                    self.comic.filepath = filepath
                    self.comic.filename = os.path.basename(filepath)
                    self._log("✅ Conversión completada")
                except Exception as e:
                    messagebox.showerror("Error", f"Error convirtiendo CBR a CBZ: {str(e)}")
                    self._log(f"❌ Error en conversión: {str(e)}")
                    return
            else:
                messagebox.showerror("Error", "No se puede acceder al método de conversión CBR a CBZ")
                return
        
        # Use parent's method to inject XML
        if hasattr(self.parent, '_inject_xml'):
            try:
                self.parent._inject_xml(filepath, self.current_metadata_xml)
                messagebox.showinfo("Éxito", "ComicInfo.xml aplicado correctamente")
                self._log("✅ ComicInfo.xml aplicado a: {}".format(self.comic.filename))
            except Exception as e:
                messagebox.showerror("Error", f"Error aplicando ComicInfo.xml: {str(e)}")
                self._log(f"❌ Error aplicando ComicInfo.xml: {str(e)}")
        else:
            messagebox.showerror("Error", "No se puede acceder al método de inyección de XML")

    def _display_preview_image(self, image):
        '''Display image in preview canvas, scaled to fit'''
        # Get canvas actual size
        self.preview_canvas.update_idletasks()
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        
        # Use reasonable defaults if canvas not yet sized
        if canvas_width < 10:
            canvas_width = 300
        if canvas_height < 10:
            canvas_height = 450
        
        # Scale image to fit canvas while maintaining aspect ratio
        img_width, img_height = image.size
        width_ratio = canvas_width / img_width
        height_ratio = canvas_height / img_height
        scale = min(width_ratio, height_ratio)
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        display_img = image.resize((new_width, new_height), ANTIALIAS)
        photo = ImageTk.PhotoImage(display_img)
        
        # Center image in canvas
        x_offset = (canvas_width - new_width) // 2
        y_offset = (canvas_height - new_height) // 2
        
        # Update label with image and position centered in canvas
        self.preview_label.config(image=photo)
        self.preview_label.image = photo  # Keep reference
        
        # Clear canvas and draw image
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(x_offset, y_offset, image=photo, anchor=tk.NW)

    def _view_issues(self):
        '''View issues for selected series'''
        if not self.selected_series:
            messagebox.showwarning("Advertencia", "Selecciona una serie primero")
            return

        self.mode = 'issues'
        self.back_button.config(state=tk.NORMAL)
        self.results_label.config(text="Issues de '{0}':".format(self.selected_series.series_name_s))
        self.select_button.config(text="✓ Seleccionar Issue", command=self._select_issue)
        self.selected_issue = None
        self._update_open_buttons()

        self.results_listbox.delete(0, tk.END)
        self.results_listbox.insert(tk.END, "Cargando issues...")
        self.status_label.config(text="Obteniendo issues de la serie...")
        self.update()

        # Query issues in background
        def query_issues():
            issues = self.db.query_series_issues(self.selected_series)

            def update_issues():
                self.results_listbox.delete(0, tk.END)
                self.issues_list = issues

                if not issues:
                    self.results_listbox.insert(tk.END, "Sin issues encontrados")
                    self.status_label.config(text="Sin issues")
                    return

                # Display issues first
                for issue in issues:
                    display_text = "#{0} - {1}".format(issue.issue_num_s, issue.title_s)
                    self.results_listbox.insert(tk.END, display_text)

                self.status_label.config(text="{0} issues encontrados - Comparando portadas...".format(len(issues)))

                # Start image comparison if comic has a cover
                if self.comic.cover_image:
                    self._compare_covers_with_issues(issues)
                else:
                    self.status_label.config(text="{0} issues encontrados".format(len(issues)))

            self.after(0, update_issues)

        thread = threading.Thread(target=query_issues)
        thread.daemon = True
        thread.start()

    def _compare_covers_with_issues(self, issues):
        '''Compare comic cover with issue covers'''
        def compare_thread():
            self.downloaded_images = []
            self.similarity_scores = []

            # Download all issue covers
            for issue in issues:
                try:
                    image_data = self._fetch_reference_image_data(issue)
                    if image_data:
                        image = Image.open(BytesIO(image_data))
                        self.downloaded_images.append(image)
                    else:
                        self.downloaded_images.append(None)
                except:
                    self.downloaded_images.append(None)

            # Compare with comic cover
            if self.comic.cover_image and self.downloaded_images:
                self.best_match_index, self.similarity_scores = ImageComparator.find_best_match(
                    self.comic.cover_image,
                    self.downloaded_images
                )

                def update_ui():
                    # Update listbox with scores
                    self.results_listbox.delete(0, tk.END)
                    for i, issue in enumerate(issues):
                        score = self.similarity_scores[i] if i < len(self.similarity_scores) else 0
                        prefix = "⭐ " if i == self.best_match_index and score > 60 else "   "
                        display_text = "{0}#{1} - {2} ({3:.0f}% similar)".format(
                            prefix, issue.issue_num_s, issue.title_s, score)
                        self.results_listbox.insert(tk.END, display_text)

                    # Auto-select best match if score is good enough
                    if self.best_match_index >= 0 and self.similarity_scores[self.best_match_index] > 60:
                        self.results_listbox.selection_clear(0, tk.END)
                        self.results_listbox.selection_set(self.best_match_index)
                        self.results_listbox.see(self.best_match_index)
                        self.results_listbox.activate(self.best_match_index)
                        # Trigger selection event
                        self.selected_issue = self.issues_list[self.best_match_index]
                        self._show_issue_preview(self.selected_issue)

                        best_score = self.similarity_scores[self.best_match_index]
                        self.status_label.config(
                            text="Mejor match encontrado: {0:.0f}% similar (⭐ marcado)".format(best_score)
                        )
                    else:
                        self.status_label.config(text="{0} issues encontrados".format(len(issues)))

                self.after(0, update_ui)

        thread = threading.Thread(target=compare_thread)
        thread.daemon = True
        thread.start()

    def _view_single_issue(self):
        '''View a single issue (when the search result IS an issue)'''
        if not self.selected_series:
            messagebox.showwarning("Advertencia", "Selecciona un ejemplar primero")
            return
        
        # El selected_series es en realidad un issue
        # Crear un IssueRef a partir del SeriesRef
        from database.dbmodels import IssueRef
        
        # Extraer información del SeriesRef que representa un issue
        issue_key = self.selected_series.series_key
        issue_title = self.selected_series.series_name_s
        thumb_url = self.selected_series.thumb_url_s
        
        # Crear un IssueRef temporal
        issue_ref = IssueRef(
            issue_num_s="1",  # No tenemos el número real
            issue_key=issue_key,
            title_s=issue_title,
            thumb_url_s=thumb_url
        )
        
        # Copiar el extra_image_url si existe
        if hasattr(self.selected_series, 'extra_image_url'):
            issue_ref.extra_image_url = self.selected_series.extra_image_url
        
        # Seleccionar este issue directamente
        self.selected_issue = issue_ref
        self._select_issue()

    def _back_to_series(self):
        '''Go back to series search results'''
        self.mode = 'series'
        self.back_button.config(state=tk.DISABLED)
        self.results_label.config(text="Series encontradas:")
        self.select_button.config(text="Ver Issues →", command=self._view_issues)
        self.selected_issue = None
        self._update_open_buttons()

        # Restore series list with scores if available
        self.results_listbox.delete(0, tk.END)
        for i, result in enumerate(self.search_results):
            if i < len(self.similarity_scores):
                score = self.similarity_scores[i]
                prefix = "⭐ " if i == self.best_match_index and score > 60 else "   "
                display_text = "{0}{1} ({2:.0f}% similar)".format(prefix, result.series_name_s, score)
            else:
                display_text = result.series_name_s
            self.results_listbox.insert(tk.END, display_text)

        if self.best_match_index >= 0 and self.best_match_index < len(self.similarity_scores):
            best_score = self.similarity_scores[self.best_match_index]
            self.status_label.config(text="{0} series encontradas - Mejor match: {1:.0f}% similar".format(
                len(self.search_results), best_score))
        else:
            self.status_label.config(text="{0} series encontradas".format(len(self.search_results)))
            
        # Update preview label size info
        self.preview_label.config(text="Selecciona un resultado para ver su portada\n(Vista previa ampliada)")

    def _select_issue(self):
        '''Select issue and fetch full metadata'''
        if not self.selected_issue:
            messagebox.showwarning("Advertencia", "Selecciona un issue primero")
            return

        self.status_label.config(text="Obteniendo metadatos completos...")
        self.update()

        # Query full issue details in background
        def query_details():
            issue = self.db.query_issue_details(self.selected_issue)

            def complete_selection():
                if issue:
                    # Convert Issue object to metadata dict for XML generator
                    self.comic.metadata = self._issue_to_metadata_dict(issue)
                    self.comic.selected_issue = self.selected_issue
                    self.comic.status = 'selected'

                    self.status_label.config(text="Metadatos obtenidos correctamente")
                    messagebox.showinfo("Éxito",
                        "Issue seleccionado:\n{0} #{1}\n\nAhora puedes generar el ComicInfo.xml".format(
                            issue.series_name_s, issue.issue_num_s))
                    self.destroy()
                else:
                    self.status_label.config(text="Error obteniendo metadatos")
                    messagebox.showerror("Error", "No se pudieron obtener los metadatos del issue")

            self.after(0, complete_selection)

        thread = threading.Thread(target=query_details)
        thread.daemon = True
        thread.start()

    def _issue_to_metadata_dict(self, issue):
        '''Convert Issue object to metadata dictionary'''
        # Debug: log summary content
        if issue.summary_s:
            self._log(f"[OK] Summary presente en Issue: {len(issue.summary_s)} chars - {issue.summary_s[:50]}...")
        else:
            self._log("[WARN] Summary vacio en Issue")
        
        metadata = {
            'title': issue.title_s,
            'series': issue.series_name_s,
            'number': issue.issue_num_s,
            'count': issue.issue_count_n if issue.issue_count_n > 0 else None,
            'volume': issue.volume_year_n if issue.volume_year_n > 0 else None,
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
            'editor': issue.editors_sl,
            'translator': issue.translators_sl,
            'genre': ', '.join(issue.crossovers_sl) if issue.crossovers_sl else None,  # Genres stored in crossovers
            'characters': ', '.join(issue.characters_sl) if issue.characters_sl else None,
            'page_count': issue.page_count_n if issue.page_count_n > 0 else None,
            'language_iso': 'es',  # Default Spanish
            'format': issue.format_s,
            'binding': issue.binding_s,
            'dimensions': issue.dimensions_s,
            'isbn': issue.isbn_s,
            'legal_deposit': issue.legal_deposit_s,
            'price': issue.price_s,
            'original_title': issue.origin_title_s,
            'original_publisher': issue.origin_publisher_s,
            'web': issue.webpage_s  # Changed from 'webpage' to 'web'
        }
        return metadata


class BatchSearchDialog(SearchDialog):
    '''Simplified search dialog for batch processing'''

    def __init__(self, parent, comic, db, on_close_callback):
        self.on_close_callback = on_close_callback
        SearchDialog.__init__(self, parent, comic, db)

    def destroy(self):
        '''Override destroy to call callback'''
        SearchDialog.destroy(self)
        if self.on_close_callback:
            self.on_close_callback()

    def _select_issue(self):
        '''Override to auto-close after selection'''
        if not self.selected_issue:
            messagebox.showwarning("Advertencia", "Selecciona un issue primero")
            return

        self.status_label.config(text="Obteniendo metadatos completos...")
        self.update()

        # Query full issue details in background
        def query_details():
            issue = self.db.query_issue_details(self.selected_issue)

            def complete_selection():
                if issue:
                    # Convert Issue object to metadata dict for XML generator
                    self.comic.metadata = self._issue_to_metadata_dict(issue)
                    self.comic.selected_issue = self.selected_issue
                    self.comic.status = 'selected'

                    self.status_label.config(text="Metadatos obtenidos correctamente")
                    # Auto-close without showing success message in batch mode
                    self.destroy()
                else:
                    self.status_label.config(text="Error obteniendo metadatos")
                    messagebox.showerror("Error", "No se pudieron obtener los metadatos del issue")

            self.after(0, complete_selection)

        thread = threading.Thread(target=query_details)
        thread.daemon = True
        thread.start()


def main():
    '''Main entry point for GUI'''
    app = TebeoSferaGUI()
    app.mainloop()


if __name__ == '__main__':
    main()
