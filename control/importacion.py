"""Previsualización revisable y confirmación transaccional de históricos."""
import hashlib
import json
import uuid
from datetime import date, datetime, time, timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .audit import registrar
from .models import (Trabajador, TipoDocumento, TipoOperacion, Justificacion,
                     LoteImportacion, IncidenciaImportacion, HistorialCambio, PeriodoAsistencia, normalizar)
from .xlsx_parser import transformar

ESTADOS_FINALES = ('CONFIRMADO', 'ANULADO')


class ErrorImportacion(ValueError):
    pass


def octubre_historico(periodo):
    # Identifica el corte administrativo: no usa el mes del movimiento.
    return periodo.fecha_inicio == date(2026, 9, 7) and periodo.fecha_fin == date(2026, 10, 9)


def vigente(lote):
    expira = lote.datos_temporales.get('expira')
    if expira and datetime.fromisoformat(expira) > timezone.now():
        return True
    return False


def crear_borrador(parsed, nombre, periodo, user):
    return LoteImportacion.objects.create(archivo_nombre=nombre[:255], checksum=parsed['checksum'],
        periodo=periodo, usuario=user, hoja='PENDIENTE-' + uuid.uuid4().hex,
        estado='SELECCION', datos_temporales={'hojas': parsed['hojas'],
            'expira': (timezone.now() + timedelta(hours=24)).isoformat()})


@transaction.atomic
def seleccionar_hoja(lote_id, hoja, conservar_cud=True):
    lote = LoteImportacion.objects.select_for_update().get(pk=lote_id)
    if lote.estado != 'SELECCION' or not vigente(lote):
        raise ErrorImportacion('La selección ya no está disponible. Vuelva a cargar el archivo.')
    lote.periodo = PeriodoAsistencia.objects.select_for_update().get(pk=lote.periodo_id)
    source = lote.datos_temporales.get('hojas', {}).get(hoja)
    if not source or not source.get('filas'):
        raise ErrorImportacion('Seleccione una hoja de registros válida.')
    anterior = LoteImportacion.objects.filter(checksum=lote.checksum, hoja=hoja, periodo=lote.periodo).exclude(pk=lote.pk).first()
    if anterior:
        expira = lote.datos_temporales['expira']
        lote.estado = 'CANCELADO'; lote.datos_temporales = {}; lote.save()
        if anterior.usuario_id != lote.usuario_id or anterior.estado in ESTADOS_FINALES or anterior.justificacion_set.exists():
            return anterior
        if anterior.estado == 'PREVIA' and vigente(anterior):
            return anterior
        lote = anterior
        lote.fecha = timezone.now()
        lote.datos_temporales = {'expira': expira}
    omitir = octubre_historico(lote.periodo) or not conservar_cud
    lote.hoja, lote.estado = hoja, 'PREVIA'
    lote.total_leidos = len(source['filas'])
    lote.reglas_aplicadas = ['cud_omitido_por_desalineacion_octubre'] if octubre_historico(lote.periodo) else ([] if conservar_cud else ['cud_omitido_por_seleccion'])
    # Descartar completamente CUD de octubre también de los datos de la previa.
    if omitir:
        for fila in source['filas']:
            fila['raw'].pop('cud', None)
    lote.datos_temporales = {'filas': source['filas'], 'mapeo': source['mapeo'],
        'expira': lote.datos_temporales['expira'], 'resoluciones': {}, 'omitir_cud': omitir,
        'revision': uuid.uuid4().hex}
    lote.save()
    return lote


def candidatos_trabajador(nombre, dni):
    q = Q(nombre_busqueda=normalizar(nombre))
    if dni:
        q |= Q(dni=dni)
    return list(Trabajador.objects.filter(q).order_by('-activo', 'pk')[:50])


def candidatos_catalogo(model, data):
    q = Q(nombre_busqueda=normalizar(data['nombre']))
    if data['codigo']:
        q |= Q(codigo_externo=data['codigo'])
    return list(model.objects.filter(q).order_by('-activo', 'pk')[:50])


def representar(obj):
    if isinstance(obj, Trabajador):
        label = f'#{obj.pk} {obj.apellidos_nombres} · DNI {obj.dni or "sin registrar"}'
    else:
        label = f'#{obj.pk} {obj}'
    return {'id': str(obj.pk), 'label': label + (' · Inactivo' if not obj.activo else ''),
            'version': obj.updated_at.isoformat()}


def firma(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def datos_registro(obj):
    return {k: str(getattr(obj, k)) if getattr(obj, k) is not None else None for k in
        ('periodo_id', 'trabajador_id', 'tipo_documento_id', 'tipo_operacion_id', 'fecha_movimiento',
         'fecha_final', 'hora_salida', 'hora_retorno', 'cud', 'observaciones')}


def preparar_plan(lote, resoluciones=None, permitir_incompletos=False):
    if lote.estado != 'PREVIA' or not vigente(lote):
        raise ErrorImportacion('La previsualización caducó o ya fue confirmada. Vuelva a cargar el archivo.')
    resoluciones = resoluciones if resoluciones is not None else lote.datos_temporales.get('resoluciones', {})
    filas, fingerprints, total = [], set(), {'listas': 0, 'omitidas': 0, 'duplicadas': 0, 'errores': 0, 'incompletas': 0}
    for row in lote.datos_temporales['filas']:
        v = transformar(row, lote.datos_temporales['omitir_cud'])
        issues = v['issues']
        rownum = row['fila']; choices = resoluciones.get(str(rownum), {})
        selected = {}; listas = {}
        candidates = candidatos_trabajador(v['nombre'], v['dni'])
        for key, model, options in [('trabajador', Trabajador, candidates),
                ('documento', TipoDocumento, candidatos_catalogo(TipoDocumento, v['documento'])),
                ('operacion', TipoOperacion, candidatos_catalogo(TipoOperacion, v['operacion']))]:
            lists = [representar(o) for o in options]
            elegido = choices.get(key)
            if elegido == 'nuevo' and key == 'trabajador':
                # La elección explícita autoriza otro homónimo, nunca fusiona fichas.
                selected[key] = 'nuevo'
            elif elegido and str(elegido).isdigit():
                obj = model.objects.filter(pk=elegido).first()
                if obj:
                    selected[key] = obj
                    distinto = (obj.nombre_busqueda != normalizar(v['nombre']) or (v['dni'] and obj.dni != v['dni'])) if key == 'trabajador' else (obj.nombre_busqueda != normalizar(v[key]['nombre']) or (v[key]['codigo'] and obj.codigo_externo != v[key]['codigo']))
                    if distinto:
                        original = {'nombre': v['nombre'], 'dni': v['dni']} if key == 'trabajador' else v[key]
                        issues.append({'campo': key, 'mensaje': 'Asignación manual distinta del origen; se conserva la discrepancia como incidencia.', 'severidad': 'ALERTA', 'original': json.dumps(original, ensure_ascii=False)[:250]})
                    if str(obj.pk) not in [x['id'] for x in lists]:
                        lists.insert(0, representar(obj))
            elif not elegido:
                exactos = []
                for obj in options:
                    if key == 'trabajador':
                        exacto = obj.nombre_busqueda == normalizar(v['nombre']) and (not v['dni'] or obj.dni == v['dni'])
                    else:
                        data = v[key]
                        exacto = obj.nombre_busqueda == normalizar(data['nombre']) and (not data['codigo'] or obj.codigo_externo == data['codigo'])
                    if exacto: exactos.append(obj)
                if len(options) == 1 and len(exactos) == 1:
                    selected[key] = exactos[0]
                elif key == 'trabajador' and not options:
                    selected[key] = 'nuevo'
            if key == 'trabajador':
                lists.append({'id': 'nuevo', 'label': 'Crear ficha nueva con el nombre de origen', 'version': ''})
            listas[key] = lists
            if key not in selected:
                issues.append({'campo': key, 'mensaje': 'Coincidencia pendiente: elija una ficha existente o cree/revise el catálogo y vuelva a revisar.', 'severidad': 'ERROR', 'original': ''})
        trabajador = selected.get('trabajador')
        if trabajador == 'nuevo':
            try:
                Trabajador(apellidos_nombres=v['nombre'], dni=v['dni']).full_clean()
            except ValidationError:
                issues.append({'campo': 'trabajador', 'mensaje': 'El nombre o DNI supera los límites del modelo.', 'severidad': 'ERROR', 'original': ''})
        op = selected.get('operacion')
        incompleto = not v['fecha_movimiento']
        if op:
            if op.requiere_fecha_final is None:
                incompleto = True
                issues.append({'campo': 'operacion', 'mensaje': 'Regla de fecha final pendiente; no se interpreta como No.', 'severidad': 'ALERTA', 'original': ''})
            elif op.requiere_fecha_final and not v['fecha_final']:
                incompleto = True
                issues.append({'campo': 'final', 'mensaje': 'Falta fecha final requerida: legado incompleto.', 'severidad': 'ALERTA', 'original': ''})
        fecha = date.fromisoformat(v['fecha_movimiento']) if v['fecha_movimiento'] else None
        if fecha and (fecha < lote.periodo.fecha_inicio or (lote.periodo.fecha_fin and fecha > lote.periodo.fecha_fin)):
            issues.append({'campo': 'periodo', 'mensaje': 'Movimiento fuera del rango: confirme la excepción con motivo.', 'severidad': 'ALERTA', 'original': ''})
            if not choices.get('motivo'):
                issues.append({'campo': 'periodo', 'mensaje': 'Falta motivo de excepción de rango.', 'severidad': 'ERROR', 'original': ''})
        if v.get('item') and len(v['item']) > 40:
            issues.append({'campo': 'item', 'mensaje': 'El ítem supera 40 caracteres; corrija el archivo.', 'severidad': 'ERROR', 'original': v['item'][:100]})
        duplicados = []
        if trabajador and trabajador != 'nuevo':
            duplicados = list(Justificacion.objects.filter(periodo=lote.periodo, trabajador=trabajador,
                fecha_movimiento=fecha).order_by('pk').values_list('pk', flat=True)[:20])
        identidad = {k: v[k] for k in v if k not in ('issues', 'item')}
        identidad['nombre'] = normalizar(v['nombre'])
        for key in ('documento', 'operacion'):
            identidad[key] = {'nombre': normalizar(v[key]['nombre']), 'codigo': v[key]['codigo']}
        identidad['elegidos'] = {k: 'nuevo' if obj == 'nuevo' else str(obj.pk) for k, obj in selected.items()}
        huella = firma(identidad)
        repetida = huella in fingerprints
        fingerprints.add(huella)
        posible = bool(duplicados or repetida)
        if posible:
            total['duplicadas'] += 1
            issues.append({'campo': 'duplicado', 'mensaje': 'Posible duplicado: revise y confirme expresamente o deje la fila omitida.', 'severidad': 'ALERTA', 'original': ''})
        accion = choices.get('accion', 'omitir' if posible else 'importar')
        error = any(i['severidad'] == 'ERROR' for i in issues)
        importar = accion in ('importar', 'confirmar_duplicado') and not error and (not incompleto or permitir_incompletos)
        if posible and accion != 'confirmar_duplicado': importar = False
        if not importar and accion == 'omitir':
            issues.append({'campo': 'decision', 'mensaje': 'Fila omitida por decisión de revisión.', 'severidad': 'ALERTA', 'original': ''})
        if error: total['errores'] += 1
        if incompleto: total['incompletas'] += 1
        total['listas' if importar else 'omitidas'] += 1
        visual = {k: date.fromisoformat(v[k]).strftime('%d/%m/%Y') if v[k] else None for k in ('fecha_movimiento', 'fecha_final')}
        visual.update({k: time.fromisoformat(v[k]).strftime('%H:%M') if v[k] else None for k in ('hora_salida', 'hora_retorno')})
        filas.append({'fila': rownum, 'valores': v, 'visual': visual, 'listas': listas,
            'elegidos': {k: 'nuevo' if obj == 'nuevo' else str(obj.pk) for k, obj in selected.items()},
            'versiones': {k: obj.updated_at.isoformat() for k, obj in selected.items() if obj != 'nuevo'},
            'issues': issues, 'importar': importar, 'incompleto': incompleto, 'duplicados': duplicados,
            'posible_duplicado': posible, 'accion': accion, 'motivo': choices.get('motivo', ''), 'huella': huella})
    signature = firma({'filas': filas, 'periodo': lote.periodo.updated_at.isoformat(), 'totales': total})
    return {'filas': filas, 'totales': total, 'firma': signature}


@transaction.atomic
def revisar(lote_id, resoluciones, permitir_incompletos):
    lote = LoteImportacion.objects.select_for_update().select_related('periodo').get(pk=lote_id)
    plan = preparar_plan(lote, resoluciones, permitir_incompletos)
    lote.datos_temporales.update(resoluciones=resoluciones, permitir_incompletos=permitir_incompletos,
        firma=plan['firma'], revision=uuid.uuid4().hex)
    lote.save(update_fields=['datos_temporales'])
    return lote, plan


@transaction.atomic
def confirmar(lote_id, user, revision):
    lote = LoteImportacion.objects.select_for_update().select_related('periodo').get(pk=lote_id)
    if lote.estado in ESTADOS_FINALES:
        return lote  # Confirmación repetida idempotente; nunca vuelve a insertar.
    if lote.datos_temporales.get('revision') != revision:
        raise ErrorImportacion('La revisión cambió. Recargue antes de confirmar.')
    plan = preparar_plan(lote, permitir_incompletos=lote.datos_temporales.get('permitir_incompletos', False))
    if lote.datos_temporales.get('firma') != plan['firma']:
        raise ErrorImportacion('Cambió un catálogo, periodo o coincidencia. Pulse Revisar decisiones antes de confirmar.')
    if not plan['totales']['listas']:
        raise ErrorImportacion('No hay filas listas para importar. Revise las incidencias y decisiones.')
    nuevos = {}
    for row in plan['filas']:
        v = row['valores']
        for issue in row['issues']:
            IncidenciaImportacion.objects.create(lote=lote, fila=row['fila'], campo=issue['campo'],
                mensaje=issue['mensaje'], severidad=issue['severidad'], valor_original=issue.get('original', ''))
        if not row['importar']:
            continue
        ids = row['elegidos']; tid = ids['trabajador']
        if tid == 'nuevo':
            if not user.has_perm('control.add_trabajador'):
                raise ErrorImportacion('Su cuenta no tiene permiso para crear trabajadores. Asigne una ficha existente.')
            key = (normalizar(v['nombre']), v['dni'])
            if key not in nuevos:
                worker = Trabajador(apellidos_nombres=v['nombre'], dni=v['dni'])
                worker.full_clean(); worker.save(); registrar(worker, user, 'crear_por_importacion')
                nuevos[key] = worker.pk
            tid = nuevos[key]
        datos = {k: v[k] for k in ('cud', 'observaciones')}
        datos['observaciones'] = datos['observaciones'] or ''
        for k in ('fecha_movimiento', 'fecha_final'):
            datos[k] = date.fromisoformat(v[k]) if v[k] else None
        for k in ('hora_salida', 'hora_retorno'):
            datos[k] = time.fromisoformat(v[k]) if v[k] else None
        obj = Justificacion(periodo=lote.periodo, trabajador_id=tid, tipo_documento_id=ids['documento'],
            tipo_operacion_id=ids['operacion'], fuente='EXCEL', created_by=user, updated_by=user,
            lote_importacion=lote, fila_origen=row['fila'], item_origen=v['item'] or '', huella=row['huella'],
            estado_calidad='INCOMPLETO_LEGADO' if row['incompleto'] else 'COMPLETO', **datos)
        obj.full_clean(); obj.save()
        registrar(obj, user, 'importar', contexto={'fila': row['fila'], 'lote': lote.pk, 'motivo_excepcion': row['motivo']})
    lote.insertados = plan['totales']['listas']; lote.omitidos = lote.total_leidos - lote.insertados
    lote.alertas = sum(len(row['issues']) for row in plan['filas'])
    lote.estado = 'CONFIRMADO'; lote.datos_temporales = {}; lote.save()
    registrar(lote, user, 'confirmar_importacion')
    return lote


@transaction.atomic
def anular_lote(lote_id, user, motivo):
    lote = LoteImportacion.objects.select_for_update().get(pk=lote_id)
    if lote.estado != 'CONFIRMADO' or not motivo.strip():
        raise ErrorImportacion('El lote no está confirmado o falta motivo.')
    cierre = HistorialCambio.objects.filter(entidad='loteimportacion', objeto_id=lote.pk, accion='confirmar_importacion').first()
    rows = list(Justificacion.objects.select_for_update().filter(lote_importacion=lote))
    if not cierre or any(obj.updated_at > cierre.fecha for obj in rows):
        raise ErrorImportacion('El lote tiene modificaciones posteriores. Revise y anule registros individualmente.')
    for obj in rows:
        obj.anulada = True; obj.motivo_anulacion = motivo; obj.anulada_at = timezone.now()
        obj.anulada_by = obj.updated_by = user; obj.save()
        registrar(obj, user, 'anular_lote', contexto={'motivo': motivo, 'lote': lote.pk})
    lote.estado = 'ANULADO'; lote.save(update_fields=['estado'])
    registrar(lote, user, 'anular_lote', contexto={'motivo': motivo})
    return lote
