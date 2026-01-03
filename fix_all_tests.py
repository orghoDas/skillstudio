#!/usr/bin/env python
"""Fix all test issues in events, social, and certificates apps."""

import re

def fix_file(filepath, replacements):
    """Apply replacements to a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    for old, new in replacements:
        content = content.replace(old, new)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Fixed {filepath}")
    else:
        print(f"- No changes needed in {filepath}")

print("=" * 60)
print("FIXING TEST ISSUES IN EVENTS, SOCIAL, CERTIFICATES")
print("=" * 60)

# Fix 1: Events tests - remove duplicate scheduled_for
print("\n1. Fixing events/tests.py...")
events_content = open('events/tests.py', 'r', encoding='utf-8').read()
# Remove duplicate scheduled_for lines
events_content = re.sub(
    r'(scheduled_for=timezone\.now\(\) \+ timedelta\(days=7\),)\s*scheduled_for=timezone\.now\(\) \+ timedelta\(days=7, hours=2\),',
    r'\1',
    events_content
)
with open('events/tests.py', 'w', encoding='utf-8') as f:
    f.write(events_content)
print("✓ Fixed events/tests.py - removed duplicate scheduled_for")

# Fix 2: Certificates tests - Module/Lesson use position not order
print("\n2. Fixing certificates/tests.py...")
fix_file('certificates/tests.py', [
    ('\n            order=', '\n            position='),
])

# Fix 3: Social tests - update Review.is_hidden to is_approved
print("\n3. Fixing social/views.py...")
fix_file('social/views.py', [
    ('is_hidden=False', 'is_approved=True'),
])

print("\n" + "=" * 60)
print("ALL FIXES APPLIED SUCCESSFULLY!")
print("=" * 60)
print("\nRun: python manage.py test events social certificates --keepdb")
