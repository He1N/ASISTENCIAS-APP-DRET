from django.contrib import admin
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import User, Group
from django.utils import timezone
from .models import Trabajador, TipoDocumento, TipoOperacion, PeriodoAsistencia, HistorialCambio
from .forms import TrabajadorForm, DocumentoForm, OperacionForm, PeriodoForm
from .audit import registrar, snapshot

admin.site.site_header = 'Control de Asistencias — DRET'
admin.site.site_title = 'DRET'
admin.site.index_title = 'Administración'

class AuditadoAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'updated_at')
    def has_delete_permission(self, request, obj=None):
        return False
    def save_model(self, request, obj, form, change):
        antes = snapshot(type(obj).objects.get(pk=obj.pk)) if change else None
        if isinstance(obj, PeriodoAsistencia):
            if obj.estado in ('CERRADO', 'PROCESADO') and not obj.fecha_cierre:
                obj.fecha_cierre = timezone.now()
            if obj.estado == 'PROCESADO' and not obj.fecha_procesamiento:
                obj.fecha_procesamiento = timezone.now()
        super().save_model(request, obj, form, change)
        registrar(obj, request.user, 'editar' if change else 'crear', antes)

@admin.register(Trabajador)
class TrabajadorAdmin(AuditadoAdmin):
    form = TrabajadorForm
    list_display = ('apellidos_nombres', 'dni', 'area', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre_busqueda', 'dni')
    ordering = ('-activo', 'apellidos_nombres', 'pk')
    def get_search_results(self, request, queryset, search_term):
        from .models import normalizar
        return super().get_search_results(request, queryset, normalizar(search_term))

class CatalogoAdmin(AuditadoAdmin):
    list_display = ('nombre', 'codigo_externo', 'activo')
    search_fields = ('nombre_busqueda', 'codigo_externo')
    list_filter = ('activo',)
    def get_search_results(self, request, queryset, search_term):
        from .models import normalizar
        return super().get_search_results(request, queryset, normalizar(search_term))

@admin.register(TipoDocumento)
class DocumentoAdmin(CatalogoAdmin):
    form = DocumentoForm

@admin.register(TipoOperacion)
class OperacionAdmin(CatalogoAdmin):
    form = OperacionForm
    list_display = ('nombre', 'codigo_externo', 'requiere_fecha_final', 'grupo_especial', 'activo')

@admin.register(PeriodoAsistencia)
class PeriodoAdmin(AuditadoAdmin):
    form = PeriodoForm
    list_display = ('titulo', 'fecha_inicio', 'fecha_fin', 'estado', 'fecha_cierre', 'fecha_procesamiento')
    list_filter = ('estado',)
    readonly_fields = AuditadoAdmin.readonly_fields + ('fecha_cierre', 'fecha_procesamiento')

@admin.register(HistorialCambio)
class HistorialAdmin(admin.ModelAdmin):
    list_display = ('entidad', 'objeto_id', 'accion', 'autor', 'fecha')
    readonly_fields = ('entidad', 'objeto_id', 'accion', 'autor', 'fecha', 'cambios')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

class SoloAdministrador:
    def autorizado(self, request):
        return request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    def has_module_permission(self, request): return self.autorizado(request)
    def has_view_permission(self, request, obj=None): return self.autorizado(request)
    def has_add_permission(self, request): return self.autorizado(request)
    def has_change_permission(self, request, obj=None): return self.autorizado(request)
    def has_delete_permission(self, request, obj=None): return False

admin.site.unregister(User)
admin.site.unregister(Group)
@admin.register(User)
class UsuarioAdmin(SoloAdministrador, UserAdmin): pass
@admin.register(Group)
class GrupoAdmin(SoloAdministrador, GroupAdmin): pass
