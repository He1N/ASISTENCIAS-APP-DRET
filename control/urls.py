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
