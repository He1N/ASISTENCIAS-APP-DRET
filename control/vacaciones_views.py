import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils.http import content_disposition_header
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from .models import CuentaVacacion, MovimientoVacacion, EnlaceVacacion
from .audit import registrar, snapshot
from .vacaciones import resumen
from .vacaciones_forms import CuentaForm, MovimientoForm


@never_cache
@login_required
@permission_required('control.view_cuentavacacion',raise_exception=True)
@require_safe
def lista(request):
    qs=CuentaVacacion.objects.filter(eliminada=False).prefetch_related('movimientos')
    q=request.GET.get('q','').strip()[:250]
    if q: qs=qs.filter(Q(nombre__icontains=q)|Q(dni__contains=q))
    page=Paginator(qs,25).get_page(request.GET.get('page'))
    rows=[resumen(c) for c in page]
    return render(request,'control/vacaciones/lista.html',dict(titulo='Control de vacaciones',tipo='control_vacaciones',
        pagina=page,filas=rows,q=q,enlaces_pendientes=EnlaceVacacion.objects.filter(estado__in=['PENDIENTE','EXCEPCION']).select_related('justificacion__trabajador','cuenta')))


@never_cache
@login_required
@permission_required('control.view_cuentavacacion',raise_exception=True)
@require_safe
def ficha(request,pk):
    c=get_object_or_404(CuentaVacacion,pk=pk,eliminada=False)
    return render(request,'control/vacaciones/ficha.html',dict(titulo=c.nombre,tipo='control_vacaciones',r=resumen(c)))


@never_cache
@login_required
@permission_required(['control.view_cuentavacacion','control.exportar_resultados'],raise_exception=True)
@require_safe
def formatos(request,pk):
    from django import forms
    from django.utils import timezone
    from .vacaciones_word import generar_docx, generar_integrado, anios_disponibles
    from io import BytesIO
    from zipfile import ZipFile,ZIP_DEFLATED
    c=get_object_or_404(CuentaVacacion.objects.prefetch_related('movimientos'),pk=pk,eliminada=False)
    class Opciones(forms.Form):
        anio=forms.IntegerField(label='Año de las fechas Del/Al (solo formatos anuales)',required=False,min_value=1900,max_value=9999,initial=timezone.localdate().year)
        formato=forms.ChoiceField(label='Formato',choices=[('integrado','Récord e informe integrados · todos los años (Word)'),('record','Récord anual'),('informe','Informe anual'),('ambos','Ambos anuales (archivo ZIP)')])
        def clean(self):
            data=super().clean()
            if data.get('formato')!='integrado' and not data.get('anio'):
                self.add_error('anio','Indique el año para el formato anual.')
            return data
    form=Opciones(request.GET if request.GET.get('generar') else None)
    years=anios_disponibles(c)
    if form.is_bound and form.is_valid():
        year=form.cleaned_data['anio']; choice=form.cleaned_data['formato']
        name=re.sub(r'[^\w .-]','',c.nombre).strip() or c.dni
        try:
            if choice=='integrado':
                data=generar_integrado(c); filename=f'Record_informe_{name}_todos_los_anios.docx'
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif choice=='ambos':
                out=BytesIO()
                with ZipFile(out,'w',ZIP_DEFLATED) as z:
                    for kind in ['record','informe']: z.writestr(f'{kind}_{name}_{year}.docx',generar_docx(c,year,kind))
                data=out.getvalue(); filename=f'Formatos_{name}_{year}.zip'; mime='application/zip'
            else:
                data=generar_docx(c,year,choice); filename=f'{choice}_{name}_{year}.docx'
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            response=HttpResponse(data,content_type=mime)
            response['Content-Disposition']=content_disposition_header(True,filename)
            return response
        except ValueError as exc: form.add_error(None,str(exc))
    return render(request,'control/vacaciones/formatos.html',dict(titulo='Generar formato',tipo='control_vacaciones',cuenta=c,form=form,anios=years))


@never_cache
@login_required
@permission_required('control.change_cuentavacacion',raise_exception=True)
@require_http_methods(['GET','POST'])
def editar(request,pk=None,movimiento=None,nuevo=False):
    with transaction.atomic():
        if pk is None and not request.user.has_perm('control.add_cuentavacacion'):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        target_id=request.POST.get('cuenta','') if request.method=='POST' else ''
        ids=[pk] if pk else []
        if target_id.isdigit(): ids.append(int(target_id))
        locked=list(CuentaVacacion.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        c=get_object_or_404(CuentaVacacion,pk=pk,eliminada=False) if pk else CuentaVacacion()
        obj=(MovimientoVacacion(cuenta=c) if nuevo else get_object_or_404(MovimientoVacacion,pk=movimiento,cuenta=c)) if (movimiento or nuevo) else c
        if movimiento:
            enlace=EnlaceVacacion.objects.filter(movimiento=obj).first()
            if enlace:
                return render(request,'control/vacaciones/movimiento_enlazado.html',dict(enlace=enlace,cuenta=c,tipo='control_vacaciones'))
        before=snapshot(obj) if obj.pk else None
        Form=MovimientoForm if isinstance(obj,MovimientoVacacion) else CuentaForm
        form=Form(request.POST or None,instance=obj)
        if request.method=='POST' and form.is_valid():
            if obj.pk and form.cleaned_data['version'] != obj.updated_at.isoformat():
                form.add_error(None,'La ficha cambió mientras editaba. Recargue antes de guardar.')
            else:
                changed=form.save(commit=False)
                if isinstance(changed,CuentaVacacion):
                    changed.asignaciones={str(y):str(form.cleaned_data[f'anio_{y}']) if form.cleaned_data.get(f'anio_{y}') is not None else None for y in range(2022,2031)}
                changed.save()
                c.refresh_from_db()
                registrar(changed,request.user,'editar' if before else 'crear',before,
                          {'motivo':form.cleaned_data.get('motivo','')})
                messages.success(request,'Cambio guardado y auditado.')
                affected=changed.cuenta if isinstance(changed,MovimientoVacacion) else c
                saldo=resumen(affected)['pendiente']
                if saldo<0:
                    messages.warning(request,f'Saldo negativo: {saldo} días. El consumo excede las asignaciones registradas en {-saldo} días.')
                return redirect('vacacion_ficha',pk=affected.pk)
    return render(request,'control/formulario.html',dict(form=form,encabezado='Editar control de vacaciones',
        titulo='Control de vacaciones',tipo='control_vacaciones',url_cancelar=reverse('vacacion_ficha',args=[pk]) if pk else reverse('vacacion_lista')))


@never_cache
@login_required
@permission_required('control.view_cuentavacacion',raise_exception=True)
@permission_required('control.exportar_resultados',raise_exception=True)
@require_safe
def exportar(request,pk=None):
    from .vacaciones_xlsx import exportar_control
    qs=CuentaVacacion.objects.filter(eliminada=False).prefetch_related('movimientos')
    qs=qs.filter(pk=pk) if pk else qs
    q=request.GET.get('q','').strip()[:250]
    if q and not pk: qs=qs.filter(Q(nombre__icontains=q)|Q(dni__contains=q))
    if pk: get_object_or_404(qs)
    results=[resumen(c) for c in qs]
    response=HttpResponse(exportar_control(results),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename='control-vacaciones.xlsx'
    if len(results)==1:
        nombre=re.sub(r'[<>:"/\\|?*\x00-\x1f]',' ',results[0]['cuenta'].nombre)
        nombre=' '.join(nombre.split()).strip(' .')[:150].rstrip(' .')
        filename=(nombre or results[0]['cuenta'].dni)+'.xlsx'
    response['Content-Disposition']=content_disposition_header(True,filename)
    response['Cache-Control']='private, no-store'
    return response


@never_cache
@login_required
@permission_required('control.change_cuentavacacion',raise_exception=True)
@require_http_methods(['GET','POST'])
def eliminar(request,pk,movimiento=None):
    with transaction.atomic():
        cuenta=get_object_or_404(CuentaVacacion.objects.select_for_update(),pk=pk,eliminada=False)
        obj=get_object_or_404(MovimientoVacacion,pk=movimiento,cuenta=cuenta) if movimiento else cuenta
        if movimiento:
            enlace=EnlaceVacacion.objects.filter(movimiento=obj).first()
            if enlace:
                return render(request,'control/vacaciones/movimiento_enlazado.html',dict(enlace=enlace,cuenta=cuenta,tipo='control_vacaciones'))
        error=None
        if request.method=='POST':
            if request.POST.get('version')!=obj.updated_at.isoformat():
                error='Los datos cambiaron. Recargue antes de eliminar.'
            else:
                before=snapshot(obj)
                if movimiento:
                    obj.estado='ANULADO'
                    obj.motivo='Eliminado desde el control de vacaciones'
                else:
                    obj.eliminada=True
                obj.save()
                registrar(obj,request.user,'eliminar_logicamente',before)
                messages.success(request,'Registro eliminado.')
                return redirect('vacacion_ficha',pk=pk) if movimiento else redirect('vacacion_lista')
    return render(request,'control/vacaciones/eliminar.html',dict(titulo='Eliminar registro',tipo='control_vacaciones',
        objeto=obj,cuenta=cuenta,movimiento=movimiento,error=error,version=obj.updated_at.isoformat()))
