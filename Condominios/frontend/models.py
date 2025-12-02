from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import RegexValidator

dni_validator = RegexValidator(
    regex=r'^\d{8}[A-Za-z]$',
    message=_('El DNI debe tener exactamente 8 números y 1 letra (ej. 12345678A).'),
)

telefono_validator = RegexValidator(
    regex=r'^\d{1,10}$',
    message=_('El teléfono solo puede contener números y máximo 10 dígitos.'),
)

# 1. UTILIDADES Y OPCIONES GENERALES

class Documento(models.Model):
    nombre = models.CharField(max_length=255)
    archivo = models.FileField(upload_to='documentos/')
    tipo = models.CharField(max_length=100, blank=True)
    fecha = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.nombre

# --- Opciones para Modelos Nuevos ---
class Prioridad(models.TextChoices):
    BAJA = 'BAJA', 'Baja'
    MEDIA = 'MEDIA', 'Media'
    ALTA = 'ALTA', 'Alta'
    EMERGENCIA = 'EMERGENCIA', 'Emergencia'

class EstadoPago(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    PAGADO = 'PAGADO', 'Pagado'
    VENCIDO = 'VENCIDO', 'Vencido'
    CANCELADO = 'CANCELADO', 'Cancelado'

# 2. GESTIÓN DE USUARIOS Y PERFILES

class Usuario(models.Model):
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('residente', 'Residente'),
        ('guardia', 'Guardia'),
        ('empleado', 'Empleado'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='frontend_profile')
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='residente')

    def __str__(self):
        return f'{self.user.username} ({self.get_rol_display()})'


class Residente(models.Model):
    # TIPO DE RESIDENTE
    PROPIETARIO = 'PR'
    ARRENDATARIO = 'AR'
    FAMILIAR = 'FA'

    TIPO_RESIDENTE_CHOICES = [
        (PROPIETARIO, _('Propietario')),
        (ARRENDATARIO, _('Arrendatario')),
        (FAMILIAR,   _('Familiar/Huésped')),
    ]

    # ESTADO
    ACTIVO = 'AC'
    INACTIVO = 'IN'
    PENDIENTE = 'PE'

    ESTADO_CHOICES = [
        (ACTIVO,   _('Activo')),
        (INACTIVO, _('Inactivo')),
        (PENDIENTE, _('Pendiente')),
    ]

    # --- Datos Personales ---
    nombre_completo = models.CharField(
        max_length=255,
        verbose_name=_('Nombre Completo'),
    )

    # 8 números + 1 letra, no repetido
    dni = models.CharField(
        max_length=9,
        unique=True,
        null=True,
        blank=True,
        validators=[dni_validator],
        verbose_name=_('DNI / Pasaporte'),
    )

    # Solo números, máximo 10 dígitos
    telefono = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        validators=[telefono_validator],
        verbose_name=_('Teléfono'),
    )

    correo_electronico = models.EmailField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Correo Electrónico'),
    )

    fecha_nacimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Fecha de Nacimiento'),
    )

    # --- Datos de Residencia y Estado ---
    tipo_residente = models.CharField(
        max_length=2,
        choices=TIPO_RESIDENTE_CHOICES,
        default=PROPIETARIO,
        verbose_name=_('Tipo de Residente'),
    )

    # OJO: ya SIN unique=True
    unidad_principal = models.CharField(
        max_length=100,
        verbose_name=_('Unidad Principal'),
    )

    estado = models.CharField(
        max_length=2,
        choices=ESTADO_CHOICES,
        default=PENDIENTE,
        verbose_name=_('Estado'),
    )

    espacios_estacionamiento = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Estacionamiento'),
    )

    class Meta:
        db_table = 'frontend_residente'
        verbose_name = _('Residente')
        verbose_name_plural = _('Residentes')
        constraints = [
            models.UniqueConstraint(
                fields=['unidad_principal', 'tipo_residente'],
                name='uniq_unidad_por_tipo',
            ),
            #models.UniqueConstraint(
            #    fields=['espacios_estacionamiento', 'tipo_residente'],
            #    name='uniq_estacionamiento_por_tipo',
            #),
        ]

    def __str__(self):
        return f'{self.nombre_completo} ({self.unidad_principal})'

# 3. PERSONAL Y PROVEEDORES

class Empleado(models.Model):
    nombre_completo = models.CharField(max_length=255)
    dni = models.CharField(max_length=50, unique=True)
    correo_electronico = models.EmailField(null=True, blank=True)
    telefono = models.CharField(max_length=50, null=True, blank=True)
    puesto = models.CharField(max_length=100)
    estado = models.CharField(max_length=20, default='ACTIVO')
    fecha_ingreso = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'frontend_empleado'
        verbose_name = 'Empleado'

    def __str__(self):
        return f"{self.nombre_completo} - {self.puesto}"


class Proveedor(models.Model):
    nombre_empresa = models.CharField(max_length=255)
    rfc_o_taxid = models.CharField(max_length=50, unique=True, null=True, blank=True)
    nombre_contacto = models.CharField(max_length=255, null=True, blank=True)
    telefono_contacto = models.CharField(max_length=50, null=True, blank=True)
    tipo_servicio = models.CharField(max_length=100) # Plomería, Seguridad...
    estado = models.CharField(max_length=20, default='ACTIVO')

    class Meta:
        db_table = 'frontend_proveedor'
        verbose_name = 'Proveedor'

    def __str__(self):
        return self.nombre_empresa

# 4. ADMINISTRACIÓN (Contratos y Tareas)

class Contrato(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, null=True, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, null=True, blank=True)

    tipo_contrato = models.CharField(max_length=250)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    salario_o_costo = models.DecimalField(max_digits=10, decimal_places=2)
    frecuencia_pago = models.CharField(max_length=20)
    archivo_contrato_url = models.CharField(max_length=255, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'gestion_contratos'

    def clean(self):
        if self.empleado and self.proveedor:
            raise ValidationError("Un contrato no puede ser de empleado y proveedor al mismo tiempo.")
        if not self.empleado and not self.proveedor:
            raise ValidationError("Debe asignar el contrato a un Empleado o a un Proveedor.")

class Tarea(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    prioridad = models.CharField(max_length=20, choices=Prioridad.choices, default=Prioridad.MEDIA)
    fecha_limite = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, default='PENDIENTE') # PENDIENTE, COMPLETADA

    class Meta:
        db_table = 'gestion_tareas'

# 5. FINANZAS (Pagos y Cobros)

class Pago(models.Model):
    # Vinculación flexible (Uno de los 3 debe existir)
    residente = models.ForeignKey(Residente, on_delete=models.SET_NULL, null=True, blank=True, related_name='pagos')
    empleado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True, related_name='pagos')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name='pagos')

    # Detalles
    tipo_movimiento = models.CharField(max_length=20, choices=[('INGRESO','Ingreso'), ('EGRESO','Egreso')])
    categoria = models.CharField(max_length=50) # Ej: Cuota, Multa, Nómina
    descripcion = models.CharField(max_length=255)

    # Montos
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Fechas
    fecha_emision = models.DateField()
    fecha_pago = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoPago.choices, default=EstadoPago.PENDIENTE)

    # Comprobantes
    metodo_pago = models.CharField(max_length=50, null=True, blank=True)
    numero_recibo = models.CharField(max_length=100, unique=True, null=True, blank=True)
    comprobante_url = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gestion_pagos'
        verbose_name = 'Pago / Cobro'

    @property
    def saldo_pendiente(self):
        return self.monto_total - self.monto_pagado

    def clean(self):
        # Validar que solo pertenezca a una entidad
        entidades = [self.residente, self.empleado, self.proveedor]
        count = sum(1 for e in entidades if e is not None)
        if count > 1:
            raise ValidationError("El pago no puede asignarse a más de un beneficiario/pagador a la vez.")
        if count == 0:
            raise ValidationError("El pago debe asignarse a un Residente, Empleado o Proveedor.")

# 6. OPERACIONES (Tickets y Áreas Comunes)

class Ticket(models.Model):
    residente = models.ForeignKey(Residente, on_delete=models.CASCADE, related_name='tickets_creados')
    empleado_asignado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True)
    proveedor_asignado = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)

    tipo_solicitud = models.CharField(max_length=100) # Mantenimiento, Queja...
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)
    prioridad = models.CharField(max_length=20, choices=Prioridad.choices, default=Prioridad.MEDIA)
    estado = models.CharField(max_length=20, default='ABIERTO')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gestion_tickets'

class AreaComun(models.Model):
    nombre = models.CharField(max_length=100)
    capacidad_maxima = models.IntegerField()
    costo_reserva = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    requiere_aprobacion = models.BooleanField(default=False)

    class Meta:
        db_table = 'cat_areas_comunes'
        verbose_name = 'Área Común'
        verbose_name_plural = 'Áreas Comunes'

    def __str__(self):
        return self.nombre

class Reserva(models.Model):
    residente = models.ForeignKey(Residente, on_delete=models.CASCADE)
    area = models.ForeignKey(AreaComun, on_delete=models.CASCADE)

    fecha_reserva = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    cantidad_personas = models.IntegerField()
    estado = models.CharField(max_length=20, default='PENDIENTE') # PENDIENTE, APROBADA...

    class Meta:
        db_table = 'reservas_areas'

    def clean(self):
        """
        Validaciones de:
        - hora_inicio < hora_fin
        - fecha_reserva no en el pasado
        - cantidad_personas <= capacidad_maxima del área
        - no empalmar reservas en misma área/fecha/horario
        """
        errors = {}

        # 1) Horas coherentes
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            errors['hora_inicio'] = _("La hora de inicio debe ser anterior a la hora de fin.")

        # 2) Fecha no en el pasado
        if self.fecha_reserva and self.fecha_reserva < timezone.localdate():
            errors['fecha_reserva'] = _("La fecha de la reserva no puede ser en el pasado.")

        # 3) Capacidad máxima del área
        if self.area and self.cantidad_personas is not None:
            if self.cantidad_personas <= 0:
                errors['cantidad_personas'] = _("La cantidad de personas debe ser mayor a cero.")
            elif self.cantidad_personas > self.area.capacidad_maxima:
                errors['cantidad_personas'] = _(
                    f"La cantidad de personas ({self.cantidad_personas}) supera la capacidad máxima del área ({self.area.capacidad_maxima})."
                )

        # 4) Empalme de horarios en la misma área y fecha
        if self.area and self.fecha_reserva and self.hora_inicio and self.hora_fin:
            qs = Reserva.objects.filter(
                area=self.area,
                fecha_reserva=self.fecha_reserva,
                estado__in=['PENDIENTE', 'APROBADA']
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            for r in qs:
                if (self.hora_inicio < r.hora_fin) and (self.hora_fin > r.hora_inicio):
                    errors['hora_inicio'] = _(
                        "Ya existe una reserva para esta área en el horario seleccionado."
                    )
                    break

        if errors:
            raise ValidationError(errors)

# 7. SEGURIDAD

class ControlAcceso(models.Model):
    residente = models.ForeignKey(Residente, on_delete=models.SET_NULL, null=True, blank=True)
    guardia_turno = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True)

    nombre_visitante = models.CharField(max_length=255)
    tipo_visitante = models.CharField(max_length=100)
    placa_vehiculo = models.CharField(max_length=20, null=True, blank=True)
    identificacion_presentada = models.CharField(max_length=100, null=True, blank=True)

    fecha_entrada = models.DateTimeField(auto_now_add=True)
    fecha_salida = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'control_accesos'
        verbose_name = 'Registro de Acceso'

# Reuniones asamblea
class Reunion(models.Model):
    # Opciones que coinciden con el ENUM de MySQL
    ESTADO_CHOICES = [
        ('PROGRAMADA', 'Programada'),
        ('EN_CURSO', 'En Curso'),
        ('FINALIZADA', 'Finalizada'),
    ]

    titulo = models.CharField(max_length=200)
    fecha_reunion = models.DateTimeField()

    # Usamos FileField. Django guardará la ruta (string) en la columna 'acta_url'
    acta_url = models.FileField(
        upload_to='actas/',
        max_length=255,
        null=True,
        blank=True
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='PROGRAMADA'
    )

    class Meta:
        # Vinculación exacta con tu tabla MySQL existente
        db_table = 'reuniones_asamblea'
        verbose_name = 'Reunión / Asamblea'
        verbose_name_plural = 'Reuniones'

    def __str__(self):
        return f"{self.titulo} - {self.fecha_reunion}"

class HistorialLog(models.Model):
    ACCION_CHOICES = [
        ('CREACION', 'Creación'),
        ('EDICION', 'Edición'),
        ('ELIMINACION', 'Eliminación'),
        ('ACCESO', 'Acceso/Login'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    modulo = models.CharField(max_length=50)
    descripcion = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.usuario} - {self.accion} - {self.fecha}"
