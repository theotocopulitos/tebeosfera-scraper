"""
Script para verificar el funcionamiento del caché de TebeoSfera
"""
import os
import sqlite3
from pathlib import Path

def get_cache_dir():
    """Obtener directorio de caché"""
    if os.name == 'nt':
        cache_base = os.path.join(
            os.environ.get('APPDATA', os.path.expanduser('~')),
            'TebeoSferaScraper'
        )
    else:
        cache_base = os.path.join(
            os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache')),
            'tebeosfera-scraper'
        )
    return Path(cache_base)

def verify_cache():
    """Verificar estado del caché"""
    cache_dir = get_cache_dir()
    db_path = cache_dir / 'cache.db'
    image_dir = cache_dir / 'images'
    xml_dir = cache_dir / 'xml'
    
    print("=" * 60)
    print("VERIFICACIÓN DEL CACHÉ DE TEBEOSFERA")
    print("=" * 60)
    print(f"\n📁 Directorio de caché: {cache_dir}")
    print(f"   Existe: {'✅ SÍ' if cache_dir.exists() else '❌ NO'}")
    
    # Verificar base de datos
    print(f"\n🗄️  Base de datos SQLite: {db_path}")
    if db_path.exists():
        print(f"   Existe: ✅ SÍ")
        print(f"   Tamaño: {db_path.stat().st_size / 1024:.2f} KB")
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Contar búsquedas
            cursor.execute('SELECT COUNT(*) FROM searches')
            search_count = cursor.fetchone()[0]
            print(f"\n   📊 Búsquedas cacheadas: {search_count}")
            
            # Mostrar últimas búsquedas
            if search_count > 0:
                cursor.execute('SELECT query_text, result_count, datetime(created_at, "unixepoch") as created FROM searches ORDER BY last_accessed DESC LIMIT 5')
                print("   Últimas búsquedas:")
                for row in cursor.fetchall():
                    query, count, created = row
                    print(f"      - '{query}' ({count} resultados) - {created}")
            
            # Contar series children
            cursor.execute('SELECT COUNT(*) FROM series_children')
            series_count = cursor.fetchone()[0]
            print(f"\n   📊 Series/colecciones cacheadas: {series_count}")
            
            # Contar issues
            cursor.execute('SELECT COUNT(*) FROM issue_details')
            issue_count = cursor.fetchone()[0]
            print(f"   📊 Issues cacheados: {issue_count}")
            
            # Contar imágenes
            cursor.execute('SELECT COUNT(*), SUM(file_size) FROM images')
            img_count, img_size = cursor.fetchone()
            img_count = img_count or 0
            img_size = img_size or 0
            print(f"   📊 Imágenes cacheadas: {img_count} ({img_size / 1024 / 1024:.2f} MB)")
            
            # Contar XML
            cursor.execute('SELECT COUNT(*), SUM(file_size) FROM xml_files')
            xml_count, xml_size = cursor.fetchone()
            xml_count = xml_count or 0
            xml_size = xml_size or 0
            print(f"   📊 XML cacheados: {xml_count} ({xml_size / 1024:.2f} KB)")
            
            conn.close()
        except Exception as e:
            print(f"   ❌ Error leyendo BD: {e}")
    else:
        print(f"   Existe: ❌ NO (el caché aún no se ha usado)")
    
    # Verificar directorio de imágenes
    print(f"\n🖼️  Directorio de imágenes: {image_dir}")
    if image_dir.exists():
        image_files = list(image_dir.glob('*.jpg'))
        print(f"   Existe: ✅ SÍ")
        print(f"   Archivos: {len(image_files)}")
        if image_files:
            total_size = sum(f.stat().st_size for f in image_files)
            print(f"   Tamaño total: {total_size / 1024 / 1024:.2f} MB")
    else:
        print(f"   Existe: ❌ NO")
    
    # Verificar directorio de XML
    print(f"\n📄 Directorio de XML: {xml_dir}")
    if xml_dir.exists():
        xml_files = list(xml_dir.glob('*.xml'))
        print(f"   Existe: ✅ SÍ")
        print(f"   Archivos: {xml_files}")
        if xml_files:
            total_size = sum(f.stat().st_size for f in xml_files)
            print(f"   Tamaño total: {total_size / 1024:.2f} KB")
    else:
        print(f"   Existe: ❌ NO")
    
    print("\n" + "=" * 60)
    print("INSTRUCCIONES PARA VERIFICAR EN LA GUI:")
    print("=" * 60)
    print("""
1. 📝 Busca la misma serie 2 veces seguidas
   - La primera vez debería hacer una petición HTTP
   - La segunda vez debería mostrar "🗄️ ✅ Resultados obtenidos del caché"
   - Las estadísticas HTTP deberían mostrar hits de caché

2. 📊 Revisa las estadísticas HTTP (abajo a la derecha en la ventana de búsqueda)
   - Deberías ver: "📡 HTTP: X solicitudes | Y KB | Z ms | 🗄️ Cache: A hits / B misses"
   - Si haces búsquedas repetidas, los hits deberían aumentar

3. 🔍 Revisa los logs en la consola
   - Busca mensajes como "✅ Cache hit for search: ..."
   - O "❌ Cache miss for search: ..."
   - O "✅ Cached search results for: ..."

4. ⚡ Verifica la velocidad
   - La primera búsqueda debería tardar varios segundos
   - Las búsquedas siguientes (del caché) deberían ser casi instantáneas

5. 🖼️  Verifica imágenes
   - Al cargar portadas, la segunda vez debería ser más rápida
   - Las imágenes se guardan en: {image_dir}

6. 📄 Verifica XML
   - Al cargar un issue, el XML se cachea automáticamente
   - Los XML se guardan en: {xml_dir}
""".format(image_dir=image_dir, xml_dir=xml_dir))
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    verify_cache()

