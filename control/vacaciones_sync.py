"""Enlace transaccional e idempotente entre Consultas y el control vacacional."""
from decimal import Decimal
from django.db import transaction
from .audit import registrar, snapshot
from .models import CuentaVacacion, EnlaceVacacion, Justificacion, MovimientoVacacion, Trabajador, normalizar


def cantidad(j):
    code=j.tipo_operacion.codigo_externo
    if not j.fecha_movimiento:
        return None, 'Falta la fecha de movimiento; no se inventan días ni fechas.'
    if code=='32':
        if j.fecha_final and j.fecha_final!=j.fecha_movimiento:
            return None, 'Media jornada con varias fechas: requiere confirmar el consumo; no se multiplica automáticamente.'
        return Decimal('.5'), ''
    if code=='05' and j.duracion:
        return Decimal(j.duracion), ''
    return None, 'Falta fecha final válida o el código vacacional no tiene una regla de descuento confirmada.'


def cuenta_para(j):
    worker=j.trabajador
    linked=CuentaVacacion.objects.filter(trabajador=worker).first()
    if linked:
        if linked.eliminada: return None, 'La ficha vacacional vinculada está eliminada; revise antes de descontar.'
        if worker.dni and linked.dni!=worker.dni:
            return None, 'El DNI de Consultas difiere del DNI de la ficha vinculada.'
        return linked, ''
    if worker.dni:
        # Un DNI compartido por varias fichas de asistencias necesita revisión.
        if Trabajador.objects.filter(dni=worker.dni).exclude(pk=worker.pk).exists():
            return None, 'El DNI está repetido en trabajadores; no se eligió una persona automáticamente.'
        account=CuentaVacacion.objects.filter(dni=worker.dni).first()
        if account:
            if account.eliminada or account.trabajador_id not in (None,worker.pk):
                return None, 'La ficha por DNI está eliminada o pertenece a otro trabajador.'
            return account, ''
    matches=[c for c in CuentaVacacion.objects.filter(eliminada=False)
             if normalizar(c.nombre)==normalizar(worker.apellidos_nombres)]
    if len(matches)==1:
        c=matches[0]
        homonyms=Trabajador.objects.filter(nombre_busqueda=worker.nombre_busqueda).exclude(pk=worker.pk).exists()
        if homonyms or c.trabajador_id not in (None,worker.pk) or worker.dni and c.dni!=worker.dni:
            return None, 'Coincidencia de nombre con identidad ambigua o DNI distinto; requiere revisión.'
        return c, ''
    if matches: return None, 'Hay varias fichas con el mismo nombre; requiere revisión.'
    if not worker.dni: return None, 'No hay ficha vacacional inequívoca ni DNI para crearla; complete la identidad y vuelva a guardar.'
    return None, ''  # Crear una ficha sin asignaciones; nunca conceder derechos.


def equivalentes(j,account,days):
    return [m for m in account.movimientos.all() if m.inicio==j.fecha_movimiento
        and (m.fin or (m.inicio if j.tipo_operacion.codigo_externo=='32' else None))==(j.fecha_final or j.fecha_movimiento)
        and m.dias==days and m.codigo in ({'05','32'} if days==Decimal('.5') else {'05'})
        and normalizar(m.observaciones)==normalizar(j.observaciones)]


def plan_historico(j):
    existing=EnlaceVacacion.objects.filter(justificacion=j).first()
    if existing:
        return dict(cuenta=existing.cuenta,movimiento=existing.movimiento,estado=existing.estado,observaciones=existing.observaciones)
    account,error=cuenta_para(j)
    days,day_error=cantidad(j)
    result=dict(cuenta=account,movimiento=None,estado='EXCEPCION',observaciones=error or day_error)
    if result['observaciones']:
        result['observaciones']+=f' Observación original de Consultas: {j.observaciones or "sin observaciones"}'
        return result
    if account is None:
        result['observaciones']='No existe ficha del control; requiere revisión del histórico.'
        return result
    matches=equivalentes(j,account,days)
    if len(matches)==1 and matches[0].estado=='VIGENTE' and not EnlaceVacacion.objects.filter(movimiento=matches[0]).exists():
        result.update(movimiento=matches[0],estado='SINCRONIZADO',observaciones='Movimiento histórico equivalente enlazado sin duplicar ni cambiar su consumo.')
    elif matches and any(m.estado!='VIGENTE' for m in matches):
        result['observaciones']='El consumo equivalente fue anulado o cancelado en el control. Se conserva ese ajuste; no se reactiva automáticamente.'
    else:
        result['observaciones']='Las fechas, cantidades o registros solapados difieren entre Consultas y el control. Se conserva el control sin añadir otro consumo. Revisión pendiente.'
    if result['estado']=='EXCEPCION':
        def fmt(d): return d.strftime('%d/%m/%Y') if d else 'sin fecha'
        result['observaciones']+=f' Consultas: {fmt(j.fecha_movimiento)} al {fmt(j.fecha_final)}, {days} días; {j.observaciones}.'
        candidates=[m for m in account.movimientos.all() if m.codigo in {'05','32'} and m.inicio and j.fecha_movimiento
            and m.inicio<=(j.fecha_final or j.fecha_movimiento) and (m.fin or m.inicio)>=j.fecha_movimiento]
        for m in candidates[:5]:
            result['observaciones']+=f' Control, movimiento {m.pk}: {fmt(m.inicio)} al {fmt(m.fin)}, {m.dias} días, {m.estado}; {m.observaciones}.'
    return result


def guardar_enlace(link,user,before):
    now=snapshot(link)
    if before is None or any(before.get(k)!=v for k,v in now.items() if k not in {'id','created_at','updated_at'}):
        link.save()
        if user: registrar(link,user,'sincronizar_vacaciones',before)
    return link


@transaction.atomic
def sincronizar(j,historico=False,usuario=None):
    # Recargar evita actuar sobre valores que no se incluyeron en update_fields.
    j=Justificacion.objects.select_related('trabajador','tipo_operacion').get(pk=j.pk)
    link=EnlaceVacacion.objects.select_for_update().filter(justificacion=j).first()
    vacation=j.tipo_operacion.grupo_especial=='VACACIONES'
    if not vacation and not link: return None
    actor=usuario or j.updated_by or j.created_by
    before=snapshot(link) if link else None
    if link and link.estado=='EXCEPCION': return link  # decisión histórica explícita
    if historico:
        if link: return link
        plan=plan_historico(j)
        link=EnlaceVacacion(justificacion=j,**plan)
        return guardar_enlace(link,actor,None)
    if link is None: link=EnlaceVacacion(justificacion=j)
    # Serializar altas de una misma persona y movimientos entre dos fichas.
    worker_ids={j.trabajador_id}
    if link.cuenta_id and link.cuenta.trabajador_id: worker_ids.add(link.cuenta.trabajador_id)
    list(Trabajador.objects.select_for_update().filter(pk__in=worker_ids).order_by('pk'))
    if not vacation or j.anulada:
        if link.movimiento_id:
            m=MovimientoVacacion.objects.select_for_update().get(pk=link.movimiento_id)
            if m.estado!='ANULADO':
                prior=snapshot(m);m.estado='ANULADO';m.motivo='Anulación o cambio de operación en Consultas';m.save()
                if actor: registrar(m,actor,'sincronizar_vacaciones',prior)
        link.estado='INACTIVO';link.observaciones='Sin descuento: justificación anulada o ya no es una operación vacacional.'
        return guardar_enlace(link,actor,before)
    account,error=cuenta_para(j)
    days,day_error=cantidad(j)
    if error or day_error:
        # Una edición incompleta nunca conserva un descuento antiguo como vigente.
        if link.movimiento_id:
            m=link.movimiento;prior=snapshot(m);m.estado='ANULADO';m.motivo='Sincronización pendiente de datos válidos';m.save()
            if actor: registrar(m,actor,'sincronizar_vacaciones',prior)
        if account: link.cuenta=account
        link.estado='PENDIENTE';link.observaciones=error or day_error
        return guardar_enlace(link,actor,before)
    if account is None:
        account=CuentaVacacion.objects.create(trabajador=j.trabajador,dni=j.trabajador.dni,
            nombre=j.trabajador.apellidos_nombres,regimen_laboral=j.trabajador.regimen_laboral,
            asignaciones={},notas='Creada desde Consultas sin asignaciones automáticas.')
        if actor: registrar(account,actor,'crear_desde_consultas')
    ids={account.pk}
    if link.cuenta_id: ids.add(link.cuenta_id)
    list(CuentaVacacion.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    if account.trabajador_id is None:
        prior=snapshot(account);account.trabajador=j.trabajador;account.save(update_fields=['trabajador','updated_at'])
        if actor: registrar(account,actor,'vincular_trabajador',prior)
    if not link.movimiento_id:
        # Al importar o registrar algo ya presente, no sumar dos veces el mismo
        # documento. Los casos ambiguos se exponen para revisión.
        matches=equivalentes(j,account,days)
        available=[m for m in matches if m.estado=='VIGENTE' and not EnlaceVacacion.objects.filter(movimiento=m).exists()]
        if len(matches)==1 and len(available)==1:
            link.movimiento=available[0]
        elif matches:
            link.cuenta=account;link.estado='PENDIENTE'
            link.observaciones='Existe un consumo equivalente enlazado, anulado o ambiguo. No se descontó otra vez; revise posible duplicado.'
            return guardar_enlace(link,actor,before)
    m=link.movimiento if link.movimiento_id else MovimientoVacacion()
    prior=snapshot(m) if m.pk else None
    values=dict(cuenta_id=account.pk,periodo=m.periodo if m.pk else str(j.fecha_movimiento.year),codigo=j.tipo_operacion.codigo_externo,
        fecha=j.fecha_movimiento,inicio=j.fecha_movimiento,fin=j.fecha_final or j.fecha_movimiento,dias=days,
        estado='VIGENTE',observaciones=j.observaciones,pendiente_revision=False)
    if prior is None or any(getattr(m,k)!=v for k,v in values.items()):
        for k,v in values.items(): setattr(m,k,v)
        m.motivo=f'Sincronizado desde Consultas, registro {j.pk}'
        if not m.pk: m.origen_clave=f'asistencia:{j.pk}';m.origen={'justificacion_id':j.pk}
        m.save()
        if actor: registrar(m,actor,'sincronizar_vacaciones',prior)
    link.movimiento=m;link.cuenta=account;link.estado='SINCRONIZADO'
    link.observaciones='El movimiento se actualiza desde Consultas; anular la justificación devuelve los días.'
    return guardar_enlace(link,actor,before)
