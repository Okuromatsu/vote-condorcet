from django.db import migrations

def update_site_domain(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    # We assume ID 1 is the default site created by Django
    if Site.objects.filter(id=1).exists():
        site = Site.objects.get(id=1)
        site.domain = 'vote-condorcet.com'
        site.name = 'Condorcet Vote'
        site.save()

def reverse_update(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    if Site.objects.filter(id=1).exists():
        site = Site.objects.get(id=1)
        site.domain = 'example.com'
        site.name = 'example.com'
        site.save()

class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0004_alter_votersession_unique_together_and_more'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(update_site_domain, reverse_update),
    ]
