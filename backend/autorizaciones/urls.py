from django.urls import path

from autorizaciones.views import AutorizarCompraView, HistorialComercioView

urlpatterns = [
    path('autorizaciones/', AutorizarCompraView.as_view(), name='autorizaciones'),
    path(
        'comercio/autorizaciones/',
        HistorialComercioView.as_view(),
        name='comercio-autorizaciones',
    ),
]
