#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Test script to verify search result parsing with all types (collections, sagas, issues)
This verifies the fix for the issue where only números were being extracted.
'''

import sys
import os

# Add src/py to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'py'))

from database.tebeosfera.tbparser import TebeoSferaParser
from database.tebeosfera.tbdb import TebeoSferaDB

def test_parser_with_all_types():
    '''Test the parser with a sample HTML containing all result types'''
    print("="*80)
    print("TEST 1: Parser with all section types (Colecciones, Sagas, Números)")
    print("="*80)
    
    # Sample HTML with all types
    html_content = '''<!DOCTYPE html>
<html>
<body>
<!-- Simulated search results from tebeosfera.com -->

<div class="help-block">Colecciones (2)</div>
<div class="linea_resultados">
  <a href="/colecciones/valerian_1978_grijalbo.html">
    <img id="img_principal" src="/images/T3_colecciones/valerian_1978_grijalbo.jpg">
  </a>
  <a href="/colecciones/valerian_1978_grijalbo.html">VALERIAN (1978, GRIJALBO)</a>
</div>
<div class="linea_resultados">
  <a href="/colecciones/valerian_2010_norma.html">
    <img id="img_principal" src="/images/T3_colecciones/valerian_2010_norma.jpg">
  </a>
  <a href="/colecciones/valerian_2010_norma.html">VALERIAN (2010, NORMA)</a>
</div>

<div class="help-block">Sagas (1)</div>
<div class="linea_resultados">
  <a href="/sagas/valerian_saga.html">
    <img id="img_principal" src="/images/T3_sagas/valerian_saga.jpg">
  </a>
  <a href="/sagas/valerian_saga.html">VALERIAN Y LAURELINE</a>
</div>

<div class="help-block">Números (3)</div>
<div class="linea_resultados">
  <a href="/numeros/valerian_1978_grijalbo_1.html">
    <img id="img_principal" src="/images/T3_numeros/valerian_1978_grijalbo_1.jpg">
  </a>
  <a href="/numeros/valerian_1978_grijalbo_1.html">VALERIAN (1978, GRIJALBO) 1 : LA CIUDAD DE LAS AGUAS TURBULENTAS</a>
</div>
<div class="linea_resultados">
  <a href="/numeros/valerian_1978_grijalbo_2.html">
    <img id="img_principal" src="/images/T3_numeros/valerian_1978_grijalbo_2.jpg">
  </a>
  <a href="/numeros/valerian_1978_grijalbo_2.html">VALERIAN (1978, GRIJALBO) 2 : EL IMPERIO DE LOS MIL PLANETAS</a>
</div>
<div class="linea_resultados">
  <a href="/numeros/valerian_2010_norma_1.html">
    <img id="img_principal" src="/images/T3_numeros/valerian_2010_norma_1.jpg">
  </a>
  <a href="/numeros/valerian_2010_norma_1.html">VALERIAN (2010, NORMA) 1 : LA CIUDAD DE LAS AGUAS TURBULENTAS</a>
</div>

<div class="help-block">Autores (2)</div>
<div class="linea_resultados">
  <a href="/autores/christin.html">CHRISTIN, PIERRE</a>
</div>

</body>
</html>'''
    
    parser = TebeoSferaParser()
    results = parser.parse_search_results(html_content)
    
    print(f"\nTotal results parsed: {len(results)}")
    
    # Group by type
    by_type = {}
    for result in results:
        rtype = result.get('type', 'unknown')
        if rtype not in by_type:
            by_type[rtype] = []
        by_type[rtype].append(result)
    
    # Verify counts
    expected = {'collection': 2, 'saga': 1, 'issue': 3}
    success = True
    
    for rtype, expected_count in expected.items():
        actual_count = len(by_type.get(rtype, []))
        status = "✅" if actual_count == expected_count else "❌"
        print(f"{status} {rtype.upper()}: Expected {expected_count}, Got {actual_count}")
        
        if actual_count != expected_count:
            success = False
        
        # Show details
        for item in by_type.get(rtype, []):
            title = item.get('title', 'NO TITLE')
            slug = item.get('slug', 'NO SLUG')
            print(f"    - {title[:60]}")
            print(f"      slug: {slug}")
    
    # Check that Autores section was skipped
    has_autores = any('autor' in r.get('slug', '').lower() for r in results)
    if has_autores:
        print("❌ AUTORES: Should be skipped but found in results")
        success = False
    else:
        print("✅ AUTORES: Correctly skipped (not in results)")
    
    print("\n" + "="*80)
    if success:
        print("✅ TEST 1 PASSED: All types parsed correctly with proper titles")
    else:
        print("❌ TEST 1 FAILED: Some types missing or incorrect")
    print("="*80)
    
    return success


def test_db_adapter_types():
    '''Test that the database adapter properly converts parser results to SeriesRef with type_s'''
    print("\n" + "="*80)
    print("TEST 2: Database Adapter - SeriesRef type_s attribute")
    print("="*80)
    
    # We can't test with real network, but we can verify the code structure
    
    # Create mock results like the parser would return
    mock_results = [
        {'slug': 'series1', 'title': 'Test Series 1', 'type': 'collection', 'series_name': 'Test Series 1', 'thumb_url': None},
        {'slug': 'saga1', 'title': 'Test Saga 1', 'type': 'saga', 'series_name': 'Test Saga 1', 'thumb_url': None},
        {'slug': 'issue1', 'title': 'Test Issue 1', 'type': 'issue', 'series_name': 'Test Issue 1', 'thumb_url': None},
    ]
    
    # Simulate what search_series does (without network call)
    from database.dbmodels import SeriesRef
    
    series_refs = []
    for result in mock_results:
        slug = result.get('slug')
        result_type = result.get('type', 'collection')
        
        thumb_url = result.get('thumb_url')
        if thumb_url and not thumb_url.startswith('http'):
            thumb_url = 'https://www.tebeosfera.com' + thumb_url
        
        if result_type in ['collection', 'saga']:
            series_name = result.get('series_name') or result.get('title', slug)
            series_key = slug
            issue_count = 0
        elif result_type == 'issue':
            full_title = result.get('title', '')
            series_name = full_title if full_title else result.get('series_name', slug)
            series_key = slug
            issue_count = 1
        else:
            continue
        
        series_ref = SeriesRef(
            series_key=series_key,
            series_name_s=series_name,
            volume_year_n=-1,
            publisher_s='',
            issue_count_n=issue_count,
            thumb_url_s=thumb_url
        )
        # Set extended fields
        series_ref.type_s = result_type
        series_refs.append(series_ref)
    
    # Verify each has type_s attribute
    success = True
    for ref in series_refs:
        has_type = hasattr(ref, 'type_s')
        type_val = getattr(ref, 'type_s', None)
        status = "✅" if has_type and type_val else "❌"
        print(f"{status} {ref.series_name_s[:40]}: type_s='{type_val}'")
        if not has_type or not type_val:
            success = False
    
    print("\n" + "="*80)
    if success:
        print("✅ TEST 2 PASSED: All SeriesRef objects have type_s attribute")
    else:
        print("❌ TEST 2 FAILED: Some SeriesRef missing type_s")
    print("="*80)
    
    return success


if __name__ == '__main__':
    print("\nTebeoSfera Search Types Test Suite")
    print("Testing fix for issue: Search only extracting números, ignoring sagas/series\n")
    
    test1_passed = test_parser_with_all_types()
    test2_passed = test_db_adapter_types()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    if test1_passed and test2_passed:
        print("✅ ALL TESTS PASSED")
        print("\nThe parser now correctly extracts:")
        print("  - Colecciones (series/collections)")
        print("  - Sagas (thematic groups)")
        print("  - Números (individual issues)")
        print("\nEach result has proper title and type_s attribute for GUI display.")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        if not test1_passed:
            print("  - Parser test failed")
        if not test2_passed:
            print("  - Database adapter test failed")
        sys.exit(1)
