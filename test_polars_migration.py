#!/usr/bin/env python3
"""
Test script to verify polars migration works correctly
"""
import polars as pl
import sys
import os

def test_polars_import():
    """Test that polars imports correctly"""
    try:
        import polars as pl
        print("✅ Polars import successful")
        print(f"   Polars version: {pl.__version__}")
        return True
    except ImportError as e:
        print(f"❌ Polars import failed: {e}")
        return False

def test_basic_operations():
    """Test basic polars operations"""
    try:
        # Create test DataFrame
        df = pl.DataFrame({
            "url": ["https://example.com", "https://test.com"],
            "title": ["Example", None],
            "status": [200, 404]
        })
        
        # Test operations
        df = df.with_columns([
            pl.col("title").fill_null("Missing").alias("title_clean"),
            pl.col("title").is_null().alias("title_missing"),
            pl.col("status").cast(pl.Int64).alias("status_int")
        ])
        
        # Test aggregation
        missing_count = df.select(pl.col("title_missing").sum()).item()
        
        print("✅ Basic polars operations successful")
        print(f"   DataFrame shape: {df.shape}")
        print(f"   Missing titles: {missing_count}")
        return True
    except Exception as e:
        print(f"❌ Basic operations failed: {e}")
        return False

def test_insights_import():
    """Test that polars insights module imports"""
    try:
        from seo_insights_polars import interpret_meta, interpret_headings
        print("✅ Polars insights import successful")
        return True
    except ImportError as e:
        print(f"❌ Polars insights import failed: {e}")
        return False

def test_audit_import():
    """Test that polars audit module imports"""
    try:
        from seo_audit_polars import main as run_seo_audit
        print("✅ Polars audit import successful")
        return True
    except ImportError as e:
        print(f"❌ Polars audit import failed: {e}")
        return False

def test_insights_functions():
    """Test insights functions with sample data"""
    try:
        from seo_insights_polars import interpret_meta, interpret_status
        
        # Test meta interpretation
        meta_df = pl.DataFrame({
            "url": ["https://example.com", "https://test.com"],
            "title_missing": [0, 1],
            "description_missing": [1, 0]
        })
        
        result = interpret_meta(meta_df)
        assert "summary" in result
        assert "red_flags" in result
        
        # Test status interpretation
        status_df = pl.DataFrame({
            "url": ["https://example.com", "https://test.com"],
            "status": [200, 404]
        })
        
        result = interpret_status(status_df)
        assert "summary" in result
        
        print("✅ Insights functions working correctly")
        return True
    except Exception as e:
        print(f"❌ Insights functions failed: {e}")
        return False

def test_file_operations():
    """Test file read/write operations"""
    try:
        # Create test data
        df = pl.DataFrame({
            "url": ["https://example.com"],
            "title": ["Test Title"],
            "status": [200]
        })
        
        # Test CSV write/read
        test_file = "test_polars.csv"
        df.write_csv(test_file)
        df_read = pl.read_csv(test_file)
        
        # Cleanup
        os.remove(test_file)
        
        print("✅ File operations successful")
        return True
    except Exception as e:
        print(f"❌ File operations failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 Testing Polars Migration")
    print("=" * 50)
    
    tests = [
        test_polars_import,
        test_basic_operations,
        test_insights_import,
        test_audit_import,
        test_insights_functions,
        test_file_operations
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! Polars migration is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())