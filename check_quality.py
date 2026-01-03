#!/usr/bin/env python
"""
Code quality verification for students and instructors apps.
Checks for proper patterns: @transaction.atomic, ValidationError, PermissionDenied
"""

import re
from pathlib import Path

def check_patterns(file_path):
    """Check if service functions follow established patterns."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    results = {
        'has_transaction_atomic': '@transaction.atomic' in content,
        'has_validation_error': 'ValidationError' in content,
        'has_permission_denied': 'PermissionDenied' in content,
        'transaction_count': content.count('@transaction.atomic'),
        'validation_count': content.count('raise ValidationError'),
        'permission_count': content.count('raise PermissionDenied'),
    }
    
    return results

def check_file_structure(app_path):
    """Check if app has all required files."""
    required_files = {
        'models.py': False,
        'services.py': False,
        'serializers.py': False,
        'views.py': False,
        'urls.py': False,
        'admin.py': False,
        'tests.py': False,
    }
    
    for file_name in required_files.keys():
        file_path = app_path / file_name
        if file_path.exists():
            required_files[file_name] = True
    
    return required_files

def count_lines(file_path):
    """Count non-empty lines in a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return len([l for l in lines if l.strip()])

def main():
    """Validate code quality."""
    apps = ['students', 'instructors']
    
    print("\n" + "="*70)
    print("CODE QUALITY VERIFICATION")
    print("="*70)
    
    for app in apps:
        app_path = Path(app)
        print(f"\n📦 {app.upper()} APP")
        print("-" * 70)
        
        # Check file structure
        structure = check_file_structure(app_path)
        all_present = all(structure.values())
        print(f"\n✓ File Structure: {'✅ Complete' if all_present else '⚠️  Missing files'}")
        for file, exists in structure.items():
            status = "✓" if exists else "✗"
            print(f"  {status} {file}")
        
        # Check services.py patterns
        services_path = app_path / 'services.py'
        if services_path.exists():
            patterns = check_patterns(services_path)
            print(f"\n✓ Service Patterns:")
            print(f"  @transaction.atomic:  {patterns['transaction_count']} usages")
            print(f"  ValidationError:      {patterns['validation_count']} raises")
            print(f"  PermissionDenied:     {patterns['permission_count']} raises")
        
        # Count lines of code
        print(f"\n✓ Lines of Code:")
        total_loc = 0
        for file_name in ['models.py', 'services.py', 'serializers.py', 'views.py', 'admin.py', 'tests.py']:
            file_path = app_path / file_name
            if file_path.exists():
                loc = count_lines(file_path)
                total_loc += loc
                print(f"  {file_name:<15} {loc:>4} lines")
        print(f"  {'TOTAL':<15} {total_loc:>4} lines")
    
    print("\n" + "="*70)
    print("✅ CODE QUALITY VERIFICATION COMPLETE")
    print("="*70 + "\n")

if __name__ == '__main__':
    main()
