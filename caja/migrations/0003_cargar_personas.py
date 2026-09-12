from django.db import migrations

def cargar_personas(apps, schema_editor):
    Persona = apps.get_model('caja', 'Persona')
    for nombre in ['Diego', 'Tula', 'Rafa', 'Fede', 'Claudio', 'Puyo']:
        Persona.objects.get_or_create(nombre=nombre)

class Migration(migrations.Migration):
    dependencies = [
        ('caja', '0002_persona_alter_movimientocaja_descripcion_and_more'),
    ]
    operations = [
        migrations.RunPython(cargar_personas, migrations.RunPython.noop),
    ]