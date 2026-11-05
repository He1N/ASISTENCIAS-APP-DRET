# Formatos individuales de vacaciones

Desde el detalle de una ficha, «Generar formato» abre la selección de año y de
Récord, Informe o Ambos. Se requiere lectura del control y permiso de exportación.
Ambos descarga un ZIP con dos DOCX editables. No hay generación general.

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
duración calendaria, debe corregirse antes de dividirlo; no se prorratea un ajuste
desconocido. Los permisos Ley (09) y movimientos sin consumo positivo no se
distribuyen como días de vacaciones.

`vacaciones_word_layout.json` contiene solo estilos, secciones y cuadros vacíos
extraídos de los dos modelos del responsable. No contiene los documentos
originales, nombres, DNI ni movimientos reales. No se agregaron dependencias ni
migraciones. La generación usa OOXML estándar y funciona sin Word instalado en
Vercel. Las referencias y ejemplos reales quedan fuera de Git.
