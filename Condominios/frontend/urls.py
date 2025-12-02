from django.urls import path
from .views import login_view, dashboard_view, logout_view, residentes_view, dashboard_logs, dashboard_usuarios, crear_usuario, actualizar_usuario, eliminar_usuario
from . import views
from . import api_views

urlpatterns = [
    # --- RUTAS DE AUTENTICACIÓN Y PRINCIPALES ---
    path("", login_view, name="home"),
    path("login/", login_view, name="login"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("logout/", logout_view, name="logout"),

    path("portal-residentes/", views.residentes_view, name="portal_residentes"),

    # RUTA PRINCIPAL DE GESTIÓN (Maneja Listado, Registro POST, Edición POST)
    path("residentes/", views.residente_listado_y_registro, name="residente_listado"),
    
    # Documentos
    path("api/documentos/", api_views.api_documentos_list, name="api_documentos_list"),
    path("api/documentos/<int:pk>/descargar/", api_views.api_documento_marcar_descarga, name="api_documento_descargar"),
    path('eliminar-documento/<int:doc_id>/', views.eliminar_documento, name='eliminar_documento'),
    
    # R/U: Detalle (GET) y Edición (POST)
    path('residentes/editar/<int:pk>/', views.residente_editar, name='residente_editar'),
    
    # D: Eliminación (POST)
    path('residentes/eliminar/<int:pk>/', views.residente_eliminar, name='residente_eliminar'),

    # PAGOS
    path('pagos/', views.dashboard_pagos, name='dashboard_pagos'),
    path('pagos/guardar/', views.guardar_pago, name='guardar_pago'),

    #TICKETS
    path('tickets/', views.dashboard_tickets, name='dashboard_tickets'),
    path('tickets/crear/', views.crear_ticket, name='crear_ticket'),
    path('tickets/actualizar/<int:pk>/', views.actualizar_ticket, name='actualizar_ticket'),

    #PERSONAL
    path('personal/', views.dashboard_personal, name='dashboard_personal'),
    path('personal/crear/', views.crear_personal, name='crear_personal'),
    path('personal/actualizar/', views.actualizar_personal, name='actualizar_personal'),
    path('personal/contrato/subir/', views.subir_contrato, name='subir_contrato'),
    path('eliminar-personal/', views.eliminar_personal, name='eliminar_personal'),

    #REUNIONES
    path('reuniones/', views.dashboard_reuniones, name='dashboard_reuniones'),
    path('reuniones/crear/', views.crear_reunion, name='crear_reunion'),
    path('reuniones/actualizar/<int:pk>/', views.actualizar_reunion, name='actualizar_reunion'),

    # VISITAS
    path('accesos/', views.dashboard_accesos, name='dashboard_accesos'),
    path('accesos/registrar_entrada/', views.registrar_entrada, name='registrar_entrada'),
    path('accesos/registrar_salida/<int:pk>/', views.registrar_salida, name='registrar_salida'),

    #ÁREAS COMUNES
    path('areas/', views.dashboard_areas, name='dashboard_areas'),
    path('areas/crear/', views.crear_reserva, name='crear_reserva'),
    path('areas/cancelar/<int:pk>/', views.cancelar_reserva, name='cancelar_reserva'),

    #REPORTES
    path('reportes/', views.dashboard_reportes, name='dashboard_reportes'),
    path('reportes/exportar/', views.exportar_csv, name='exportar_csv'),

    #lOGS
    path('logs/', views.dashboard_logs, name='dashboard_logs'),

    #CREACION Y MODIFICACION DE USUARIOS
    path("usuarios/", views.dashboard_usuarios, name="dashboard_usuarios"),
    path("usuarios/crear/", views.crear_usuario, name="crear_usuario"),
    path("usuarios/<int:pk>/actualizar/", views.actualizar_usuario, name="actualizar_usuario"),
    path("usuarios/<int:pk>/eliminar/", views.eliminar_usuario, name="eliminar_usuario"),
]