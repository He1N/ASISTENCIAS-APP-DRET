"""Control de derechos confirmados e historial, separado de los periodos de asistencia."""
from decimal import Decimal
from datetime import date


def decimal(value):
    return Decimal(str(value or 0))


def cantidad_ley(movimiento):
    # El Excel separa días vacacionales y permiso de ley en dos columnas.
    return movimiento.permiso_ley if movimiento.permiso_ley else movimiento.dias


def saldo_ley276_anual(cuenta, anio):
    asignado = Decimal(3)
    usado = Decimal(0)
    permisos = []
    for fila in detalle(cuenta):
        if fila['codigo'] != '09':
            continue
        fecha = fila['inicio'] or fila['fin'] or fila['fecha']
        descuento = Decimal(0)
        if fila['estado'] == 'VIGENTE' and fecha and fecha.year == anio:
            descuento = decimal(fila['dias_ley'])
        fila['descontado'] = descuento
        usado += descuento
        permisos.append(fila)
    return dict(programado=asignado, usado=usado, pendiente=asignado-usado, movimientos=permisos)


def detalle(cuenta):
    rows = []
    for m in cuenta.movimientos.all():
        rows.append(dict(pk=m.pk, periodo=m.periodo, codigo=m.codigo, fecha=m.fecha, cud=m.cud,
            inicio=m.inicio, fin=m.fin, dias=m.dias, permiso=m.permiso_ley,
            observaciones=m.observaciones, estado=m.estado, pendiente=m.pendiente_revision,
            origen=m.origen, justificacion=None, dias_ley=cantidad_ley(m) if m.codigo=='09' else None))
    return sorted(rows, key=lambda r: (r['fecha'] or r['inicio'] or date.max,
                                      r['inicio'] or date.max, r['pk'] or 0))


def asignacion_ley276_automatica(cuenta):
    return Decimal(3)*sum(str(y).isdigit() and v is not None and decimal(v)>0 for y,v in cuenta.asignaciones.items())


def resumen(cuenta):
    rows = detalle(cuenta)
    total = sum((decimal(v) for v in cuenta.asignaciones.values() if v is not None), Decimal(0))
    used = sum((decimal(r['dias']) for r in rows if r['estado']=='VIGENTE' and r['codigo']!='09'), Decimal(0))
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
    from .regimenes import normalizar_regimen
    ley=None
    if normalizar_regimen(cuenta.regimen_laboral)=='DEC. LEG. 276':
        anios=[y for y,v in cuenta.asignaciones.items() if str(y).isdigit() and v is not None and decimal(v)>0]
        manual=getattr(cuenta,'asignacion_ley276',None)
        asignado=asignacion_ley276_automatica(cuenta) if manual is None else decimal(manual)
        permisos=[r for r in rows if r['codigo']=='09' and r['estado']=='VIGENTE']
        usado=sum((decimal(r['dias_ley']) for r in permisos),Decimal(0))
        ley=dict(programado=asignado,usado=usado,pendiente=asignado-usado,anios=anios)
    return dict(ley_276=ley,cuenta=cuenta, programado=total, usado=used, pendiente=pending,
                por_anio=remaining, incidencias=issues, bloqueos=blockers, filas=rows)
