from django import forms
from django.db.models import Q
from .models import Justificacion, Trabajador, PeriodoAsistencia, TipoDocumento, TipoOperacion, normalizar


class EstiloForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})
                field.input_formats = ['%Y-%m-%d', '%d/%m/%Y']
            elif isinstance(field, forms.TimeField):
                field.widget = forms.TimeInput(format='%H:%M', attrs={'type': 'time'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 3


class TrabajadorForm(EstiloForm):
    confirmar_coincidencias = forms.BooleanField(required=False, label='He revisado las coincidencias; conservar esta ficha independiente')
    class Meta:
        model = Trabajador
        fields = ['apellidos_nombres', 'dni', 'area', 'activo']
    def clean_dni(self):
        value = self.cleaned_data['dni']
        if value and (not value.isdigit() or len(value) != 8):
            raise forms.ValidationError('El DNI debe contener 8 dígitos o quedar vacío.')
        return value or None
    def clean(self):
        data = super().clean()
        q = Q(nombre_busqueda=normalizar(data.get('apellidos_nombres')))
        if data.get('dni'):
            q |= Q(dni=data['dni'])
        matches = Trabajador.objects.filter(q).exclude(pk=self.instance.pk)
        if matches.exists() and not data.get('confirmar_coincidencias'):
            self.add_error('confirmar_coincidencias', 'Hay fichas coincidentes: ' + '; '.join(f'#{x.pk} {x.apellidos_nombres}' for x in matches[:5]) + '. Revise si corresponde reactivar una ficha existente.')
        return data


class PeriodoForm(EstiloForm):
    autorizar_solapamiento = forms.BooleanField(required=False, label='Autorizar solapamiento y explicar la excepción en notas')
    class Meta:
        model = PeriodoAsistencia
        fields = ['titulo', 'fecha_inicio', 'fecha_fin', 'estado', 'notas']
    def clean(self):
        d = super().clean()
        if d.get('fecha_inicio'):
            qs = PeriodoAsistencia.objects.exclude(pk=self.instance.pk).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=d['fecha_inicio']))
            if d.get('fecha_fin'):
                qs = qs.filter(fecha_inicio__lte=d['fecha_fin'])
            if qs.exists() and not (d.get('autorizar_solapamiento') and d.get('notas')):
                self.add_error('autorizar_solapamiento', 'El rango se solapa con otro periodo. Revise y motive la excepción.')
        return d


class DocumentoForm(EstiloForm):
    class Meta:
        model = TipoDocumento
        fields = ['nombre', 'codigo_externo', 'activo']


class OperacionForm(EstiloForm):
    class Meta:
        model = TipoOperacion
        fields = ['nombre', 'codigo_externo', 'requiere_fecha_final', 'grupo_especial', 'activo']
