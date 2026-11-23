"""Carga y consulta privada del documento firmado de un movimiento."""
import re
from io import BytesIO
from pathlib import PurePath

from PIL import Image, UnidentifiedImageError
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from .audit import registrar, snapshot
from .models import EvidenciaVacacion, MovimientoVacacion

MAX_BYTES = 4_000_000
IMAGENES = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}
EXTENSIONES = {'application/pdf': '.pdf', 'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}


class EvidenciaForm(forms.Form):
    archivo = forms.FileField(label='Documento firmado', max_length=255,
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png,.webp'}),
        help_text='PDF, JPG, PNG o WebP. Máximo 4 MB.')

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        if archivo.size > MAX_BYTES:
            raise forms.ValidationError('El archivo supera los 4 MB.')
        contenido = archivo.read(MAX_BYTES + 1)
        if len(contenido) > MAX_BYTES:
            raise forms.ValidationError('El archivo supera los 4 MB.')
        if re.match(rb'%PDF-[12]\.\d(?:\r\n|\r|\n)', contenido) and contenido.rstrip().endswith(b'%%EOF'):
            tipo = 'application/pdf'
        else:
            try:
                with Image.open(BytesIO(contenido), formats=list(IMAGENES)) as imagen:
                    if imagen.width * imagen.height > 25_000_000:
                        raise forms.ValidationError('La imagen supera los 25 megapíxeles.')
                    tipo = IMAGENES[imagen.format]
                    imagen.verify()
            except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
                raise forms.ValidationError('Suba un PDF o una imagen JPG, PNG o WebP válida.') from None
        base = re.sub(r'[\x00-\x1f\x7f]', '', PurePath(archivo.name).stem).strip()[:250]
        return (base or 'documento-firmado') + EXTENSIONES[tipo], tipo, contenido


def movimientos_de_cuenta(pk):
    return MovimientoVacacion.objects.filter(cuenta_id=pk, cuenta__eliminada=False).exclude(codigo='09')


@never_cache
@login_required
@permission_required(['control.view_cuentavacacion', 'control.change_cuentavacacion'], raise_exception=True)
@require_http_methods(['GET', 'POST'])
def subir(request, pk, movimiento):
    movimientos = movimientos_de_cuenta(pk)
    registro = get_object_or_404(movimientos, pk=movimiento)
    form = EvidenciaForm(request.POST, request.FILES) if request.method == 'POST' else EvidenciaForm()
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            registro = get_object_or_404(movimientos.select_for_update(), pk=movimiento)
            nombre, tipo, contenido = form.cleaned_data['archivo']
            _, creada = EvidenciaVacacion.objects.get_or_create(movimiento=registro,
                defaults={'nombre': nombre, 'tipo_mime': tipo, 'contenido': contenido})
            if creada:
                registrar(registro, request.user, 'subir_evidencia', snapshot(registro),
                          {'archivo': nombre, 'tipo_mime': tipo})
                messages.success(request, 'Documento firmado guardado.')
            else:
                messages.info(request, 'El movimiento ya tiene evidencia guardada.')
        return redirect('vacacion_ficha', pk=pk)
    if EvidenciaVacacion.objects.filter(movimiento=registro).exists():
        return redirect('vacacion_evidencia_ver', pk=pk, movimiento=movimiento)
    return render(request, 'control/vacaciones/evidencia.html', {
        'form': form, 'registro': registro, 'titulo': 'Subir evidencia', 'tipo': 'control_vacaciones',
    })


@never_cache
@login_required
@permission_required('control.view_cuentavacacion', raise_exception=True)
@require_safe
def ver(request, pk, movimiento):
    evidencia = get_object_or_404(EvidenciaVacacion, movimiento_id=movimiento,
                                  movimiento__in=movimientos_de_cuenta(pk))
    response = HttpResponse(bytes(evidencia.contenido), content_type=evidencia.tipo_mime)
    response['Content-Disposition'] = content_disposition_header(False, evidencia.nombre)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
    return response
