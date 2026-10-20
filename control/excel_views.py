from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .audit import registrar
from .excel_forms import SeleccionarHojaForm, SubirExcelForm
from .importacion import (ErrorImportacion, anular_lote, confirmar, crear_borrador,
    octubre_historico, preparar_plan, revisar, seleccionar_hoja, vigente)
from .models import LoteImportacion
from .xlsx_parser import CAMPOS, ErrorXLSX, leer_archivo


def propio(request, pk):
    lote = get_object_or_404(LoteImportacion.objects.select_related('periodo', 'usuario'), pk=pk)
    if lote.usuario_id != request.user.pk and not request.user.has_perm('control.change_loteimportacion'):
        raise PermissionDenied
    if lote.estado in ('SELECCION', 'PREVIA') and not vigente(lote):
        lote.datos_temporales = {}; lote.estado = 'EXPIRADO'; lote.save()
    return lote


def base_context(lote=None):
    return {'tipo': 'importar', 'titulo': 'Importar Excel', 'lote': lote}


@never_cache
@login_required
@permission_required(['control.importar_excel', 'control.add_justificacion', 'control.view_justificacion'], raise_exception=True)
@require_http_methods(['GET', 'POST'])
def importar_excel(request):
    form = SubirExcelForm(request.POST if request.method == 'POST' else None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            d = form.cleaned_data
            parsed = leer_archivo(d['archivo'], d['encabezado'], d['primera_fila'],
                                  {k: d['col_' + k] for k in CAMPOS})
            lote = crear_borrador(parsed, d['archivo'].name, d['periodo'], request.user)
            return redirect('importacion_revisar', pk=lote.pk)
        except ErrorXLSX as exc:
            form.add_error('archivo', str(exc))
    ctx = base_context(); ctx['form'] = form
    return render(request, 'control/excel/subir.html', ctx)


def decisiones(request, lote):
    result = {}
    for row in lote.datos_temporales.get('filas', []):
        num = str(row['fila'])
        result[num] = {key: request.POST.get(f'{key}_{num}', '')[:2000] for key in
                       ('trabajador', 'documento', 'operacion', 'accion', 'motivo')}
    return result


@never_cache
@login_required
@permission_required(['control.importar_excel', 'control.add_justificacion', 'control.view_justificacion'], raise_exception=True)
@require_http_methods(['GET', 'POST'])
def importacion_revisar(request, pk):
    lote = propio(request, pk)
    if lote.estado not in ('SELECCION', 'PREVIA'):
        return redirect('importacion_resumen', pk=lote.pk)
    if request.method == 'POST' and request.POST.get('accion') == 'cancelar':
        with transaction.atomic():
            locked = LoteImportacion.objects.select_for_update().get(pk=lote.pk)
            if locked.estado in ('SELECCION', 'PREVIA'):
                locked.estado = 'CANCELADO'; locked.datos_temporales = {}; locked.save()
                registrar(locked, request.user, 'cancelar_previsualizacion')
        return redirect('importacion_resumen', pk=lote.pk)
    ctx = base_context(lote)
    if lote.estado == 'SELECCION':
        form = SeleccionarHojaForm(request.POST if request.method == 'POST' else None,
                                  hojas=lote.datos_temporales['hojas'])
        if request.method == 'POST' and form.is_valid():
            try:
                target = seleccionar_hoja(lote.pk, form.cleaned_data['hoja'], form.cleaned_data['conservar_cud'])
                if target.usuario_id != request.user.pk and not request.user.has_perm('control.change_loteimportacion'):
                    form.add_error(None, 'Este archivo/hoja/periodo ya tiene un lote de otra cuenta. No se importó nuevamente.')
                else:
                    return redirect('importacion_revisar' if target.estado == 'PREVIA' else 'importacion_resumen', pk=target.pk)
            except ErrorImportacion as exc:
                form.add_error(None, str(exc))
        ctx.update(form=form, octubre=octubre_historico(lote.periodo), hojas=lote.datos_temporales.get('hojas', {}))
        return render(request, 'control/excel/hoja.html', ctx)
    error = None
    try:
        if request.method == 'POST' and request.POST.get('accion') == 'confirmar':
            # Las decisiones deben haber pasado por Revisar; confirmar no aplica
            # campos nuevos del POST ni acepta una firma enviada por el cliente.
            actuales = decisiones(request, lote)
            incompletos = request.POST.get('permitir_incompletos') == 'on'
            if actuales != lote.datos_temporales.get('resoluciones') or incompletos != lote.datos_temporales.get('permitir_incompletos', False):
                lote, plan = revisar(lote.pk, actuales, incompletos)
                error = 'Las decisiones cambiaron. Revise este resumen y confirme de nuevo; no se insertaron registros.'
            else:
                lote = confirmar(lote.pk, request.user, request.POST.get('revision', ''))
                return redirect('importacion_resumen', pk=lote.pk)
        elif request.method == 'POST':
            lote, plan = revisar(lote.pk, decisiones(request, lote), request.POST.get('permitir_incompletos') == 'on')
        else:
            plan = preparar_plan(lote, permitir_incompletos=lote.datos_temporales.get('permitir_incompletos', False))
    except (ErrorImportacion, ValidationError) as exc:
        error = str(exc) if isinstance(exc, ErrorImportacion) else 'Una fila no cumple el modelo. Corrija el archivo y vuelva a cargarlo; no se guardaron registros.'
        lote.refresh_from_db()
        if lote.estado != 'PREVIA' or not vigente(lote):
            return redirect('importacion_resumen', pk=lote.pk)
        plan = preparar_plan(lote, permitir_incompletos=lote.datos_temporales.get('permitir_incompletos', False))
    ctx.update(plan=plan, error=error, listo=bool(lote.datos_temporales.get('firma')),
        revision=lote.datos_temporales['revision'], permitir_incompletos=lote.datos_temporales.get('permitir_incompletos', False),
        octubre='cud_omitido_por_desalineacion_octubre' in lote.reglas_aplicadas)
    return render(request, 'control/excel/previa.html', ctx)


@never_cache
@login_required
@permission_required(['control.importar_excel', 'control.add_justificacion', 'control.view_justificacion'], raise_exception=True)
@require_http_methods(['GET', 'POST'])
def importacion_resumen(request, pk):
    lote = propio(request, pk)
    if lote.estado in ('SELECCION', 'PREVIA'):
        return redirect('importacion_revisar', pk=lote.pk)
    error = None
    if request.method == 'POST':
        if not request.user.has_perm('control.anular_justificacion'):
            raise PermissionDenied
        try:
            lote = anular_lote(lote.pk, request.user, request.POST.get('motivo', '')[:2000])
        except ErrorImportacion as exc:
            error = str(exc)
    ctx = base_context(lote)
    ctx.update(error=error, registros=Paginator(lote.justificacion_set.select_related('trabajador').order_by('pk'),25).get_page(request.GET.get('page')),
        incidencias=Paginator(lote.incidencias.order_by('fila','pk'),50).get_page(request.GET.get('incidencia_page')))
    return render(request, 'control/excel/resumen.html', ctx)
