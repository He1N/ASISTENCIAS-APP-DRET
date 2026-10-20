from datetime import date, datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from .audit import registrar, snapshot
from .models import Trabajador, TipoDocumento, TipoOperacion, PeriodoAsistencia, normalizar
from .services import preparar_fechas_estado
from .webforms import (TrabajadorWebForm, DocumentoWebForm, OperacionWebForm,
                       PeriodoWebForm, FiltroMaestros, FiltroPeriodos)


MAESTROS = {
    'trabajadores': {
        'modelo': Trabajador, 'formulario': TrabajadorWebForm,
        'titulo': 'Trabajadores', 'nuevo': 'Nuevo trabajador',
        'columnas': ['Apellidos y nombres', 'DNI', 'Área', 'Estado'],
        'campos': ['apellidos_nombres', 'dni', 'area', 'activo'],
    },
    'documentos': {
        'modelo': TipoDocumento, 'formulario': DocumentoWebForm,
        'titulo': 'Tipos de documento', 'nuevo': 'Nuevo tipo de documento',
        'columnas': ['Nombre', 'Código externo', 'Estado'],
        'campos': ['nombre', 'codigo_externo', 'activo'],
    },
    'operaciones': {
        'modelo': TipoOperacion, 'formulario': OperacionWebForm,
        'titulo': 'Tipos de operación', 'nuevo': 'Nuevo tipo de operación',
        'columnas': ['Nombre', 'Código externo', 'Fecha final', 'Grupo especial', 'Estado'],
        'campos': ['nombre', 'codigo_externo', 'requiere_fecha_final', 'grupo_especial', 'activo'],
    },
    'periodos': {
        'modelo': PeriodoAsistencia, 'formulario': PeriodoWebForm,
        'titulo': 'Periodos', 'nuevo': 'Nuevo periodo',
        'columnas': ['Título', 'Inicio', 'Fin', 'Estado', 'Registros', 'Cierre', 'Procesamiento'],
        'campos': ['titulo', 'fecha_inicio', 'fecha_fin', 'estado', 'total_registros',
                   'fecha_cierre', 'fecha_procesamiento'],
    },
}


def configuracion(tipo):
    if tipo not in MAESTROS:
        raise Http404
    return MAESTROS[tipo]


def exigir_permiso(user, modelo, accion):
    if not user.has_perm(f'control.{accion}_{modelo._meta.model_name}'):
        raise PermissionDenied


def consulta_url(request):
    # Se conservan solo filtros locales; nunca se admite una URL de retorno externa.
    query = request.GET.copy()
    for key in list(query):
        if key not in ('q', 'activo', 'estado', 'page'):
            del query[key]
    return query


def enlace(nombre, tipo, query, pk=None):
    kwargs = {'tipo': tipo}
    if pk is not None:
        kwargs['pk'] = pk
    url = reverse(nombre, kwargs=kwargs)
    return url + ('?' + query.urlencode() if query else '')


def valor_visible(obj, campo):
    value = getattr(obj, campo)
    if campo == 'activo':
        return 'Activo' if value else 'Inactivo'
    if campo == 'requiere_fecha_final':
        return 'Pendiente de revisión' if value is None else ('Sí' if value else 'No')
    display = getattr(obj, f'get_{campo}_display', None)
    if display:
        return display()
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime('%d/%m/%Y %H:%M')
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    if value is None or value == '':
        return 'Sin definir' if campo == 'fecha_fin' else '—'
    return value


def contexto(request, tipo):
    spec = configuracion(tipo)
    model = spec['modelo']
    return {
        'tipo': tipo, 'titulo': spec['titulo'], 'nuevo': spec['nuevo'],
        'puede_crear': request.user.has_perm(f'control.add_{model._meta.model_name}'),
        'puede_editar': request.user.has_perm(f'control.change_{model._meta.model_name}'),
        'url_lista': enlace('maestro_lista', tipo, consulta_url(request)),
        'url_nuevo': enlace('maestro_nuevo', tipo, consulta_url(request)),
    }


@never_cache
@login_required
@require_safe
def inicio(request):
    for tipo, spec in MAESTROS.items():
        if request.user.has_perm(f"control.view_{spec['modelo']._meta.model_name}"):
            return redirect('maestro_lista', tipo=tipo)
    raise PermissionDenied


@never_cache
@login_required
@require_safe
def maestro_lista(request, tipo):
    spec = configuracion(tipo)
    model = spec['modelo']
    exigir_permiso(request.user, model, 'view')
    qs = model.objects.all()
    form_class = FiltroPeriodos if tipo == 'periodos' else FiltroMaestros
    filtros = form_class(request.GET)
    if filtros.is_valid():
        data = filtros.cleaned_data
        term = data['q']
        if tipo == 'periodos':
            if term:
                qs = qs.filter(Q(titulo__icontains=term) | Q(notas__icontains=term))
            if data['estado']:
                qs = qs.filter(estado=data['estado'])
        else:
            if term:
                search = Q(nombre_busqueda__contains=normalizar(term))
                search |= Q(dni__contains=term) if tipo == 'trabajadores' else Q(codigo_externo__icontains=term)
                if tipo == 'trabajadores':
                    search |= Q(area__icontains=term)
                qs = qs.filter(search)
            if data['activo']:
                qs = qs.filter(activo=data['activo'] == '1')
    else:
        qs = qs.none()
    if tipo == 'periodos':
        qs = qs.annotate(total_registros=Count('justificacion')).order_by('-fecha_inicio', '-pk')
    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    query = consulta_url(request)
    rows = [{'celdas': [valor_visible(obj, campo) for campo in spec['campos']],
             'url': enlace('maestro_detalle', tipo, query, obj.pk)} for obj in page]
    page_query = query.copy()
    page_query.pop('page', None)
    ctx = contexto(request, tipo)
    ctx.update(filtros=filtros, pagina=page, filas=rows, columnas=spec['columnas'],
               consulta_pagina=page_query.urlencode(),
               url_limpiar=reverse('maestro_lista', kwargs={'tipo': tipo}))
    return render(request, 'control/lista.html', ctx)


@never_cache
@login_required
@require_safe
def maestro_detalle(request, tipo, pk):
    spec = configuracion(tipo)
    exigir_permiso(request.user, spec['modelo'], 'view')
    obj = get_object_or_404(spec['modelo'], pk=pk)
    fields = [f for f in obj._meta.fields if f.name not in ('id', 'nombre_busqueda')]
    etiquetas = {'created_at': 'Creado el', 'updated_at': 'Última modificación'}
    ctx = contexto(request, tipo)
    ctx.update(objeto=obj, datos=[(etiquetas.get(f.name, str(f.verbose_name).capitalize()), valor_visible(obj, f.name)) for f in fields],
               url_editar=enlace('maestro_editar', tipo, consulta_url(request), pk))
    if tipo in ('trabajadores', 'periodos'):
        ctx['total_relacionados'] = obj.justificacion_set.count()
        # No ampliar los permisos de fase 1 al mostrar el historial relacionado.
        if request.user.has_perm('control.view_justificacion'):
            qs = obj.justificacion_set.select_related('trabajador', 'periodo', 'tipo_documento', 'tipo_operacion')
            ctx['relacionados'] = Paginator(qs, 25).get_page(request.GET.get('historial_page'))
            ctx['consulta_historial'] = consulta_url(request).urlencode()
    return render(request, 'control/detalle.html', ctx)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def maestro_formulario(request, tipo, pk=None):
    spec = configuracion(tipo)
    model = spec['modelo']
    exigir_permiso(request.user, model, 'change' if pk is not None else 'add')
    # Las escrituras y su auditoría se confirman juntas. Se comprueba la versión
    # leída al abrir el formulario, además del bloqueo disponible en el motor.
    with transaction.atomic():
        obj = get_object_or_404(model.objects.select_for_update(), pk=pk) if pk is not None else model()
        version = obj.updated_at.isoformat() if pk is not None else None
        antes = snapshot(obj) if pk is not None else None
        form = spec['formulario'](request.POST if request.method == 'POST' else None, instance=obj)
        if request.method == 'POST' and form.is_valid():
            if pk is not None and form.cleaned_data['version'] != version:
                form.add_error(None, 'La ficha cambió en otra sesión. Recargue la página y revise los cambios antes de guardar.')
            else:
                obj = form.save(commit=False)
                preparar_fechas_estado(obj)
                obj.save()
                registrar(obj, request.user, 'editar' if pk is not None else 'crear', antes)
                messages.success(request, 'Cambios guardados.' if pk is not None else 'Registro creado.')
                # Un permiso de escritura no concede por sí solo permiso de lectura.
                if request.user.has_perm(f'control.view_{model._meta.model_name}'):
                    return redirect(enlace('maestro_detalle', tipo, consulta_url(request), obj.pk))
                return redirect('inicio')
    ctx = contexto(request, tipo)
    ctx.update(form=form, objeto=obj if pk is not None else None,
               encabezado='Editar ' + str(model._meta.verbose_name) if pk is not None else spec['nuevo'],
               url_cancelar=enlace('maestro_detalle', tipo, consulta_url(request), pk) if pk is not None else ctx['url_lista'])
    return render(request, 'control/formulario.html', ctx)
