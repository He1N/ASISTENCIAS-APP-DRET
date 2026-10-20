# Importación y exportación XLSX — fase 4

## Fuente y alcance verificable

Implementado según ESPECIFICACION.md y las instrucciones de fase 4. No está el
workbook institucional real ni asistencias_instructions.txt en el repositorio.
Se usaron exclusivamente XLSX sintéticos; **no se afirma validación del Excel real**.
Se deben cotejar encabezados, formatos, filas y catálogo completo OJO con la fuente
autorizada antes de una migración institucional. No se inventan códigos o reglas.

## Lectura y límites

Dependencias fijadas: openpyxl y defusedxml. Solo XLSX, máximo 10 MB comprimidos,
50 MB descomprimidos, 2000 entradas ZIP, 12 hojas de registros, 5000 filas no vacías
en total y 20000 filas inspeccionadas por hoja. Se rechazan macros y fórmulas en
campos importados; nunca se evalúan ni se consulta una caché de fórmula. OJO se
excluye. Las hojas sin encabezados identificables se informan y no son seleccionables.

Por defecto: encabezado desde fila 2 (incluye fila 3), datos desde fila 5. Se
reconocen etiquetas, incluidos Salida/Retorno con subcolumnas Hora/Minuto. Las
columnas pueden cambiar de posición. Es posible indicar manualmente letras A–BL
para sustituir el mapa detectado y ajustar las filas; no se presupone el mes
natural. Solo se interpretan los campos mapeados. Revisar el mapa mostrado, en
particular columnas fuera de A:L, antes de confirmar. Campos ajenos no se importan.

El nombre/DNI se divide por el último `|`; DNI plausible son ocho dígitos textuales.
Si no es plausible, se conserva el texto completo como nombre y se advierte. Los
catálogos se separan como Nombre | código. Un código numérico con formato 000...
se conserva con ese relleno; no se pueden recuperar ceros que la fuente ya perdió.
Fechas nativas, seriales Excel (época del workbook incluida), ISO y dd/mm/aaaa se
interpretan como fechas. Horas válidas se conservan; componentes parciales o inválidos
no se completan: generan error de fila y requieren corregir u omitir la fuente.

## Excepción CUD

Se identifica el periodo administrativo por su corte exacto 07/09/2026–09/10/2026,
no por el mes de movimiento, por ID numérico ni solo por el nombre de la hoja.
Todos sus CUD se eliminan de la previa seleccionada y se insertan NULL. La regla
`cud_omitido_por_desalineacion_octubre` queda en el lote. No se modifican fichas
existentes. Noviembre desde 12/10/2026 y octubre de otros años conservan CUD si
el usuario mantiene Conservar CUD; no se infieren ni reasignan códigos faltantes.
Una papeleta puede mantener CUD si la fuente lo indica, conforme a la especificación.

## Revisión e integridad

La carga crea un lote de selección con hojas y columnas reconocidas en JSON privado;
no conserva el XLSX ni lo envía a servicios externos. Elegir hoja descarta las demás.
La revisión ofrece candidatos de trabajadores/catálogos. No une homónimos ni
conflictos de nombre/código automáticamente. Se pueden elegir IDs existentes o una
ficha nueva con solo nombre; los catálogos se agregan mediante su pantalla y
permisos administrativos. La asignación manual discrepante deja incidencia con el
valor original mínimo necesario. No se alteran códigos de maestros al importar.

Se informa falta de movimiento, regla final pendiente o fin obligatorio faltante
como INCOMPLETO_LEGADO; su importación exige aceptación explícita. Fecha final igual
al inicio es válida. Fecha final anterior o una fecha/hora no interpretable bloquea
la fila, conservando el crudo mínimo como incidencia si se confirma el resto del lote.
La corrección de esas celdas se realiza en el archivo y se recarga; no hay editor
de celdas Excel incrustado. Fuera de rango requiere motivo por fila. La recepción
queda NULL y los registros EXCEL tienen plazo indeterminado.

La detección de duplicados es conservadora: coincidencias existentes por persona,
periodo y movimiento, y huellas de filas normalizadas dentro del archivo. Son
avisos, no restricciones únicas: se omiten por defecto, pero se permite confirmación
explícita para justificaciones legítimas distintas. No se reemplaza ni elimina nada.

Revisar decisiones guarda una firma y una versión de la revisión. Confirmar vuelve
a resolver/validar desde el servidor y exige que no haya cambiado la revisión ni
sus catálogos/periodo/coincidencias. Una edición de decisiones al confirmar primero
se vuelve a presentar sin insertar. Escritura, nuevas fichas, incidencias y auditoría
se ejecutan en una transacción. Un fallo revierte todo. Se registran SHA-256, usuario,
hoja, fila e ítem; los estados del periodo no se modifican.

El mismo SHA-256 + hoja + periodo es idempotente. Volver a guardar un workbook puede
cambiar sus bytes aunque las celdas sean iguales: en ese caso se revisan duplicados
por registro. Un lote anulado tampoco se reimporta silenciosamente. Un lote cancelado
puede volverse a cargar por su dueño si no creó registros. No hay restauración de
anulados. Anular un lote confirmado exige motivo y permiso, y se rechaza si alguna
ficha tuvo modificaciones posteriores; se puede anular individualmente después de revisar.

## Privacidad y permisos

La previa solo es accesible al dueño o a Administrador con permiso de lote. Importar
requiere importar_excel + add/view_justificacion; crear trabajadores exige además
add_trabajador. Operador/Administrador reciben la política mediante preparar_roles.
Consulta no importa ni exporta por defecto. Las descargas necesitan exportar_resultados
y lectura del módulo; habilitar lectura no otorga exportación.

JSON de previsualización caduca en 24 h y se purga al confirmar/cancelar o al abrir
una revisión caducada. Programar en la operación futura (no se configura despliegue):

```bash
python manage.py purgar_previsualizaciones
```

Las incidencias y auditoría quedan con acceso controlado. No registrar datos en logs,
no publicar archivos, volcados ni libros reales. No probar este flujo sobre datos
institucionales sin fuente/copia verificable y revisión autorizada.

## Exportación

Consultas, Vacaciones y Licencias usan el mismo filtrado ORM que sus listas;
Periodos comparte su filtro con la pantalla de maestros. Se exportan todas las
coincidencias, no solo la página actual. Fechas/horas son celdas tipadas con formato
local y códigos/DNI/CUD son texto. Los textos se fuerzan a tipo string de XLSX,
incluso si empiezan con =, +, -, @ o tabuladores; no se crean fórmulas ejecutables.
La respuesta privada sin caché transmite un archivo temporal que se cierra al
terminar la descarga. No conserva exportaciones como documentos permanentes.
Exportar no equivale a un backup de base de datos.
