from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models


class UsuarioManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('rol', Usuario.Rol.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """Usuario de Django con un rol. `is_active` y `last_login` son el activo y último login."""

    class Rol(models.TextChoices):
        COMERCIO = 'COMERCIO', 'Comercio'
        ASOCIADO = 'ASOCIADO', 'Asociado'
        ANALISTA = 'ANALISTA', 'Analista'
        ADMIN = 'ADMIN', 'Administrador'

    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.ASOCIADO)

    objects = UsuarioManager()

    class Meta(AbstractUser.Meta):
        db_table = 'usuario'

    def save(self, *args, **kwargs):
        # El rol ADMIN es el que opera el admin de Django, con acceso completo a su CRUD.
        es_admin = self.rol == self.Rol.ADMIN
        self.is_staff = es_admin
        self.is_superuser = es_admin
        super().save(*args, **kwargs)


validar_celular = RegexValidator(r'^\+?\d{7,15}$', 'Ingresa un celular válido.')


class Asociado(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    class TipoDocumento(models.TextChoices):
        CC = 'CC', 'Cédula de ciudadanía'
        CE = 'CE', 'Cédula de extranjería'
        PA = 'PA', 'Pasaporte'

    usuario = models.OneToOneField(Usuario, on_delete=models.PROTECT, related_name='asociado')
    tipo_documento = models.CharField(max_length=2, choices=TipoDocumento.choices)
    numero_documento = models.CharField(max_length=20, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField()
    ciudad = models.CharField(max_length=80)
    celular = models.CharField(max_length=16, validators=[validar_celular])
    email = models.EmailField()
    ingreso_anual = models.DecimalField(max_digits=14, decimal_places=2)
    puntaje_crediticio = models.PositiveSmallIntegerField()
    fecha_afiliacion = models.DateField()
    estado = models.CharField(max_length=8, choices=Estado.choices, default=Estado.ACTIVO)
    # Columna de marca de agua: la ingesta por batch extrae lo que cambió desde la última corrida.
    fecha_actualizacion = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        db_table = 'asociado'
        ordering = ['apellidos', 'nombres']

    def __str__(self):
        return f'{self.nombres} {self.apellidos}'


class Comercio(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        BLOQUEADO = 'BLOQUEADO', 'Bloqueado'

    class Categoria(models.TextChoices):
        SUPERMERCADO = 'SUPERMERCADO', 'Supermercado'
        RESTAURANTE = 'RESTAURANTE', 'Restaurante'
        COMBUSTIBLE = 'COMBUSTIBLE', 'Combustible'
        ELECTRONICA = 'ELECTRONICA', 'Electrónica'
        ROPA = 'ROPA', 'Ropa'
        FARMACIA = 'FARMACIA', 'Farmacia'
        VIAJES = 'VIAJES', 'Viajes'
        ENTRETENIMIENTO = 'ENTRETENIMIENTO', 'Entretenimiento'
        SERVICIOS_PUBLICOS = 'SERVICIOS_PUBLICOS', 'Servicios públicos'
        HOGAR = 'HOGAR', 'Hogar'
        TRANSPORTE = 'TRANSPORTE', 'Transporte'
        OTROS = 'OTROS', 'Otros'

    usuario = models.OneToOneField(Usuario, on_delete=models.PROTECT, related_name='comercio')
    nombre = models.CharField(max_length=150)
    nit = models.CharField(max_length=20, unique=True)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    ciudad = models.CharField(max_length=80)
    vende_en_linea = models.BooleanField(default=False)
    estado = models.CharField(
        max_length=9,
        choices=Estado.choices,
        default=Estado.ACTIVO,
        help_text='Acceso rápido. Para bloquear con historial usa la consola del analista.',
    )

    # Columna de marca de agua: la ingesta por batch extrae lo que cambió desde la última corrida.
    fecha_actualizacion = models.DateTimeField(auto_now=True, db_index=True)
    class Meta:
        db_table = 'comercio'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
