from django import forms
from django.db.models import Q
from .autocomplete import configurar_busquedas
from .forms import EstiloForm
from .models import Justificacion, Trabajador, PeriodoAsistencia, TipoDocumento, TipoOperacion
from .webforms import VersionFormulario


class JustificacionForm(VersionFormulario, EstiloForm):
    motivo_excepcion = forms.CharField(label='Motivo de excepción de rango', required=False,
        max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    motivo_edicion = forms.CharField(label='Motivo de corrección', required=False,
        max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = Justificacion
        fields = ['trabajador', 'periodo', 'tipo_documento', 'tipo_operacion',
                  'fecha_movimiento', 'fecha_final', 'hora_salida', 'hora_retorno',
                  'cud', 'observaciones', 'fecha_recepcion']

    def __init__(self, *args, parametros=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cud'].strip = False
        self.fields['fecha_movimiento'].required = self.instance.fuente == 'MANUAL'
        self.fields['hora_salida'].input_formats = ['%H:%M', '%H:%M:%S']
        self.fields['hora_retorno'].input_formats = ['%H:%M', '%H:%M:%S']
        if self.instance.pk:
            self.fields['motivo_edicion'].required = True
        else:
            del self.fields['motivo_edicion']
        # Un catálogo inactivo puede conservarse en su registro histórico, pero
        # no se asigna a una nueva justificación ni a otra ficha.
        for campo, model in [('tipo_documento', TipoDocumento), ('tipo_operacion', TipoOperacion)]:
            anterior = getattr(self.instance, campo + '_id', None)
            self.fields[campo].queryset = model.objects.filter(Q(activo=True) | Q(pk=anterior))
        configurar_busquedas(self, parametros or {})
        self.fields['fecha_recepcion'].help_text = 'Opcional. No se deduce de la fecha de movimiento ni de la captura.'
        self.fields['motivo_excepcion'].help_text = 'Obligatorio si el movimiento cae fuera del rango del periodo elegido.'

    def clean(self):
        data = super().clean()
        periodo, fecha = data.get('periodo'), data.get('fecha_movimiento')
        if periodo and fecha and (fecha < periodo.fecha_inicio or (periodo.fecha_fin and fecha > periodo.fecha_fin)):
            if not data.get('motivo_excepcion'):
                self.add_error('motivo_excepcion', 'La fecha está fuera del rango del periodo. Explique la excepción para guardar.')
        return data


class FiltroJustificaciones(forms.Form):
    q = forms.CharField(label='Nombre, DNI, CUD u observaciones', required=False, max_length=250)
    trabajador = forms.ModelChoiceField(label='Trabajador', queryset=Trabajador.objects.all(), required=False)
    dni = forms.CharField(label='DNI (fragmento)', required=False, max_length=20)
    fecha = forms.DateField(label='Fecha de movimiento exacta', required=False)
    desde = forms.DateField(label='Movimiento desde', required=False)
    hasta = forms.DateField(label='Movimiento hasta', required=False)
    periodo = forms.ModelChoiceField(label='Periodo', queryset=PeriodoAsistencia.objects.all(), required=False)
    tipo_documento = forms.ModelChoiceField(label='Tipo de documento', queryset=TipoDocumento.objects.all(), required=False)
    tipo_operacion = forms.ModelChoiceField(label='Tipo de operación', queryset=TipoOperacion.objects.all(), required=False)
    cud = forms.CharField(label='CUD (fragmento)', required=False, max_length=250)
    activo = forms.ChoiceField(label='Estado del trabajador', required=False,
        choices=[('', 'Todos'), ('1', 'Activos'), ('0', 'Inactivos')])
    estado = forms.ChoiceField(label='Estado del registro', required=False,
        choices=[('', 'Vigentes'), ('TODOS', 'Todos'), ('ANULADAS', 'Anuladas')])
    orden = forms.ChoiceField(label='Orden', required=False,
        choices=[('', 'Fecha de movimiento'), ('captura', 'Última captura')])

    def __init__(self, *args, grupo=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})
                field.input_formats = ['%Y-%m-%d', '%d/%m/%Y']
        if grupo:
            self.fields['tipo_operacion'].queryset = self.fields['tipo_operacion'].queryset.filter(grupo_especial=grupo)
        configurar_busquedas(self, self.data, modo='consulta', grupo=grupo)

    def clean(self):
        data = super().clean()
        if data.get('desde') and data.get('hasta') and data['desde'] > data['hasta']:
            self.add_error('hasta', 'La fecha hasta no puede ser anterior a desde.')
        return data


class AnulacionForm(forms.Form):
    motivo = forms.CharField(label='Motivo de anulación', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    version = forms.CharField(widget=forms.HiddenInput)


class FiltroEspecial(FiltroJustificaciones):
    final_desde = forms.DateField(label='Fecha final desde', required=False)
    final_hasta = forms.DateField(label='Fecha final hasta', required=False)
    def clean(self):
        data = super().clean()
        if data.get('final_desde') and data.get('final_hasta') and data['final_desde'] > data['final_hasta']:
            self.add_error('final_hasta', 'La fecha final hasta no puede ser anterior a desde.')
        return data
