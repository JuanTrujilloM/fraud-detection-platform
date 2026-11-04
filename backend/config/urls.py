from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('usuarios.urls')),
    path('api/', include('autorizaciones.urls')),
    path('api/', include('tarjetas.urls')),
    path('api/', include('alertas.urls')),
    path('api/', include('portal.urls')),
]
