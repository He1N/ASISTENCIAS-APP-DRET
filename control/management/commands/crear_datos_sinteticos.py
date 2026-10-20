from django.core.management.base import BaseCommand
from control.models import Trabajador
class Command(BaseCommand):
    help = 'Crea tres fichas explícitamente ficticias; no crea cuentas.'
    def handle(self, *args, **options):
        for n in range(1, 4):
            Trabajador.objects.get_or_create(apellidos_nombres=f'PRUEBA FICTICIA {n}', defaults={'area':'Área de prueba'})
        self.stdout.write('Datos sintéticos preparados.')
