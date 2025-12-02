import random
import string
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import IntegrityError

# Importamos tus modelos (incluyendo Documento)
from frontend.models import (
    Residente,
    Empleado,
    Proveedor,
    Pago,
    Ticket,
    AreaComun,
    Reserva,
    ControlAcceso,
    Reunion,
    Prioridad,
    Documento,
)

class Command(BaseCommand):
    help = "Carga datos de demostración (residente, pagos, tickets, documentos, etc.)"

    NOMBRES = [
        "Ana", "Luis", "Diego", "María", "Carlos", "Lucía", "Jorge", "Paola",
        "Fernanda", "Juan", "Sofía", "Miguel", "Andrea", "Ricardo", "Valeria",
        "Daniel", "Alejandra", "Arturo", "Diana", "Emilio"
    ]

    APELLIDOS = [
        "García", "Hernández", "Martínez", "López", "González", "Rodríguez",
        "Pérez", "Sánchez", "Ramírez", "Cruz", "Flores", "Torres", "Vargas",
        "Jiménez", "Ruiz", "Reyes", "Mendoza", "Aguilar", "Morales", "Ortiz"
    ]

    def handle(self, *args, **options):
        self.stdout.write("Iniciando generación masiva de datos...")

        # 1. Crear 1000 Residentes
        self._crear_residentes(1000)
        
        # 2. Empleados y Proveedores (necesarios para los demás)
        self._crear_empleados_y_proveedores(num_empleados=500, num_proveedores=500)
        
        # 3. Crear 1000 Documentos
        self._crear_documentos(1000)

        # 4. Crear 1000 Pagos
        self._crear_pagos(1000)

        # 5. Crear 800 Tickets
        self._crear_tickets(1000)

        # 6. Áreas y Reservas
        self._crear_areas_y_reservas()

        # 7. Accesos y Reuniones
        self._crear_accesos(500)
        self._crear_reuniones(500)

        self.stdout.write(self.style.SUCCESS("¡Datos de demostración generados correctamente!"))

    # ==========================
    # Helpers generales
    # ==========================

    def _random_email(self, base: str) -> str:
        slug = (
            base.lower()
            .replace(" ", "")
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ñ", "n")
        )
        sufijo = random.randint(10, 9999)
        return f"{slug}{sufijo}@demo.condogest"

    def _random_nombre_completo_unico(self, usados: set) -> str:
        while True:
            nombre = random.choice(self.NOMBRES)
            ap_p = random.choice(self.APELLIDOS)
            ap_m = random.choice(self.APELLIDOS)
            full = f"{nombre} {ap_p} {ap_m}"
            if full not in usados:
                usados.add(full)
                return full

    # ==========================
    # 1) Residentes
    # ==========================

    def _crear_residentes(self, cantidad: int):
        existentes = Residente.objects.count()
        self.stdout.write(f"→ Creando ~{cantidad} residentes (ya existen {existentes}).")

        nombres_usados = set(Residente.objects.values_list("nombre_completo", flat=True))
        creados = 0
        intentos = 0
        max_intentos = cantidad * 6

        tipos_posibles = [Residente.PROPIETARIO, Residente.ARRENDATARIO, Residente.FAMILIAR]

        while creados < cantidad and intentos < max_intentos:
            intentos += 1
            idx = existentes + creados + intentos

            letra = chr(ord("A") + (idx % 5))
            num = (idx % 999) or 999
            unidad = f"Torres {letra}-{num:03d}"
            tipo_residente = random.choice(tipos_posibles)

            if Residente.objects.filter(unidad_principal=unidad, tipo_residente=tipo_residente).exists():
                continue
            
            nombre_completo = self._random_nombre_completo_unico(nombres_usados)
            dni_num = 20000000 + idx
            letra_dni = string.ascii_uppercase[idx % 26]
            dni = f"{dni_num:08d}{letra_dni}"
            
            if Residente.objects.filter(dni=dni).exists():
                continue

            telefono = f"{random.randint(10**9, 10**10 - 1)}"

            try:
                Residente.objects.create(
                    nombre_completo=nombre_completo,
                    dni=dni,
                    telefono=telefono,
                    correo_electronico=self._random_email(nombre_completo),
                    fecha_nacimiento=None,
                    tipo_residente=tipo_residente,
                    unidad_principal=unidad,
                    estado=random.choice([Residente.ACTIVO, Residente.INACTIVO, Residente.PENDIENTE]),
                    espacios_estacionamiento=None,
                )
                creados += 1
            except IntegrityError:
                continue

        self.stdout.write(self.style.SUCCESS(f"   Residentes creados exitosamente: {creados}"))

    # ==========================
    # 2) Empleados y Proveedores
    # ==========================

    def _crear_empleados_y_proveedores(self, num_empleados: int, num_proveedores: int):
        self.stdout.write(f"→ Creando {num_empleados} empleados y {num_proveedores} proveedores...")

        base_empleados = Empleado.objects.count()
        for i in range(num_empleados):
            idx = base_empleados + i + 1
            nombre = self._random_nombre_completo_unico(set())
            Empleado.objects.create(
                nombre_completo=nombre,
                dni=f"E{100000 + idx}",
                correo_electronico=self._random_email("empleado"),
                telefono=str(random.randint(10**9, 10**10 - 1)),
                puesto=random.choice(["Guardia", "Conserje", "Administrador", "Mantenimiento"]),
                estado="ACTIVO",
                fecha_ingreso=timezone.now().date() - timedelta(days=random.randint(0, 1200)),
            )

        base_prov = Proveedor.objects.count()
        for i in range(num_proveedores):
            idx = base_prov + i + 1
            nombre_empresa = f"Proveedor {idx}"
            Proveedor.objects.create(
                nombre_empresa=nombre_empresa,
                rfc_o_taxid=f"RFC{200000 + idx}",
                nombre_contacto=random.choice(self.NOMBRES),
                telefono_contacto=str(random.randint(10**9, 10**10 - 1)),
                tipo_servicio=random.choice(["Plomería", "Jardinería", "Seguridad", "Limpieza"]),
                estado="ACTIVO",
            )

        self.stdout.write(self.style.SUCCESS("   Empleados y Proveedores creados."))

    # ==========================
    # 3) Documentos (NUEVO)
    # ==========================

    def _crear_documentos(self, cantidad: int):
        self.stdout.write(f"→ Creando {cantidad} documentos...")
        
        tipos_doc = ["Reglamento", "Acta de Asamblea", "Aviso Importante", "Comprobante Fiscal", "Circular", "Contrato"]
        extensiones = ["pdf", "docx", "xlsx", "jpg"]
        
        batch_docs = []
        
        for i in range(cantidad):
            tipo = random.choice(tipos_doc)
            anio = random.randint(2023, 2025)
            mes = random.randint(1, 12)
            
            # Nombre descriptivo
            nombre = f"{tipo} {anio}-{mes:02d} - Ref #{i+1}"
            
            # Simulamos una ruta de archivo. No crea el archivo físico, 
            # pero llena el campo FileField en la BD correctamente.
            ext = random.choice(extensiones)
            ruta_simulada = f"documentos/demo_data/{tipo.lower().replace(' ', '_')}_{i}.{ext}"
            
            doc = Documento(
                nombre=nombre,
                tipo=tipo,
                archivo=ruta_simulada,
            )
            batch_docs.append(doc)
            
        Documento.objects.bulk_create(batch_docs)
        self.stdout.write(self.style.SUCCESS("   Documentos creados."))

    # ==========================
    # 4) Pagos
    # ==========================

    def _crear_pagos(self, cantidad: int):
        self.stdout.write(f"→ Creando ~{cantidad} pagos...")

        residentes = list(Residente.objects.all())
        empleados = list(Empleado.objects.all())
        proveedores = list(Proveedor.objects.all())

        if not residents_check(residentes, empleados, proveedores):
             return

        pagos_batch = [] 
                
        for i in range(cantidad):
            tipo_mov = random.choice(["INGRESO", "EGRESO"])
            categoria = random.choice(["Cuota", "Mantenimiento", "Nómina", "Servicio"])
            descripcion = f"Pago {categoria} #{i+1}"
            monto_total = random.randint(300, 5000)
            dias_atras = random.randint(0, 180)
            fecha_emision = timezone.now().date() - timedelta(days=dias_atras)

            pago = Pago(
                categoria=categoria,
                descripcion=descripcion,
                monto_total=monto_total,
                tipo_movimiento=tipo_mov,
                fecha_emision=fecha_emision,
                estado=random.choice(["PENDIENTE", "PAGADO", "VENCIDO"]),
            )
            
            destino = random.choice(["residente", "empleado", "proveedor"])
            
            # Asignación segura
            if destino == "residente" and residentes:
                pago.residente = random.choice(residentes)
            elif destino == "empleado" and empleados:
                pago.empleado = random.choice(empleados)
            elif destino == "proveedor" and proveedores:
                pago.proveedor = random.choice(proveedores)
            else:
                if residentes:
                    pago.residente = random.choice(residentes)

            # Lógica de estados
            if pago.estado == "PAGADO":
                pago.monto_pagado = monto_total
                pago.fecha_pago = fecha_emision + timedelta(days=random.randint(0, 10))
                pago.metodo_pago = random.choice(["Efectivo", "Transferencia", "Tarjeta"])
            elif pago.estado == "VENCIDO":
                pago.monto_pagado = random.randint(0, int(monto_total * 0.5))
                pago.fecha_pago = None
            else:
                pago.monto_pagado = 0
                pago.fecha_pago = None

            try:
                pago.save()
            except Exception:
                pass # Ignorar errores de validación en seed random

        self.stdout.write(self.style.SUCCESS("   Pagos creados."))

    # ==========================
    # 5) Tickets
    # ==========================

    def _crear_tickets(self, cantidad: int):
        self.stdout.write(f"→ Creando ~{cantidad} tickets...")

        residentes = list(Residente.objects.all())
        empleados = list(Empleado.objects.all())
        proveedores = list(Proveedor.objects.all())

        if not residentes:
            self.stdout.write("   No hay residentes para tickets, se omite.")
            return

        estados_posibles = ["ABIERTO", "EN_PROCESO", "CERRADO"]
        tipos_solicitud = ["Mantenimiento", "Queja", "Sugerencia", "Otro"]

        for i in range(cantidad):
            res = random.choice(residentes)
            ticket = Ticket.objects.create(
                residente=res,
                tipo_solicitud=random.choice(tipos_solicitud),
                asunto=f"Ticket #{i+1} - {random.choice(['Fuga', 'Ruido', 'Limpieza', 'Elevador'])}",
                descripcion="Generado automáticamente para pruebas de carga.",
                prioridad=random.choice([p[0] for p in Prioridad.choices]),
                estado=random.choice(estados_posibles),
            )

            if random.random() < 0.5 and empleados:
                ticket.empleado_asignado = random.choice(empleados)
            elif random.random() < 0.5 and proveedores:
                ticket.proveedor_asignado = random.choice(proveedores)
            ticket.save()

        self.stdout.write(self.style.SUCCESS("   Tickets creados."))

    # ==========================
    # 6) Áreas comunes y reservas
    # ==========================

    def _crear_areas_y_reservas(self):
        self.stdout.write("→ Creando áreas comunes y reservas...")
        if AreaComun.objects.count() == 0:
            AreaComun.objects.bulk_create([
                AreaComun(nombre="Salón de Usos Múltiples", capacidad_maxima=80, costo_reserva=800, requiere_aprobacion=True),
                AreaComun(nombre="Alberca", capacidad_maxima=40, costo_reserva=0, requiere_aprobacion=False),
                AreaComun(nombre="Terraza", capacidad_maxima=60, costo_reserva=500, requiere_aprobacion=True),
                AreaComun(nombre="Gimnasio", capacidad_maxima=25, costo_reserva=0, requiere_aprobacion=False),
            ])

        areas = list(AreaComun.objects.all())
        residentes = list(Residente.objects.all())

        if not areas or not residentes:
            return

        for _ in range(1001):
            area = random.choice(areas)
            res = random.choice(residentes)

            fecha = timezone.now().date() + timedelta(days=random.randint(-10, 30))
            hora_inicio = datetime.strptime(f"{random.randint(8, 19):02d}:00", "%H:%M").time()
            hora_fin = (datetime.combine(fecha, hora_inicio) + timedelta(hours=2)).time()

            cantidad_personas = random.randint(1, area.capacidad_maxima)

            try:
                Reserva.objects.create(
                    residente=res,
                    area=area,
                    fecha_reserva=fecha,
                    hora_inicio=hora_inicio,
                    hora_fin=hora_fin,
                    cantidad_personas=cantidad_personas,
                    estado=random.choice(["APROBADA", "PENDIENTE", "CANCELADA"]),
                )
            except Exception:
                pass 

        self.stdout.write(self.style.SUCCESS("   Áreas y reservas creadas."))

    # ==========================
    # 7) Control de accesos
    # ==========================

    def _crear_accesos(self, cantidad: int):
        self.stdout.write(f"→ Creando ~{cantidad} registros de acceso...")

        residentes = list(Residente.objects.all())
        empleados = list(Empleado.objects.all())

        if not empleados:
            return

        tipos_visitante = ["Visita", "Proveedor", "Uber", "Servicio"]

        for i in range(cantidad):
            guardia = random.choice(empleados)
            residente = random.choice(residentes) if residentes else None
            fecha_entrada = timezone.now() - timedelta(hours=random.randint(0, 240))
            fecha_salida = (
                fecha_entrada + timedelta(hours=random.randint(1, 5))
                if random.random() < 0.7
                else None
            )

            ControlAcceso.objects.create(
                residente=residente,
                guardia_turno=guardia,
                nombre_visitante=f"Visitante {i+1}",
                tipo_visitante=random.choice(tipos_visitante),
                placa_vehiculo=f"{random.choice(['ABC', 'XYZ', 'QWE'])}-{random.randint(100, 999)}",
                identificacion_presentada="INE",
                fecha_entrada=fecha_entrada,
                fecha_salida=fecha_salida,
            )

        self.stdout.write(self.style.SUCCESS("   Registros de acceso creados."))

    # ==========================
    # 8) Reuniones / asambleas
    # ==========================

    def _crear_reuniones(self, cantidad: int):
        self.stdout.write(f"→ Creando ~{cantidad} reuniones/asambleas...")

        estados = ["PROGRAMADA", "EN_CURSO", "FINALIZADA"]

        for i in range(cantidad):
            fecha = timezone.now() + timedelta(days=random.randint(-60, 60))
            Reunion.objects.create(
                titulo=f"Asamblea de Condominio #{i+1}",
                fecha_reunion=fecha,
                estado=random.choice(estados),
            )

        self.stdout.write(self.style.SUCCESS("   Reuniones creadas."))


def residents_check(residentes, empleados, proveedores):
    if not residentes and not empleados and not proveedores:
        print("   No hay entidades para crear pagos, se omite.")
        return False
    return True