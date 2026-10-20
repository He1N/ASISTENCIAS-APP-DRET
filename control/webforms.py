from django import forms
from .forms import TrabajadorForm, DocumentoForm, OperacionForm, PeriodoForm
from .models import PeriodoAsistencia


class VersionFormulario:
    """Evita reemplazar sin aviso una ficha editada desde otra sesión."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['version'] = forms.CharField(
                widget=forms.HiddenInput, initial=self.instance.updated_at.isoformat())


class TrabajadorWebForm(VersionFormulario, TrabajadorForm):
    pass


class DocumentoWebForm(VersionFormulario, DocumentoForm):
    pass


class OperacionWebForm(VersionFormulario, OperacionForm):
    pass


class PeriodoWebForm(VersionFormulario, PeriodoForm):
    pass


class FiltroMaestros(forms.Form):
    q = forms.CharField(label='Buscar', required=False, max_length=250)
    activo = forms.ChoiceField(label='Estado', required=False,
        choices=[('', 'Todos'), ('1', 'Activos'), ('0', 'Inactivos')])


class FiltroPeriodos(forms.Form):
    q = forms.CharField(label='Título o notas', required=False, max_length=250)
    estado = forms.ChoiceField(label='Estado', required=False,
        choices=[('', 'Todos')] + PeriodoAsistencia.ESTADOS)
