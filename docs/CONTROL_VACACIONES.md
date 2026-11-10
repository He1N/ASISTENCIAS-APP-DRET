# Control vacacional

**Actualización del 09/11/2026:** Consultas y el control están enlazados para
nuevas vacaciones. La regla de separación descrita en el historial de este
documento queda sustituida por [Enlace de vacaciones](ENLACE_VACACIONES.md).

Ampliación solicitada el 01/11/2026: asignaciones explícitas por trabajador/año,
consumo del año más antiguo primero, edición con motivo, anulación/cancelación
sin eliminación y exportación general o individual de exactamente dos hojas:
Resumen y detalle. No se incluyen las fichas individuales antiguas.

No se otorgan 30 días por defecto ni se interpreta el código de contrato.
La habilitación y los días de cada año son editables por administradores.
Los lectores necesitan view_cuentavacacion; exportar requiere además
exportar_resultados. Cambiar fichas y movimientos requiere change_cuentavacacion.
Operador y Consulta reciben lectura al sincronizar roles; solo Administrador
recibe edición. No ejecutar preparar_roles sin revisar ajustes institucionales.

## Carga inicial

Crear un respaldo verificable antes de migrar una base con datos. La migración
0003 añade dos tablas. No contiene datos personales ni importa ningún Excel.

```text
python manage.py importar_control_vacaciones archivo.xlsx
python manage.py importar_control_vacaciones archivo.xlsx --confirmar --usuario administrador
```

El primer comando es la previa. El segundo conserva valores crudos, checksum,
hoja/fila e historial en una transacción. Repetir el mismo archivo no duplica ni
sobrescribe correcciones. Una carga inicial distinta sobre fichas existentes se
rechaza. La carga es independiente: no busca, crea ni vincula trabajadores del
registro de asistencias. Los DNI de detalle ausentes del resumen se conservan
como fichas de incidencia, sin nombre/asignación inventados.

Por indicación posterior del responsable, no se combinan movimientos del Excel
con las justificaciones de la aplicación. Crear, editar o anular una justificación
no modifica este control. Sus saldos y validaciones tampoco afectan las altas
ni ediciones de justificaciones. Un futuro cruce exige revisión explícita previa.

El histórico conserva cantidades explícitas, incluso excepciones. El código 88
no tiene regla automática; no se inventa su significado. Los movimientos de
código desconocido se revisan con días explícitos y motivo. 32 representa 0,5
en las justificaciones de media jornada existentes. Las cancelaciones y
anulaciones quedan visibles en la ficha pero no consumen ni salen como vigentes
en el detalle exportado.

## Saldos y exportación

Desde el 09/11/2026 se permite crear o agravar saldos negativos al registrar o
editar movimientos y asignaciones. Se conserva el saldo real, la auditoría y un
aviso con los días de exceso; no se añaden asignaciones ni se convierte a cero.
Las cantidades de días del movimiento siguen siendo no negativas. El cambio
solo aplica al control independiente, sin cruzar registros de asistencias.

Por indicación del responsable, la exportación no exige revisión individual y no
se bloquea por incidencias históricas. Conserva los datos disponibles, incluidos
los saldos originales; no añade asignaciones ni transforma déficits en ceros.
RESUMEN mantiene las fichas que existían en esa hoja. Los movimientos de DNI
presentes únicamente en DETALLE permanecen en DETALLE, sin inventar filas de resumen.
La búsqueda filtra también la exportación, sobre todos los resultados y no solo
la página visible.

La lista y las tablas de detalle usan Bootstrap Table 1.27.3, Bootstrap 5.3.8 y
jQuery 3.7.1, servidos como archivos estáticos locales, sin solicitudes externas
al navegar. Los recursos conservan sus cabeceras de licencia MIT. Versiones y
documentación: https://bootstrap-table.com/docs/getting-started/introduction/ y
https://getbootstrap.com/docs/5.3/getting-started/introduction/.

Las acciones por fila incluyen exportar, editar y eliminar. Eliminar exige POST,
CSRF y versión vigente; marca la cuenta como eliminada o el movimiento como
anulado, conserva auditoría e historial y los excluye de exportaciones vigentes.

vacaciones_layout.json conserva únicamente estilos, anchos, alturas, encabezados
y configuración de las dos hojas originales. No contiene nombres/DNI ni datos.
La salida escribe texto como literal, conserva ceros iniciales y contiene fórmulas
de resumen con resultados cacheados. Los pendientes 2024/2025 se calculan a partir
de las asignaciones reales y consumo por antigüedad, sin el límite fijo heredado
de 30 días. No se requiere el archivo original en Vercel ni se carga al repositorio.

Pruebas: control.tests_vacaciones. El Excel institucional y respaldos permanecen
fuera de Git. La carga en Neon se ejecuta por separado desde la terminal autorizada,
después de aplicar 0003/0004 y verificar el respaldo. Las incidencias históricas
no bloquean la exportación solicitada; no se inventan correcciones de saldos.

El exportador descarta atributos de compatibilidad Office cuyo prefijo o relación
ya no existe y abre ambas hojas desde A1. La descarga individual usa el nombre del
trabajador, sanitizado para archivos Windows y con cabecera UTF-8 para conservar
tildes. Las pruebas de regresión cubren esos casos. Las salidas individual, general,
vacía y con datos solo en DETALLE pasaron el SDK Open XML de Microsoft sin errores.
