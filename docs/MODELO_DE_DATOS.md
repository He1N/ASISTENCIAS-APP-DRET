# Modelo de datos — fases 1, 2 y 3

Trabajador: nombre obligatorio no único, DNI textual nullable, área opcional,
activo y timestamps. Índice normalizado auxiliar sin modificar el nombre original.
TipoDocumento y TipoOperacion mantienen nombre, código textual, activo y fechas.
La operación admite regla final nullable: NULL significa pendiente, no falso.
Grupo especial NINGUNO/VACACIONES/SINDICAL independiente del nombre literal.

PeriodoAsistencia tiene rango administrativo, fin nullable, estados ABIERTO,
CERRADO, PROCESADO y fechas de transición. La interfaz registra cierre y
procesamiento con fecha/actor auditados y conserva esas fechas al reabrir. El
estado no se modifica al guardar una justificación. Rangos invertidos se rechazan;
solapamientos requieren confirmación y notas. No se infiere el fin de noviembre.

Justificacion referencia trabajador, periodo, documento y operación con PROTECT;
fecha de movimiento/final/recepción separadas, horas independientes, CUD textual,
creador/editor, captura, origen y anulación lógica. `full_clean()` valida altas
manuales y reglas finales, incluyendo fin igual al inicio. Como Django no llama
`full_clean()` en `save()`, futuros servicios deben validar explícitamente.
Importados devuelven tardanza indeterminada. La restricción SQL de orden de fechas
rechaza contradicciones; el futuro importador deberá conservar el crudo en
incidencias y evitar insertar fechas contradictorias sin revisión.

LoteImportacion contiene checksum, hoja, periodo, contadores, actor y reglas;
IncidenciaImportacion enlaza lote, fila, campo y severidad. Son estructura sin
importador activo. La política de reimportación se completará con el asistente.
HistorialCambio almacena actor, fecha y diferencias; protegido en la interfaz,
sin almacenar contraseñas. Usuarios y grupos usan el historial nativo de Django.
No hay borrado físico de maestros desde la interfaz; las relaciones históricas
usan PROTECT. Roles se preparan después de migrar con `preparar_roles`.

## Interfaces de fase 2

Sin cambios en modelos ni migraciones. Las pantallas propias reutilizan los
ModelForms de fase 1 y una función compartida con Admin para las fechas de estado.
Cada ruta aplica permisos Django; lectura no concede escritura. La edición web
valida la versión `updated_at` leída al abrir y guarda dentro de `atomic()` con
su HistorialCambio. Los campos de versión/autorizaciones son solo de formulario.
SQLite no implementa bloqueo de filas: antes de producción se debe probar el
comportamiento con el motor definitivo. Las escrituras por Admin conservan el
comportamiento de fase 1; su formulario no usa la versión de las pantallas web.

## Justificaciones y consultas — fase 3

No se añaden campos ni migraciones. El cambio de modelo es de comportamiento:
si falta un corte verificable en un periodo cerrado/procesado, el plazo es Sin
determinar, en lugar de marcarlo ordinario. Los importados conservan plazo incierto.

Los ModelForms reutilizan validaciones de modelo, controles de fechas/rango y
catálogos existentes. La edición guarda motivo, versión y actor en transacción.
`HistorialCambio.cambios` añade motivo_excepcion/motivo_edicion como contexto con
valores previos/nuevos. La anulación usa los campos ya existentes; no borra datos.
Los campos de captura, usuario y fuente no están expuestos al POST del formulario.

Los filtros/autocompletados usan Django ORM, índice normalizado auxiliar y
`select_related`; no dependen de extensiones PostgreSQL ni SQL específico de SQLite.
El orden de Consultas indica NULLS LAST explícitamente para igualar ambos motores.
SQLite se ha probado; PostgreSQL no se ha ejecutado todavía ni se configura Neon.
En un despliegue futuro deberán validarse el controlador, configuración y migraciones
bajo PostgreSQL antes de introducir datos institucionales.

Roles fase 3: Operador obtiene view/add/change_justificacion; Consulta obtiene
view_justificacion. Administrador conserva todos los permisos de control. No se
conceden permisos de Excel ni anulación a Operador por defecto. Ejecutar
preparar_roles tras actualizar; no se añade una migración que reasigne cuentas.
