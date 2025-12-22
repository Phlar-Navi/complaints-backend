import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'complaintsManager.settings')
django.setup()

from tenants.models import Tenant, Domain

print("\n" + "="*60)
print("DIAGNOSTIC DES TENANTS")
print("="*60)

tenants = Tenant.objects.all()
print(f"\n📊 Nombre total de tenants: {tenants.count()}\n")

for tenant in tenants:
    print(f"✓ Tenant: {tenant.name}")
    print(f"  Schema: {tenant.schema_name}")
    print(f"  ID: {tenant.id}")
    
    domains = Domain.objects.filter(tenant=tenant)
    if domains.exists():
        print(f"  Domaines:")
        for domain in domains:
            primary = "⭐ PRIMARY" if domain.is_primary else ""
            print(f"    - {domain.domain} {primary}")
    else:
        print(f"  ⚠️  Aucun domaine configuré!")
    print()

print("="*60)
print("\n💡 Pour que /api/dashboard/ fonctionne:")
print("   Le domaine doit correspondre exactement à celui utilisé dans le navigateur")
print("   Exemple: hopital_laquintinie.localhost\n")