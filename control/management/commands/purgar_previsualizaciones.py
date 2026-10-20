from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from control.models import LoteImportacion

class Command(BaseCommand):
    help = 'Purga datos temporales de revisiones pendientes de más de 24 horas.'
    def handle(self, *args, **options):
        count = LoteImportacion.objects.filter(estado__in=['SELECCION','PREVIA'], fecha__lt=timezone.now()-timedelta(hours=24)).update(datos_temporales={}, estado='EXPIRADO')
        self.stdout.write(f'Previsualizaciones purgadas: {count}')
