#!/usr/bin/env python
"""Fix all test issues in one go."""

import re

def fix_file(filepath, replacements):
    """Apply replacements to a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed {filepath}")

# Fix certificates/tests.py - remove escaped quotes
fix_file('certificates/tests.py', [
    (r'\"\"\"', '"""'),
])

# Fix events/tests.py - update field names to match current model
fix_file('events/tests.py', [
    ('start_time', 'scheduled_for'),
    ('end_time', 'scheduled_for'),  # Use same field for both
    ('total_seats', 'max_seats'),
    ('organizer', 'host'),
    ('student', 'user'),  # Enrollment.student -> Enrollment.user
])

# Fix social/tests.py - update field names
fix_file('social/tests.py', [
    ("Forum.objects.create(\n            name=", "Forum.objects.create(\n            title="),
    ("Forum.objects.create(\n                name=", "Forum.objects.create(\n                title="),
])

print("\nAll fixes applied!")
