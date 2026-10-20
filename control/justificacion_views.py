from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from .audit import registrar, snapshot
from .autocomplete import MODELOS, buscar_opciones, etiqueta
from .justificacion_forms import AnulacionForm, FiltroJustificaciones, JustificacionForm
from .models import Justificacion, PeriodoAsistencia, normalizar
from .views import exigir_permiso, valor_visible


def consulta_query(request):
    query = request.GET.copy()
    permitidos = set(FiltroJustificaciones.base_fields) | {'page', 'trabajador_buscar',
                    'tipo_documento_buscar', 'tipo_operacion_buscar'}
    for key in list(query):
        if key not in permitidos:
            del query[key]
    return query


def url_consulta(request, nombre='consultas', pk=None):
    url = reverse(nombre, kwargs={'pk': pk} if pk is not None else None)
    query = consulta_query(request).urlencode()
    return url + ('?' + query if query else '')


def relacionados():
    return Justificacion.objects.select_related('trabajador', 'periodo', 'tipo_documento',
                                               'tipo_operacion', 'created_by', 'updated_by')


def avisos_horas(obj):
    if bool(obj.hora_salida) != bool(obj.hora_retorno):
        return ['Solo se registró una de las dos horas. Se conserva el dato sin completar la otra.']
    if obj.hora_salida and obj.hora_retorno and obj.hora_retorno < obj.hora_salida:
        return ['El retorno es anterior a la salida. Revise las horas; no se presume un turno ni un cruce de medianoche.']
    return []


def contexto(request):
    return {'tipo': 'justificaciones', 'titulo': 'Consultas',
            'url_lista': url_consulta(request),
            'url_nuevo': url_consulta(request, 'justificacion_nueva')}


@never_cache
@login_required
@require_safe
def autocompletar(request, campo):
    model = MODELOS.get(campo)
    if model is None:
        return JsonResponse({'error': 'Campo no encontrado.'}, status=404)
    if not any(request.user.has_perm('control.' + action + '_justificacion') for action in ('view', 'add', 'change')):
        raise PermissionDenied
    exigir_permiso(request.user, model, 'view')
    term = request.GET.get('q', '')[:250].strip()
    objetos = buscar_opciones(model, term, incluir_inactivos=request.GET.get('modo') == 'consulta')
    results = []
    for obj in objetos:
        item = {'id': obj.pk, 'label': etiqueta(obj)}
        if campo == 'tipo_operacion':
            item['requiere_fecha_final'] = obj.requiere_fecha_final
        results.append(item)
    return JsonResponse({'results': results, 'limite': 20})


@never_cache
@login_required
@require_safe
def consultas(request):
    exigir_permiso(request.user, Justificacion, 'view')
    filtros = FiltroJustificaciones(request.GET)
    qs = relacionados()
    if filtros.is_valid():
        data = filtros.cleaned_data
        if data['q']:
            term = data['q']
            qs = qs.filter(Q(trabajador__nombre_busqueda__contains=normalizar(term)) |
                Q(trabajador__dni__contains=term) | Q(cud__icontains=term) | Q(observaciones__icontains=term))
        for field in ('trabajador', 'periodo', 'tipo_documento', 'tipo_operacion'):
            if data[field]:
                qs = qs.filter(**{field: data[field]})
        for form_field, lookup in [('dni', 'trabajador__dni__contains'), ('cud', 'cud__icontains'),
                ('fecha', 'fecha_movimiento'), ('desde', 'fecha_movimiento__gte'), ('hasta', 'fecha_movimiento__lte')]:
            if data[form_field]:
                qs = qs.filter(**{lookup: data[form_field]})
        if data['activo']:
            qs = qs.filter(trabajador__activo=data['activo'] == '1')
        if data['estado'] != 'TODOS':
            qs = qs.filter(anulada=data['estado'] == 'ANULADAS')
        # NULLS LAST explícito: mismo orden en SQLite y PostgreSQL.
        qs = qs.order_by('-created_at', '-pk') if data['orden'] == 'captura' else qs.order_by(F('fecha_movimiento').desc(nulls_last=True), '-pk')
    else:
        qs = qs.none()
    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    query = consulta_query(request)
    query.pop('page', None)
    ctx = contexto(request)
    principales = ['q', 'trabajador', 'periodo', 'fecha']
    avanzados = [key for key in filtros.fields if key not in principales]
    ctx.update(filtros_principales=[filtros[key] for key in principales],
        filtros_avanzados=[filtros[key] for key in avanzados],
        abrir_avanzados=any(request.GET.get(key) or request.GET.get(key + '_buscar') for key in avanzados),
        filtros=filtros, pagina=page, consulta_pagina=query.urlencode(),
        filas=[{'obj': obj, 'url': url_consulta(request, 'justificacion_detalle', obj.pk)} for obj in page])
    return render(request, 'control/justificaciones/consultas.html', ctx)


@never_cache
@login_required
@require_safe
def justificacion_detalle(request, pk):
    exigir_permiso(request.user, Justificacion, 'view')
    obj = get_object_or_404(relacionados(), pk=pk)
    fields = [('periodo', 'Periodo'), ('trabajador', 'Trabajador'), ('tipo_documento', 'Tipo de documento'),
        ('tipo_operacion', 'Tipo de operación'), ('fecha_movimiento', 'Fecha de movimiento'),
        ('fecha_final', 'Fecha final'), ('hora_salida', 'Hora de salida'), ('hora_retorno', 'Hora de retorno'),
        ('cud', 'CUD'), ('fecha_recepcion', 'Fecha de recepción'), ('observaciones', 'Observaciones'),
        ('created_at', 'Fecha de captura'), ('created_by', 'Registrado por'),
        ('updated_at', 'Última modificación'), ('updated_by', 'Modificado por'), ('fuente', 'Fuente')]
    datos = [(label, valor_visible(obj, field)) for field, label in fields]
    datos += [('Plazo', obj.plazo), ('Estado', 'Anulada' if obj.anulada else 'Vigente')]
    if obj.anulada:
        datos += [('Motivo de anulación', obj.motivo_anulacion), ('Anulada el', valor_visible(obj, 'anulada_at')),
                  ('Anulada por', obj.anulada_by)]
    ctx = contexto(request)
    ctx.update(objeto=obj, datos=datos, avisos_horas=avisos_horas(obj), url_editar=url_consulta(request, 'justificacion_editar', pk),
               url_anular=url_consulta(request, 'justificacion_anular', pk))
    if request.user.has_perm('control.view_historialcambio'):
        from .models import HistorialCambio
        ctx['auditoria'] = HistorialCambio.objects.filter(entidad='justificacion', objeto_id=pk).select_related('autor')
    return render(request, 'control/justificaciones/detalle.html', ctx)


def avisos_formulario(form):
    avisos = []
    def elegido(campo):
        value = form.data.get(campo) if form.is_bound else form.initial.get(campo)
        if value and str(value).isdigit():
            return form.fields[campo].queryset.filter(pk=value).first()
    p, op = elegido('periodo'), elegido('tipo_operacion')
    if p and p.estado != 'ABIERTO':
        avisos.append('Este periodo está cerrado. El registro se añadirá al historial.' if p.estado == 'CERRADO'
                      else 'Este periodo está procesado. El registro se añadirá al historial.')
    if op and op.requiere_fecha_final is None:
        avisos.append('La regla de fecha final de esta operación está pendiente de revisión.')
    return avisos, op


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def justificacion_formulario(request, pk=None):
    exigir_permiso(request.user, Justificacion, 'change' if pk is not None else 'add')
    buscar = request.method == 'POST' and request.POST.get('accion') == 'buscar'
    with transaction.atomic():
        obj = get_object_or_404(Justificacion.objects.select_for_update(), pk=pk) if pk is not None else Justificacion()
        if obj.anulada:
            raise PermissionDenied('El registro está anulado.')
        antes = snapshot(obj) if pk is not None else None
        version = obj.updated_at.isoformat() if pk is not None else None
        params = request.POST if request.method == 'POST' else request.GET
        initial = request.POST.dict() if buscar else {}
        if request.method == 'GET' and pk is None:
            # Solo estos valores explícitos se admiten como preselección; no se
            # deduce el periodo por fecha ni por el título de la hoja.
            initial = {k: request.GET[k] for k in ('trabajador', 'periodo') if k in request.GET}
        form = JustificacionForm(request.POST if request.method == 'POST' and not buscar else None,
            initial=initial, instance=obj, parametros=params)
        if request.method == 'POST' and not buscar and form.is_valid():
            if pk is not None and form.cleaned_data['version'] != version:
                form.add_error(None, 'El registro cambió en otra sesión. Recargue y revise los cambios antes de guardar.')
            else:
                obj = form.save(commit=False)
                if pk is None:
                    obj.created_by = request.user
                obj.updated_by = request.user
                obj.save()
                motivos = {k: form.cleaned_data[k] for k in ('motivo_excepcion', 'motivo_edicion') if form.cleaned_data.get(k)}
                registrar(obj, request.user, 'editar' if pk is not None else 'crear', antes, contexto=motivos)
                if request.POST.get('accion') == 'otro':
                    for aviso in avisos_horas(obj):
                        messages.warning(request, aviso)
                messages.success(request, 'Justificación actualizada.' if pk is not None else 'Justificación registrada.')
                if request.POST.get('accion') == 'otro':
                    return redirect(url_consulta(request, 'justificacion_nueva'))
                if request.user.has_perm('control.view_justificacion'):
                    return redirect(url_consulta(request, 'justificacion_detalle', obj.pk))
                return redirect('inicio')
    avisos, op = avisos_formulario(form)
    ctx = contexto(request)
    ctx.update(form=form, objeto=obj if pk is not None else None, avisos=avisos,
        operacion_inicial={'id': op.pk, 'requiere_fecha_final': op.requiere_fecha_final} if op else None,
        periodos=[{'id': p.pk, 'estado': p.estado} for p in PeriodoAsistencia.objects.all()],
        encabezado='Editar justificación' if pk is not None else 'Nueva justificación',
        url_cancelar=url_consulta(request, 'justificacion_detalle', pk) if pk is not None else url_consulta(request))
    return render(request, 'control/justificaciones/formulario.html', ctx)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def justificacion_anular(request, pk):
    if not request.user.has_perm('control.anular_justificacion'):
        raise PermissionDenied
    with transaction.atomic():
        obj = get_object_or_404(Justificacion.objects.select_for_update(), pk=pk)
        if obj.anulada:
            raise PermissionDenied('El registro ya está anulado.')
        form = AnulacionForm(request.POST if request.method == 'POST' else None,
                             initial={'version': obj.updated_at.isoformat()})
        if request.method == 'POST' and form.is_valid():
            if form.cleaned_data['version'] != obj.updated_at.isoformat():
                form.add_error(None, 'El registro cambió. Recargue y revise antes de anular.')
            else:
                antes = snapshot(obj)
                obj.anulada = True
                obj.motivo_anulacion = form.cleaned_data['motivo']
                obj.anulada_at = timezone.now()
                obj.anulada_by = obj.updated_by = request.user
                obj.save()
                registrar(obj, request.user, 'anular', antes)
                messages.success(request, 'Justificación anulada; se conserva el historial.')
                return redirect(url_consulta(request, 'justificacion_detalle', pk))
    ctx = contexto(request)
    ctx.update(form=form, objeto=obj, url_cancelar=url_consulta(request, 'justificacion_detalle', pk))
    return render(request, 'control/justificaciones/anular.html', ctx)
