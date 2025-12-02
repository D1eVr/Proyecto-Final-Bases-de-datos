Sistema de Gestión de Condominios
CondoGest es una plataforma web diseñada para la administración eficiente de condominios y propiedades residenciales. Facilita la gestión de residentes, finanzas, control de accesos, mantenimiento y comunicación interna.

Tecnologías y Arquitectura
El sistema está construido bajo una arquitectura modular utilizando:
	•	Django (Python) – Lógica de negocio, ORM y autenticación.
	•	MySQL 8.0 – Base de datos transaccional.
	•	Docker / Docker Compose – Despliegue y orquestación de servicios.
	•	HTML/CSS/JS – Interfaz moderna estilo Glassmorphism.
	•	Transacciones Atómicas – Uso de select_for_update() y F() para integridad de datos.

Instalación Rápida
1.⁠ ⁠Clonar el repositorio
git clone https://github.com/D1eVr/Proyecto-Final-Bases-de-datos.git
cd Condominios

2.⁠ ⁠Levantar contenedores
docker-compose up --build -d

3.⁠ ⁠Inicializar la base de datos
docker exec -it <contenedor_web> bash
python manage.py migrate
python manage.py loaddata initial_data.json
exit

4.⁠ ⁠Acceso al sistema
http://localhost:8000

Estructura del Proyecto
	•	accounts — Autenticación y gestión de roles (admin, residente, guardia).
	•	frontend — Modelos y lógica de negocio (Pagos, Tickets, Áreas Comunes, etc.).


Seguridad
	•	RBAC (control de acceso basado en roles).
	•	Registros de auditoría (HistorialLog).
	•	Validación estricta de datos.
	•	Protección CSRF en formularios.
