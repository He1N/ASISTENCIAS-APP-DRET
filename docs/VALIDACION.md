# Validación — fases 2 a 4

## Comandos ejecutados

En Python 3.12 con las dependencias fijadas de requirements.txt:

```bash
export DEBUG=True
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
```

Resultados: check sin incidencias, ninguna migración pendiente y 26 pruebas
aprobadas (11 de cimientos y 15 web). La base de pruebas SQLite se crea desde cero
con las migraciones de fase 1 y se elimina al terminar. También se verificó
`migrate --noinput` en una SQLite nueva aislada para la revisión de navegador.

## Cobertura automatizada

Las pruebas web verifican login sin is_staff, logout POST, redirección externa
rechazada, protección de lectura/escritura por rol, anonimato, CSRF, 404 y métodos
permitidos; búsqueda parcial normalizada y por DNI; filtros/paginación y retorno;
alta con solo nombre, DNI con ceros, coincidencias confirmables y validación;
desactivación/reactivación sin perder relaciones; códigos de catálogo, regla final
pendiente/verdadera y grupos especiales; periodo abierto sin fin, validación de
rangos/solapamientos y transiciones con fechas servidor; auditoría y rollback
si falla, rechazo de versiones obsoletas, escape HTML y respuestas sin caché.

## Revisión en navegador

Flujo ejecutado con Playwright y Chromium local, usando una base separada con
fichas ficticias y una cuenta de prueba sin is_staff. Escritorio 1440×1000 y móvil
390×844: iniciar sesión, crear trabajador con DNI textual, editar/inactivar,
buscar sin tilde y filtrar inactivos, navegar por ambos catálogos y periodos,
consultar noviembre sin fin, plegar menú, validar formulario vacío y cerrar sesión.
Se verificó ausencia de desbordamiento horizontal de la página móvil (la tabla
mantiene su propio desplazamiento) y ausencia de errores JavaScript.
La herramienta de navegador solo se instaló en el entorno de revisión; no es una
dependencia de ejecución del proyecto. No se emplearon datos reales.

## Límites

No se probó PostgreSQL, concurrencia simultánea bajo ese motor, Vercel ni Neon.
En fase 2 tampoco se probó importación/exportación Excel; su verificación se añade abajo en fase 4. No se afirma una auditoría completa de accesibilidad ni
compatibilidad con todos los navegadores. La suite CI reutiliza los comandos de
Django; los resultados locales no garantizan por sí solos el estado remoto.

## Validación añadida en fase 3

Se ejecutaron de nuevo `check`, `makemigrations --check --dry-run` y la suite
completa: 48 pruebas SQLite aprobadas (26 previas, 22 nuevas). El esquema queda sin
migraciones nuevas. Las bases de pruebas y de navegador se crean con migraciones
desde cero y únicamente datos ficticios. No se probaron servicios externos.

Cobertura nueva: alta manual y campos obligatorios, actor/fecha/fuente no
manipulables por POST, CUD literal, regla final pendiente/obligatoria/opcional e
igual al inicio; horas válidas, independientes y fuera de papeletas; periodos
cerrados/procesados con captura tardía sin transición automática; excepción de rango
motivada; edición con motivo y versión conservando creador/origen; actualización
de opciones sin guardar; autocompletado parcial sin tildes en los tres campos,
homónimos identificados e inactivos; catálogo inactivo conservado en históricos;
filtros combinados y errores seguros; permisos servidor y auditoría restringida;
anulación lógica y rollback al fallar auditoría; CSRF, caché, escape y métodos HTTP.

Se paginaron 511 justificaciones sintéticas en 21 páginas con orden estable y
fechas nulas al final; la consulta de página se mantuvo debajo de 20 consultas SQL
para detectar regresiones N+1. Es una prueba funcional, no un SLA de rendimiento.

Playwright/Chromium (locale es-PE), escritorio 1440×1000 y móvil 390×844: acceso
Operador, tres autocompletados y homónimos, nueva justificación en periodo procesado,
error contextual por fin obligatorio y posterior alta con fin igual al inicio,
registro tardío, edición motivada, búsqueda combinada con DNI/fechas/periodo/catálogos/
CUD y retorno con filtros. Se verificó Consulta sin escritura y Administrador con
auditoría/anulación, menú móvil y ausencia de desbordamiento de página/errores JS.
Los filtros adicionales quedan plegados cuando no se usan; se abren al aplicar
criterios. La tabla conserva su desplazamiento horizontal en pantallas pequeñas.

PostgreSQL se mantiene como objetivo compatible del ORM; falta ejecutar esta suite
bajo ese motor. Al cerrar fase 3 no se incorporaban Vercel/Neon, importación/exportación ni datos reales.

## Fase 4

81 pruebas Django/SQLite aprobadas: las 48 anteriores y 33 nuevas. `check` sin
incidencias, `makemigrations --check --dry-run` sin cambios y `migrate --noinput`
verificado. La base de navegador se creó desde cero con las migraciones existentes.

Pruebas nuevas: duración inclusiva/no calculable; grupos configurables independientes
del nombre, filtros de sindical y rangos de fin; exportación completa de filtros y
periodos, permisos independientes y textos sin fórmulas. Importación con columnas
reordenadas y encabezados originales de dos filas, época Excel 1904 y ceros iniciales;
CUD octubre descartado/noviembre conservado y no extendido a otros años; homónimos,
solo nombre, catálogo discrepante con asignación auditada, reglas pendientes/faltantes,
horas incompletas y fechas contradictorias; periodo cerrado/fuera de rango motivado;
duplicados dentro de archivo y contra registros existentes, reimportación idempotente,
rollback total ante un fallo, versiones y maestros cambiantes, carga/hoja/revisión/
confirmación por servidor, CSRF, acceso por dueño, purga y anulación de lote protegida.
Se importaron además 511 filas ficticias y se verificaron las cantidades finales.

Playwright/Chromium local a 1440×1000 y 390×844: carga XLSX, selección de hoja,
previsualización con excepción octubre, revisar/confirmar, resumen, reimportación
sin duplicados, Vacaciones y Licencias, filtros, acceso al registro original y
exportaciones descargadas y reabiertas con openpyxl. Se comprobaron DNI textual,
CUD nulo de octubre y duración, permisos de Consulta y ausencia de desbordamiento
horizontal de página/errores JavaScript. Las tablas tienen desplazamiento propio.

No se validó el workbook real ni la guía OJO completa. Tampoco PostgreSQL,
concurrencia bajo ese motor, Vercel/Neon, backups ni despliegue. Los límites de formato
y de revisión se documentan en IMPORTACION_EXCEL.md. No hay datos reales en pruebas.

## Fase 5 — preparación de producción

Python 3.12, Django 5.2.18 y las versiones de requirements.txt. Se ejecutaron
**93 pruebas completas en SQLite y 93 en PostgreSQL 17.11**, en una instancia
Docker local desechable con credenciales y datos sintéticos. PostgreSQL aplicó
todas las migraciones desde cero; `makemigrations --check --dry-run` no detectó
cambios en ambos motores y `migrate --check` confirmó el esquema al día. No se
crean modelos ni migraciones en este PR. `pip check` sin dependencias rotas.

Las 12 pruebas nuevas cubren configuración aislada de desarrollo/producción,
rechazo de SQLite/hosts comodín/DEBUG/TLS inseguro en producción, URL inválida sin
exposición de secretos, opciones de pooling, límites compartidos de formulario y
parser, rechazo HTTP de entradas/resultados excesivos y cierre de descargas sin
truncarlas; respaldo privado, checksum, no sobrescritura, limpieza de archivos
parciales, rechazo de checksum alterado, pooler y destino de restauración ocupado.
Se corrigió una prueba de exportación anterior para consumir el streaming con el
cliente Django, evitando cerrar la conexión dentro del atomic de TestCase al usar
CONN_MAX_AGE=0 en PostgreSQL. No se cambió la lógica de permisos ni los modelos.

Se ejecutaron `check --deploy --fail-level ERROR` y `collectstatic --noinput` con
DEBUG=False, VERCEL=1 y una URL PostgreSQL en un puerto sin servidor. Confirmaron
que preparar estáticos no necesita conectarse ni ejecutar migraciones. Se generó
el manifiesto, CSS/JS con hash y estáticos de Admin. check --deploy muestra solo
W005/W021: includeSubDomains y preload de HSTS permanecen desactivados hasta
conocer el dominio y su política. Los avisos no se silencian.

En producción local, PostgreSQL aceptó conexiones TLS (certificado autofirmado
exclusivo del ensayo, sslmode=require). Cliente Django con CSRF obligatorio:
login, consulta autenticada, cookie de sesión Secure/HttpOnly, cookie CSRF Secure,
HSTS de 3600 s, DENY, nosniff y CSS con hash servido por WhiteNoise. Comprobación
SQL de pg_stat_ssl confirmó cifrado en la conexión usada por la app.

Chromium/Playwright sobre HTTPS local con DEBUG=False y PostgreSQL/TLS: login con
CSRF, consultas, descarga y lectura XLSX con openpyxl, CSS con hash, cookie segura,
formulario con máximo 4 MB y rechazo de un archivo de 4.000.001 bytes, logout y
sin errores JavaScript. El proxy se simuló con X-Forwarded-Proto=https; no es una
prueba de infraestructura Vercel. El estado 413 por cuerpo completo y por respuesta
excesiva se verificó mediante las pruebas automatizadas del middleware.

Respaldo/restauración real con clientes pg_dump/pg_restore 17.11 y el script de
RESPALDOS.md: formato custom con checksum y permisos 0600, restaurado en una base
vacía separada, comparando contenido completo de **18 tablas**, incluidas
migraciones, usuarios/grupos y auditoría. Se rechazó repetir la restauración sobre
el destino ocupado. Todo el ensayo usó datos sintéticos, fuera del repositorio.

La matriz CI ejecuta SQLite/PostgreSQL 17, migraciones, suite y preparación de
estáticos/seguridad. El resultado remoto debe revisarse en el PR.

Pendientes: primer build y despliegue reales en Vercel, conexión Neon con su CA y
pooler real, región/latencia/límites temporales del proveedor, ensayo de escrituras
simultáneas, programación institucional de respaldos/purga y recuperación del
servicio real. No se crearon proyectos externos, cron, cuentas institucionales ni
se procesaron datos reales. Sigue pendiente la revisión del workbook y OJO reales.


## Confirmación de operación — 29/10/2026

El responsable confirmó despliegue Vercel + Neon, carga de datos y funcionamiento
correcto en https://asistencias-app-dret.vercel.app. Los pendientes de primer
despliegue indicados en las fases anteriores son históricos y quedan superados
por esta confirmación. El diseño se mejorará en una etapa posterior.

En la revisión del repositorio se ejecutaron 93 pruebas SQLite aprobadas,
`manage.py check` sin incidencias y `makemigrations --check --dry-run` sin cambios.
No se accedió a datos reales ni se ensayó recuperación productiva. El éxito de la
carga no confirma por sí mismo la revisión completa de OJO ni la concurrencia.
La activación de tareas, el destino de copias y el primer ensayo real deben
registrarse según MANTENIMIENTO.md.

### Automatización de mantenimiento

Tras esta actualización: 94 pruebas SQLite aprobadas, incluida purga repetible
que respeta el límite estricto de 24 horas y conserva justificaciones, lotes
confirmados y auditoría. `check` sin incidencias y `makemigrations --check
--dry-run` sin cambios. `bash -n scripts/backup_diario.sh` correcto; horario
systemd interpretado como 07:45 UTC. No se pudo validar el servicio completo con
`systemd-analyze verify` en este entorno (SO_PASSCRED: Operation not permitted).
No se ejecutó el workflow en producción ni se instaló el timer; no se creó una
copia real ni se restauraron datos institucionales.
