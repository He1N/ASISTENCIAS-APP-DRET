"""Búsquedas acotadas compartidas por widgets y endpoint autenticado."""
from django import forms
from django.db.models import Q
from django.urls import reverse
from .models import Trabajador, TipoDocumento, TipoOperacion, normalizar

MODELOS = {'trabajador': Trabajador, 'tipo_documento': TipoDocumento, 'tipo_operacion': TipoOperacion}


def buscar_opciones(model, term, incluir_inactivos=False, grupo=None):
    qs = model.objects.all()
    if model is not Trabajador and not incluir_inactivos:
        qs = qs.filter(activo=True)
    if model is TipoOperacion and grupo in ('VACACIONES', 'SINDICAL'):
        qs = qs.filter(grupo_especial=grupo)
    if term:
        predicate = Q(nombre_busqueda__contains=normalizar(term))
        predicate |= Q(dni__contains=term) if model is Trabajador else Q(codigo_externo__icontains=term)
        qs = qs.filter(predicate)
    nombre = 'apellidos_nombres' if model is Trabajador else 'nombre'
    return qs.order_by('-activo', nombre, 'pk')[:20]


def etiqueta(obj):
    estado = 'Activo' if obj.activo else 'Inactivo'
    dni = f' · DNI {obj.dni}' if isinstance(obj, Trabajador) and obj.dni else ''
    return f'#{obj.pk} {obj}{dni} · {estado}'


class BusquedaSelect(forms.Select):
    template_name = 'control/widgets/busqueda_select.html'

    def __init__(self, campo, termino='', modo='alta', *args, **kwargs):
        self.campo, self.termino, self.modo = campo, termino, modo
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        nombres = {'trabajador': 'trabajador', 'tipo_documento': 'tipo de documento', 'tipo_operacion': 'tipo de operación'}
        ctx.update(campo=self.campo, nombre_busqueda=nombres[self.campo], termino=self.termino, modo=self.modo,
                   endpoint=reverse('autocompletar', kwargs={'campo': self.campo}))
        return ctx


def configurar_busquedas(form, parametros, modo='alta', grupo=None):
    for campo, model in MODELOS.items():
        field = form.fields[campo]
        seleccionado = form.data.get(campo) if form.is_bound else form.initial.get(campo)
        term = str(parametros.get(campo + '_buscar', ''))[:250].strip()
        options = list(buscar_opciones(model, term, incluir_inactivos=modo == 'consulta', grupo=grupo))
        current = None
        if seleccionado and str(seleccionado).isdigit():
            current = field.queryset.filter(pk=seleccionado).first()
        if current and current.pk not in [obj.pk for obj in options]:
            options.insert(0, current)
        widget = BusquedaSelect(campo, term, modo)
        if grupo and campo == 'tipo_operacion':
            widget.attrs['data-grupo'] = grupo
        field.widget = widget
        widget.choices = [('', 'Seleccione…')] + [(obj.pk, etiqueta(obj)) for obj in options]
