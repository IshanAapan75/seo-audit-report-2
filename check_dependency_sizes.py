#!/usr/bin/env python3
"""
Script to check and compare dependency sizes
"""
import subprocess
import sys
import json

def get_package_size(package_name):
    """Get approximate package size"""
    try:
        # This is an approximation - actual sizes may vary
        size_estimates = {
            'pandas': 80,  # MB (with numpy dependencies)
            'polars': 20,  # MB
            'numpy': 25,   # MB (pandas dependency)
            'weasyprint': 150,  # MB (with system dependencies)
            'reportlab': 15,    # MB
            'Flask': 2,         # MB
            'requests': 1,      # MB
            'beautifulsoup4': 1, # MB
            'lxml': 15,         # MB
            'Pillow': 10,       # MB
            'advertools': 5,    # MB
            'networkx': 3,      # MB
        }
        
        return size_estimates.get(package_name.lower(), 1)
    except:
        return 1

def analyze_requirements(file_path):
    """Analyze requirements file and estimate total size"""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        total_size = 0
        packages = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                package = line.split('==')[0].split('>=')[0].split('<=')[0]
                size = get_package_size(package)
                total_size += size
                packages.append((package, size))
        
        return packages, total_size
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return [], 0

def main():
    """Compare dependency sizes"""
    print("📦 Dependency Size Analysis")
    print("=" * 60)
    
    # Analyze original requirements
    print("\n🔍 Original Requirements (with pandas):")
    original_packages, original_total = analyze_requirements('requirements.txt')
    
    # Create temporary pandas requirements for comparison
    pandas_requirements = """Flask==2.3.3
pandas==2.0.3
requests==2.31.0
beautifulsoup4==4.12.2
lxml==4.9.3
weasyprint==60.0
Pillow==10.0.0"""
    
    with open('temp_pandas_requirements.txt', 'w') as f:
        f.write(pandas_requirements)
    
    pandas_packages, pandas_total = analyze_requirements('temp_pandas_requirements.txt')
    
    # Clean up
    import os
    os.remove('temp_pandas_requirements.txt')
    
    print(f"{'Package':<20} {'Size (MB)':<10}")
    print("-" * 30)
    for package, size in original_packages:
        print(f"{package:<20} {size:<10}")
    print("-" * 30)
    print(f"{'TOTAL':<20} {original_total:<10}")
    
    print(f"\n📊 Size Comparison:")
    print(f"Current (polars):     ~{original_total} MB")
    print(f"Original (pandas):    ~{pandas_total} MB")
    print(f"Savings:              ~{pandas_total - original_total} MB")
    
    # Vercel limit check
    vercel_limit = 250
    print(f"\n🚀 Vercel Deployment Check:")
    print(f"Vercel limit:         {vercel_limit} MB")
    print(f"Current size:         ~{original_total} MB")
    
    if original_total <= vercel_limit:
        print("✅ Under Vercel limit!")
    else:
        print("❌ Still over Vercel limit")
        print(f"   Need to reduce by: ~{original_total - vercel_limit} MB")
        
        print(f"\n💡 Suggestions to reduce further:")
        print(f"   • Replace weasyprint with reportlab: -135 MB")
        print(f"   • Remove lxml if possible: -15 MB")
        print(f"   • Use hybrid architecture (API only): -170 MB")
    
    print(f"\n🎯 Alternative Deployment Options:")
    print(f"   • Railway: No size limits")
    print(f"   • Render: 500 MB limit")
    print(f"   • DigitalOcean App Platform: 1 GB limit")
    print(f"   • Heroku: 500 MB slug size limit")

if __name__ == "__main__":
    main()