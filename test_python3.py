#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Quick test to verify Python 3 compatibility of TebeoSfera scraper modules.
'''

import sys
import os

# Check Python version
print("=" * 60)
print("Testing Python 3 Compatibility")
print("=" * 60)
print(f"Python version: {sys.version}")
print(f"Python version info: {sys.version_info}")

if sys.version_info < (3, 6):
    print("\n❌ ERROR: Python 3.6+ is required")
    sys.exit(1)

print("✅ Python version check passed\n")

# Add src/py to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'py'))

# Test imports
print("Testing module imports...")
print("-" * 60)

try:
    print("  Importing TebeoSferaDB...", end=" ")
    from database.tebeosfera.tbdb import TebeoSferaDB
    print("✅")
except ImportError as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

try:
    print("  Importing TebeoSferaConnection...", end=" ")
    from database.tebeosfera.tbconnection import TebeoSferaConnection
    print("✅")
except ImportError as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

try:
    print("  Importing TebeoSferaParser...", end=" ")
    from database.tebeosfera.tbparser import TebeoSferaParser
    print("✅")
except ImportError as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

try:
    print("  Importing ComicInfoGenerator...", end=" ")
    from comicinfo_xml import ComicInfoGenerator
    print("✅")
except ImportError as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

print("\n✅ All core modules imported successfully!")

# Test GUI modules (optional)
print("\nTesting GUI modules (optional)...")
print("-" * 60)

try:
    print("  Importing tkinter...", end=" ")
    import tkinter as tk
    print("✅")

    print("  Importing PIL/Pillow...", end=" ")
    from PIL import Image, ImageTk
    print("✅")

    print("\n✅ GUI modules available! You can use the GUI application.")
    gui_available = True
except ImportError as e:
    print(f"⚠️  Not available: {e}")
    print("\n⚠️  GUI not available. Install Pillow with: pip3 install pillow")
    gui_available = False

# Test basic functionality
print("\nTesting basic functionality...")
print("-" * 60)

try:
    print("  Creating TebeoSferaDB instance...", end=" ")
    db = TebeoSferaDB()
    print("✅")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

try:
    print("  Creating ComicInfoGenerator instance...", end=" ")
    xml_gen = ComicInfoGenerator()
    print("✅")
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

try:
    print("  Testing XML generation with sample data...", end=" ")
    sample_data = {
        'title': 'Test Comic',
        'series': 'Test Series',
        'number': '1',
        'writers': ['Test Writer'],
        'artists': ['Test Artist']
    }
    xml = xml_gen.generate_xml(sample_data)
    if '<Title>Test Comic</Title>' in xml and '<Series>Test Series</Series>' in xml:
        print("✅")
    else:
        print("❌ XML generation failed")
        sys.exit(1)
except Exception as e:
    print(f"❌ Failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("✅ Python 3 compatibility: PASSED")
print("✅ Core modules: WORKING")
print(f"{'✅' if gui_available else '⚠️ '} GUI modules: {'AVAILABLE' if gui_available else 'NOT INSTALLED'}")
print("\n🎉 TebeoSfera scraper is ready to use with Python 3!")

if not gui_available:
    print("\n📝 To use the GUI, install Pillow:")
    print("   pip3 install pillow")
print("\n" + "=" * 60)
