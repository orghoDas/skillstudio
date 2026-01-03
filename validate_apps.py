#!/usr/bin/env python
"""
Validation script to verify students and instructors app code quality.
Tests that all files have valid Python syntax.
"""

import ast
import sys
from pathlib import Path

def check_syntax(file_path):
    """Check if a Python file has valid syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)

def main():
    """Validate all Python files in students and instructors apps."""
    apps_to_check = ['students', 'instructors']
    all_valid = True
    
    for app in apps_to_check:
        app_path = Path(app)
        if not app_path.exists():
            print(f"❌ App directory not found: {app}")
            all_valid = False
            continue
        
        print(f"\n{'='*60}")
        print(f"Checking {app} app...")
        print(f"{'='*60}")
        
        python_files = list(app_path.glob('*.py'))
        
        for py_file in python_files:
            if py_file.name.startswith('__'):
                continue
            
            valid, error = check_syntax(py_file)
            
            if valid:
                print(f"✓ {py_file.name:<25} - Valid syntax")
            else:
                print(f"✗ {py_file.name:<25} - Syntax error: {error}")
                all_valid = False
    
    print(f"\n{'='*60}")
    if all_valid:
        print("✅ All files passed syntax validation!")
        print("\n📊 Summary:")
        for app in apps_to_check:
            files = list(Path(app).glob('*.py'))
            non_init = [f for f in files if not f.name.startswith('__')]
            print(f"  {app:12} - {len(non_init)} files validated")
        return 0
    else:
        print("❌ Some files have syntax errors!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
