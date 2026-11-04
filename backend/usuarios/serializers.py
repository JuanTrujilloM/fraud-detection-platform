from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class LoginSerializer(TokenObtainPairSerializer):
    """Agrega el rol al token y a la respuesta, para que el frontend redirija sin otra petición."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        return token

    def validate(self, attrs):
        datos = super().validate(attrs)
        datos['usuario'] = self._datos_usuario(self.user)
        return datos

    @staticmethod
    def _datos_usuario(usuario) -> dict:
        datos = {'id': usuario.id, 'username': usuario.username, 'rol': usuario.rol}
        comercio = getattr(usuario, 'comercio', None)
        if comercio:
            datos['nombre'] = comercio.nombre
            datos['vende_en_linea'] = comercio.vende_en_linea
        asociado = getattr(usuario, 'asociado', None)
        if asociado:
            datos['nombre'] = str(asociado)
        return datos
