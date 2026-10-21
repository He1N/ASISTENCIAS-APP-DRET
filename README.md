# Control de Asistencias — DRET

Implementación de fases 1 a 5 (maestros, justificaciones, consultas e históricos) conforme a `ESPECIFICACION.md` y `AGENTS.md`.
Python 3.12 y Django 5.2 LTS. SQLite local y PostgreSQL mediante DATABASE_URL.
Configuración preparada para Vercel/Neon; no se ha desplegado ni creado proyectos.
Guías: [despliegue y migraciones](docs/DESPLIEGUE.md), [respaldos](docs/RESPALDOS.md).

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

Abrir http://127.0.0.1:8000/; se dirige a Consultas tras ingresar.
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
- Alta, edición con motivo, detalle y anulación lógica de justificaciones fuera
  de Admin. Autor/fechas registrados por el servidor, auditoría transaccional y
  detección de edición obsoleta. Guardar y registrar otro.
- Consultas con filtros combinados por nombre/DNI/observaciones/CUD, trabajador,
  fechas, periodo, documento, operación y estados; orden estable y 25 filas.
- Autocompletados acotados en los tres selectores con selección por ID, sin
  fusionar homónimos. Se admiten trabajadores inactivos y catálogos históricos.
- Validación de fecha final según operación, fechas de recepción/captura separadas
  y horas independientes. Se admiten registros tardíos sin reabrir periodos.
- Vacaciones y Licencias sindicales por grupo configurable, sin duplicar registros,
  con rangos de fechas y duración calendaria inclusiva solo cuando es calculable.
- Exportación XLSX de consultas, vacaciones, sindicales y periodos, respetando los
  filtros completos y permisos; textos exportados sin fórmulas ejecutables.
- Asistente XLSX: cargar/seleccionar hoja, revisar coincidencias e incidencias y
  confirmar en transacción. Reimportación idempotente, CUD histórico de octubre
  omitido y trazabilidad de hoja/fila/ítem. Anulación auditada de lote si no hubo
  cambios posteriores.
- Siete documentos iniciales, tres operaciones conocidas con regla final pendiente
  y sin códigos inventados. Periodos octubre y noviembre según la especificación.

Los periodos sembrados están ABIERTO: sus estados administrativos reales no están
confirmados. La hoja OJO no está disponible en este alcance; revisar reglas antes
de utilizar las operaciones para altas manuales. En legados se permite aceptarlas
como pendientes con incidencia y confirmación explícita; no se inventan reglas.

## Verificar

```bash
export DEBUG=True
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test -v 1
```

La suite completa pasa 93 pruebas en SQLite y 93 en PostgreSQL 17, incluidas
importación y paginación de 511 registros sintéticos.
`check` no reporta incidencias y `makemigrations --check --dry-run` no detecta
cambios. Se verificó además el flujo web con Chromium en escritorio y móvil.
Las pruebas crean su base desde cero con las migraciones existentes; esta fase
no modifica el esquema ni añade migraciones. Ver [validación](docs/VALIDACION.md).
Se probaron XLSX sintéticos y descargas en navegador. La fase 5 verifica también
producción local con HTTPS, PostgreSQL con TLS, estáticos y respaldo/restauración.
No se validó el workbook institucional real ni un despliegue Vercel/Neon.

## Roles y continuidad

Después de `preparar_roles`, crear usuarios desde Usuarios y asignar un grupo.
Marcar **Activo** y asignar un grupo para entrar a la interfaz propia; no requiere
`is_staff`. Para administrar cuentas y auditoría en `/admin/`, marcar también
**Acceso al sitio administrativo (is_staff)**. Esta marca no concede permisos
sobre los modelos.
Administrador administra usuarios, grupos, catálogos, periodos y justificaciones.
Operador crea/edita trabajadores y justificaciones, importa/exporta Excel y consulta
catálogos/periodos.
Consulta lee maestros y justificaciones; no escribe, exporta ni accede a auditoría
o cuentas. Anular requiere `anular_justificacion` (Administrador por defecto). En esta fase los lectores autorizados
ven nombre, DNI y área: la política de acceso institucional debe revisarse antes
de introducir información real. No otorgar permisos individuales sin necesidad.
El comando sincroniza permisos de grupos; volver a ejecutarlo restablece su política.

Crear al menos dos administradores institucionales con cuentas individuales;
probar el segundo acceso antes del traspaso. Otro administrador puede restablecer
contraseñas y desactivar cuentas desde Usuarios. Desactivar, no borrar cuentas.
No compartir credenciales ni usar al desarrollador como único administrador.
La auditoría del negocio es de solo lectura en Django Admin y en el detalle
de justificación para quien tenga `view_historialcambio`; las pantallas web
y Admin registran cambios de maestros. Cambios por shell/ORM no generan historial
automáticamente. Las fechas de cierre y procesamiento usan una regla compartida
por ambas interfaces y se conservan al reabrir un periodo.

En la ficha del trabajador y del periodo se cuenta el historial relacionado.
El detalle de justificaciones solo aparece con `view_justificacion`; los roles
Operador y Consulta reciben ese permiso al sincronizar los roles.
Las fichas relacionadas enlazan al detalle; la edición exige `change_justificacion`.

Al actualizar desde una fase anterior ejecutar `python manage.py preparar_roles` para
aplicar los permisos actuales, incluidos importar/exportar para Operador. Este comando restablece la política de
los grupos; revisar asignaciones institucionales antes de aplicarlo en una base real.

## Pendiente

Pendientes: primer despliegue y comprobación en Vercel/Neon, operación de
respaldos y ensayos de concurrencia simultánea. El XLSX real y las reglas completas de OJO siguen pendientes
de revisión; no se afirma haber validado esos documentos. No hay borrado físico ni
restauración de registros anulados.
El aviso por versión de esta fase cubre formularios web abiertos antes de otra
edición; SQLite no ofrece bloqueos de fila para garantizar escrituras simultáneas.
Los autocompletados requieren seleccionar una coincidencia explícita; escribir
un texto no asigna automáticamente una persona ni un catálogo.
No se calcula saldo oficial. La fase 5 incorpora DATABASE_URL, validación PostgreSQL,
configuración de despliegue y procedimientos de migración y recuperación.
En Vercel el XLSX admite 4 MB y las respuestas 4 MB; aplicar filtros o dividir
fuentes grandes. Fuera de Vercel se conserva el límite de 10 MiB.
Ver [límites y variables de producción](docs/DESPLIEGUE.md).

Documentación: [modelo](docs/MODELO_DE_DATOS.md),
[manual](docs/MANUAL_USUARIO.md), [importación](docs/IMPORTACION_EXCEL.md).

## Excel y mantenimiento

Instalar las nuevas dependencias fijadas y ejecutar `migrate` y `preparar_roles`.
No hay migraciones nuevas de esquema en fase 4.
Entrar en `/importar/`; seleccionar XLSX/periodo y luego hoja. Revisar mapeo,
coincidencias y duplicados antes de confirmar. Los errores se omiten hasta corregir
la fuente; los legados incompletos requieren aceptación explícita. Cada operación
usa su grupo configurable para aparecer en Vacaciones o Licencias sindicales.

Las previsualizaciones contienen datos temporales con caducidad de 24 horas;
confirmar/cancelar los purga. Ejecutar periódicamente (programación de despliegue
pendiente):

```bash
python manage.py purgar_previsualizaciones
```

Exportar Excel descarga **todas** las filas filtradas, no solo la página visible.
Consulta no exporta por defecto; un administrador puede habilitar el permiso
`exportar_resultados` específicamente. Se exige además lectura del módulo.
Detalles, límites y supuestos: [Importación Excel](docs/IMPORTACION_EXCEL.md).
