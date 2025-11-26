"""
Sistema de caché híbrido completo para TebeoSfera.
SQLite para metadatos, archivos para imágenes y XML.
"""
import sqlite3
import os
import json
import hashlib
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
import pickle

try:
    from database.dbmodels import SeriesRef, IssueRef, Issue
except ImportError:
    SeriesRef = IssueRef = Issue = None


class TebeoSferaCache:
    """
    Sistema de caché completo para TebeoSfera.
    Cachea: búsquedas, imágenes, hijos de series, detalles de issues, y ComicInfo.xml
    """
    
    # Tiempos de expiración (en segundos)
    SEARCH_CACHE_TTL = 7 * 24 * 60 * 60      # 7 días
    SERIES_CHILDREN_TTL = 7 * 24 * 60 * 60   # 7 días
    IMAGE_CACHE_TTL = 30 * 24 * 60 * 60      # 30 días
    ISSUE_DETAILS_TTL = 30 * 24 * 60 * 60    # 30 días
    XML_CACHE_TTL = 30 * 24 * 60 * 60        # 30 días (mismo que issue)
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Inicializar caché."""
        try:
            if cache_dir is None:
                import tempfile
                if os.name == 'nt':
                    cache_base = os.path.join(
                        os.environ.get('APPDATA', tempfile.gettempdir()),
                        'TebeoSferaScraper'
                    )
                else:
                    cache_base = os.path.join(
                        os.environ.get('XDG_CACHE_HOME', 
                                     os.path.expanduser('~/.cache')),
                        'tebeosfera-scraper'
                    )
                cache_dir = cache_base
            
            self.cache_dir = Path(cache_dir)
            self.image_cache_dir = self.cache_dir / 'images'
            self.xml_cache_dir = self.cache_dir / 'xml'
            self.db_path = self.cache_dir / 'cache.db'
            
            # Crear directorios
            self.image_cache_dir.mkdir(parents=True, exist_ok=True)
            self.xml_cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Inicializar base de datos
            self._init_database()
        except Exception as e:
            # Si falla la inicialización del caché, continuar sin caché
            # pero registrar el error
            import sys
            print(f"Warning: Cache initialization failed: {e}", file=sys.stderr)
            # Establecer valores por defecto para evitar errores
            self.cache_dir = None
            self.image_cache_dir = None
            self.xml_cache_dir = None
            self.db_path = None
    
    def _init_database(self):
        """Inicializar SQLite con todas las tablas."""
        if self.db_path is None:
            return
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Tabla de búsquedas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS searches (
                    query_hash TEXT PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    results_data BLOB NOT NULL,
                    result_count INTEGER,
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL
                )
            ''')
            
            # Tabla de hijos de series (collections/issues de una serie)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS series_children (
                    series_key TEXT PRIMARY KEY,
                    children_data BLOB NOT NULL,
                    collection_count INTEGER,
                    issue_count INTEGER,
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL
                )
            ''')
            
            # Tabla de detalles de issues
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS issue_details (
                    issue_key TEXT PRIMARY KEY,
                    issue_data BLOB NOT NULL,
                    series_name TEXT,
                    issue_number TEXT,
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL
                )
            ''')
            
            # Tabla de imágenes (metadatos)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL
                )
            ''')
            
            # Tabla de XML generados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS xml_files (
                    issue_key TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    created_at REAL NOT NULL,
                    last_accessed REAL NOT NULL
                )
            ''')
            
            # Índices para limpieza rápida
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_searches_created ON searches(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_series_children_created ON series_children(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_issue_details_created ON issue_details(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_images_created ON images(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_xml_created ON xml_files(created_at)')
            
            conn.commit()
            conn.close()
        except Exception as e:
            # Si falla la inicialización de la BD, continuar sin caché
            import sys
            print(f"Warning: Database initialization failed: {e}", file=sys.stderr)
            try:
                conn.close()
            except:
                pass
    
    def _get_search_key(self, query: str) -> str:
        """Generar clave para búsqueda."""
        normalized = ' '.join(query.lower().strip().split())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def _get_image_key(self, url: str) -> str:
        """Generar clave para imagen."""
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    # ========== CACHÉ DE BÚSQUEDAS ==========
    
    def get_cached_search(self, query: str) -> Optional[List]:
        """Obtener resultados de búsqueda cacheados."""
        if self.db_path is None:
            return None
        query_hash = self._get_search_key(query)
        now = time.time()
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT results_data, created_at 
                FROM searches 
                WHERE query_hash = ?
            ''', (query_hash,))
            
            row = cursor.fetchone()
            if row is None:
                conn.close()
                return None
            
            results_data, created_at = row
            
            if now - created_at > self.SEARCH_CACHE_TTL:
                cursor.execute('DELETE FROM searches WHERE query_hash = ?', (query_hash,))
                conn.commit()
                conn.close()
                return None
            
            cursor.execute('UPDATE searches SET last_accessed = ? WHERE query_hash = ?', (now, query_hash))
            conn.commit()
            conn.close()
            
            try:
                return pickle.loads(results_data)
            except Exception:
                return None
        except Exception:
            return None
    
    def cache_search(self, query: str, results: List):
        """Cachear resultados de búsqueda."""
        if self.db_path is None:
            return
        query_hash = self._get_search_key(query)
        now = time.time()
        
        try:
            results_data = pickle.dumps(results)
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO searches 
                (query_hash, query_text, results_data, result_count, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (query_hash, query, results_data, len(results), now, now))
            
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    # ========== CACHÉ DE HIJOS DE SERIES ==========
    
    def get_cached_series_children(self, series_key: str) -> Optional[Dict]:
        """Obtener hijos de serie cacheados."""
        if self.db_path is None:
            return None
        now = time.time()
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT children_data, created_at 
                FROM series_children 
                WHERE series_key = ?
            ''', (series_key,))
            
            row = cursor.fetchone()
            if row is None:
                conn.close()
                return None
            
            children_data, created_at = row
            
            if now - created_at > self.SERIES_CHILDREN_TTL:
                cursor.execute('DELETE FROM series_children WHERE series_key = ?', (series_key,))
                conn.commit()
                conn.close()
                return None
            
            cursor.execute('UPDATE series_children SET last_accessed = ? WHERE series_key = ?', (now, series_key))
            conn.commit()
            conn.close()
            
            try:
                return pickle.loads(children_data)
            except Exception:
                return None
        except Exception:
            return None
    
    def cache_series_children(self, series_key: str, children: Dict):
        """Cachear hijos de serie."""
        if self.db_path is None:
            return
        now = time.time()
        
        try:
            children_data = pickle.dumps(children)
            collections = children.get('collections', [])
            issues = children.get('issues', [])
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO series_children 
                (series_key, children_data, collection_count, issue_count, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (series_key, children_data, len(collections), len(issues), now, now))
            
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    # ========== CACHÉ DE DETALLES DE ISSUE ==========
    
    def get_cached_issue_details(self, issue_key: str) -> Optional[Any]:
        """Obtener detalles de issue cacheados."""
        if self.db_path is None:
            return None
        now = time.time()
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT issue_data, created_at 
                FROM issue_details 
                WHERE issue_key = ?
            ''', (issue_key,))
            
            row = cursor.fetchone()
            if row is None:
                conn.close()
                return None
            
            issue_data, created_at = row
            
            if now - created_at > self.ISSUE_DETAILS_TTL:
                cursor.execute('DELETE FROM issue_details WHERE issue_key = ?', (issue_key,))
                # También eliminar XML asociado
                cursor.execute('SELECT file_path FROM xml_files WHERE issue_key = ?', (issue_key,))
                xml_row = cursor.fetchone()
                if xml_row:
                    try:
                        Path(xml_row[0]).unlink(missing_ok=True)
                    except Exception:
                        pass
                cursor.execute('DELETE FROM xml_files WHERE issue_key = ?', (issue_key,))
                conn.commit()
                conn.close()
                return None
            
            cursor.execute('UPDATE issue_details SET last_accessed = ? WHERE issue_key = ?', (now, issue_key))
            conn.commit()
            conn.close()
            
            try:
                return pickle.loads(issue_data)
            except Exception:
                return None
        except Exception:
            return None
    
    def cache_issue_details(self, issue_key: str, issue: Any, xml_content: Optional[str] = None):
        """
        Cachear detalles de issue y opcionalmente el XML generado.
        
        issue_key: Clave del issue
        issue: Objeto Issue
        xml_content: Contenido XML generado (si se proporciona, se cachea automáticamente)
        """
        if self.db_path is None:
            return
        now = time.time()
        
        try:
            issue_data = pickle.dumps(issue)
            series_name = getattr(issue, 'series_name_s', '') or getattr(issue, 'collection_s', '')
            issue_number = getattr(issue, 'issue_num_s', '')
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO issue_details 
                (issue_key, issue_data, series_name, issue_number, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (issue_key, issue_data, series_name, issue_number, now, now))
            
            # Si se proporciona XML, cachearlo también
            if xml_content:
                xml_file = self.xml_cache_dir / f"{issue_key}.xml"
                try:
                    with open(xml_file, 'w', encoding='utf-8') as f:
                        f.write(xml_content)
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO xml_files 
                        (issue_key, file_path, file_size, created_at, last_accessed)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (issue_key, str(xml_file), len(xml_content.encode('utf-8')), now, now))
                except Exception:
                    pass
            
            conn.commit()
            conn.close()
        except Exception:
            pass
    
    # ========== CACHÉ DE XML ==========
    
    def get_cached_xml(self, issue_key: str) -> Optional[str]:
        """Obtener XML cacheado para un issue."""
        if self.db_path is None or self.xml_cache_dir is None:
            return None
        now = time.time()
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT file_path, created_at 
                FROM xml_files 
                WHERE issue_key = ?
            ''', (issue_key,))
            
            row = cursor.fetchone()
            if row is None:
                conn.close()
                return None
            
            file_path, created_at = row
            
            if now - created_at > self.XML_CACHE_TTL:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass
                cursor.execute('DELETE FROM xml_files WHERE issue_key = ?', (issue_key,))
                conn.commit()
                conn.close()
                return None
            
            if not Path(file_path).exists():
                cursor.execute('DELETE FROM xml_files WHERE issue_key = ?', (issue_key,))
                conn.commit()
                conn.close()
                return None
            
            cursor.execute('UPDATE xml_files SET last_accessed = ? WHERE issue_key = ?', (now, issue_key))
            conn.commit()
            conn.close()
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                return None
        except Exception:
            return None
    
    def cache_xml(self, issue_key: str, xml_content: str):
        """Cachear XML generado."""
        if self.db_path is None or self.xml_cache_dir is None:
            return
        now = time.time()
        xml_file = self.xml_cache_dir / f"{issue_key}.xml"
        
        try:
            with open(xml_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO xml_files 
                (issue_key, file_path, file_size, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?)
            ''', (issue_key, str(xml_file), len(xml_content.encode('utf-8')), now, now))
            
            conn.commit()
            conn.close()
        except Exception:
            try:
                xml_file.unlink(missing_ok=True)
            except Exception:
                pass
    
    # ========== CACHÉ DE IMÁGENES ==========
    
    def get_cached_image(self, url: str) -> Optional[bytes]:
        """Obtener imagen cacheada."""
        if self.db_path is None or self.image_cache_dir is None:
            return None
        url_hash = self._get_image_key(url)
        now = time.time()
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT file_path, created_at 
                FROM images 
                WHERE url_hash = ?
            ''', (url_hash,))
            
            row = cursor.fetchone()
            if row is None:
                conn.close()
                return None
            
            file_path, created_at = row
            
            if now - created_at > self.IMAGE_CACHE_TTL:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass
                cursor.execute('DELETE FROM images WHERE url_hash = ?', (url_hash,))
                conn.commit()
                conn.close()
                return None
            
            if not Path(file_path).exists():
                cursor.execute('DELETE FROM images WHERE url_hash = ?', (url_hash,))
                conn.commit()
                conn.close()
                return None
            
            cursor.execute('UPDATE images SET last_accessed = ? WHERE url_hash = ?', (now, url_hash))
            conn.commit()
            conn.close()
            
            try:
                with open(file_path, 'rb') as f:
                    return f.read()
            except Exception:
                return None
        except Exception:
            return None
    
    def cache_image(self, url: str, image_data: bytes):
        """Cachear imagen."""
        if self.db_path is None or self.image_cache_dir is None:
            return
        url_hash = self._get_image_key(url)
        now = time.time()
        file_path = self.image_cache_dir / f"{url_hash}.jpg"
        
        try:
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO images 
                (url_hash, url, file_path, file_size, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (url_hash, url, str(file_path), len(image_data), now, now))
            
            conn.commit()
            conn.close()
        except Exception:
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
    
    # ========== UTILIDADES ==========
    
    def cleanup_expired(self):
        """Limpiar entradas expiradas."""
        now = time.time()
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Limpiar búsquedas
        cursor.execute('DELETE FROM searches WHERE ? - created_at > ?', (now, self.SEARCH_CACHE_TTL))
        
        # Limpiar hijos de series
        cursor.execute('DELETE FROM series_children WHERE ? - created_at > ?', (now, self.SERIES_CHILDREN_TTL))
        
        # Limpiar issues y XML asociados
        cursor.execute('SELECT issue_key FROM issue_details WHERE ? - created_at > ?', (now, self.ISSUE_DETAILS_TTL))
        expired_issues = [row[0] for row in cursor.fetchall()]
        for issue_key in expired_issues:
            cursor.execute('SELECT file_path FROM xml_files WHERE issue_key = ?', (issue_key,))
            xml_row = cursor.fetchone()
            if xml_row:
                try:
                    Path(xml_row[0]).unlink(missing_ok=True)
                except Exception:
                    pass
        cursor.execute('DELETE FROM issue_details WHERE ? - created_at > ?', (now, self.ISSUE_DETAILS_TTL))
        cursor.execute('DELETE FROM xml_files WHERE ? - created_at > ?', (now, self.XML_CACHE_TTL))
        
        # Limpiar imágenes
        cursor.execute('SELECT file_path FROM images WHERE ? - created_at > ?', (now, self.IMAGE_CACHE_TTL))
        expired_images = cursor.fetchall()
        for (file_path,) in expired_images:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass
        cursor.execute('DELETE FROM images WHERE ? - created_at > ?', (now, self.IMAGE_CACHE_TTL))
        
        conn.commit()
        conn.close()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del caché."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Contar y sumar tamaños
        stats = {}
        
        # Búsquedas
        cursor.execute('SELECT COUNT(*), SUM(LENGTH(results_data)) FROM searches')
        count, size = cursor.fetchone()
        stats['searches_count'] = count or 0
        stats['searches_size'] = size or 0
        
        # Hijos de series
        cursor.execute('SELECT COUNT(*), SUM(LENGTH(children_data)) FROM series_children')
        count, size = cursor.fetchone()
        stats['series_children_count'] = count or 0
        stats['series_children_size'] = size or 0
        
        # Detalles de issues
        cursor.execute('SELECT COUNT(*), SUM(LENGTH(issue_data)) FROM issue_details')
        count, size = cursor.fetchone()
        stats['issue_details_count'] = count or 0
        stats['issue_details_size'] = size or 0
        
        # Imágenes
        cursor.execute('SELECT COUNT(*), SUM(file_size) FROM images')
        count, size = cursor.fetchone()
        stats['images_count'] = count or 0
        stats['images_size'] = size or 0
        
        # XML
        cursor.execute('SELECT COUNT(*), SUM(file_size) FROM xml_files')
        count, size = cursor.fetchone()
        stats['xml_files_count'] = count or 0
        stats['xml_files_size'] = size or 0
        
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        conn.close()
        
        return {
            'search_count': stats.get('searches_count', 0),
            'series_children_count': stats.get('series_children_count', 0),
            'issue_details_count': stats.get('issue_details_count', 0),
            'image_count': stats.get('images_count', 0),
            'xml_count': stats.get('xml_files_count', 0),
            'search_size_mb': stats.get('searches_size', 0) / (1024 * 1024),
            'series_children_size_mb': stats.get('series_children_size', 0) / (1024 * 1024),
            'issue_details_size_mb': stats.get('issue_details_size', 0) / (1024 * 1024),
            'image_size_mb': stats.get('images_size', 0) / (1024 * 1024),
            'xml_size_mb': stats.get('xml_files_size', 0) / (1024 * 1024),
            'db_size_mb': db_size / (1024 * 1024),
            'total_size_mb': (sum([stats.get('searches_size', 0), 
                                  stats.get('series_children_size', 0),
                                  stats.get('issue_details_size', 0),
                                  stats.get('images_size', 0),
                                  stats.get('xml_files_size', 0)]) + db_size) / (1024 * 1024)
        }
    
    def clear_cache(self, search_only: bool = False, image_only: bool = False, 
                    series_only: bool = False, issue_only: bool = False, xml_only: bool = False):
        """Limpiar caché selectivamente."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if not search_only and not series_only and not issue_only and not xml_only:
            # Limpiar imágenes
            cursor.execute('SELECT file_path FROM images')
            for (file_path,) in cursor.fetchall():
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass
            cursor.execute('DELETE FROM images')
        
        if not image_only and not series_only and not issue_only and not xml_only:
            cursor.execute('DELETE FROM searches')
        
        if not image_only and not search_only and not issue_only and not xml_only:
            cursor.execute('DELETE FROM series_children')
        
        if not image_only and not search_only and not series_only and not xml_only:
            cursor.execute('SELECT file_path FROM xml_files')
            for (file_path,) in cursor.fetchall():
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass
            cursor.execute('DELETE FROM xml_files')
            cursor.execute('DELETE FROM issue_details')
        
        if not image_only and not search_only and not series_only and not issue_only:
            cursor.execute('SELECT file_path FROM xml_files')
            for (file_path,) in cursor.fetchall():
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass
            cursor.execute('DELETE FROM xml_files')
        
        conn.commit()
        conn.close()

