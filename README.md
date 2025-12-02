Sistema de Gestión de Condominios
CondoGest es una plataforma web diseñada para la administración eficiente de condominios y propiedades residenciales. Facilita la gestión de residentes, finanzas, control de accesos, mantenimiento y comunicación interna.

Tecnologías y Arquitectura
El sistema está construido bajo una arquitectura modular utilizando:
	•	Django (Python) – Lógica de negocio, ORM y autenticación.
	•	MySQL 8.0 – Base de datos transaccional.
	•	Docker / Docker Compose – Despliegue y orquestación de servicios.
	•	HTML/CSS/JS – Interfaz moderna estilo Glassmorphism.
	•	Transacciones Atómicas – Uso de select_for_update() y F() para integridad de datos.

Instalación Rápida para Mac
1.⁠ ⁠Clonar el repositorio
git clone https://github.com/D1eVr/Proyecto-Final-Bases-de-datos.git 

3.Entrar a la carpeta de Proyecto-Final-Bases-de-datos/Condominios desde la terminal con 
cd Proyecto-Final-Bases-de-datos/Condominios

2.⁠ ⁠Levantar contenedores
docker-compose up --build -d

4.⁠ ⁠Acceso al sistema
http://localhost:8000



Instalación Rápida para Windows
1.⁠ ⁠Clonar el repositorio
git clone https://github.com/D1eVr/Proyecto-Final-Bases-de-datos.git 

3.Entrar a la carpeta de Proyecto-Final-Bases-de-datos/Condominios desde la terminal con 
cd Proyecto-Final-Bases-de-datos/Condominios

2.⁠ ⁠Levantar contenedores
docker-compose up --build -d
docker compose ps
docker exec web python manage.py migrate python manage.py loaddata initial_data.json
docker ps -a
docker-compose up -d
docker logs condominios-db-1
(Get-Content -Raw wait-for-db.sh) -replace "`r`n", "`n" | Set-Content -NoNewline -Encoding UTF8 wait-for-db.sh
docker-compose down --volumes
docker-compose build --no-cache
docker-compose up



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
