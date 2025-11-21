## Description

**🎉 ¡AHORA FUNCIONAL! - TebeoSfera Scraper para Comics Españoles 🎉**

Este proyecto ha sido completamente renovado para convertirse en un scraper funcional de **tebeosfera.com**,
la mejor base de datos de cómics en español.

### ✨ Nuevas Características

- ✅ **Scraping completo desde tebeosfera.com**
- ✅ **Visualización de portadas** 🖼️ - Muestra portadas durante búsqueda y selección (¡como el scraper original!)
- ✅ **Generación de ComicInfo.xml** estándar para lectores como ComicRack, Kavita, Komga
- ✅ **Campos específicos españoles**: ISBN, Depósito Legal, Formato (Álbum/Grapa), Encuadernación, Traductor, etc.
- ✅ **Script standalone** - No requiere ComicRack, funciona desde línea de comandos
- ✅ **Inyección de metadatos en CBZ** - Inserta ComicInfo.xml en tus archivos existentes

### 🚀 Inicio Rápido

```bash
# Buscar un comic (¡ahora con portadas!)
python tebeosfera_scraper.py search "Thorgal"

# Ver issues de una serie (modo interactivo para elegir portadas)
python tebeosfera_scraper.py series "tintin_1958_juventud" -i

# Ver detalles de un número con portada
python tebeosfera_scraper.py issue "leyendas_de_los_otori_2021_tengu_5" --show-cover

# Generar ComicInfo.xml
python tebeosfera_scraper.py xml "leyendas_de_los_otori_2021_tengu_5" -o ComicInfo.xml

# Inyectar en CBZ
python tebeosfera_scraper.py inject "mi_comic.cbz" "leyendas_de_los_otori_2021_tengu_5"

# Ejecutar tests
python test_scraper.py
```

### 📚 Documentación Completa

Ver **[TEBEOSFERA_README.md](TEBEOSFERA_README.md)** para documentación completa en español.

---

