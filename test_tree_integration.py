#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Integration test to verify tree expansion with mock data simulating real GUI behavior
'''

import sys
import os

# Add src/py to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'py'))

from database.dbmodels import SeriesRef
from database.tebeosfera.tbdb import TebeoSferaDB
from database.tebeosfera.tbconnection import TebeoSferaConnection


class MockConnection:
    '''Mock connection that returns HTML content without network calls'''
    
    def __init__(self):
        self.last_url = None
    
    def get_saga_page(self, saga_slug):
        '''Return mock saga page HTML'''
        self.last_url = f"/sagas/{saga_slug}.html"
        print(f"  MockConnection.get_saga_page called with: {saga_slug}")
        print(f"  Would fetch: {self.last_url}")
        
        # Return HTML simulating a saga page with collections
        return '''<!DOCTYPE html>
<html><body>
<div class="help-block">Colecciones (2)</div>
<div class="linea_resultados">
  <a href="/colecciones/test_collection_1.html">TEST COLLECTION 1</a>
</div>
<div class="linea_resultados">
  <a href="/colecciones/test_collection_2.html">TEST COLLECTION 2</a>
</div>
</body></html>'''
    
    def get_collection_page(self, collection_slug):
        '''Return mock collection page HTML'''
        self.last_url = f"/colecciones/{collection_slug}.html"
        print(f"  MockConnection.get_collection_page called with: {collection_slug}")
        print(f"  Would fetch: {self.last_url}")
        
        # Return HTML simulating a collection page with issues
        return '''<!DOCTYPE html>
<html><body>
<div class="help-block">Números (3)</div>
<div class="linea_resultados">
  <a href="/numeros/test_issue_1.html">TEST ISSUE 1</a>
</div>
<div class="linea_resultados">
  <a href="/numeros/test_issue_2.html">TEST ISSUE 2</a>
</div>
<div class="linea_resultados">
  <a href="/numeros/test_issue_3.html">TEST ISSUE 3</a>
</div>
</body></html>'''


def test_saga_expansion_integration():
    '''Test expanding a saga - simulating real GUI behavior'''
    print("="*80)
    print("INTEGRATION TEST: Expanding a saga")
    print("="*80)
    
    # Create database with mock connection
    db = TebeoSferaDB()
    db.connection = MockConnection()
    
    # Simulate a saga SeriesRef as would be created from search results
    saga_ref = SeriesRef(
        series_key='test_saga',  # This is what gets extracted from /sagas/test_saga.html
        series_name_s='TEST SAGA',
        volume_year_n=-1,
        publisher_s='',
        issue_count_n=0,
        thumb_url_s=None
    )
    saga_ref.type_s = 'saga'
    
    print(f"\n1. User expands saga: {saga_ref.series_name_s}")
    print(f"   Saga type: {saga_ref.type_s}")
    print(f"   Saga key: {saga_ref.series_key}")
    
    print(f"\n2. GUI calls query_series_children...")
    children = db.query_series_children(saga_ref)
    
    collections = children.get('collections', [])
    issues = children.get('issues', [])
    
    print(f"\n3. Results:")
    print(f"   Collections found: {len(collections)}")
    for c in collections:
        print(f"     - {c.series_name_s} (key: {c.series_key}, type: {c.type_s})")
    print(f"   Issues found: {len(issues)}")
    for i in issues:
        print(f"     - {i.title_s}")
    
    # Verify
    success = len(collections) == 2 and len(issues) == 0
    
    print(f"\n4. Verification:")
    if success:
        print("   ✅ Saga expanded correctly with 2 collections")
    else:
        print(f"   ❌ Expected 2 collections, 0 issues. Got {len(collections)} collections, {len(issues)} issues")
    
    return success


def test_collection_expansion_integration():
    '''Test expanding a collection - simulating real GUI behavior'''
    print("\n" + "="*80)
    print("INTEGRATION TEST: Expanding a collection")
    print("="*80)
    
    # Create database with mock connection
    db = TebeoSferaDB()
    db.connection = MockConnection()
    
    # Simulate a collection SeriesRef as would be created from search results
    collection_ref = SeriesRef(
        series_key='test_collection_1',  # This is what gets extracted from /colecciones/test_collection_1.html
        series_name_s='TEST COLLECTION 1',
        volume_year_n=-1,
        publisher_s='',
        issue_count_n=0,
        thumb_url_s=None
    )
    collection_ref.type_s = 'collection'
    
    print(f"\n1. User expands collection: {collection_ref.series_name_s}")
    print(f"   Collection type: {collection_ref.type_s}")
    print(f"   Collection key: {collection_ref.series_key}")
    
    print(f"\n2. GUI calls query_series_children...")
    children = db.query_series_children(collection_ref)
    
    collections = children.get('collections', [])
    issues = children.get('issues', [])
    
    print(f"\n3. Results:")
    print(f"   Collections found: {len(collections)}")
    print(f"   Issues found: {len(issues)}")
    for i in issues:
        print(f"     - {i.title_s}")
    
    # Verify
    success = len(collections) == 0 and len(issues) == 3
    
    print(f"\n4. Verification:")
    if success:
        print("   ✅ Collection expanded correctly with 3 issues")
    else:
        print(f"   ❌ Expected 0 collections, 3 issues. Got {len(collections)} collections, {len(issues)} issues")
    
    return success


def test_nested_expansion_integration():
    '''Test nested expansion: saga -> collection -> issues'''
    print("\n" + "="*80)
    print("INTEGRATION TEST: Nested expansion (saga -> collection -> issues)")
    print("="*80)
    
    # Create database with mock connection
    db = TebeoSferaDB()
    db.connection = MockConnection()
    
    # Step 1: Expand saga
    print("\n1. User expands saga...")
    saga_ref = SeriesRef(
        series_key='test_saga',
        series_name_s='TEST SAGA',
        volume_year_n=-1,
        publisher_s='',
        issue_count_n=0,
        thumb_url_s=None
    )
    saga_ref.type_s = 'saga'
    
    saga_children = db.query_series_children(saga_ref)
    saga_collections = saga_children.get('collections', [])
    
    print(f"   Found {len(saga_collections)} collections in saga")
    
    if not saga_collections:
        print("   ❌ No collections found in saga - cannot continue test")
        return False
    
    # Step 2: Expand first collection from saga
    print("\n2. User expands first collection from saga...")
    first_collection = saga_collections[0]
    print(f"   Collection: {first_collection.series_name_s}")
    print(f"   Collection key: {first_collection.series_key}")
    print(f"   Collection type: {first_collection.type_s}")
    
    collection_children = db.query_series_children(first_collection)
    collection_issues = collection_children.get('issues', [])
    
    print(f"   Found {len(collection_issues)} issues in collection")
    
    # Verify
    success = len(saga_collections) == 2 and len(collection_issues) == 3
    
    print(f"\n3. Verification:")
    if success:
        print("   ✅ Nested expansion works correctly")
        print(f"      - Saga has {len(saga_collections)} collections")
        print(f"      - Collection has {len(collection_issues)} issues")
    else:
        print(f"   ❌ Expected 2 collections with 3 issues each")
        print(f"      Got {len(saga_collections)} collections, {len(collection_issues)} issues")
    
    return success


if __name__ == '__main__':
    print("\nTebeoSfera Tree Expansion Integration Tests")
    print("Testing with mock connection (no network calls)\n")
    
    test1 = test_saga_expansion_integration()
    test2 = test_collection_expansion_integration()
    test3 = test_nested_expansion_integration()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    if test1 and test2 and test3:
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("\nThe tree expansion logic is working correctly:")
        print("  - Sagas fetch from /sagas/ and return collections")
        print("  - Collections fetch from /colecciones/ and return issues")
        print("  - Nested expansion works (saga -> collection -> issues)")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        if not test1:
            print("  - Saga expansion test failed")
        if not test2:
            print("  - Collection expansion test failed")
        if not test3:
            print("  - Nested expansion test failed")
        sys.exit(1)
