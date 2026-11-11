# Formatos individuales de vacaciones

Actualización del 10/11/2026: el régimen laboral aparece en la cabecera. El récord
incluye matriz mensual con lunes a domingo, sumas horizontales y total anual por
columna. El informe mantiene las fechas del calendario e incorpora subtotales
mensuales de días y total anual por día de semana. Las medias jornadas cuentan
0,5; una fecha con varios consumos muestra su cantidad entre paréntesis. Las
superposiciones se conservan y señalan en las observaciones, sin corregir datos.

Si un intervalo de varios días declara una cantidad distinta de su duración,
no se prorratea arbitrariamente: se marca con † y se muestra la cantidad sin
distribución fiable, junto al total distribuido y al total declarado del año.
No se suman números de fechas. Las observaciones usan una tabla de fechas,
detalle y registros; en el integrado se reúnen al final. Los encabezados de
las tablas se repiten al continuar a otra página.

Desde el detalle de una ficha, «Generar formato» abre la selección de año y de
Récord, Informe o Ambos. Se requiere lectura del control y permiso de exportación.
Ambos descarga un ZIP con dos DOCX editables. La opción predeterminada «Récord e
informe integrados» descarga un único Word con ambos cuadros por cada año de la
persona y observaciones generales al final. Incluye años con asignaciones,
periodos y fechas vigentes, así como los años intermedios de intervalos; no exige
elegir año. No hay generación general de varias personas.

Se usan solo movimientos vigentes del control independiente. No se mezclan con
justificaciones de asistencia. El año corresponde al intervalo Del/Al, no al
periodo de asignación. Los intervalos que cruzan de año se recortan al año elegido.
En el informe se distribuyen los números de día por semana y mes, de lunes a
domingo, incluidos fines de semana comprendidos en el intervalo. Una fecha
coincidente aparece una sola vez; las medias jornadas se aclaran fuera del cuadro.

El récord conserva cantidades declaradas cuando el intervalo pertenece entero al
año. Las asignaciones y saldo de su cabecera son los acumulados actuales de la
ficha; el total utilizado corresponde a los movimientos con fechas del año elegido.
No reconstruye un saldo histórico al cierre del año. Se aclara esto en el Word.

No se inventan fechas para ajustes sin Del/Al. Aparece una nota con la cantidad
declarada. Si un intervalo cruza años y sus días declarados no coinciden con la
duración calendaria, se explica en observaciones y no se distribuye en los
cuadros anuales; conserva su consumo en el acumulado. No se prorratea un ajuste
desconocido. Los permisos Ley (09) y movimientos sin consumo positivo no se
distribuyen como días de vacaciones.

Ambos formatos muestran asignación, consumo vigente, saldo acumulado actual y
exceso exacto cuando el saldo es negativo. No son saldos históricos al cierre
del año ni una determinación automática de derechos. Al final se señalan códigos
sin regla, días sin confirmar, fechas faltantes o invertidas, discrepancias de
cantidades y posibles superposiciones (que pueden corresponder a medias
jornadas). Las observaciones no alteran datos ni bloquean la descarga.

`vacaciones_word_layout.json` contiene solo estilos, secciones y cuadros vacíos
extraídos de los dos modelos del responsable. No contiene los documentos
originales, nombres, DNI ni movimientos reales. No se agregaron dependencias ni
migraciones. La generación usa OOXML estándar y funciona sin Word instalado en
Vercel. Las referencias y ejemplos reales quedan fuera de Git.
