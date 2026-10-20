from .models import HistorialCambio


def snapshot(obj):
    return {f.name: (str(getattr(obj, f.attname)) if getattr(obj, f.attname) is not None else None)
            for f in obj._meta.concrete_fields if f.name not in {'nombre_busqueda', 'updated_at', 'created_at', 'datos_temporales'}}


def registrar(obj, user, accion, antes=None):
    despues = snapshot(obj)
    cambios = {k: {'antes': (antes or {}).get(k), 'despues': v} for k, v in despues.items() if (antes or {}).get(k) != v}
    HistorialCambio.objects.create(entidad=obj._meta.model_name, objeto_id=obj.pk, accion=accion, autor=user, cambios=cambios)
