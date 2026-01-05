import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')
django.setup()

from django.db import connection
cur = connection.cursor()
engine = connection.settings_dict['ENGINE']
print('DB engine:', engine)
if 'sqlite' in engine:
    cur.execute("PRAGMA table_info(accounts_profile);")
    rows = cur.fetchall()
    print('columns:', rows)
else:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='accounts_profile';")
    rows = cur.fetchall()
    print('columns:', rows)
