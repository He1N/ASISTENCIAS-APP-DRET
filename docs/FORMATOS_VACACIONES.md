# Formatos individuales de vacaciones

El récord y el informe usan un diseño breve, sin secciones de observaciones
generales, incidencias, códigos pendientes ni advertencias. Solo el récord
incluye una columna Sustento / observación con el texto original de cada movimiento.
La revisión de incidencias sigue disponible en la aplicación y no se elimina de
los registros.

Ambos muestran trabajador, DNI, régimen laboral y un resumen corto del saldo
acumulado. Si es negativo se conserva el valor y se indica el exceso de días.
El récord presenta asignaciones y movimientos con Del, Al, Días, Periodo y Sustento / observación. El
informe conserva el calendario anterior de lunes a domingo, sin filas de
subtotales por día de semana. Ambos añaden una tabla pequeña Mes / Días con los
meses que tienen consumo y una fila TOTAL. No se suman números de fechas.

Se conservan las medias jornadas y las cantidades declaradas. Si un intervalo
no permite distribuir su cantidad sin inventar datos, la tabla incluye esa
cantidad como «Sin mes definido». Las reglas de selección anual y recorte de
intervalos entre años no cambian. No se asignan fechas que no estén registradas.

Desde «Generar formato» se elige Récord, Informe, ambos en ZIP o un único Word
integrado con ambos cuadros para todos los años registrados. El sustento aparece
únicamente en los cuadros de récord, también dentro del ZIP y del integrado.
Se requiere lectura del control y permiso de exportación.
La generación no modifica datos, saldos, régimen laboral ni sincronización.

La generación usa OOXML estándar y las tablas del modelo original, sin requerir
Word instalado en producción. Las pruebas comprueban sumas mensuales, medias
jornadas, saldos negativos, permisos, selección anual y ausencia de observaciones.
