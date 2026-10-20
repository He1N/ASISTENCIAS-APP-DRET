# Control de Asistencias — DRET

Implementación de fases 1 y 2 (gestión de maestros) conforme a `ESPECIFICACION.md` y `AGENTS.md`.
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

Abrir http://127.0.0.1:8000/; se dirige al listado de trabajadores tras ingresar.
Django Admin permanece en `/admin/` para cuentas, grupos y auditoría. El login y la salida usan sesiones Django,
contraseñas hasheadas y CSRF. No hay registro público ni cuentas predefinidas.
`DEBUG=True` habilita una clave exclusivamente local; fuera de desarrollo se exige
`SECRET_KEY` y HTTPS. Variables disponibles en `.env.example`; el proyecto lee
variables del proceso, **no carga automáticamente `.env`**. No cargar datos reales.

## Alcance entregado

- Interfaz propia con plantillas Django en español: trabajadores, catálogos y
  periodos fuera de Django Admin; navegación lateral y menú móvil plegable.
- Listados de 25 registros con búsqueda, filtros, totales y retorno conservando
  filtros/página; fichas de detalle, altas y edición con errores por campo.
- Guardado y auditoría en una transacción; aviso ante edición obsoleta de una ficha.
  Sin rutas de borrado; las bajas se realizan editando Activo.
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

La suite completa pasa 26 pruebas en SQLite (incluidas 15 pruebas web nuevas).
`check` no reporta incidencias y `makemigrations --check --dry-run` no detecta
cambios. Se verificó además el flujo web con Chromium en escritorio y móvil.
Las pruebas crean su base desde cero con las migraciones existentes; esta fase
no cambia modelos ni añade migraciones. Ver [validación](docs/VALIDACION.md).
No se probó PostgreSQL ni despliegue ni importación/exportación de Excel.

## Roles y continuidad

Después de `preparar_roles`, crear usuarios desde Usuarios y asignar un grupo.
Marcar **Activo** y asignar un grupo para entrar a la interfaz propia; no requiere
`is_staff`. Para administrar cuentas y auditoría en `/admin/`, marcar también
**Acceso al sitio administrativo (is_staff)**. Esta marca no concede permisos
sobre los modelos.
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
La auditoría del negocio es de solo lectura en Django Admin; las pantallas web
y Admin registran cambios de maestros. Cambios por shell/ORM no generan historial
automáticamente. Las fechas de cierre y procesamiento usan una regla compartida
por ambas interfaces y se conservan al reabrir un periodo.

En la ficha del trabajador y del periodo se cuenta el historial relacionado.
El detalle de justificaciones solo aparece con `view_justificacion`; los roles
Operador y Consulta conservan los permisos de fase 1 y no lo reciben por defecto.
Las fichas relacionadas se muestran en lectura, sin habilitar su edición.

## Pendiente

Fases siguientes: consultas y edición de justificaciones con autocompletados,
exportaciones filtradas, vacaciones y licencias sindicales, importador XLSX con
previsualización y reglas CUD, anulación auditada y revisión de concurrencia bajo el motor de producción.
El aviso por versión de esta fase cubre formularios web abiertos antes de otra
edición; SQLite no ofrece bloqueos de fila para garantizar escrituras simultáneas.
El autocompletado de los tres selectores corresponde al formulario futuro de
justificación; esta fase ofrece búsquedas en los maestros.
No se calcula saldo oficial. `DATABASE_URL`, validación PostgreSQL, respaldos y
configuración de despliegue se incorporarán posteriormente; hoy solo SQLite.

Documentación: [modelo](docs/MODELO_DE_DATOS.md),
[manual](docs/MANUAL_USUARIO.md), [importación](docs/IMPORTACION_EXCEL.md).
