from django.urls import path

from tarjetas.views import BloqueosView, LevantarBloqueoView

urlpatterns = [
    path('bloqueos/', BloqueosView.as_view(), name='bloqueos'),
    path('bloqueos/<int:pk>/levantar/', LevantarBloqueoView.as_view(), name='bloqueos-levantar'),
]
