from django.urls import path

from alertas.views import (
    AlertaDetalleView,
    AlertaStreamingView,
    AlertasView,
    ResolverAlertaView,
)

urlpatterns = [
    path('alertas/', AlertasView.as_view(), name='alertas'),
    path('alertas/streaming/', AlertaStreamingView.as_view(), name='alertas-streaming'),
    path('alertas/<int:pk>/', AlertaDetalleView.as_view(), name='alertas-detalle'),
    path('alertas/<int:pk>/resolver/', ResolverAlertaView.as_view(), name='alertas-resolver'),
]
