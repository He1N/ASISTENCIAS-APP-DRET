from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from .exportacion import exportar_justificaciones, respuesta_xlsx
from .justificacion_forms import FiltroEspecial, FiltroJustificaciones
from .justificacion_views import aplicar_filtros
from .models import Justificacion, PeriodoAsistencia
from .services import filtrar_periodos
from .views import exigir_permiso
from .webforms import FiltroPeriodos


def exigir_exportar(request):
    if not request.user.has_perm('control.exportar_resultados'):
        raise PermissionDenied


@never_cache
@login_required
@require_safe
def exportar_consultas(request):
    exigir_permiso(request.user, Justificacion, 'view'); exigir_exportar(request)
    return exportar_justificaciones(aplicar_filtros(FiltroJustificaciones(request.GET)))


@never_cache
@login_required
@require_safe
def especiales(request, grupo, exportar=False):
    exigir_permiso(request.user, Justificacion, 'view')
    form = FiltroEspecial(request.GET, grupo=grupo)
    qs = aplicar_filtros(form).filter(tipo_operacion__grupo_especial=grupo)
    if form.is_valid():
        for campo, lookup in [('final_desde','fecha_final__gte'),('final_hasta','fecha_final__lte')]:
            if form.cleaned_data[campo]: qs = qs.filter(**{lookup: form.cleaned_data[campo]})
    if exportar:
        exigir_exportar(request)
        return exportar_justificaciones(qs)
    ruta = 'vacaciones' if grupo == 'VACACIONES' else 'sindicales'
    query = request.GET.copy(); query.pop('page', None)
    titulo = 'Vacaciones' if grupo == 'VACACIONES' else 'Licencias sindicales'
    principales = ['q','trabajador','periodo','fecha']
    avanzados = [k for k in form.fields if k not in principales]
    return render(request, 'control/especiales.html', {'filtros_principales':[form[k] for k in principales],
        'filtros_avanzados':[form[k] for k in avanzados],
        'abrir_avanzados':any(request.GET.get(k) or request.GET.get(k+'_buscar') for k in avanzados), 'tipo': ruta, 'titulo': titulo, 'filtros': form,
        'pagina': Paginator(qs,25).get_page(request.GET.get('page')), 'consulta_pagina': query.urlencode(),
        'url_limpiar': reverse(ruta), 'url_exportar': reverse('exportar_' + ruta) + ('?' + query.urlencode() if query else '')})


@never_cache
@login_required
@require_safe
def exportar_periodos(request):
    exigir_permiso(request.user, PeriodoAsistencia, 'view'); exigir_exportar(request)
    form = FiltroPeriodos(request.GET)
    qs = filtrar_periodos(PeriodoAsistencia.objects.all(), form.cleaned_data) if form.is_valid() else PeriodoAsistencia.objects.none()
    qs = qs.annotate(total=Count('justificacion')).order_by('-fecha_inicio','-pk')
    return respuesta_xlsx('periodos.xlsx', ['Periodo','Inicio','Fin','Estado','Registros','Cierre','Procesamiento','Notas'],
        ([p.titulo,p.fecha_inicio,p.fecha_fin,p.get_estado_display(),p.total,p.fecha_cierre,p.fecha_procesamiento,p.notas] for p in qs.iterator()))
