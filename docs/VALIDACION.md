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
