#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Check if admin migration already exists
    cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'admin' AND name = '0001_initial'")
    exists = cursor.fetchone()[0]
    
    if exists == 0:
        # Insert if it doesn't exist
        cursor.execute("""
            INSERT INTO django_migrations (app, name, applied)
            VALUES ('admin', '0001_initial', NOW())
        """)
        connection.commit()
        print('Marked admin.0001_initial as applied')
    else:
        print('admin.0001_initial is already marked as applied')
