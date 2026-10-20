# Manual — gestión de maestros

## Acceso y navegación

Entrar en `/ingresar/` con una cuenta activa y permisos. La interfaz propia no
requiere acceso a Django Admin (`is_staff`). No existe registro público. La
portada es el listado de trabajadores; si su cuenta carece de ese permiso, se
abre el primer maestro que pueda consultar. Cerrar sesión desde la cabecera.
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
justificaciones; el detalle del historial requiere `view_justificacion`, sin
ampliar por defecto los permisos Operador/Consulta de fase 1.

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
cambia por añadir justificaciones; su formulario de alta aún está pendiente.

## Guardado, permisos y auditoría

Guardar valida en servidor y muestra confirmación. Los errores mantienen los datos
ingresados y señalan campos concretos. Si otra sesión guardó la ficha desde que se
abrió el formulario, se avisa y se evita reemplazarla: recargar y revisar antes de
volver a editar. Guardado y auditoría son una sola transacción.

Consulta no escribe; Operador crea/edita trabajadores; Administrador gestiona
maestros. Las rutas comprueban permisos aun si se invocan directamente. Usuarios,
grupos y auditoría permanecen en `/admin/`, con los requisitos de acceso de fase 1.
No hay todavía consultas generales, edición diaria de justificaciones ni carga o
exportación Excel. Vercel y Neon siguen fuera de este alcance.
