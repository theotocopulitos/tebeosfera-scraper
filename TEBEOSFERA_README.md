# TebeoSfera Scraper para Comics Españoles

Scraper completo para extraer metadatos de comics españoles desde tebeosfera.com y generar archivos ComicInfo.xml compatibles con ComicRack, Kavita, y otros lectores de comics.

## 🌟 Características

### ✅ Implementado

- ✅ **Scraping completo de tebeosfera.com**
  - Búsqueda de series y colecciones
  - Extracción de fichas de números/tebeos
  - Metadatos completos en español

- ✅ **Generación de ComicInfo.xml estándar**
  - Compatible con ComicRack, Kavita, Komga, etc.
  - Todos los campos estándar soportados
  - Extensiones para campos específicos españoles

- ✅ **Campos específicos españoles**
  - ISBN / Depósito Legal
  - Formato (Álbum, Grapa, Tomo, etc.)
  - Encuadernación (Cartoné, Rústica, etc.)
  - Dimensiones físicas
  - Precio con moneda
  - Editorial y ubicación
  - Idioma original y traducción
  - Traductor(es)
  - Autor(es) adaptado(s)
  - Título y editorial original

- ✅ **Inyección en CBZ**
  - Inserta ComicInfo.xml en archivos CBZ existentes
  - Preserva archivos existentes
  - Reemplaza ComicInfo.xml si ya existe

- ✅ **Script standalone**
  - No requiere ComicRack
  - Funciona desde línea de comandos
  - Salida JSON para integración

## 📋 Requisitos

- Python 2.7 (compatible con el código base existente)
- Acceso a Internet para consultar tebeosfera.com

No se requieren dependencias externas - usa solo librerías estándar de Python.

## 🚀 Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tuusuario/tebeosfera-scraper.git
cd tebeosfera-scraper

# No requiere instalación adicional - listo para usar
```

## 💻 Uso

### Búsqueda de Series

```bash
# Buscar una serie
python tebeosfera_scraper.py search "Thorgal"

# Salida JSON
python tebeosfera_scraper.py search "Astérix" --json
```

### Listar Issues de una Serie

```bash
# Obtener issues de una colección
python tebeosfera_scraper.py series "leyendas_de_los_otori_2021_tengu"
```

### Detalles de un Issue

```bash
# Ver detalles completos de un tebeo
python tebeosfera_scraper.py issue "leyendas_de_los_otori_2021_tengu_5"

# Salida JSON
python tebeosfera_scraper.py issue "leyendas_de_los_otori_2021_tengu_5" --json
```

### Generar ComicInfo.xml

```bash
# Generar y mostrar ComicInfo.xml
python tebeosfera_scraper.py xml "leyendas_de_los_otori_2021_tengu_5"

# Guardar en archivo
python tebeosfera_scraper.py xml "leyendas_de_los_otori_2021_tengu_5" -o ComicInfo.xml
```

### Inyectar ComicInfo.xml en CBZ

```bash
# Inyectar metadatos en un archivo CBZ
python tebeosfera_scraper.py inject "mi_comic.cbz" "leyendas_de_los_otori_2021_tengu_5"
```

## 📖 Estructura del Proyecto

```
tebeosfera-scraper/
├── tebeosfera_scraper.py          # Script principal standalone
├── src/py/
│   ├── comicinfo_xml.py           # Generador de ComicInfo.xml
│   ├── database/
│   │   ├── dbmodels.py            # Modelos de datos (extendidos)
│   │   └── tebeosfera/
│   │       ├── __init__.py
│   │       ├── tbconnection.py    # Conexión HTTP a tebeosfera.com
│   │       ├── tbparser.py        # Parser HTML
│   │       └── tbdb.py            # Adaptador de base de datos
│   └── book/
│       └── bookdata.py            # Estructura de datos de comics
└── TEBEOSFERA_README.md           # Este archivo
```

## 🔍 Cómo Encontrar el Slug de un Issue

Para usar el scraper necesitas el "slug" del issue (identificador único en la URL):

1. Busca el comic en tebeosfera.com
2. Abre la ficha del número que quieres
3. La URL será algo como: `https://www.tebeosfera.com/numeros/leyendas_de_los_otori_2021_tengu_5.html`
4. El slug es: `leyendas_de_los_otori_2021_tengu_5` (todo entre `/numeros/` y `.html`)

O usa el comando `search` para encontrar slugs:

```bash
python tebeosfera_scraper.py search "Leyendas de los Otori"
# Te mostrará los slugs de todas las colecciones encontradas

python tebeosfera_scraper.py series "leyendas_de_los_otori_2021_tengu"
# Te mostrará los slugs de todos los números de la colección
```

## 📝 Campos Extraídos

### Campos Estándar ComicInfo.xml

- Title (Título del número)
- Series (Nombre de la serie)
- Number (Número del issue)
- Count (Total de issues en la serie)
- Volume (Año de volumen)
- Summary (Sinopsis)
- Publisher (Editorial)
- Year, Month, Day (Fecha de publicación)
- Writer (Guionista)
- Penciller (Dibujante)
- Inker (Entintador)
- Colorist (Colorista)
- Letterer (Rotulista)
- CoverArtist (Artista de portada)
- Editor (Editor)
- Genre (Géneros)
- Characters (Personajes)
- PageCount (Número de páginas)
- LanguageISO (Código de idioma)
- Format (Formato)
- Web (URL de la ficha)

### Campos Específicos Españoles (en Notes)

- ISBN
- Depósito Legal
- Precio (con moneda)
- Título Original
- Editorial Original
- Colección
- Encuadernación (Cartoné, Rústica, etc.)
- Dimensiones (cm)
- Translator (Traductor)

## 🎯 Ejemplos de ComicInfo.xml Generado

```xml
<?xml version="1.0" encoding="utf-8"?>
<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Title>LAS NIEVES DEL EXILIO</Title>
  <Series>LEYENDAS DE LOS OTORI</Series>
  <Number>5</Number>
  <Count>5</Count>
  <Volume>2021</Volume>
  <Summary>El invierno ha caído sobre los Tres Países... El coraje sigue siendo su único recurso.</Summary>
  <Publisher>Tengu Ediciones</Publisher>
  <LanguageISO>es</LanguageISO>
  <Format>ÁLBUM</Format>
  <Year>2025</Year>
  <Month>11</Month>
  <Day>18</Day>
  <Writer>STÉPHANE MELCHIOR</Writer>
  <Penciller>BACHELIER</Penciller>
  <Colorist>BACHELIER</Colorist>
  <Genre>Acción, Adaptación, Aventura, Fantasía, Fantástico, Histórico, Juvenil, Samuráis</Genre>
  <PageCount>80</PageCount>
  <Web>https://www.tebeosfera.com/numeros/leyendas_de_los_otori_2021_tengu_5.html</Web>
  <Notes>ISBN: 978-84-19949-45-5
Precio: 18.00 EUR
Título Original: Le clan des Otori nº 5
Editorial Original: Gallimard
Encuadernación: CARTONÉ
Dimensiones: 31 x 23 cm</Notes>
</ComicInfo>
```

## 🤝 Contribuir

Este es un proyecto de código abierto. ¡Las contribuciones son bienvenidas!

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📜 Licencia

Este proyecto está licenciado bajo Apache License 2.0 - ver el archivo LICENSE para detalles.

## 🙏 Agradecimientos

- **tebeosfera.com** - Por mantener la mejor base de datos de cómics en español
- **Comic Vine Scraper** (Cory Banack) - Por la base de código original
- **Comunidad de ComicRack** - Por el estándar ComicInfo.xml

## 🐛 Reportar Bugs

Si encuentras algún problema:

1. Verifica que tebeosfera.com esté accesible
2. Comprueba que el slug del issue sea correcto
3. Abre un issue en GitHub con:
   - Comando ejecutado
   - Error recibido
   - URL del comic en tebeosfera.com (si aplica)

## 📧 Contacto

Para preguntas o sugerencias, abre un issue en GitHub.

---

**¡Disfruta catalogando tu colección de cómics españoles!** 🎨📚
