"""
Drop all tables from the PostgreSQL database for a complete reset.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')
django.setup()

from django.db import connection

def drop_all_tables():
    """Drop all tables in the database"""
    with connection.cursor() as cursor:
        # Get all table names
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        tables = cursor.fetchall()
        
        if not tables:
            print("No tables found in the database.")
            return
        
        print(f"\n🗑️  Found {len(tables)} tables to drop:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Drop all tables
        print("\n🔥 Dropping all tables...")
        cursor.execute("DROP SCHEMA public CASCADE;")
        cursor.execute("CREATE SCHEMA public;")
        cursor.execute("GRANT ALL ON SCHEMA public TO public;")
        
        print("✅ All tables dropped successfully!")
        print("\nNext steps:")
        print("1. python manage.py migrate")
        print("2. python manage.py createsuperuser")

if __name__ == '__main__':
    print("=" * 60)
    print("DROP ALL TABLES")
    print("=" * 60)
    print("\n⚠️  WARNING: This will DELETE ALL TABLES and DATA!")
    
    response = input("\nAre you absolutely sure? Type 'DROP ALL' to confirm: ")
    
    if response == 'DROP ALL':
        drop_all_tables()
    else:
        print("\n❌ Operation cancelled.")
