"""Reglas compartidas por las pantallas web y Django Admin."""
from django.utils import timezone
from .models import PeriodoAsistencia


def preparar_fechas_estado(obj):
    # Conservar las fechas históricas también al reabrir, como en fase 1.
    if isinstance(obj, PeriodoAsistencia):
        if obj.estado in ('CERRADO', 'PROCESADO') and not obj.fecha_cierre:
            obj.fecha_cierre = timezone.now()
        if obj.estado == 'PROCESADO' and not obj.fecha_procesamiento:
            obj.fecha_procesamiento = timezone.now()


def filtrar_periodos(qs, data):
    from django.db.models import Q
    if data.get('q'):
        qs = qs.filter(Q(titulo__icontains=data['q']) | Q(notas__icontains=data['q']))
    if data.get('estado'):
        qs = qs.filter(estado=data['estado'])
    return qs
