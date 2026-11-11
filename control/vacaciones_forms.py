from decimal import Decimal
from django import forms
from .forms import EstiloForm
from .models import CuentaVacacion, MovimientoVacacion


class CuentaForm(EstiloForm):
    version = forms.CharField(widget=forms.HiddenInput, required=False)
    motivo = forms.CharField(widget=forms.Textarea, label='Motivo del cambio')
    def clean_regimen_laboral(self):
        from .regimenes import normalizar_regimen
        return normalizar_regimen(self.cleaned_data['regimen_laboral'])
    class Meta:
        model = CuentaVacacion
        fields = ['dni','nombre','regimen_laboral','tipo','estado','habilitada','notas']

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['version'].initial = self.instance.updated_at.isoformat() if self.instance.pk else ''
        for year in range(2022,2031):
            self.fields[f'anio_{year}'] = forms.DecimalField(label=f'Asignación {year}', required=False,
                min_value=0, max_value=99999, decimal_places=2, initial=self.instance.asignaciones.get(str(year)))



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

    def clean(self):
        d=super().clean()
        if d.get('fin') and d.get('inicio') and d['fin']<d['inicio']:
            self.add_error('fin','La fecha final es anterior al inicio.')
        if d.get('dias') is not None and d['dias']<0:
            self.add_error('dias','Los días no pueden ser negativos.')
        if d.get('permiso_ley') is not None and d['permiso_ley']<0:
            self.add_error('permiso_ley','El permiso no puede ser negativo.')
        if d.get('estado')=='VIGENTE' and d.get('dias') is None:
            self.add_error('dias','Confirme los días antes de activar el movimiento.')
        # Un código desconocido nunca calcula días automáticamente. La persona
        # responsable puede confirmar una cantidad explícita con motivo auditado.
        return d
