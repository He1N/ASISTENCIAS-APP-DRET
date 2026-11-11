# Régimen laboral

La migración 0006 añade un campo opcional a Trabajador y CuentaVacacion. Es una
clasificación informativa separada de Tipo: no determina derechos, asignaciones
ni días a descontar. Las nuevas fichas vacacionales creadas desde Consultas
heredan el régimen informado del trabajador.

La clasificación inicial usa únicamente DNI y reg. Labor de la hoja Resumen
del archivo suministrado. No se importan sus movimientos, saldos, condición ni
fechas de contrato. Las identidades ambiguas no se actualizan automáticamente.
«NO EXISTE» y los DNI ausentes quedan sin régimen informado. No se crean fichas
ni se infiere un régimen por nombres.

```text
python manage.py importar_regimenes archivo.xlsx
python manage.py importar_regimenes archivo.xlsx --confirmar --usuario ADMINISTRADOR
```

El primer comando previsualiza. Confirmar requiere permisos de edición de
trabajadores y cuentas; registra fuente y checksum en auditoría. Repetir no
duplica cambios. Verificar respaldo y ensayar la migración en una copia aislada
antes de actualizar producción. El archivo real permanece fuera de Git.

El régimen se muestra y edita en Trabajadores y Control de vacaciones. Los
cambios desde formularios se reflejan en la ficha del otro módulo si el vínculo
o DNI son inequívocos, con auditoría y comprobación de versión. Se conserva una
clasificación conocida al crear una nueva ficha vinculable que no informa otra.

En Control de vacaciones se filtra por régimen y «Excel por régimen laboral»
descarga resumen y detalle por cada grupo. Los saldos negativos se conservan y
las sumas de los grupos coinciden con los mismos datos del control. Cada hoja
está preparada para imprimir A4 horizontal, a una página de ancho, sin forzar
una única página de alto, con títulos de filas 1 a 3 repetidos y área delimitada.

En Consultas, Vacaciones y Licencias sindicales, el filtro Régimen laboral y la
casilla «Exportar Excel agrupado por régimen laboral» conservan los demás
filtros. La salida agrupada organiza las filas de asistencia en hojas imprimibles
por régimen; «Días calendario» sigue siendo duración informativa, no saldo.
La exportación habitual conserva sus campos y agrega Régimen laboral al final.

La plantilla de impresión versionada contiene únicamente estilos y textos
genéricos, generados con Artifact Tool. El servidor completa OOXML estándar
con valores tipados y fórmulas SUM con resultados cacheados, sin añadir un
runtime de hojas de cálculo ni nuevas dependencias al despliegue Django.
