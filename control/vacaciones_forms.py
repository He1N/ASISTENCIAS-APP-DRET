from decimal import Decimal
from django import forms
from .forms import EstiloForm
from .models import CuentaVacacion, MovimientoVacacion


class CuentaForm(EstiloForm):
    ley276_automatico = forms.BooleanField(label='Calcular Ley 276 automáticamente (3 días por año)', required=False)

    version = forms.CharField(widget=forms.HiddenInput, required=False)
    motivo = forms.CharField(widget=forms.Textarea, label='Motivo del cambio')
    def clean_regimen_laboral(self):
        from .regimenes import normalizar_regimen
        return normalizar_regimen(self.cleaned_data['regimen_laboral'])
    class Meta:
        model = CuentaVacacion
        fields = ['dni','nombre','regimen_laboral','condicion_laboral','fin_contrato','asignacion_ley276','tipo','estado','habilitada','notas']

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['version'].initial = self.instance.updated_at.isoformat() if self.instance.pk else ''
        from .vacaciones import asignacion_ley276_automatica
        manual=self.instance.asignacion_ley276
        self.initial['ley276_automatico']=manual is None
        self.initial['asignacion_ley276']=asignacion_ley276_automatica(self.instance) if manual is None else manual
        self.fields['asignacion_ley276'].help_text='Solo se aplica a DEC. LEG. 276. Al editar este total se desactiva el cálculo automático; puede volver a activarlo con la casilla.'
        self.fields['asignacion_ley276'].min_value=0

        for year in range(2022,2031):
            self.fields[f'anio_{year}'] = forms.DecimalField(label=f'Asignación {year}', required=False,
                min_value=0, max_value=99999, decimal_places=2, initial=self.instance.asignaciones.get(str(year)))

        order=list(self.fields)
        order.remove('ley276_automatico');order.insert(order.index('asignacion_ley276'),'ley276_automatico')
        self.order_fields(order)

    def clean(self):
        data=super().clean()
        if self.is_bound and not any(key in self.data for key in ('ley276_automatico','asignacion_ley276')):
            # Compatibilidad con formularios abiertos antes de esta actualización.
            data['asignacion_ley276']=self.instance.asignacion_ley276
        elif data.get('ley276_automatico'):
            data['asignacion_ley276']=None
        elif data.get('asignacion_ley276') is None and 'asignacion_ley276' not in self.errors:
            self.add_error('asignacion_ley276','Indique el total manual o active el cálculo automático.')
        return data


class MovimientoForm(EstiloForm):
    version = forms.CharField(widget=forms.HiddenInput, required=False)
    class Meta:
        model = MovimientoVacacion
        fields = ['cuenta','periodo','codigo','fecha','inicio','fin','dias','permiso_ley','observaciones',
                  'estado','motivo']

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['version'].initial = self.instance.updated_at.isoformat() if self.instance.pk else ''
        self.fields['cuenta'].queryset = CuentaVacacion.objects.filter(eliminada=False)
        self.fields['motivo'].required=True
        self.fields['dias'].min_value=0
        self.fields['permiso_ley'].min_value=0
        self.fields['permiso_ley'].label='Días de permiso Ley 276 (código 09)'
        self.fields['permiso_ley'].help_text='Se descuentan únicamente del saldo Ley 276. Si no hay cantidad registrada, no se descuenta.'

    def clean(self):
        d=super().clean()
        if d.get('fin') and d.get('inicio') and d['fin']<d['inicio']:
            self.add_error('fin','La fecha final es anterior al inicio.')
        if d.get('dias') is not None and d['dias']<0:
            self.add_error('dias','Los días no pueden ser negativos.')
        if d.get('permiso_ley') is not None and d['permiso_ley']<0:
            self.add_error('permiso_ley','El permiso no puede ser negativo.')
        if d.get('estado')=='VIGENTE' and d.get('codigo')!='09' and d.get('dias') is None:
            self.add_error('dias','Confirme los días antes de activar el movimiento.')
        # Un código desconocido nunca calcula días automáticamente. La persona
        # responsable puede confirmar una cantidad explícita con motivo auditado.
        return d
