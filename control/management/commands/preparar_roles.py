from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Crea/sincroniza roles sin cuentas ni contraseñas predeterminadas.'
    def add_arguments(self, parser):
        parser.add_argument('--solo-vacaciones', action='store_true',
                            help='Agrega permisos del control nuevo sin reemplazar permisos existentes.')

    def handle(self, *args, **options):
        app = Permission.objects.filter(content_type__app_label='control')
        if options.get('solo_vacaciones'):
            nuevos = app.filter(content_type__model__in=['cuentavacacion','movimientovacacion'])
            for nombre in ['Administrador','Operador','Consulta']:
                grupo, _ = Group.objects.get_or_create(name=nombre)
                permisos = nuevos if nombre == 'Administrador' else nuevos.filter(codename__startswith='view_')
                grupo.permissions.add(*permisos)
            self.stdout.write(self.style.SUCCESS('Permisos de vacaciones agregados; se conservaron los permisos anteriores.'))
            return
        admin, _ = Group.objects.get_or_create(name='Administrador')
        admin.permissions.set(app | Permission.objects.filter(content_type__app_label='auth'))
        operador, _ = Group.objects.get_or_create(name='Operador')
        allowed = {'view_trabajador', 'add_trabajador', 'change_trabajador', 'view_periodoasistencia', 'view_tipodocumento', 'view_tipooperacion'}
        allowed |= {'view_justificacion', 'add_justificacion', 'change_justificacion', 'importar_excel', 'exportar_resultados', 'view_loteimportacion'}
        allowed |= {'view_cuentavacacion', 'view_movimientovacacion'}
        operador.permissions.set(app.filter(codename__in=allowed))
        consulta, _ = Group.objects.get_or_create(name='Consulta')
        consulta.permissions.set(app.filter(codename__in=['view_justificacion', 'view_trabajador', 'view_periodoasistencia', 'view_tipodocumento', 'view_tipooperacion']))
        consulta.permissions.add(*app.filter(codename__in=['view_cuentavacacion','view_movimientovacacion']))
        self.stdout.write(self.style.SUCCESS('Roles preparados; no se crearon usuarios. Consulta no exporta por defecto.'))
