# Changelog - TebeoSfera Scraper

Todos los cambios notables en este proyecto serán documentados en este archivo.

## [2.0.0] - 2025-01-18

### 🎉 Lanzamiento Mayor - TebeoSfera Integration

Este es un lanzamiento transformador que convierte el proyecto de Comic Vine Scraper
en un scraper completo para comics españoles usando tebeosfera.com.

### ✨ Nuevas Características

#### Scraping de TebeoSfera
- **Módulo de conexión HTTP** (`tbconnection.py`)
  - Conexión robusta a tebeosfera.com
  - Rate limiting respetuoso (1.5s entre peticiones)
  - Manejo de cookies y sesiones
  - Soporte para gzip y encodings

- **Parser HTML** (`tbparser.py`)
  - Extracción completa de metadatos de fichas
  - Parsing de fechas en formato español (DD-MM-YYYY y DD-MON-YYYY con romanos)
  - Decodificación de entidades HTML
  - Extracción de autores por rol (guionista, dibujante, colorista, etc.)

- **Adaptador de Base de Datos** (`tbdb.py`)
  - Compatible con arquitectura existente
  - Búsqueda de series
  - Consulta de issues de una serie
  - Detalles completos de issues individuales

#### Generación de ComicInfo.xml
- **Generador completo** (`comicinfo_xml.py`)
  - Soporte para todos los campos estándar ComicInfo.xml v2.0
  - Formato XML con indentación correcta
  - Compatibilidad con ComicRack, Kavita, Komga, etc.
  - Campos específicos españoles integrados en Notes

#### Campos Específicos Españoles
- **Extensiones al modelo Issue** (en `dbmodels.py`):
  - `isbn_s` - ISBN del tebeo
  - `legal_deposit_s` - Depósito Legal
  - `price_s` - Precio con moneda (ej: "18.00 EUR")
  - `format_s` - Formato (Álbum, Grapa, Tomo, etc.)
  - `binding_s` - Encuadernación (Cartoné, Rústica, etc.)
  - `dimensions_s` - Dimensiones físicas (ej: "31 x 23 cm")
  - `page_count_n` - Número de páginas
  - `color_s` - Información de color (COLOR, B/N, etc.)
  - `origin_title_s` - Título original si es traducción
  - `origin_publisher_s` - Editorial original
  - `origin_country_s` - País de origen
  - `language_s` - Información de idioma/traducción
  - `collection_s` - Nombre de la colección
  - `collection_url_s` - URL a la página de colección
  - `issue_count_n` - Total de issues en la serie
  - `translators_sl` - Lista de traductores
  - `adapted_authors_sl` - Autores originales (para adaptaciones)

#### Script Standalone
- **tebeosfera_scraper.py** - Script principal con comandos:
  - `search` - Buscar series en tebeosfera
  - `series` - Listar issues de una serie
  - `issue` - Ver detalles de un issue
  - `xml` - Generar ComicInfo.xml
  - `inject` - Inyectar ComicInfo.xml en archivos CBZ
  - Salida JSON para integración con otros sistemas
  - No requiere ComicRack - completamente standalone

#### Inyección en CBZ
- Inserta ComicInfo.xml en archivos CBZ existentes
- Preserva todos los archivos originales
- Reemplaza ComicInfo.xml si ya existe
- Usa compresión DEFLATE

### 📚 Documentación
- **TEBEOSFERA_README.md** - Documentación completa en español
  - Guía de instalación y uso
  - Ejemplos de todos los comandos
  - Explicación de campos extraídos
  - Ejemplos de ComicInfo.xml generado

- **test_scraper.py** - Suite de tests
  - Test de conexión
  - Test de parser
  - Test de generador ComicInfo.xml
  - Test de adaptador de base de datos
  - Test de modelos extendidos

- **README.md** actualizado con nuevo estado del proyecto

### 🔧 Cambios Técnicos

#### Arquitectura
- Modular y extensible
- Separación clara de responsabilidades
- Compatible con código base existente
- Sin dependencias externas (solo stdlib de Python)

#### Compatibilidad
- Python 2.7 (mantiene compatibilidad con proyecto original)
- Solo usa librerías estándar de Python
- Sin dependencias de .NET (versión standalone)

### 📊 Cobertura de Datos

Metadatos extraídos de tebeosfera.com:
- ✅ Título y serie
- ✅ Número y total de issues
- ✅ Editorial, ubicación, país
- ✅ Fecha de publicación (día/mes/año)
- ✅ Precio con moneda
- ✅ ISBN y Depósito Legal
- ✅ Formato y encuadernación
- ✅ Dimensiones físicas
- ✅ Número de páginas
- ✅ Color/B&N
- ✅ Guionistas, dibujantes, entintadores, coloristas, letristas
- ✅ Artistas de portada, editores
- ✅ Traductores y autores adaptados
- ✅ Géneros
- ✅ Información de origen (título, editorial, país)
- ✅ Idioma y traducción
- ✅ URLs de portadas
- ✅ Enlace a ficha en tebeosfera

### 🎯 Casos de Uso

Este scraper es perfecto para:
1. Catalogar colecciones de cómics españoles
2. Generar metadatos para bibliotecas digitales (Kavita, Komga)
3. Etiquetar archivos CBZ con ComicInfo.xml
4. Integración con sistemas de gestión de colecciones
5. Búsqueda y consulta de información sobre tebeos

### 🔜 Trabajo Futuro

Posibles mejoras para futuras versiones:
- Soporte para CBR (archivos RAR)
- Cache de búsquedas
- Descarga de portadas
- Scraping de personajes
- Búsqueda por autor
- Integración con otras bases de datos españolas
- GUI opcional
- Migración a Python 3

### 🙏 Agradecimientos

- **tebeosfera.com** - Por mantener la mejor base de datos de tebeos
- **Comic Vine Scraper** (Cory Banack) - Por la arquitectura base
- **Comunidad de ComicRack** - Por el estándar ComicInfo.xml

---

## Versiones Anteriores

Ver historial de Git para versiones del Comic Vine Scraper original.
