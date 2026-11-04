from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from eventos.contexto import obtener_contexto
from eventos.servicios import registrar_evento
from usuarios.serializers import LoginSerializer


def _motivo_fallo(username: str | None):
    """Usuario intentado y motivo. Solo van al log: al cliente se le responde igual."""
    usuario = get_user_model().objects.filter(username=username).first() if username else None
    if usuario is None:
        return None, 'USUARIO_INEXISTENTE'
    if not usuario.is_active:
        return usuario, 'USUARIO_INACTIVO'
    return usuario, 'CONTRASENA_INVALIDA'


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/. Cada intento, exitoso o fallido, registra INICIO_SESION."""

    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        contexto = obtener_contexto(request)
        datos_contexto = {
            'ip': contexto.ip,
            'tipo_dispositivo': contexto.tipo_dispositivo,
            'navegador': contexto.navegador,
            'sistema_operativo': contexto.sistema_operativo,
        }
        try:
            respuesta = super().post(request, *args, **kwargs)
        except (AuthenticationFailed, InvalidToken, TokenError):
            usuario, motivo = _motivo_fallo(request.data.get('username'))
            registrar_evento(
                'INICIO_SESION',
                'portal',
                usuario,
                {'exitoso': False, 'motivo_fallo': motivo, **datos_contexto},
            )
            raise

        usuario = get_user_model().objects.get(pk=respuesta.data['usuario']['id'])
        registrar_evento(
            'INICIO_SESION',
            'portal',
            usuario,
            {'exitoso': True, 'motivo_fallo': None, **datos_contexto},
        )
        return respuesta
