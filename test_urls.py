import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'complaintsManager.settings')
django.setup()

from django.urls import get_resolver
from django.conf import settings

print("\n" + "="*60)
print("ANALYSE DES URLS")
print("="*60)

# Afficher ROOT_URLCONF
print(f"\nROOT_URLCONF: {settings.ROOT_URLCONF}")
print(f"PUBLIC_SCHEMA_URLCONF: {getattr(settings, 'PUBLIC_SCHEMA_URLCONF', 'Non défini')}")

# Récupérer toutes les URLs
resolver = get_resolver()

print("\n📋 URLs disponibles contenant 'dashboard':\n")

def show_urls(urlpatterns, prefix=''):
    for pattern in urlpatterns:
        if hasattr(pattern, 'url_patterns'):
            # C'est un include
            show_urls(pattern.url_patterns, prefix + str(pattern.pattern))
        else:
            full_pattern = prefix + str(pattern.pattern)
            if 'dashboard' in full_pattern.lower():
                name = pattern.name if hasattr(pattern, 'name') else 'No name'
                print(f"  ✓ {full_pattern}")
                print(f"    → Name: {name}")
                if hasattr(pattern, 'callback'):
                    print(f"    → View: {pattern.callback}")
                print()

show_urls(resolver.url_patterns)

print("="*60)