#!/usr/bin/env python3
"""
Compression script to run after any data fetch
Reduces data from ~550MB to ~2MB using columnar storage
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def find_latest_data_directory():
    """Find the most recent data directory (backup or current)"""
    data_dir = Path("data")
    
    # Check for current directory first
    current_dir = data_dir / "current"
    if current_dir.exists() and (current_dir / "hybrid_data_90d.json").exists():
        return str(current_dir)
    
    # Otherwise find latest backup
    backup_dirs = [d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("backup")]
    if backup_dirs:
        latest_backup = max(backup_dirs, key=lambda d: d.stat().st_mtime)
        if (latest_backup / "hybrid_data_90d.json").exists():
            return str(latest_backup)
    
    return None

def run_compression(input_dir=None):
    """Run the compression pipeline"""
    
    # 1. Find input directory if not specified
    if not input_dir:
        input_dir = find_latest_data_directory()
        if not input_dir:
            print("❌ No data directory found with hybrid_data_90d.json")
            return False
    
    print(f"📁 Using data from: {input_dir}")
    
    # 2. Check that transform script exists
    transform_script = Path("scripts/transform_to_columnar.py")
    if not transform_script.exists():
        print("❌ Transform script not found: scripts/transform_to_columnar.py")
        return False
    
    # 3. Run transformation
    print("🗜️  Compressing data to columnar format...")
    result = subprocess.run(
        [sys.executable, str(transform_script)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ Transformation failed: {result.stderr}")
        return False
    
    print("✅ Data compressed successfully")
    
    # 4. Copy optimized files to dashboard
    output_dir = Path("data/optimized")
    dashboard_dir = Path("dashboards/optimized/data/optimized")
    
    if not output_dir.exists():
        print("❌ Optimized data directory not found")
        return False
    
    print("📋 Copying files to dashboard...")
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    
    files_to_copy = ['meta_v1.json', 'agg_v1.json', 'summary_v1.json', 'manifest.json']
    for file in files_to_copy:
        src = output_dir / file
        dst = dashboard_dir / file
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} not found")
    
    # 5. Copy previous week data if exists
    prev_week_src = Path(input_dir) / "hybrid_data_prev_week.json"
    if prev_week_src.exists():
        print("📅 Copying previous week data...")
        prev_week_dst = dashboard_dir / "prev_week_original.json"
        shutil.copy2(prev_week_src, prev_week_dst)
        print(f"  ✓ Previous week data ({prev_week_src.stat().st_size / 1024 / 1024:.1f}MB)")
    else:
        print("⚠️  No previous week data found")
    
    # 6. Report sizes
    print("\n📊 Compression results:")
    print("─" * 40)
    
    original_90d = Path(input_dir) / "hybrid_data_90d.json"
    if original_90d.exists():
        original_size = original_90d.stat().st_size / 1024 / 1024
        print(f"Original 90d file: {original_size:.1f}MB")
    
    total_optimized = sum(
        (dashboard_dir / f).stat().st_size 
        for f in files_to_copy 
        if (dashboard_dir / f).exists()
    ) / 1024 / 1024
    print(f"Optimized files: {total_optimized:.1f}MB")
    
    if original_90d.exists():
        compression_ratio = (1 - total_optimized / original_size) * 100
        print(f"Compression ratio: {compression_ratio:.1f}%")
    
    print("\n✅ Compression pipeline complete!")
    print("\n🌐 To test the optimized dashboard:")
    print("   cd dashboards/optimized")
    print("   python3 -m http.server 8001")
    print("   Open http://localhost:8001/index_full.html")
    
    return True

def main():
    """Main entry point"""
    import argparse
    parser = argparse.ArgumentParser(description='Compress fetch data to columnar format')
    parser.add_argument('--input-dir', help='Input directory with hybrid_data files')
    args = parser.parse_args()
    
    success = run_compression(args.input_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()