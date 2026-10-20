from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path('ingresar/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('salir/', auth_views.LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('', include('control.urls')),
]
