# TebeoSfera Scraper

> ⚠️ **TRABAJO EN PROGRESO** - Este proyecto está en desarrollo activo y tiene limitaciones conocidas.

Scraper para extraer metadatos de cómics españoles desde tebeosfera.com y generar archivos ComicInfo.xml.

## Estado del Proyecto

Este scraper es funcional pero **todavía está en desarrollo**. 

### ⚠️ Limitaciones Conocidas

- **Gestión de series incompleta**: El scraper actualmente no maneja bien todas las series y colecciones. Funciona mejor con números individuales específicos.
- **Búsquedas pueden devolver resultados mixtos**: Mezcla de ejemplares individuales, colecciones y sagas que requieren revisión manual.
- **Sin caché de resultados**: Cada búsqueda consulta la web directamente.

### Funcionalidades Actuales

- Scraping de metadatos desde tebeosfera.com
- Generación de ComicInfo.xml estándar
- Visualización de portadas
- Inyección de metadatos en archivos CBZ
- Interfaz gráfica (GUI) y línea de comandos (CLI)
- Campos específicos para cómics españoles (ISBN, Depósito Legal, etc.)

## Inicio Rápido

### Interfaz Gráfica (GUI)

```bash
# Linux/Mac
./tebeosfera_gui.sh

# Windows
tebeosfera_gui.bat

# O directamente con Python
python3 tebeosfera_gui.py
```

### Línea de Comandos (CLI)

```bash
# Buscar un cómic
python tebeosfera_scraper.py search "Thorgal"

# Ver números de una serie
python tebeosfera_scraper.py series "tintin_1958_juventud"

# Ver detalles de un número
python tebeosfera_scraper.py issue "leyendas_de_los_otori_2021_tengu_5" --show-cover

# Generar ComicInfo.xml
python tebeosfera_scraper.py xml "leyendas_de_los_otori_2021_tengu_5" -o ComicInfo.xml

# Inyectar en archivo CBZ
python tebeosfera_scraper.py inject "mi_comic.cbz" "leyendas_de_los_otori_2021_tengu_5"
```

## Instalación

### Requisitos

- Python 3.6+
- PIL/Pillow: `pip install pillow`
- CustomTkinter (para GUI): `pip install customtkinter`
- BeautifulSoup4: `pip install beautifulsoup4`

### Pasos

```bash
git clone https://github.com/theotocopulitos/tebeosfera-scraper.git
cd tebeosfera-scraper

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar tests
python test_scraper.py
```

## Documentación

Ver [TEBEOSFERA_README.md](TEBEOSFERA_README.md) para documentación completa incluyendo:
- Guía de uso detallada
- Todos los comandos disponibles
- Campos extraídos
- Ejemplos de ComicInfo.xml generado

## Contribuir

Las contribuciones son bienvenidas. Por favor:
1. Haz un fork del proyecto
2. Crea una rama para tu feature
3. Haz commit de tus cambios
4. Envía un pull request

## Licencia

Apache License 2.0

---

**Nota**: Este es un proyecto en desarrollo. Si encuentras problemas o tienes sugerencias, abre un issue en GitHub.