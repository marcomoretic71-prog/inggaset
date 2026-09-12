from django.db import migrations

def cargar_personas(apps, schema_editor):
    Persona = apps.get_model('caja', 'Persona')
    nombres = ['Diego', 'Tula', 'Rafa', 'Fede', 'Claudio', 'Puyo']
    for nombre in nombres:
        Persona.objects.get_or_create(nombre=nombre)

class Migration(migrations.Migration):

    dependencies = [
        ('caja', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(cargar_personas),
    ]