# Control de Asistencias — DRET

Implementación de fase 1 conforme a `ESPECIFICACION.md` y `AGENTS.md`.
Python 3.12 y Django 5.2 LTS. SQLite local. No hay configuración de Vercel ni Neon.

## Ejecutar localmente (Bash)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export DEBUG=True
python manage.py migrate
python manage.py preparar_roles
python manage.py createsuperuser
# Opcional: únicamente fichas inventadas, sin cuentas ni contraseñas
python manage.py crear_datos_sinteticos
python manage.py runserver
```

Abrir http://127.0.0.1:8000/admin/. El login y la salida usan sesiones Django,
contraseñas hasheadas y CSRF. No hay registro público ni cuentas predefinidas.
`DEBUG=True` habilita una clave exclusivamente local; fuera de desarrollo se exige
`SECRET_KEY` y HTTPS. Variables disponibles en `.env.example`; el proyecto lee
variables del proceso, **no carga automáticamente `.env`**. No cargar datos reales.

## Alcance entregado

- Interfaz administrativa Django en español: trabajadores, catálogos y periodos.
- Trabajador con solo nombre; DNI opcional textual; coincidencias requieren revisión
  y confirmación, sin prohibir homónimos. Desactivación y reactivación sin borrado.
- Búsqueda parcial sin tildes/mayúsculas en nombres de trabajadores y catálogos.
- Roles Administrador, Operador y Consulta, permisos servidor y auditoría de altas
  y modificaciones de trabajadores, catálogos y periodos. Django registra cambios
  de usuarios y grupos mediante su propio historial administrativo.
- Periodos arbitrarios, fin abierto, solapamiento con excepción motivada,
  fechas de cierre/procesamiento capturadas por el servidor al cambiar estado.
- Modelos y migraciones para justificaciones, lotes, incidencias y auditoría como
  cimientos de fases posteriores; sin pantallas operativas para esos modelos.
- Siete documentos iniciales, tres operaciones conocidas con regla final pendiente
  y sin códigos inventados. Periodos octubre y noviembre según la especificación.

Los periodos sembrados están ABIERTO: sus estados administrativos reales no están
confirmados. La hoja OJO no está disponible en este alcance; revisar reglas antes
 de utilizar las operaciones para altas manuales. No se ejecutan importaciones.

## Verificar

```bash
export DEBUG=True
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test -v 1
```

Se aplicaron migraciones desde cero en una SQLite nueva y pasaron 11 pruebas
(modelos, formularios, roles, CSRF, sesión, auditoría y conservación histórica).
No se probó PostgreSQL ni despliegue ni importación/exportación de Excel.

## Roles y continuidad

Después de `preparar_roles`, crear usuarios desde Usuarios y asignar un grupo.
Marcar **Activo** y **Acceso al sitio administrativo (is_staff)** para entrar.
`is_staff` habilita la entrada, no concede permisos sobre los modelos.
Administrador administra usuarios, grupos, catálogos y periodos. Operador crea y
edita trabajadores, y consulta catálogos/periodos. Consulta solo lee esos maestros;
no exporta ni accede a auditoría o cuentas. En esta fase los lectores autorizados
ven nombre, DNI y área: la política de acceso institucional debe revisarse antes
de introducir información real. No otorgar permisos individuales sin necesidad.
El comando sincroniza permisos de grupos; volver a ejecutarlo restablece su política.

Crear al menos dos administradores institucionales con cuentas individuales;
probar el segundo acceso antes del traspaso. Otro administrador puede restablecer
contraseñas y desactivar cuentas desde Usuarios. Desactivar, no borrar cuentas.
No compartir credenciales ni usar al desarrollador como único administrador.
La auditoría del negocio es de solo lectura; cambios por shell/ORM no generan
historial automáticamente: usar las rutas administrativas para operar.

## Pendiente

Fases siguientes: consultas y edición de justificaciones con autocompletados,
exportaciones filtradas, vacaciones y licencias sindicales, importador XLSX con
previsualización y reglas CUD, controles de concurrencia y anulación auditada.
El autocompletado de los tres selectores corresponde al formulario futuro de
justificación; esta fase ofrece búsquedas en los maestros.
No se calcula saldo oficial. `DATABASE_URL`, validación PostgreSQL, respaldos y
configuración de despliegue se incorporarán posteriormente; hoy solo SQLite.

Documentación: [modelo](docs/MODELO_DE_DATOS.md),
[manual](docs/MANUAL_USUARIO.md), [importación](docs/IMPORTACION_EXCEL.md).
