import json
from django.http import JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404, redirect # Añadido 'redirect' para la eliminación
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_http_methods
# Eliminamos csrf_exempt, ya que es inseguro en vistas que manejan sesiones y formularios.
# En su lugar, usaremos el token CSRF estándar de Django.
from django.db import transaction
from django.db.models import F
from django.urls import reverse # Necesario para redireccionar
from .models import Documento, Residente # Asegúrate de que Documento y Residente existan

# --- VISTAS DE DOCUMENTOS ---

@login_required
@require_GET
def api_documentos_list(request: HttpRequest):
    """
    GET /api/documentos/
    Lista documentos.
    """
    data = []
    # Usamos .select_related() si Documento tiene FKs
    for doc in Documento.objects.order_by("-fecha"): 
        data.append({
            "id": doc.id,
            "nombre": doc.nombre,
            "tipo": doc.tipo or "Documento",
            "fecha": doc.fecha.isoformat(),
            "descargas": doc.descargas,
            # Mejor usar doc.archivo.url directamente si es posible
            "url": doc.archivo.url if doc.archivo else "", 
        })
    return JsonResponse({"results": data})


@login_required
@require_http_methods(["POST"])
# Eliminamos @csrf_exempt
def api_documento_marcar_descarga(request: HttpRequest, pk: int):
    """
    POST /api/documentos/<pk>/descargar/
    Incrementa el contador de descargas de forma atómica.
    """
    try:
        with transaction.atomic():
            # select_for_update() garantiza que nadie más modifique la fila durante la transacción
            doc = Documento.objects.select_for_update().get(pk=pk)
            # F() realiza la operación directamente en la BD (evita race conditions)
            doc.descargas = F("descargas") + 1
            doc.save(update_fields=['descargas']) 
            doc.refresh_from_db()

        data = {
            "id": doc.id,
            "nombre": doc.nombre,
            "descargas": doc.descargas,
        }
        return JsonResponse(data)
    except Documento.DoesNotExist:
        return JsonResponse({"detail": "Documento no encontrado."}, status=404)
    except Exception as e:
        return JsonResponse({"detail": f"Error en la operación: {str(e)}"}, status=500)

# --- VISTAS DE RESIDENTES ---

@login_required
@require_GET
def api_residentes_list(request: HttpRequest):
    """
    GET /api/residentes/
    Lista de residentes.
    """
    residentes = Residente.objects.all().order_by("nombre_completo")
    data = [
        {
            "id": r.id,
            "nombre_completo": r.nombre_completo, # Campo corregido
            "tipo_residente": r.tipo_residente,
            "unidad_principal": r.unidad_principal, # Campo corregido
            "email": r.email,
            "telefono": r.telefono,
            "estado": r.estado,
        }
        for r in residentes
    ]
    return JsonResponse({"results": data})


@login_required
@require_http_methods(["POST"])
# Eliminamos @csrf_exempt
def api_residentes_create(request: HttpRequest):
    """
    POST /api/residentes/nuevo/
    Crea un residente a partir de JSON (Si usas esta ruta para crear vía API).
    """
    try:
        # Aseguramos que solo se use para crear vía API, no para el formulario principal.
        # Si la creación se hace por el formulario principal, esta vista no se necesita.
        if request.content_type != 'application/json':
             return JsonResponse({"detail": "Se requiere JSON."}, status=400)
             
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    nombre_completo = payload.get("nombre_completo", "").strip()
    unidad_principal = payload.get("unidad_principal", "").strip()

    if not nombre_completo or not unidad_principal:
        return JsonResponse({"detail": "nombre_completo y unidad_principal son requeridos"}, status=400)

    try:
        r = Residente.objects.create(
            nombre_completo=nombre_completo,
            unidad_principal=unidad_principal,
            email=payload.get("email", ""),
            telefono=payload.get("telefono", ""),
            # Asegura que el estado sea válido según choices
            estado=payload.get("estado", "ACTIVO"), 
            tipo_residente=payload.get("tipo_residente", "RESIDENTE"),
        )
    except Exception as e:
         return JsonResponse({"detail": f"Error al crear: {e}"}, status=400)

    data = {
        "id": r.id,
        "nombre_completo": r.nombre_completo,
        "unidad_principal": r.unidad_principal,
        # ... otros campos
    }
    return JsonResponse(data, status=201)

# --- VISTAS DE DETALLE Y EDICIÓN (para el CRUD del HTML) ---

@login_required
@require_GET
def residente_detalle_json(request: HttpRequest, pk: int):
    """
    GET /api/residentes/<pk>/
    Obtiene los datos de un residente específico para el formulario de edición.
    """
    try:
        residente = get_object_or_404(Residente, pk=pk)
        data = {
            'id': residente.pk,
            'nombre_completo': residente.nombre_completo,
            'tipo_residente': residente.tipo_residente,
            'unidad_principal': residente.unidad_principal,
            'email': residente.email,
            'telefono': residente.telefono,
            'dni_pasaporte': residente.dni_pasaporte,
            'fecha_nacimiento': residente.fecha_nacimiento.isoformat() if residente.fecha_nacimiento else '',
            'estado': residente.estado,
            'unidades_asignadas': residente.unidades_asignadas,
            'estacionamientos': residente.estacionamientos,
        }
        return JsonResponse(data)
    except Residente.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Residente no encontrado"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def residente_eliminar(request: HttpRequest, pk: int):
    """
    POST /api/residentes/<pk>/eliminar/
    Elimina un residente y redirige a la lista.
    """
    residente = get_object_or_404(Residente, pk=pk)
    residente.delete()
    
    # Redirigimos al listado después de la eliminación.
    # El HTML de la tabla usa esta ruta en un formulario POST estándar.
    return redirect(reverse('residentes_url'))