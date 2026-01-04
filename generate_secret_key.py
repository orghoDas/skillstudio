"""
Generate a new Django SECRET_KEY for production
Run this and copy the output to Railway environment variables
"""

from django.core.management.utils import get_random_secret_key

if __name__ == "__main__":
    secret_key = get_random_secret_key()
    print("\n" + "="*60)
    print("Your new Django SECRET_KEY:")
    print("="*60)
    print(secret_key)
    print("="*60)
    print("\nCopy this key and add it to Railway as DJANGO_SECRET_KEY")
    print("="*60 + "\n")
