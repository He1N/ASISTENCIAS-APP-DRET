from django.urls import path
from . import views

urlpatterns = [path('', views.inicio, name='inicio')]
for tipo, ruta in [('trabajadores', 'trabajadores'), ('documentos', 'catalogos/documentos'),
                   ('operaciones', 'catalogos/operaciones'), ('periodos', 'periodos')]:
    urlpatterns += [
        path(ruta + '/', views.maestro_lista, {'tipo': tipo}, name='maestro_lista'),
        path(ruta + '/nuevo/', views.maestro_formulario, {'tipo': tipo}, name='maestro_nuevo'),
        path(ruta + '/<int:pk>/', views.maestro_detalle, {'tipo': tipo}, name='maestro_detalle'),
        path(ruta + '/<int:pk>/editar/', views.maestro_formulario, {'tipo': tipo}, name='maestro_editar'),
    ]

from . import justificacion_views as justificaciones
urlpatterns += [
    path('consultas/', justificaciones.consultas, name='consultas'),
    path('justificaciones/nueva/', justificaciones.justificacion_formulario, name='justificacion_nueva'),
    path('justificaciones/<int:pk>/', justificaciones.justificacion_detalle, name='justificacion_detalle'),
    path('justificaciones/<int:pk>/editar/', justificaciones.justificacion_formulario, name='justificacion_editar'),
    path('justificaciones/<int:pk>/anular/', justificaciones.justificacion_anular, name='justificacion_anular'),
    path('autocompletar/<str:campo>/', justificaciones.autocompletar, name='autocompletar'),
]

from . import excel_views, reportes
from . import vacaciones_views as vacaciones_control
urlpatterns += [
    path('control-vacaciones/', vacaciones_control.lista, name='vacacion_lista'),
    path('control-vacaciones/nuevo/', vacaciones_control.editar, name='vacacion_nueva'),
    path('control-vacaciones/exportar/', vacaciones_control.exportar, name='vacacion_exportar'),
    path('control-vacaciones/<int:pk>/', vacaciones_control.ficha, name='vacacion_ficha'),
    path('control-vacaciones/<int:pk>/exportar/', vacaciones_control.exportar, name='vacacion_exportar_individual'),
    path('control-vacaciones/<int:pk>/editar/', vacaciones_control.editar, name='vacacion_editar'),
    path('control-vacaciones/<int:pk>/eliminar/', vacaciones_control.eliminar, name='vacacion_eliminar'),
    path('control-vacaciones/<int:pk>/movimiento/<int:movimiento>/eliminar/', vacaciones_control.eliminar, name='vacacion_movimiento_eliminar'),
    path('control-vacaciones/<int:pk>/nuevo/', vacaciones_control.editar, {'nuevo':True}, name='vacacion_movimiento_nuevo'),
    path('control-vacaciones/<int:pk>/movimiento/<int:movimiento>/', vacaciones_control.editar, name='vacacion_movimiento_editar'),
    path('vacaciones/', reportes.especiales, {'grupo': 'VACACIONES'}, name='vacaciones'),
    path('licencias-sindicales/', reportes.especiales, {'grupo': 'SINDICAL'}, name='sindicales'),
    path('vacaciones/exportar/', reportes.especiales, {'grupo': 'VACACIONES', 'exportar': True}, name='exportar_vacaciones'),
    path('licencias-sindicales/exportar/', reportes.especiales, {'grupo': 'SINDICAL', 'exportar': True}, name='exportar_sindicales'),
    path('consultas/exportar/', reportes.exportar_consultas, name='exportar_consultas'),
    path('periodos/exportar/', reportes.exportar_periodos, name='exportar_periodos'),
    path('importar/', excel_views.importar_excel, name='importar_excel'),
    path('importar/<int:pk>/', excel_views.importacion_revisar, name='importacion_revisar'),
    path('importar/<int:pk>/resumen/', excel_views.importacion_resumen, name='importacion_resumen'),
]
