from django.urls import path

from portal import views

urlpatterns = [
    path('asociado/tarjetas/', views.MisTarjetasView.as_view(), name='asociado-tarjetas'),
    path(
        'asociado/tarjetas/<int:pk>/autorizaciones/',
        views.MovimientosView.as_view(),
        name='asociado-movimientos',
    ),
    path(
        'asociado/tarjetas/<int:pk>/bloquear/',
        views.BloquearMiTarjetaView.as_view(),
        name='asociado-bloquear',
    ),
    path(
        'asociado/tarjetas/<int:pk>/desbloquear/',
        views.DesbloquearMiTarjetaView.as_view(),
        name='asociado-desbloquear',
    ),
    path('asociado/reclamos/', views.MisReclamosView.as_view(), name='asociado-reclamos'),
    path('asociado/perfil/', views.PerfilView.as_view(), name='asociado-perfil'),
    path('reclamos/', views.ReclamosView.as_view(), name='reclamos'),
    path('reclamos/<int:pk>/', views.ReclamoDetalleView.as_view(), name='reclamos-detalle'),
]
