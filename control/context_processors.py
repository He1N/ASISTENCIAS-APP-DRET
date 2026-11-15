"""Avisos actuales, calculados con los mismos consumos del control vacacional."""
from decimal import Decimal
from django.db.models import Q, Sum
from .models import CuentaVacacion


def notificaciones_vacaciones(request):
    if not getattr(request,'user',None) or not request.user.is_authenticated or not request.user.has_perm('control.view_cuentavacacion'):
        return {}
    avisos=[]
    cuentas=CuentaVacacion.objects.filter(eliminada=False).annotate(
        consumo_notificacion=Sum('movimientos__dias',filter=Q(movimientos__estado='VIGENTE') & ~Q(movimientos__codigo='09'))
    ).order_by('nombre','pk')
    for cuenta in cuentas:
        programado=sum((Decimal(str(v)) for v in cuenta.asignaciones.values() if v is not None),Decimal(0))
        saldo=programado-(cuenta.consumo_notificacion or Decimal(0))
        if saldo<0:
            avisos.append(dict(cuenta=cuenta,pendiente=saldo))
    return {'notificaciones_vacaciones':avisos}
