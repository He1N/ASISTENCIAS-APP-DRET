"""Consulta y exportación del derecho separado de Ley 276."""
import re
from django.contrib.auth.decorators import login_required,permission_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render,get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header
from .models import CuentaVacacion
from .regimenes import normalizar_regimen
from .vacaciones import resumen, saldo_ley276_anual
from .exportacion_regimen import libro_agrupado


def cuentas(q='',exportacion=False):
    qs=CuentaVacacion.objects.filter(eliminada=False).prefetch_related('movimientos')
    if exportacion:qs=qs.filter(habilitada=True)
    if q:qs=qs.filter(Q(nombre__icontains=q)|Q(dni__contains=q))
    return [c for c in qs if normalizar_regimen(c.regimen_laboral)=='DEC. LEG. 276']


def obtener(pk,exportacion=False):
    qs=CuentaVacacion.objects.filter(eliminada=False).prefetch_related('movimientos')
    if exportacion:qs=qs.filter(habilitada=True)
    c=get_object_or_404(qs,pk=pk)
    if normalizar_regimen(c.regimen_laboral)!='DEC. LEG. 276':
        from django.http import Http404
        raise Http404
    return c


@never_cache
@login_required
@permission_required('control.view_cuentavacacion',raise_exception=True)
@require_safe
def lista(request):
    q=request.GET.get('q','').strip()[:250]
    page=Paginator(cuentas(q),25).get_page(request.GET.get('page'))
    anio = timezone.localdate().year
    filas = [dict(cuenta=c, ley_276=saldo_ley276_anual(c, anio)) for c in page]
    return render(request, 'control/ley276/lista.html', dict(
        titulo='LEY 276', tipo='ley276', q=q, pagina=page, filas=filas, anio=anio))


@never_cache
@login_required
@permission_required('control.view_cuentavacacion',raise_exception=True)
@require_safe
def ficha(request,pk):
    c=obtener(pk);r=resumen(c)
    return render(request,'control/ley276/ficha.html',dict(titulo=c.nombre,tipo='ley276',r=r,movimientos=[m for m in r['filas'] if m['codigo']=='09']))


@never_cache
@login_required
@permission_required(['control.view_cuentavacacion','control.exportar_resultados'],raise_exception=True)
@require_safe
def exportar(request,pk=None):
    q=request.GET.get('q','').strip()[:250]
    records=[resumen(c) for c in ([obtener(pk,True)] if pk else cuentas(q,True))]
    summary=[[r['cuenta'].dni,r['cuenta'].nombre,r['ley_276']['programado'],r['ley_276']['usado'],r['ley_276']['pendiente']] for r in records]
    details=[[r['cuenta'].dni,r['cuenta'].nombre,m['periodo'],m['fecha'],m['inicio'],m['fin'],m['dias_ley'],m['dias_ley'] if m['estado']=='VIGENTE' else 0,m['estado'],m['observaciones']] for r in records for m in r['filas'] if m['codigo']=='09']
    data=libro_agrupado([
        dict(nombre='Resumen',titulo='LEY 276',regimen='DEC. LEG. 276',headers=['DNI','Nombres y apellidos','Días totales asignados','Días usados','Días restantes'],widths=[13,45,24,17,18],totales=[3,4,5],rows=summary),
        dict(nombre='detalle',titulo='PERMISOS LEY 276',regimen='DEC. LEG. 276',headers=['DNI','Nombres y apellidos','Periodo','Fecha','Del','Al','Días de permiso','Descontado','Estado','Sustento / observación'],widths=[13,40,12,14,14,14,18,16,17,58],totales=[8],rows=details)])
    name='Ley_276'
    if pk:name+='_'+(re.sub(r'[^\w .-]','',records[0]['cuenta'].nombre).strip() or records[0]['cuenta'].dni)
    response=HttpResponse(data,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition']=content_disposition_header(True,name+'.xlsx')
    return response
