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

try:
    from database.tebeosfera.tbdb import TebeoSferaDB
    from comicinfo_xml import ComicInfoGenerator
    import zipfile
    import tempfile
    from io import BytesIO
except ImportError as e:
    print("Error importing modules: {0}".format(e))
    sys.exit(1)


class ImageComparator(object):
    '''Compares images to find visual similarity'''

    @staticmethod
    def calculate_dhash(image, hash_size=8):
        '''Calculate difference hash (dHash) for an image'''
        # Resize to hash_size + 1 width, hash_size height
        resized = image.convert('L').resize((hash_size + 1, hash_size), Image.ANTIALIAS)
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
            img1 = image1.convert('RGB').resize((100, 100), Image.ANTIALIAS)
            img2 = image2.convert('RGB').resize((100, 100), Image.ANTIALIAS)

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

    def extract_cover(self):
        '''Extract the first page (cover) from the comic file'''
        if not zipfile.is_zipfile(self.filepath):
            return None

        try:
            with zipfile.ZipFile(self.filepath, 'r') as zf:
                # Get list of image files
                images = [f for f in zf.namelist()
                         if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                images.sort()

                if images:
                    # Read first image
                    image_data = zf.read(images[0])
                    self.cover_image = Image.open(BytesIO(image_data))
                    return self.cover_image
        except Exception as e:
            print("Error extracting cover from {0}: {1}".format(self.filename, e))
            return None


class TebeoSferaGUI(tk.Tk):
    '''Main GUI application window'''

    def __init__(self):
        tk.Tk.__init__(self)

        self.title("TebeoSfera Scraper - Comic Metadata Editor")
        self.geometry("1200x800")

        # Initialize scraper
        self.db = TebeoSferaDB()
        self.xml_generator = ComicInfoGenerator()

        # Comic files list
        self.comic_files = []
        self.current_comic_index = 0

        # Thread-safe queue for UI updates
        self.update_queue = queue.Queue()

        # Create UI
        self._create_menu()
        self._create_toolbar()
        self._create_main_panel()
        self._create_status_bar()

        # Start queue processor
        self.after(100, self._process_queue)

        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel - File list
        left_frame = tk.Frame(paned)
        paned.add(left_frame, minsize=300)

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

        # Right panel - Preview and details
        right_frame = tk.Frame(paned)
        paned.add(right_frame, minsize=400)

        tk.Label(right_frame, text="Vista previa:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=5)

        # Cover preview
        self.cover_label = tk.Label(right_frame, text="Selecciona un comic para ver su portada",
                                    bg='gray90', width=40, height=20)
        self.cover_label.pack(padx=5, pady=5)

        # Details frame
        details_frame = tk.Frame(right_frame)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Label(details_frame, text="Detalles:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        self.details_text = tk.Text(details_frame, height=10, wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons
        button_frame = tk.Frame(right_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(button_frame, text="🔍 Buscar en TebeoSfera", command=self._search_current).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="💾 Generar ComicInfo.xml", command=self._generate_xml_current).pack(side=tk.LEFT, padx=2)

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

        # Extract and show cover
        cover = comic.extract_cover()
        if cover:
            # Resize to fit
            cover.thumbnail((400, 600), Image.ANTIALIAS)
            photo = ImageTk.PhotoImage(cover)
            self.cover_label.config(image=photo, text='')
            self.cover_label.image = photo  # Keep reference
        else:
            self.cover_label.config(image='', text='No se pudo extraer la portada')

        # Show details
        details = "Archivo: {0}\n".format(comic.filename)
        details += "Ruta: {0}\n".format(comic.filepath)
        details += "Estado: {0}\n".format(comic.status)

        if comic.metadata:
            details += "\nMetadatos encontrados:\n"
            details += "Serie: {0}\n".format(comic.metadata.get('series', 'N/A'))
            details += "Número: {0}\n".format(comic.metadata.get('number', 'N/A'))

        self.details_text.delete('1.0', tk.END)
        self.details_text.insert('1.0', details)

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

            # Inject into CBZ
            self._inject_xml(comic.filepath, xml_content)

            comic.status = 'completed'
            messagebox.showinfo("Éxito", "ComicInfo.xml generado e inyectado correctamente")

        except Exception as e:
            comic.status = 'error'
            messagebox.showerror("Error", "Error generando XML: {0}".format(e))

    def _inject_xml(self, cbz_path, xml_content):
        '''Inject ComicInfo.xml into CBZ file'''
        import shutil
        temp_dir = tempfile.mkdtemp()
        temp_cbz = os.path.join(temp_dir, 'temp.cbz')

        try:
            with zipfile.ZipFile(cbz_path, 'r') as zip_in:
                with zipfile.ZipFile(temp_cbz, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                    for item in zip_in.infolist():
                        if item.filename != 'ComicInfo.xml':
                            data = zip_in.read(item.filename)
                            zip_out.writestr(item, data)

                    zip_out.writestr('ComicInfo.xml', xml_content.encode('utf-8'))

            shutil.move(temp_cbz, cbz_path)

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


class SearchDialog(tk.Toplevel):
    '''Dialog for searching and selecting issues from TebeoSfera'''

    def __init__(self, parent, comic, db):
        tk.Toplevel.__init__(self, parent)

        self.title("Buscar en TebeoSfera - {0}".format(comic.filename))
        self.geometry("1000x700")
        self.transient(parent)

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
        self.back_button = tk.Button(search_frame, text="← Volver a series", command=self._back_to_series, state=tk.DISABLED)
        self.back_button.pack(side=tk.LEFT, padx=10)

        # Main panel - split between results and preview
        main_paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: Results list
        left_frame = tk.Frame(main_paned)
        main_paned.add(left_frame, minsize=400)

        self.results_label = tk.Label(left_frame, text="Series encontradas:", font=('Arial', 10, 'bold'))
        self.results_label.pack(anchor=tk.W)

        # Listbox for results
        list_frame = tk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.results_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.results_listbox.bind('<<ListboxSelect>>', self._on_result_select)
        self.results_listbox.bind('<Double-Button-1>', self._on_double_click)

        scrollbar.config(command=self.results_listbox.yview)

        # Right: Preview panel
        right_frame = tk.Frame(main_paned)
        main_paned.add(right_frame, minsize=300)

        tk.Label(right_frame, text="Vista previa:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        self.preview_label = tk.Label(right_frame, text="Selecciona un resultado para ver su portada",
                                       bg='gray90', width=30, height=20)
        self.preview_label.pack(padx=5, pady=5)

        # Info text
        self.info_text = tk.Text(right_frame, height=8, wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Buttons
        button_frame = tk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        self.select_button = tk.Button(button_frame, text="Ver Issues →", command=self._view_issues)
        self.select_button.pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="✗ Cancelar", command=self.destroy).pack(side=tk.LEFT)

        # Status label
        self.status_label = tk.Label(self, text="", fg='blue')
        self.status_label.pack(fill=tk.X, padx=10)

    def _auto_search(self):
        '''Auto-search based on filename'''
        # Extract series name from filename
        filename = self.comic.filename
        # Remove extension
        name = os.path.splitext(filename)[0]
        # Remove common patterns like numbers, dates, etc.
        import re
        name = re.sub(r'[_\-.]', ' ', name)
        name = re.sub(r'\d+', '', name)
        name = name.strip()

        if name:
            self.search_entry.insert(0, name)
            self._search()

    def _search(self):
        '''Perform search'''
        query = self.search_entry.get().strip()
        if not query:
            return

        self.mode = 'series'
        self.back_button.config(state=tk.DISABLED)
        self.results_label.config(text="Series encontradas:")
        self.select_button.config(text="Ver Issues →", command=self._view_issues)

        self.results_listbox.delete(0, tk.END)
        self.results_listbox.insert(tk.END, "Buscando...")
        self.status_label.config(text="Buscando en TebeoSfera...")
        self.update()

        # Perform search in background
        def search_thread():
            results = self.db.search_series(query)

            def update_results():
                self.results_listbox.delete(0, tk.END)
                self.search_results = results

                if not results:
                    self.results_listbox.insert(tk.END, "Sin resultados")
                    self.status_label.config(text="Sin resultados")
                    return

                # Display results first
                for result in results:
                    self.results_listbox.insert(tk.END, result.series_name_s)

                self.status_label.config(text="{0} series encontradas - Comparando portadas...".format(len(results)))

                # Start image comparison if comic has a cover
                if self.comic.cover_image:
                    self._compare_covers_with_results(results)
                else:
                    self.status_label.config(text="{0} series encontradas".format(len(results)))

            self.after(0, update_results)

        thread = threading.Thread(target=search_thread)
        thread.daemon = True
        thread.start()

    def _compare_covers_with_results(self, results):
        '''Compare comic cover with search results covers'''
        def compare_thread():
            self.downloaded_images = []
            self.similarity_scores = []

            # Download all covers
            for result in results:
                try:
                    image_data = self.db.query_image(result)
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
                    for i, result in enumerate(results):
                        score = self.similarity_scores[i] if i < len(self.similarity_scores) else 0
                        prefix = "⭐ " if i == self.best_match_index and score > 60 else "   "
                        display_text = "{0}{1} ({2:.0f}% similar)".format(prefix, result.series_name_s, score)
                        self.results_listbox.insert(tk.END, display_text)

                    # Auto-select best match if score is good enough
                    if self.best_match_index >= 0 and self.similarity_scores[self.best_match_index] > 60:
                        self.results_listbox.selection_clear(0, tk.END)
                        self.results_listbox.selection_set(self.best_match_index)
                        self.results_listbox.see(self.best_match_index)
                        self.results_listbox.activate(self.best_match_index)
                        # Trigger selection event
                        self.selected_series = self.search_results[self.best_match_index]
                        self._show_series_preview(self.selected_series)

                        best_score = self.similarity_scores[self.best_match_index]
                        self.status_label.config(
                            text="Mejor match encontrado: {0:.0f}% similar (⭐ marcado)".format(best_score)
                        )
                    else:
                        self.status_label.config(text="{0} series encontradas".format(len(results)))

                self.after(0, update_ui)

        thread = threading.Thread(target=compare_thread)
        thread.daemon = True
        thread.start()

    def _on_result_select(self, event):
        '''Handle result selection'''
        selection = self.results_listbox.curselection()
        if not selection:
            return

        index = selection[0]

        if self.mode == 'series' and index < len(self.search_results):
            self.selected_series = self.search_results[index]
            self._show_series_preview(self.selected_series)
        elif self.mode == 'issues' and index < len(self.issues_list):
            self.selected_issue = self.issues_list[index]
            self._show_issue_preview(self.selected_issue)

    def _on_double_click(self, event):
        '''Handle double-click on result'''
        if self.mode == 'series':
            self._view_issues()
        elif self.mode == 'issues':
            self._select_issue()

    def _show_series_preview(self, series_ref):
        '''Show preview of selected series'''
        # Clear previous preview
        self.preview_label.config(image='', text='Cargando portada...')
        self.info_text.delete('1.0', tk.END)
        self.update()

        # Show series info
        info = "Serie: {0}\n".format(series_ref.series_name_s)
        info += "Clave: {0}\n".format(series_ref.series_key)
        self.info_text.insert('1.0', info)

        # Load cover in background
        def load_cover():
            image_data = self.db.query_image(series_ref)
            if image_data:
                def show_cover():
                    try:
                        image = Image.open(BytesIO(image_data))
                        image.thumbnail((300, 450), Image.ANTIALIAS)
                        photo = ImageTk.PhotoImage(image)
                        self.preview_label.config(image=photo, text='')
                        self.cover_images['current'] = photo  # Keep reference
                    except Exception as e:
                        self.preview_label.config(text='Error mostrando portada')
                self.after(0, show_cover)
            else:
                self.after(0, lambda: self.preview_label.config(text='Sin portada disponible'))

        thread = threading.Thread(target=load_cover)
        thread.daemon = True
        thread.start()

    def _show_issue_preview(self, issue_ref):
        '''Show preview of selected issue'''
        # Clear previous preview
        self.preview_label.config(image='', text='Cargando portada...')
        self.info_text.delete('1.0', tk.END)
        self.update()

        # Show issue info
        info = "Título: {0}\n".format(issue_ref.title_s)
        info += "Número: {0}\n".format(issue_ref.issue_num_s)
        info += "Clave: {0}\n".format(issue_ref.issue_key)
        self.info_text.insert('1.0', info)

        # Load cover in background
        def load_cover():
            image_data = self.db.query_image(issue_ref)
            if image_data:
                def show_cover():
                    try:
                        image = Image.open(BytesIO(image_data))
                        image.thumbnail((300, 450), Image.ANTIALIAS)
                        photo = ImageTk.PhotoImage(image)
                        self.preview_label.config(image=photo, text='')
                        self.cover_images['current'] = photo  # Keep reference
                    except Exception as e:
                        self.preview_label.config(text='Error mostrando portada')
                self.after(0, show_cover)
            else:
                self.after(0, lambda: self.preview_label.config(text='Sin portada disponible'))

        thread = threading.Thread(target=load_cover)
        thread.daemon = True
        thread.start()

    def _view_issues(self):
        '''View issues for selected series'''
        if not self.selected_series:
            messagebox.showwarning("Advertencia", "Selecciona una serie primero")
            return

        self.mode = 'issues'
        self.back_button.config(state=tk.NORMAL)
        self.results_label.config(text="Issues de '{0}':".format(self.selected_series.series_name_s))
        self.select_button.config(text="✓ Seleccionar Issue", command=self._select_issue)

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
                    image_data = self.db.query_image(issue)
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

    def _back_to_series(self):
        '''Go back to series search results'''
        self.mode = 'series'
        self.back_button.config(state=tk.DISABLED)
        self.results_label.config(text="Series encontradas:")
        self.select_button.config(text="Ver Issues →", command=self._view_issues)

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
            'writers': issue.writers_sl,
            'pencillers': issue.pencillers_sl,
            'inkers': issue.inkers_sl,
            'colorists': issue.colorists_sl,
            'letterers': issue.letterers_sl,
            'cover_artists': issue.cover_artists_sl,
            'editors': issue.editors_sl,
            'translators': issue.translators_sl,
            'genres': issue.crossovers_sl,  # Genres stored in crossovers
            'characters': issue.characters_sl,
            'page_count': issue.page_count_n if issue.page_count_n > 0 else None,
            'language': issue.language_s,
            'format': issue.format_s,
            'binding': issue.binding_s,
            'dimensions': issue.dimensions_s,
            'isbn': issue.isbn_s,
            'legal_deposit': issue.legal_deposit_s,
            'price': issue.price_s,
            'origin_title': issue.origin_title_s,
            'origin_publisher': issue.origin_publisher_s,
            'webpage': issue.webpage_s
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
