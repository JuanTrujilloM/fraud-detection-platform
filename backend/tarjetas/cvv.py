"""Hash del CVV.

Se usa HMAC-SHA256 con una llave del servidor y no PBKDF2 (make_password): corre dentro de la
transacción que tiene la fila de la tarjeta bloqueada, así que no puede tardar cientos de ms. Con
solo mil CVV posibles, un hash lento sin llave tampoco resistiría; lo que protege es la llave, que
vive fuera de la base de datos. El número de la tarjeta actúa como sal.
"""

from django.conf import settings
from django.utils.crypto import constant_time_compare, salted_hmac


def _calcular(numero: str, cvv: str) -> str:
    return salted_hmac(numero, cvv, secret=settings.CVV_HMAC_KEY, algorithm='sha256').hexdigest()


def hashear_cvv(numero: str, cvv: str) -> str:
    return _calcular(numero, cvv)


def cvv_coincide(numero: str, cvv: str, cvv_hash: str) -> bool:
    return constant_time_compare(_calcular(numero, cvv), cvv_hash)
