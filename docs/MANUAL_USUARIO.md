# Manual — maestros, justificaciones y consultas

## Acceso y navegación

Entrar en `/ingresar/` con una cuenta activa y permisos. La interfaz propia no
requiere acceso a Django Admin (`is_staff`). No existe registro público. La
portada es Consultas; si su cuenta carece de ese permiso,
se abre el primer maestro que pueda consultar. Cerrar sesión desde la cabecera.
En móvil, pulsar Menú para plegar o desplegar la navegación.

Rutas: `/trabajadores/`, `/catalogos/documentos/`, `/catalogos/operaciones/` y
`/periodos/`. Cada listado ofrece búsqueda, estado, total y páginas de 25 filas.
Buscar aplica los filtros; Limpiar filtros los elimina. Ver abre la ficha; Volver,
Editar y Cancelar conservan los filtros y la página del listado. Las tablas se
desplazan horizontalmente en pantallas pequeñas.

## Trabajadores

Buscar por fragmento de nombre, DNI o área; el nombre se busca sin distinguir
tildes o mayúsculas. Filtrar Activos/Inactivos/Todos. Nuevo trabajador necesita
solo nombre; DNI textual de ocho dígitos y área son opcionales. Si hay coincidencias
normalizadas o de DNI, revisar si corresponde reactivar una ficha existente.
La confirmación permite registrar homónimos legítimos sin fusionarlos.

Editar Activo permite desactivar o reactivar, manteniendo ID e historial. No hay
borrado físico desde estas pantallas. La ficha muestra datos y cantidad de
justificaciones; el detalle del historial requiere `view_justificacion`, incluido por defecto para Operador/Consulta al preparar los roles de fase 3.

## Catálogos

Tipos de documento y operación se administran por separado. Buscar por fragmento
de nombre sin tildes/mayúsculas o por código; filtrar por Activos/Inactivos/Todos.
Administrador crea, edita y desactiva; Operador y Consulta solo leen.
Los códigos son texto: conservar, por ejemplo, `01`.

En operaciones, Desconocido significa que la regla de fecha final está pendiente
de revisión; no equivale a No. Seleccionar Sí/No únicamente después de revisar la
fuente. El grupo especial clasifica vacaciones/licencias sindicales, sin calcular
saldos. No se inventan códigos ni reglas a partir de datos faltantes.

## Periodos

Buscar por título/notas y filtrar Abierto/Cerrado/Procesado. El listado muestra
rangos, cantidad total de registros y fechas de cierre/procesamiento.
Administrador crea y edita; los demás roles consultan.

Usar fechas reales del corte administrativo, no meses naturales. El fin puede
quedar vacío y se muestra Sin definir. Fechas invertidas generan error. Si hay
solapamiento, revisar, explicar en Notas y marcar la autorización. El formulario
no adivina ni ajusta fechas.

Cambiar Estado y guardar captura fecha de cierre/procesamiento desde el servidor;
no son campos editables. Al reabrir se conservan las fechas históricas, como en
fase 1. La transición y su autor quedan en auditoría. El estado de un periodo no
cambia por añadir justificaciones; el alta admite periodos cerrados y procesados sin reabrirlos.

## Guardado, permisos y auditoría

Guardar valida en servidor y muestra confirmación. Los errores mantienen los datos
ingresados y señalan campos concretos. Si otra sesión guardó la ficha desde que se
abrió el formulario, se avisa y se evita reemplazarla: recargar y revisar antes de
volver a editar. Guardado y auditoría son una sola transacción.

Consulta no escribe; Operador crea/edita trabajadores y justificaciones;
Administrador gestiona maestros y puede anular justificaciones. Las rutas comprueban permisos aun si se invocan directamente. Usuarios,
grupos y auditoría permanecen en `/admin/`, con los requisitos de acceso de fase 1.
No hay carga o exportación Excel. Vercel y Neon siguen fuera de este alcance.

## Consultas

`/consultas/` muestra resultados con 25 filas por página. La búsqueda general admite
fragmentos de nombre, DNI, CUD y observaciones. Los nombres se buscan sin distinguir
tildes o mayúsculas. Periodo y fecha exacta están a la vista; Más filtros contiene
rango de movimiento, DNI, documento, operación, CUD y estados. Los filtros se
combinan con AND. Fechas inválidas o rango invertido muestran errores y no devuelven
toda la base silenciosamente. Limpiar filtros vuelve al listado sin criterios.

El orden predeterminado es fecha de movimiento descendente, ID descendente como
desempate y fechas faltantes al final. También puede ordenar por última captura.
Se muestran las vigentes por defecto; Anuladas/Todos permite consultar el historial.
Ver abre el detalle. Volver, Editar y Cancelar conservan filtros y página.

## Nueva justificación

En `/justificaciones/nueva/`, seleccionar trabajador, periodo, documento y operación.
Escribir un fragmento en cada buscador actualiza hasta 20 opciones. Seleccionar
explícitamente la ficha por ID y revisar DNI/estado, especialmente si hay homónimos.
No se elige la primera coincidencia automáticamente. Activos aparecen primero;
los trabajadores inactivos siguen disponibles. Si faltan opciones, afinar el texto.
Nuevo trabajador abre otra pestaña; volver y buscar su ficha después de guardarla.
Sin JavaScript, escribir los términos y pulsar Actualizar opciones antes de elegir.

En altas manuales se exige fecha de movimiento. La fecha final es obligatoria solo
si la operación lo indica y puede ser igual al inicio. Una regla pendiente debe
ser revisada por Administrador antes de dar de alta: no se convierte en No.
No se crean documentos u operaciones improvisados desde este formulario.
Los catálogos inactivos sirven para buscar históricos y pueden mantenerse en una
edición existente; no se asignan a nuevas justificaciones.

Salida y retorno son opcionales e independientes; se admiten en papeletas y otros
documentos. Las horas inválidas se rechazan. Una hora aislada o retorno anterior
genera un aviso informativo sin inventar el valor faltante ni presumir un turno.
CUD es opcional, textual, sin unicidad global y conserva ceros/guiones/formato.
Fecha de recepción es opcional y distinta de movimiento, final y captura.

El periodo se elige explícitamente. Si está cerrado/procesado, se avisa y se puede
guardar sin reabrirlo. Cuando hay corte conocido se compara la captura real para
mostrar Tardío; sin corte verificable se muestra Sin determinar. En registros Excel
existentes la tardanza es Importado / sin determinar. El movimiento fuera de rango
exige motivo de excepción, conservado en auditoría; no se reasigna el periodo.

Guardar abre el detalle; Guardar y registrar otro abre una nueva entrada. Fechas y
usuario de captura se asignan en servidor. No representan aprobación administrativa.

## Edición, auditoría y anulación

Editar exige motivo de corrección y mantiene creador, captura, fuente y origen.
Los registros históricos incompletos conservan sus excepciones; no se fabrican fechas.
La edición desactualizada se rechaza. Administradores ven en el detalle el historial
de campos anteriores/nuevos y los motivos; Operador/Consulta no ven la auditoría.

Anular requiere permiso específico, motivo y confirmación en una pantalla separada.
Conserva el registro, actor, fecha y motivo; no se borra ni se edita una ficha anulada.
No se incluye restauración. Vacaciones muestran únicamente duración calendaria
informativa si inicio/fin se conocen; no calculan saldos ni descuentos oficiales.
