from django import forms
from django.conf import settings
from openpyxl.utils import column_index_from_string
from .models import PeriodoAsistencia
from .xlsx_parser import CAMPOS, limite_archivo_texto


class SubirExcelForm(forms.Form):
    archivo = forms.FileField(label='Archivo XLSX')
    periodo = forms.ModelChoiceField(label='Periodo administrativo', queryset=PeriodoAsistencia.objects.all())
    encabezado = forms.IntegerField(label='Primera fila de encabezado', min_value=1, max_value=50, initial=2)
    primera_fila = forms.IntegerField(label='Primera fila de datos', min_value=2, max_value=100, initial=5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['archivo'].label = f'Archivo XLSX (máximo {limite_archivo_texto()})'
        for key, nombre in CAMPOS.items():
            self.fields['col_' + key] = forms.CharField(label=nombre + ' — columna', required=False,
                max_length=2, help_text='Opcional: letra para sustituir la detección del encabezado.')

    def clean_archivo(self):
        file = self.cleaned_data['archivo']
        if file.size > settings.XLSX_UPLOAD_MAX_BYTES or not file.name.lower().endswith('.xlsx'):
            raise forms.ValidationError(f'Seleccione un .xlsx de hasta {limite_archivo_texto()}.')
        return file

    def clean(self):
        data = super().clean()
        if data.get('primera_fila', 0) <= data.get('encabezado', 0):
            self.add_error('primera_fila', 'Los datos deben empezar después del encabezado.')
        for key in CAMPOS:
            value = data.get('col_' + key)
            if value:
                try:
                    if not value.isalpha() or column_index_from_string(value.upper()) > 64:
                        raise ValueError
                except ValueError:
                    self.add_error('col_' + key, 'Use una columna entre A y BL.')
        return data


class SeleccionarHojaForm(forms.Form):
    hoja = forms.ChoiceField(label='Hoja de registros')
    conservar_cud = forms.BooleanField(label='Conservar CUD de la hoja (octubre histórico de 2026 siempre se omite)',
                                     required=False, initial=True)
    def __init__(self, *args, hojas, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hoja'].choices = [(key, f'{key} ({len(value["filas"])} filas)') for key, value in hojas.items() if value.get('filas')]
