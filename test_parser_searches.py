#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Test script to analyze search results for specific queries
and improve the parser based on real HTML structure.
'''

import sys
import os

# Add src/py to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'py'))

from database.tebeosfera.tbdb import TebeoSferaDB
from database.tebeosfera.tbconnection import get_connection
import tempfile

# Test queries
test_queries = [
    "Pitufos",
    "Tintín", 
    "Supergrupo",
    "El hombre que ríe. La casa"
]

def test_search(query):
    print(f"\n{'='*80}")
    print(f"Testing search: '{query}'")
    print(f"{'='*80}")
    
    db = TebeoSferaDB()
    
    # Perform search
    results = db.search_series(query)
    
    print(f"\nResults found: {len(results)}")
    for i, result in enumerate(results[:10], 1):
        print(f"  {i}. {result.series_name_s} (key: {result.series_key})")
    
    # Get HTML for analysis
    connection = get_connection()
    html = connection.search(query)
    
    if html:
        # Save HTML
        debug_file = os.path.join(tempfile.gettempdir(), f'tebeosfera_{query.replace(" ", "_")}.html')
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\nHTML saved to: {debug_file}")
        
        # Analyze HTML structure
        print(f"\nHTML Analysis:")
        print(f"  Total size: {len(html)} bytes")
        print(f"  Contains '/numeros/': {html.count('/numeros/')} times")
        print(f"  Contains '/colecciones/': {html.count('/colecciones/')} times")
        
        # Find result sections
        import re
        section_headers = re.findall(r'<h[234][^>]*>(.*?)(?:N[UÚ]MEROS|COLECCIONES|AUTORES)(.*?)</h[234]>', html, re.IGNORECASE)
        print(f"  Section headers found: {len(section_headers)}")

if __name__ == '__main__':
    print("Testing TebeoSfera parser with multiple search queries...")
    print("This will help identify parser issues and improve it.\n")
    
    for query in test_queries:
        try:
            test_search(query)
        except Exception as e:
            print(f"Error testing '{query}': {e}")
            import traceback
            traceback.print_exc()

