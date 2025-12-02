from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum, Count, F
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import datetime, timedelta
import time
import csv
from django.http import HttpResponse
from django.core.paginator import Paginator

from .models import (
    Documento, Residente, Pago, Ticket,
    Empleado, Proveedor, Contrato, Tarea, Prioridad,
    Reunion, ControlAcceso, AreaComun, Reserva, HistorialLog, Usuario,
)


def obtener_rol(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return 'admin'
    perfil = getattr(user, 'frontend_profile', None)
    if perfil and getattr(perfil, 'rol', None):
        return perfil.rol
    return None


def registrar_log(user, accion, modulo, descripcion):
    try:
        usuario_actual = user if user.is_authenticated else None
        HistorialLog.objects.create(
            usuario=usuario_actual,
            accion=accion,
            modulo=modulo,
            descripcion=descripcion
        )
    except Exception as e:
        print(f"Advertencia: No se pudo guardar el log. Error: {e}")


def es_admin(user):
    return obtener_rol(user) == 'admin'


def es_residente(user):
    return obtener_rol(user) in ('residente', 'propietario')


def es_empleado(user):
    return obtener_rol(user) == 'empleado'


def es_guardia(user):
    return obtener_rol(user) == 'guardia'


def _limpiar_slots_estacionamiento(cadena):
    if not cadena:
        return []
    slots = []
    for raw in cadena.split(','):
        s = raw.strip().upper()
        if s:
            slots.append(s)
    return slots


def _buscar_slots_ocupados(slots_nuevos, residente_actual=None):
    if not slots_nuevos:
        return []

    qs = Residente.objects.all()
    if residente_actual is not None:
        qs = qs.exclude(pk=residente_actual.pk)

    ocupados = set()
    for otro in qs:
        existentes = set(_limpiar_slots_estacionamiento(otro.espacios_estacionamiento or ""))
        inter = existentes.intersection(slots_nuevos)
        if inter:
            ocupados.update(inter)
    return sorted(list(ocupados))


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            registrar_log(user, 'ACCESO', 'Sistema', f"Login exitoso: {username}")

            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)

            rol = obtener_rol(user)
            if rol in ('admin', 'residente', 'empleado', 'guardia', 'propietario'):
                return redirect('dashboard')
            else:
                return redirect('residente_listado')
        else:
            messages.error(request, "Credenciales incorrectas.")
    return render(request, 'login.html')


@login_required
def logout_view(request):
    registrar_log(request.user, 'ACCESO', 'Sistema', f"Logout: {request.user.username}")
    logout(request)
    messages.info(request, "Sesión cerrada.")
    return redirect("login")


@login_required
def dashboard_view(request):
    rol = obtener_rol(request.user)

    if rol not in ('admin', 'residente', 'empleado', 'guardia', 'propietario'):
        messages.error(request, "No tienes un rol válido para acceder al dashboard.")
        return redirect('residente_listado')

    if request.method == "POST":
        if rol != 'admin':
            messages.error(request, "No tienes permisos para subir documentación al dashboard.")
            return redirect('dashboard')

        archivo = request.FILES.get("archivo_pdf")
        if archivo:
            if not archivo.name.lower().endswith(".pdf"):
                messages.error(request, "Solo PDF permitidos.")
            else:
                doc = Documento.objects.create(nombre=archivo.name, archivo=archivo, tipo="PDF")
                registrar_log(request.user, 'CREACION', 'Docs', f"Subió: {doc.nombre}")
                messages.success(request, "Documento subido.")
                return redirect("dashboard")

    kpi_residentes = Residente.objects.filter(estado='AC').count()
    kpi_cuotas = Pago.objects.filter(estado__in=['PENDIENTE', 'VENCIDO']).count()
    kpi_tickets = Ticket.objects.exclude(estado='CERRADO').count()
    actividad_reciente = []
    logs_list = HistorialLog.objects.all().order_by('-fecha')
    query_logs = request.GET.get('q_logs')
    if query_logs:
        logs_list = logs_list.filter(
            descripcion__icontains=query_logs
        ) | logs_list.filter(
            usuario__username__icontains=query_logs
        )

    paginator = Paginator(logs_list, 20)
    page_number = request.GET.get('page')
    logs_page = paginator.get_page(page_number)

    pagos_recent_feed = Pago.objects.select_related('residente', 'empleado', 'proveedor').order_by('-created_at')[:3]
    for p in pagos_recent_feed:
        if p.residente:
            nom, uni = p.residente.nombre_completo, p.residente.unidad_principal
        elif p.empleado:
            nom, uni = p.empleado.nombre_completo, "Staff"
        elif p.proveedor:
            nom, uni = p.proveedor.nombre_empresa, "Proveedor"
        else:
            nom, uni = "Sistema", "-"

        actividad_reciente.append({
            'hora': p.created_at,
            'evento': 'Pago registrado',
            'detalle': f"${p.monto_pagado}",
            'usuario': nom,
            'unidad': uni,
            'tipo': 'pago'
        })

    tickets_recent_feed = Ticket.objects.select_related('residente').order_by('-fecha_creacion')[:3]
    for t in tickets_recent_feed:
        nom = t.residente.nombre_completo if t.residente else "Desconocido"
        uni = t.residente.unidad_principal if t.residente else "-"
        actividad_reciente.append({
            'hora': t.fecha_creacion,
            'evento': 'Ticket creado',
            'detalle': t.asunto,
            'usuario': nom,
            'unidad': uni,
            'tipo': 'ticket'
        })

    actividad_reciente.sort(key=lambda x: x['hora'], reverse=True)

    ultimos_pagos = Pago.objects.select_related('residente').order_by('-fecha_emision')[:15]
    ultimos_tickets = Ticket.objects.select_related('residente').order_by('-fecha_creacion')[:15]

    empleados = Empleado.objects.filter(estado='ACTIVO')
    proveedores = Proveedor.objects.filter(estado='ACTIVO')

    ultimas_reuniones = Reunion.objects.filter(
        estado__in=['PROGRAMADA', 'EN_CURSO']
    ).order_by('fecha_reunion')

    accesos_recientes = ControlAcceso.objects.filter(
        fecha_salida__isnull=True
    ).select_related('residente').order_by('-fecha_entrada')[:5]

    total_ingresos = Pago.objects.filter(
        tipo_movimiento='INGRESO', estado='PAGADO'
    ).aggregate(t=Sum('monto_pagado'))['t'] or 0

    areas_comunes = AreaComun.objects.all()
    proximas_reservas = Reserva.objects.filter(
        fecha_reserva__gte=timezone.now().date(),
        estado__in=['APROBADA', 'PENDIENTE']
    ).select_related('area', 'residente')[:5]

    usuarios = None
    logs_recientes = None
    if rol == 'admin':
        usuarios = User.objects.select_related('frontend_profile').order_by('username')
        logs_recientes = HistorialLog.objects.select_related('usuario').order_by('-id')[:50]

    context = {
        "kpi_residentes": kpi_residentes,
        "kpi_cuotas": kpi_cuotas,
        "kpi_tickets": kpi_tickets,
        "actividad_reciente": actividad_reciente[:5],
        "ultimos_pagos": ultimos_pagos,
        "ultimos_tickets": ultimos_tickets,
        "empleados": empleados,
        "proveedores": proveedores,
        "ultimas_reuniones": ultimas_reuniones,
        "accesos_recientes": accesos_recientes,
        "total_ingresos": total_ingresos,
        "areas_comunes": areas_comunes,
        "proximas_reservas": proximas_reservas,
        "documentos": Documento.objects.order_by("-fecha")[:5],
        "residentes": Residente.objects.filter(estado='AC'),
        "usuarios": usuarios,
        "logs_recientes": logs_recientes,
        "rol_usuario": rol,
        "logs": logs_page,
        "tab_activa": request.GET.get('section','home')
    }
    return render(request, "dashboard.html", context)


@login_required
def dashboard_logs(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para ver el historial de actividad.")
        return redirect('residente_listado')

    logs = HistorialLog.objects.select_related('usuario').all()
    query = request.GET.get('q')
    if query:
        logs = logs.filter(
            Q(usuario__username__icontains=query)
            | Q(descripcion__icontains=query)
            | Q(modulo__icontains=query)
        )
    return render(request, 'logs.html', {'logs': logs[:100], 'busqueda_actual': query})


@login_required
def dashboard_usuarios(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para administrar usuarios.")
        return redirect('residente_listado')

    users = User.objects.select_related('frontend_profile').order_by('username')

    usuario_seleccionado = None
    perfil_seleccionado = None

    user_id_param = request.GET.get('user_id')
    if user_id_param:
        try:
            usuario_seleccionado = User.objects.get(pk=user_id_param)
            perfil_seleccionado = getattr(usuario_seleccionado, 'frontend_profile', None)
        except User.DoesNotExist:
            usuario_seleccionado = None

    if request.method == 'POST':
        accion = request.POST.get('accion') or 'create'

        if accion == 'update':
            user_id = request.POST.get('user_id')
            u = get_object_or_404(User, pk=user_id)

            username = (request.POST.get('username') or '').strip()
            email = (request.POST.get('email') or '').strip()
            password = (request.POST.get('password') or '').strip()
            rol = request.POST.get('rol') or 'residente'

            if not username:
                messages.error(request, "El nombre de usuario es obligatorio.")
                return redirect(f"{request.path}?user_id={u.id}#advanced")

            if ' ' in username:
                messages.error(request, "El nombre de usuario no puede contener espacios.")
                return redirect(f"{request.path}?user_id={u.id}#advanced")

            if email and '@' not in email:
                messages.error(request, "El correo electrónico debe contener un @ válido.")
                return redirect(f"{request.path}?user_id={u.id}#advanced")

            if User.objects.exclude(pk=u.pk).filter(username=username).exists():
                messages.error(request, "Ya existe otro usuario con ese nombre de usuario.")
                return redirect(f"{request.path}?user_id={u.id}#advanced")

            u.username = username
            u.email = email or ""

            if password:
                u.set_password(password)

            u.is_staff = (rol == 'admin')
            u.save()

            perfil, _ = Usuario.objects.get_or_create(user=u, defaults={'rol': rol})
            perfil.rol = rol
            perfil.save()

            registrar_log(request.user, 'EDICION', 'Usuarios', f"Actualizó usuario {u.username}")
            messages.success(request, "Usuario actualizado correctamente.")
            return redirect('dashboard_usuarios')

        else:
            username = (request.POST.get('username') or '').strip()
            email = (request.POST.get('email') or '').strip()
            password = (request.POST.get('password') or '').strip()
            rol = request.POST.get('rol') or 'residente'

            if not username or not password:
                messages.error(request, "Usuario y contraseña son obligatorios.")
                return redirect('dashboard_usuarios')

            if ' ' in username:
                messages.error(request, "El nombre de usuario no puede contener espacios.")
                return redirect('dashboard_usuarios')

            if email and '@' not in email:
                messages.error(request, "El correo electrónico debe contener un @ válido.")
                return redirect('dashboard_usuarios')

            if User.objects.filter(username=username).exists():
                messages.error(request, "Ya existe un usuario con ese nombre de usuario.")
                return redirect('dashboard_usuarios')

            try:
                u = User.objects.create_user(
                    username=username,
                    email=email or "",
                    password=password
                )
                u.is_active = True
                if rol == 'admin':
                    u.is_staff = True
                u.save()

                Usuario.objects.create(
                    user=u,
                    rol=rol
                )

                registrar_log(
                    request.user,
                    'CREACION',
                    'Usuarios',
                    f"Creó usuario {username} con rol {rol}"
                )
                messages.success(request, "Usuario creado correctamente.")
            except Exception as e:
                messages.error(request, f"Error al crear usuario: {e}")

            return redirect('dashboard_usuarios')

    context = {
        'usuarios': users,
        'ROL_CHOICES': Usuario.ROL_CHOICES,
        'usuario_seleccionado': usuario_seleccionado,
        'perfil_seleccionado': perfil_seleccionado,
    }
    return render(request, 'usuarios.html', context)


@login_required
@require_POST
def crear_usuario(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para crear usuarios.")
        return redirect('residente_listado')

    username = (request.POST.get("username") or "").strip()
    email = (request.POST.get("email") or "").strip()
    password1 = request.POST.get("password1") or ""
    password2 = request.POST.get("password2") or ""

    if not username or not password1 or not password2:
        messages.error(request, "Usuario y contraseña son obligatorios.")
        return redirect("dashboard_usuarios")

    if password1 != password2:
        messages.error(request, "Las contraseñas no coinciden.")
        return redirect("dashboard_usuarios")

    if User.objects.filter(username=username).exists():
        messages.error(request, "Ya existe un usuario con ese nombre de usuario.")
        return redirect("dashboard_usuarios")

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password1,
        is_active=True
    )

    perfil = Usuario.objects.create(
        user=user,
        rol="residente"
    )

    registrar_log(request.user, "CREACION", "Usuarios", f"Creó usuario {username} con rol residente")
    messages.success(request, "Usuario creado correctamente con rol residente.")
    return redirect("dashboard_usuarios")


@login_required
@require_POST
def actualizar_usuario(request, pk):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para editar usuarios.")
        return redirect("residente_listado")

    perfil = get_object_or_404(Usuario, pk=pk)
    user = perfil.user

    nuevo_rol = request.POST.get("rol") or perfil.rol
    activo = request.POST.get("activo") == "on"

    perfil.rol = nuevo_rol
    perfil.save()

    user.is_active = activo
    user.is_staff = (nuevo_rol == "admin")
    user.save()

    registrar_log(request.user, "EDICION", "Usuarios", f"Actualizó usuario {user.username} a rol {nuevo_rol}")
    messages.success(request, "Usuario actualizado correctamente.")
    return redirect("dashboard_usuarios")

@login_required
@require_POST
def eliminar_usuario(request, pk):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para eliminar usuarios.")
        return redirect("residente_listado")

    perfil = get_object_or_404(Usuario, user__pk=pk)
    username = perfil.user.username

    perfil.user.delete()

    registrar_log(request.user, "ELIMINACION", "Usuarios", f"Eliminó usuario {username}")
    messages.warning(request, "Usuario eliminado.")
    return redirect("dashboard_usuarios")



@login_required
def residentes_view(request):
    return redirect('residente_listado')


@login_required
def residente_listado_y_registro(request):
    if request.method == 'POST':
        try:
            nombre = (request.POST.get('reg_nombre') or '').strip()
            apellido_p = (request.POST.get('reg_apellido_p') or '').strip()
            apellido_m = (request.POST.get('reg_apellido_m') or '').strip()

            if not (nombre or apellido_p or apellido_m):
                nombre_completo = (request.POST.get('reg_name') or '').strip()
            else:
                nombre_completo = " ".join(
                    parte for parte in [nombre, apellido_p, apellido_m] if parte
                )

            dni = (request.POST.get('reg_id') or '').strip()
            telefono = (request.POST.get('reg_phone') or '').strip()
            correo = (request.POST.get('reg_email') or '').strip()
            tipo_residente = request.POST.get('reg_type')
            unidad = (request.POST.get('reg_unit') or '').strip()
            estado = request.POST.get('reg_status')
            parking_text = (request.POST.get('reg_parking') or '').strip()

            if unidad and Residente.objects.filter(unidad_principal=unidad).exists():
                messages.error(request, "Ya existe un residente registrado para esa unidad.")
                return redirect('residente_listado')

            if dni and Residente.objects.filter(dni=dni).exists():
                messages.error(request, "Ya existe un residente con ese DNI.")
                return redirect('residente_listado')

            nuevos_slots = set(_limpiar_slots_estacionamiento(parking_text))
            ocupados = _buscar_slots_ocupados(nuevos_slots)
            if ocupados:
                messages.error(
                    request,
                    f"Los espacios de estacionamiento {', '.join(ocupados)} ya están asignados a otro residente."
                )
                return redirect('residente_listado')

            r = Residente.objects.create(
                nombre_completo=nombre_completo,
                dni=dni,
                telefono=telefono,
                correo_electronico=correo,
                tipo_residente=tipo_residente,
                unidad_principal=unidad,
                estado=estado,
                espacios_estacionamiento=parking_text or None,
            )
            registrar_log(request.user, 'CREACION', 'Residentes', f"Nuevo residente: {r.nombre_completo}")
            messages.success(request, "Registrado.")
            return redirect('residente_listado')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    query = request.GET.get('q')
    residentes = Residente.objects.all().order_by('unidad_principal')
    if query:
        residentes = residentes.filter(nombre_completo__icontains=query)

    return render(request, 'residentes.html', {
        'residentes': residentes,
        'busqueda_actual': query,
        'TIPO_RESIDENTE_CHOICES': Residente.TIPO_RESIDENTE_CHOICES,
        'ESTADO_CHOICES': Residente.ESTADO_CHOICES,
        'rol_usuario': obtener_rol(request.user),
    })


@login_required
def residente_editar(request, pk):
    r = get_object_or_404(Residente, pk=pk)
    if request.method == 'POST':
        nuevo_nombre = (request.POST.get('edit_name') or '').strip()
        nuevo_dni = (request.POST.get('edit_id') or '').strip()
        nuevo_tel = (request.POST.get('edit_phone') or '').strip()
        nuevo_tipo = request.POST.get('edit_type')
        nueva_unidad = (request.POST.get('edit_unit') or '').strip()
        nuevo_estado = request.POST.get('edit_status')
        nuevo_parking = (request.POST.get('edit_parking') or '').strip()

        if nueva_unidad and Residente.objects.exclude(pk=r.pk).filter(unidad_principal=nueva_unidad).exists():
            messages.error(request, "Ya existe otro residente registrado con esa unidad.")
            return redirect('residente_listado')

        if nuevo_dni and Residente.objects.exclude(pk=r.pk).filter(dni=nuevo_dni).exists():
            messages.error(request, "Ya existe otro residente con ese DNI.")
            return redirect('residente_listado')

        nuevos_slots = set(_limpiar_slots_estacionamiento(nuevo_parking))
        ocupados = _buscar_slots_ocupados(nuevos_slots, residente_actual=r)
        if ocupados:
            messages.error(
                request,
                f"Los espacios de estacionamiento {', '.join(ocupados)} ya están asignados a otro residente."
            )
            return redirect('residente_listado')

        r.nombre_completo = nuevo_nombre
        r.dni = nuevo_dni or None
        r.telefono = nuevo_tel or None
        r.tipo_residente = nuevo_tipo
        r.unidad_principal = nueva_unidad
        r.estado = nuevo_estado
        r.espacios_estacionamiento = nuevo_parking or None
        r.save()
        registrar_log(request.user, 'EDICION', 'Residentes', f"Editó a {r.nombre_completo}")
        messages.success(request, "Actualizado.")
        return redirect('residente_listado')

    query = request.GET.get('q')
    residentes = Residente.objects.all().order_by('unidad_principal')
    if query:
        residentes = residentes.filter(nombre_completo__icontains=query)

    return render(request, 'residentes.html', {
        'residentes': residentes,
        'busqueda_actual': query,
        'TIPO_RESIDENTE_CHOICES': Residente.TIPO_RESIDENTE_CHOICES,
        'ESTADO_CHOICES': Residente.ESTADO_CHOICES,
        'residente_a_editar': r,
        'rol_usuario': obtener_rol(request.user),
    })


@login_required
def residente_eliminar(request, pk):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para eliminar residentes.")
        return redirect('residente_listado')

    r = get_object_or_404(Residente, pk=pk)
    nombre = r.nombre_completo
    if request.method == 'POST':
        r.delete()
        registrar_log(request.user, 'ELIMINACION', 'Residentes', f"Eliminó a {nombre}")
        messages.warning(request, "Eliminado.")
    return redirect('residente_listado')

@login_required
def dashboard_pagos(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'residente', 'empleado', 'guardia', 'propietario'):
        messages.error(request, "No tienes permisos para gestionar pagos.")
        return redirect('residente_listado')

    res_list = Residente.objects.filter(estado='AC').order_by('unidad_principal')
    emp_list = Empleado.objects.filter(estado='ACTIVO').order_by('nombre_completo')
    prov_list = Proveedor.objects.filter(estado='ACTIVO').order_by('nombre_empresa')

    deuda = Pago.objects.filter(
        estado__in=['PENDIENTE', 'VENCIDO', 'PARCIAL'],
        tipo_movimiento='INGRESO'
    ).aggregate(t=Sum(F('monto_total') - F('monto_pagado')))['t'] or 0
    hoy = timezone.now()
    ingresos = Pago.objects.filter(
        tipo_movimiento='INGRESO',
        monto_pagado__gt=0,
        fecha_pago__month=hoy.month
    ).aggregate(t=Sum('monto_pagado'))['t'] or 0
    morosos = Pago.objects.filter(estado='VENCIDO').count()

    pendientes = Pago.objects.filter(
        estado__in=['PENDIENTE', 'VENCIDO']
    ).select_related('residente', 'empleado', 'proveedor').order_by('fecha_emision')
    historial = Pago.objects.filter(
        monto_pagado__gt=0
    ).select_related('residente', 'empleado', 'proveedor').order_by('-fecha_pago')

    query = request.GET.get('q')
    if query:
        f = (Q(descripcion__icontains=query) | Q(residente__nombre_completo__icontains=query))
        pendientes = pendientes.filter(f)
        historial = historial.filter(f)

    return render(request, 'pagos.html', {
        'total_pendiente': deuda,
        'ingresos_mes': ingresos,
        'cantidad_morosos': morosos,
        'pagos_pendientes': pendientes[:20],
        'historial_pagos': historial[:20],
        'residentes_list': res_list,
        'empleados_list': emp_list,
        'proveedores_list': prov_list,
        'busqueda_actual': query,
        'rol_usuario': rol,
    })


@login_required
@require_POST
def guardar_pago(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'residente', 'empleado', 'guardia', 'propietario'):
        messages.error(request, "No tienes permisos para registrar pagos.")
        return redirect('residente_listado')

    try:
        tipo = request.POST.get('tipo_entidad')
        obj_id = request.POST.get('entidad_id')
        monto_t = Decimal(request.POST.get('monto_total') or 0)
        monto_p = Decimal(request.POST.get('monto_pagado') or 0)
        estado = request.POST.get('estado')

        nuevo = Pago(
            categoria=request.POST.get('categoria'),
            descripcion=request.POST.get('descripcion'),
            monto_total=monto_t,
            fecha_emision=request.POST.get('fecha_emision') or timezone.now().date(),
            estado=estado
        )

        entidad_nombre = "Desconocido"
        if tipo == 'residente':
            nuevo.residente = get_object_or_404(Residente, id=obj_id)
            nuevo.tipo_movimiento = 'INGRESO'
            entidad_nombre = nuevo.residente.nombre_completo
        elif tipo == 'empleado':
            nuevo.empleado = get_object_or_404(Empleado, id=obj_id)
            nuevo.tipo_movimiento = 'EGRESO'
            entidad_nombre = nuevo.empleado.nombre_completo
        elif tipo == 'proveedor':
            nuevo.proveedor = get_object_or_404(Proveedor, id=obj_id)
            nuevo.tipo_movimiento = 'EGRESO'
            entidad_nombre = nuevo.proveedor.nombre_empresa

        if estado != 'PENDIENTE':
            if monto_p == 0 and estado == 'PAGADO':
                monto_p = monto_t
            nuevo.monto_pagado = monto_p
            nuevo.fecha_pago = timezone.now().date()
            nuevo.metodo_pago = request.POST.get('metodo_pago')
            if estado == 'PAGADO':
                pref = "ING" if nuevo.tipo_movimiento == 'INGRESO' else "EGR"
                nuevo.numero_recibo = f"{pref}-{int(time.time())}"
        else:
            nuevo.monto_pagado = 0

        nuevo.save()
        registrar_log(request.user, 'CREACION', 'Pagos', f"Transacción ${monto_t} con {entidad_nombre}")
        messages.success(request, "Guardado.")
    except Exception as e:
        messages.error(request, f"Error: {e}")
    return redirect('dashboard_pagos')


@login_required
def dashboard_tickets(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'residente', 'empleado', 'propietario'):
        messages.error(request, "No tienes permisos para gestionar tickets.")
        return redirect('residente_listado')

    tickets = Ticket.objects.select_related(
        'residente', 'empleado_asignado', 'proveedor_asignado'
    ).all().order_by('-fecha_creacion')
    estado = request.GET.get('estado')
    if estado and estado != 'TODOS':
        tickets = tickets.filter(estado=estado)

    sel_ticket = None
    if request.GET.get('ticket_id'):
        sel_ticket = get_object_or_404(Ticket, id=request.GET.get('ticket_id'))

    return render(request, 'solicitudes.html', {
        'tickets': tickets,
        'ticket_seleccionado': sel_ticket,
        'residentes': Residente.objects.filter(estado='AC'),
        'empleados': Empleado.objects.filter(estado='ACTIVO'),
        'proveedores': Proveedor.objects.filter(estado='ACTIVO'),
        'prioridades': Prioridad.choices,
        'active_tab': 'detalle' if sel_ticket else request.GET.get('tab', 'listado'),
        'rol_usuario': rol,
    })


@login_required
def crear_ticket(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'residente', 'empleado', 'propietario'):
        messages.error(request, "No tienes permisos para crear tickets.")
        return redirect('residente_listado')

    if request.method == 'POST':
        try:
            res = Residente.objects.get(id=request.POST.get('residente_id'))
            Ticket.objects.create(
                residente=res,
                asunto=request.POST.get('asunto'),
                descripcion=request.POST.get('descripcion'),
                prioridad=request.POST.get('prioridad'),
                estado='ABIERTO'
            )
            registrar_log(
                request.user,
                'CREACION',
                'Tickets',
                f"Ticket '{request.POST.get('asunto')}' para {res.unidad_principal}"
            )
            messages.success(request, "Creado.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('dashboard_tickets')


@login_required
def actualizar_ticket(request, pk):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'residente', 'empleado', 'propietario'):
        messages.error(request, "No tienes permisos para actualizar tickets.")
        return redirect('residente_listado')

    t = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        tipo, obj_id = request.POST.get('asignado_tipo'), request.POST.get('asignado_id')
        if tipo == 'empleado' and obj_id:
            t.empleado_asignado_id, t.proveedor_asignado_id = obj_id, None
        elif tipo == 'proveedor' and obj_id:
            t.proveedor_asignado_id, t.empleado_asignado_id = obj_id, None

        t.estado = request.POST.get('estado')
        nota = request.POST.get('notas')
        if nota:
            prev = t.descripcion or ""
            t.descripcion = f"{prev}\n[Nota]: {nota}"

        t.save()
        registrar_log(request.user, 'EDICION', 'Tickets', f"Actualizó ticket #{t.id}")
        messages.success(request, "Actualizado.")
        if t.estado == 'CERRADO':
            return redirect('dashboard_tickets')
        return redirect(f'/tickets/?ticket_id={t.id}')
    return redirect('dashboard_tickets')


def eliminar_personal(request):
    if request.method == 'POST':
        obj_id = request.POST.get('obj_id')
        tipo = request.POST.get('tipo_entidad')

        try:
            if tipo == 'empleado':
                objeto = get_object_or_404(Empleado, id=obj_id)
                nombre = objeto.nombre_completo
                objeto.delete()
                messages.success(request, f'El empleado {nombre} ha sido eliminado correctamente.')

            elif tipo == 'proveedor':
                objeto = get_object_or_404(Proveedor, id=obj_id)
                nombre = objeto.nombre_empresa
                objeto.delete()
                messages.success(request, f'El proveedor {nombre} ha sido eliminado correctamente.')

        except Exception as e:
            messages.error(request, f'Error al eliminar: {str(e)}')

    return redirect('dashboard_personal')

@login_required
def dashboard_personal(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para gestionar personal.")
        return redirect('residente_listado')

    emps = Empleado.objects.all()
    provs = Proveedor.objects.all()
    sel, tipo = None, None
    contratos, tareas = [], []

    v_tipo, v_id = request.GET.get('tipo'), request.GET.get('id')
    if v_tipo and v_id:
        tipo = v_tipo
        if tipo == 'empleado':
            sel = get_object_or_404(Empleado, id=v_id)
            contratos = Contrato.objects.filter(empleado=sel)
            tareas = Tarea.objects.filter(empleado=sel)
        elif tipo == 'proveedor':
            sel = get_object_or_404(Proveedor, id=v_id)
            contratos = Contrato.objects.filter(proveedor=sel)
            tareas = Tarea.objects.filter(proveedor=sel)

    return render(request, 'personal.html', {
        'empleados': emps,
        'proveedores': provs,
        'seleccionado': sel,
        'tipo_seleccionado': tipo,
        'contratos': contratos,
        'tareas': tareas,
        'active_tab': 'detalle' if sel else request.GET.get('tab', 'listado'),
        'rol_usuario': obtener_rol(request.user),
    })


@login_required
def crear_personal(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para gestionar personal.")
        return redirect('residente_listado')

    if request.method == 'POST':
        tipo, nom = request.POST.get('tipo_entidad'), request.POST.get('nombre')
        try:
            if tipo == 'empleado':
                Empleado.objects.create(
                    nombre_completo=nom,
                    puesto=request.POST.get('rol'),
                    telefono=request.POST.get('contacto'),
                    dni=f"T-{int(time.time())}",
                    fecha_ingreso=timezone.now().date()
                )
            else:
                Proveedor.objects.create(
                    nombre_empresa=nom,
                    tipo_servicio=request.POST.get('rol'),
                    telefono_contacto=request.POST.get('contacto')
                )
            registrar_log(request.user, 'CREACION', 'Personal', f"Nuevo {tipo}: {nom}")
            messages.success(request, "Creado.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('dashboard_personal')



@login_required
def actualizar_personal(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para gestionar personal.")
        return redirect('residente_listado')

    if request.method == 'POST':
        tipo, oid = request.POST.get('tipo_entidad'), request.POST.get('obj_id')
        try:
            if tipo == 'empleado':
                o = Empleado.objects.get(id=oid)
                o.puesto = request.POST.get('rol')
                o.estado = request.POST.get('estado')
                o.save()
            else:
                o = Proveedor.objects.get(id=oid)
                o.tipo_servicio = request.POST.get('rol')
                o.estado = request.POST.get('estado')
                o.save()
            registrar_log(request.user, 'EDICION', 'Personal', f"Editó {tipo} ID {oid}")
            messages.success(request, "Actualizado.")
            return redirect(f'/personal/?tipo={tipo}&id={oid}')
        except Exception:
            pass
    return redirect('dashboard_personal')

@login_required
def subir_contrato(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para gestionar personal.")
        return redirect('residente_listado')

    if request.method == 'POST':
        tipo, oid = request.POST.get('tipo_entidad'), request.POST.get('obj_id')
        f = request.FILES.get('archivo')
        if f:
            c = Contrato(
                tipo_contrato=request.POST.get('nombre_doc'),
                fecha_inicio=timezone.now().date(),
                archivo_contrato_url=f.name,
                salario_o_costo=0,
                frecuencia_pago='MENSUAL'
            )
            if tipo == 'empleado':
                c.empleado_id = oid
            else:
                c.proveedor_id = oid
            c.save()
            registrar_log(request.user, 'CREACION', 'Personal', f"Contrato subido para ID {oid}")
            messages.success(request, "Subido.")
            return redirect(f'/personal/?tipo={tipo}&id={oid}')
    return redirect('dashboard_personal')

@login_required
def dashboard_areas(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'residente', 'empleado', 'propietario','guardia'):
        messages.error(request, "No tienes permisos para gestionar áreas comunes.")
        return redirect('residente_listado')

    reservas_list = Reserva.objects.filter(
        fecha_reserva__gte=timezone.now().date()
    ).order_by('fecha_reserva', 'hora_inicio')
    res = Reserva.objects.filter(
        fecha_reserva__gte=timezone.now().date()
    ).select_related('residente', 'area').order_by('fecha_reserva')
    return render(request, 'areas.html', {
        'areas_list': AreaComun.objects.all(),
        'residentes_list': Residente.objects.filter(estado='AC'),
        'reservas_list': res,
        'active_tab': request.GET.get('tab', 'calendario'),
        'rol_usuario': rol,
    })


@login_required
def crear_reserva(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'residente', 'empleado', 'propietario'):
        messages.error(request, "No tienes permisos para crear reservas.")
        return redirect('residente_listado')

    if request.method == 'POST':
        try:
            r_id = request.POST.get('residente_id')
            a_id = request.POST.get('area_id')
            fecha_str = request.POST.get('fecha_reserva')
            hora_ini_str = request.POST.get('hora_inicio')
            hora_fin_str = request.POST.get('hora_fin')
            cant_str = request.POST.get('cantidad_personas') or '0'

            try:
                hora_ini = datetime.strptime(hora_ini_str, '%H:%M').time()
                hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
            except Exception:
                messages.error(request, "Formato de hora inválido.")
                return redirect('dashboard_areas')

            if hora_ini >= hora_fin:
                messages.error(request, "La hora de inicio debe ser anterior a la hora de fin.")
                return redirect('dashboard_areas')

            try:
                cantidad = int(cant_str)
            except ValueError:
                messages.error(request, "La cantidad de personas no es válida.")
                return redirect('dashboard_areas')

            area = get_object_or_404(AreaComun, id=a_id)

            if cantidad > area.capacidad_maxima:
                messages.error(
                    request,
                    f"La cantidad de personas excede la capacidad máxima del área ({area.capacidad_maxima})."
                )
                return redirect('dashboard_areas')

            reservas_existentes = Reserva.objects.filter(
                area_id=a_id,
                fecha_reserva=fecha_str,
                estado__in=['APROBADA', 'PENDIENTE']
            )

            for resv in reservas_existentes:
                if not (hora_fin <= resv.hora_inicio or hora_ini >= resv.hora_fin):
                    messages.error(
                        request,
                        "Ya existe una reserva aprobada en ese horario para esta área."
                    )
                    return redirect('dashboard_areas')

            Reserva.objects.create(
                residente_id=r_id,
                area_id=a_id,
                fecha_reserva=fecha_str,
                hora_inicio=hora_ini,
                hora_fin=hora_fin,
                cantidad_personas=cantidad,
                estado='APROBADA'
            )
            registrar_log(request.user, 'CREACION', 'Areas', f"Reserva creada area ID {a_id}")
            messages.success(request, "Reserva creada.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('dashboard_areas')


@login_required
def cancelar_reserva(request, pk):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'residente', 'empleado', 'propietario'):
        messages.error(request, "No tienes permisos para cancelar reservas.")
        return redirect('residente_listado')

    r = get_object_or_404(Reserva, pk=pk)
    r.estado = 'CANCELADA'
    r.save()
    registrar_log(request.user, 'EDICION', 'Areas', f"Canceló reserva #{pk}")
    messages.warning(request, "Cancelada.")
    return redirect('dashboard_areas')


@login_required
def dashboard_accesos(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'guardia'):
        messages.error(request, "No tienes permisos para gestionar accesos.")
        return redirect('residente_listado')

    activos = ControlAcceso.objects.filter(fecha_salida__isnull=True).order_by('-fecha_entrada')
    hist = ControlAcceso.objects.filter(fecha_salida__isnull=False).order_by('-fecha_entrada')[:50]
    return render(request, 'accesos.html', {
        'residentes': Residente.objects.filter(estado='AC'),
        'accesos_activos': activos,
        'historial_accesos': hist,
        'active_tab': request.GET.get('tab', 'activos'),
        'rol_usuario': rol,
    })


@login_required
def registrar_entrada(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'guardia'):
        messages.error(request, "No tienes permisos para registrar accesos.")
        return redirect('residente_listado')

    if request.method == 'POST':
        try:
            rid = request.POST.get('residente_id')
            vis = request.POST.get('nombre_visitante')
            ControlAcceso.objects.create(
                residente_id=rid if rid else None,
                nombre_visitante=vis,
                tipo_visitante=request.POST.get('tipo_visitante'),
                placa_vehiculo=request.POST.get('placa_vehiculo')
            )
            registrar_log(request.user, 'CREACION', 'Accesos', f"Ingreso: {vis}")
            messages.success(request, "Entrada registrada.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('dashboard_accesos')


@login_required
def registrar_salida(request, pk):
    rol = obtener_rol(request.user)
    if rol not in ('admin', 'guardia'):
        messages.error(request, "No tienes permisos para registrar salidas.")
        return redirect('residente_listado')

    a = get_object_or_404(ControlAcceso, pk=pk)
    a.fecha_salida = timezone.now()
    a.save()
    registrar_log(request.user, 'EDICION', 'Accesos', f"Salida: {a.nombre_visitante}")
    return redirect('dashboard_accesos')


@login_required
def dashboard_reuniones(request):
    rol = obtener_rol(request.user)
    if rol not in ('admin','guardia','residente','propietario'):
        messages.error(request, "No tienes permisos para gestionar reuniones.")
        return redirect('residente_listado')

    activas = Reunion.objects.filter(estado__in=['PROGRAMADA', 'EN_CURSO']).order_by('fecha_reunion')
    pasadas = Reunion.objects.filter(estado='FINALIZADA').order_by('-fecha_reunion')
    sel = None
    if request.GET.get('id'):
        sel = get_object_or_404(Reunion, id=request.GET.get('id'))
    return render(request, 'reuniones.html', {
        'reuniones_activas': activas,
        'reuniones_pasadas': pasadas,
        'active_tab': 'detalle' if sel else request.GET.get('tab', 'proximas'),
        'seleccionada': sel,
        'rol_usuario': obtener_rol(request.user),
    })


@login_required
def crear_reunion(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para crear reuniones.")
        return redirect('residente_listado')

    if request.method == 'POST':
        tit = request.POST.get('titulo')
        Reunion.objects.create(
            titulo=tit,
            fecha_reunion=request.POST.get('fecha_reunion'),
            estado='PROGRAMADA'
        )
        registrar_log(request.user, 'CREACION', 'Reuniones', f"Nueva asamblea: {tit}")
        messages.success(request, "Creada.")
    return redirect('dashboard_reuniones')


@login_required
def actualizar_reunion(request, pk):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para actualizar reuniones.")
        return redirect('residente_listado')

    r = get_object_or_404(Reunion, pk=pk)
    if request.method == 'POST':
        r.titulo = request.POST.get('titulo')
        r.fecha_reunion = request.POST.get('fecha_reunion')
        r.estado = request.POST.get('estado')
        r.save()
        registrar_log(request.user, 'EDICION', 'Reuniones', f"Actualizó reunión #{pk}")
        messages.success(request, "Actualizada.")
    return redirect('dashboard_reuniones')


@login_required
def dashboard_reportes(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para ver reportes.")
        return redirect('residente_listado')

    ing = Pago.objects.filter(
        tipo_movimiento='INGRESO',
        estado='PAGADO'
    ).aggregate(t=Sum('monto_pagado'))['t'] or 0
    egr = Pago.objects.filter(
        tipo_movimiento='EGRESO',
        estado='PAGADO'
    ).aggregate(t=Sum('monto_pagado'))['t'] or 0
    deuda = Pago.objects.filter(
        estado='VENCIDO'
    ).aggregate(t=Sum(F('monto_total') - F('monto_pagado')))['t'] or 0
    tickets = [Ticket.objects.filter(estado=x).count() for x in ['ABIERTO', 'EN_PROCESO', 'CERRADO']]
    morosos = Pago.objects.filter(
        estado='VENCIDO'
    ).values(
        'residente__unidad_principal',
        'residente__nombre_completo'
    ).annotate(
        deuda=Sum(F('monto_total') - F('monto_pagado'))
    ).order_by('-deuda')[:5]

    return render(request, 'reportes.html', {
        'ingresos': ing,
        'egresos': egr,
        'balance': ing - egr,
        'total_deuda': deuda,
        'tickets_stats': tickets,
        'top_morosos': morosos,
        'active_tab': request.GET.get('tab', 'financiero'),
        'rol_usuario': obtener_rol(request.user),
    })

@login_required
def exportar_csv(request):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para exportar reportes.")
        return redirect('residente_listado')

    tipo_reporte = request.POST.get('tipo_reporte')
    fecha_inicio = request.POST.get('fecha_inicio')
    fecha_fin = request.POST.get('fecha_fin')

    filename = f"Reporte_{tipo_reporte}_{timezone.now().strftime('%d-%m-%Y')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # 1. BOM para acentos
    response.write(u'\ufeff'.encode('utf8'))

    # 2. CAMBIO IMPORTANTE: Usamos coma (,) en lugar de punto y coma (;)
    writer = csv.writer(response, delimiter=',')

    # Filtros de fecha
    start, end = None, None
    if fecha_inicio and fecha_fin:
        try:
            start = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            end = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except ValueError:
            pass

    if tipo_reporte == 'finanzas':
        # Cabeceras
        writer.writerow(['ID', 'FECHA', 'TIPO', 'NOMBRE / ENTIDAD', 'CONCEPTO', 'MONTO', 'ESTADO'])

        pagos = Pago.objects.select_related('residente', 'empleado', 'proveedor').all().order_by('-fecha_emision')

        if start and end:
            pagos = pagos.filter(fecha_emision__range=(start, end))

        for p in pagos:
            nombre = "Desconocido"
            if p.residente:
                nombre = f"{p.residente.nombre_completo}"
            elif p.empleado:
                nombre = f"{p.empleado.nombre_completo} (Empleado)"
            elif p.proveedor:
                nombre = f"{p.proveedor.nombre_empresa} (Proveedor)"
            
            # Formato de fecha
            fecha_str = p.fecha_emision.strftime('%d/%m/%Y')
            
            # 3. CAMBIO IMPORTANTE: Mantenemos el punto en los decimales para no romper el CSV
            # (Si usas comas aquí, Excel pensará que es otra columna)
            monto_str = f"{p.monto_total:.2f}"

            writer.writerow([
                p.id,
                fecha_str,
                p.tipo_movimiento,
                nombre,
                p.descripcion,
                monto_str,
                p.estado
            ])

    elif tipo_reporte == 'residentes':
        writer.writerow(['UNIDAD', 'NOMBRE', 'TIPO', 'DNI', 'TELEFONO', 'EMAIL', 'ESTADO'])
        residentes = Residente.objects.all().order_by('unidad_principal')
        for r in residentes:
            writer.writerow([
                r.unidad_principal,
                r.nombre_completo,
                r.get_tipo_residente_display(),
                r.dni or '',
                r.telefono or '',
                r.correo_electronico or '',
                r.get_estado_display()
            ])

    elif tipo_reporte == 'tickets':
        writer.writerow(['ID', 'FECHA', 'ASUNTO', 'SOLICITANTE', 'ESTADO', 'PRIORIDAD'])
        tickets = Ticket.objects.select_related('residente').all().order_by('-fecha_creacion')
        if start and end:
            end_full = datetime.combine(end, datetime.max.time())
            start_full = datetime.combine(start, datetime.min.time())
            tickets = tickets.filter(fecha_creacion__range=(start_full, end_full))

        for t in tickets:
            writer.writerow([
                t.id,
                t.fecha_creacion.strftime('%d/%m/%Y'),
                t.asunto,
                t.residente.nombre_completo if t.residente else 'Sistema',
                t.estado,
                t.prioridad
            ])

    registrar_log(request.user, 'ACCESO', 'Reportes', f"Descargó CSV: {tipo_reporte}")
    return response


@login_required
@require_POST
def eliminar_documento(request, doc_id):
    if not es_admin(request.user):
        messages.error(request, "No tienes permisos para eliminar documentos.")
        return redirect('dashboard')

    try:
        documento = get_object_or_404(Documento, id=doc_id)
        if documento.archivo:
            documento.archivo.delete()
        documento.delete()
        try:
            registrar_log(request.user, 'ELIMINACION', 'Documentación', f"Eliminó documento: {documento.nombre}")
        except Exception:
            pass
        messages.success(request, "Documento eliminado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al eliminar: {e}")

    return redirect('dashboard')
