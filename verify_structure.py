#!/usr/bin/env python3
"""Verify package structure before deployment."""

import sys
from pathlib import Path

def verify_structure():
    """Verify all necessary files and directories exist."""
    print("Verifying package structure...\n")
    
    root = Path(__file__).parent
    issues = []
    
    # Check critical files
    files_to_check = [
        'Procfile',
        'setup.py',
        'requirements.txt',
        'railway.json',
        'src/__init__.py',
        'src/api/__init__.py',
        'src/api/main.py',
        'src/api/routes/__init__.py',
        'src/core/__init__.py',
        'src/data/__init__.py',
        'src/data/category_mapper.py',
        'src/search/__init__.py',
    ]
    
    for file in files_to_check:
        file_path = root / file
        if file_path.exists():
            print(f"✓ {file}")
        else:
            print(f"✗ {file} - MISSING!")
            issues.append(f"Missing file: {file}")
    
    # Check Procfile content
    procfile = root / 'Procfile'
    if procfile.exists():
        content = procfile.read_text()
        if 'python -m uvicorn' in content:
            print("\n✓ Procfile uses correct command format")
        else:
            print("\n⚠ Procfile might need updating")
            issues.append("Procfile should use 'python -m uvicorn'")
    
    # Check setup.py exists and has content
    setup_py = root / 'setup.py'
    if setup_py.exists() and setup_py.stat().st_size > 0:
        print("✓ setup.py is present and not empty")
    else:
        issues.append("setup.py is missing or empty")
    
    # Summary
    print("\n" + "="*50)
    if not issues:
        print("✅ All structure checks passed!")
        print("\nYour package is ready for Railway deployment.")
        print("\nNext steps:")
        print("1. git add .")
        print("2. git commit -m 'Fix Railway deployment'")
        print("3. git push")
        return True
    else:
        print("❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False

if __name__ == "__main__":
    success = verify_structure()
    sys.exit(0 if success else 1)
