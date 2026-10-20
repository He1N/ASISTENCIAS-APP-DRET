from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Crea/sincroniza roles sin cuentas ni contraseñas predeterminadas.'
    def handle(self, *args, **options):
        app = Permission.objects.filter(content_type__app_label='control')
        admin, _ = Group.objects.get_or_create(name='Administrador')
        admin.permissions.set(app | Permission.objects.filter(content_type__app_label='auth'))
        operador, _ = Group.objects.get_or_create(name='Operador')
        allowed = {'view_trabajador', 'add_trabajador', 'change_trabajador', 'view_periodoasistencia', 'view_tipodocumento', 'view_tipooperacion'}
        allowed |= {'view_justificacion', 'add_justificacion', 'change_justificacion', 'importar_excel', 'exportar_resultados', 'view_loteimportacion'}
        operador.permissions.set(app.filter(codename__in=allowed))
        consulta, _ = Group.objects.get_or_create(name='Consulta')
        consulta.permissions.set(app.filter(codename__in=['view_justificacion', 'view_trabajador', 'view_periodoasistencia', 'view_tipodocumento', 'view_tipooperacion']))
        self.stdout.write(self.style.SUCCESS('Roles preparados; no se crearon usuarios. Consulta no exporta por defecto.'))
