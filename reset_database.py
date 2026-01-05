"""
Script to completely reset the database and migrations for a fresh start.
WARNING: This will delete ALL data and migration files!
"""
import os
import shutil
from pathlib import Path

# Apps to reset migrations for
APPS = [
    'accounts', 'ai_recommender', 'assessments',
    'certificates', 'core', 'courses', 'enrollments', 'events', 'exams',
    'instructors', 'live', 'payments', 'social', 'students'
]

def delete_migration_files():
    """Delete all migration files except __init__.py"""
    print("\n🗑️  Deleting migration files...")
    for app in APPS:
        migrations_dir = Path(app) / 'migrations'
        if migrations_dir.exists():
            for file in migrations_dir.glob('*.py'):
                if file.name != '__init__.py':
                    file.unlink()
                    print(f"   Deleted: {file}")
            for file in migrations_dir.glob('*.pyc'):
                file.unlink()
            # Delete __pycache__ in migrations
            pycache = migrations_dir / '__pycache__'
            if pycache.exists():
                shutil.rmtree(pycache)

def delete_db_file():
    """Delete SQLite database file if it exists"""
    db_file = Path('db.sqlite3')
    if db_file.exists():
        print(f"\n🗑️  Deleting database file: {db_file}")
        db_file.unlink()
        print("   Database deleted!")
    else:
        print("\n⚠️  No db.sqlite3 found (you might be using PostgreSQL/MySQL)")
        print("   You'll need to manually drop and recreate your database")

if __name__ == '__main__':
    print("=" * 60)
    print("DATABASE RESET SCRIPT")
    print("=" * 60)
    print("\n⚠️  WARNING: This will DELETE ALL DATA and migrations!")
    
    response = input("\nAre you sure you want to continue? (yes/no): ")
    
    if response.lower() == 'yes':
        delete_db_file()
        delete_migration_files()
        
        print("\n" + "=" * 60)
        print("✅ CLEANUP COMPLETE!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. python manage.py makemigrations")
        print("2. python manage.py migrate")
        print("3. python manage.py createsuperuser")
        print("\n")
    else:
        print("\n❌ Reset cancelled.")
