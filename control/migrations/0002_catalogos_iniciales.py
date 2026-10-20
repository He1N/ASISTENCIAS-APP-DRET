from datetime import date
from django.db import migrations


def seed(apps, schema_editor):
    Documento = apps.get_model('control', 'TipoDocumento')
    for nombre, codigo in [('Papeleta de Permiso', '01'), ('Oficio', '03'), ('Memorandum', '04'), ('Informe', '05'), ('Carta', '06'), ('Solicitud', '07'), ('Otros', '09')]:
        Documento.objects.create(nombre=nombre, nombre_busqueda=nombre.casefold(), codigo_externo=codigo)
    Operacion = apps.get_model('control', 'TipoOperacion')
    for nombre, grupo in [('Vacaciones', 'VACACIONES'), ('Vacaciones 1/2 Jornada', 'VACACIONES'), ('Permiso Sindical', 'SINDICAL')]:
        Operacion.objects.create(nombre=nombre, nombre_busqueda=nombre.casefold(), grupo_especial=grupo, requiere_fecha_final=None)
    Periodo = apps.get_model('control', 'PeriodoAsistencia')
    Periodo.objects.create(titulo='Octubre 2026', fecha_inicio=date(2026, 9, 7), fecha_fin=date(2026, 10, 9))
    Periodo.objects.create(titulo='Noviembre 2026', fecha_inicio=date(2026, 10, 12), fecha_fin=None)


class Migration(migrations.Migration):
    dependencies = [('control', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
