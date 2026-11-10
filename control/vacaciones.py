"""Control de derechos confirmados e historial, separado de los periodos de asistencia."""
from decimal import Decimal
from datetime import date


def decimal(value):
    return Decimal(str(value or 0))


def detalle(cuenta):
    rows = []
    for m in cuenta.movimientos.all():
        rows.append(dict(pk=m.pk, periodo=m.periodo, codigo=m.codigo, fecha=m.fecha,
            inicio=m.inicio, fin=m.fin, dias=m.dias, permiso=m.permiso_ley,
            observaciones=m.observaciones, estado=m.estado, pendiente=m.pendiente_revision,
            origen=m.origen, justificacion=None))
    return sorted(rows, key=lambda r: (r['fecha'] or r['inicio'] or date.max,
                                      r['inicio'] or date.max, r['pk'] or 0))


def resumen(cuenta):
    rows = detalle(cuenta)
    total = sum((decimal(v) for v in cuenta.asignaciones.values() if v is not None), Decimal(0))
    used = sum((decimal(r['dias']) for r in rows if r['estado']=='VIGENTE'), Decimal(0))
    pending = total-used
    issues = []
    blockers = []
    if pending < 0:
        issues.append(f'Saldo negativo: {pending} días. El consumo supera las asignaciones registradas en {-pending} días.')
    if any(r['pendiente'] and r['estado']=='VIGENTE' for r in rows):
        issues.append('Movimientos del Excel pendientes de revisión (código o días)')
    if any(r['estado']=='VIGENTE' and (r['dias'] is None or r.get('duplicado')) for r in rows):
        blockers.append('Confirme los días o resuelva los posibles duplicados antes de exportar')
    remaining = {}
    consumption = used
    for year, assigned in sorted(cuenta.asignaciones.items()):
        amount = decimal(assigned)
        take = min(max(consumption, Decimal(0)), amount)
        remaining[year] = amount-take
        consumption -= take
    return dict(cuenta=cuenta, programado=total, usado=used, pendiente=pending,
                por_anio=remaining, incidencias=issues, bloqueos=blockers, filas=rows)
