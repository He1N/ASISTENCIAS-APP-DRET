# Vacaciones desde Consultas

Desde esta actualización, guardar una justificación del grupo Vacaciones genera
o actualiza su consumo en el control vacacional dentro de la misma transacción.
Aplica tanto al formulario web como a la importación Excel confirmada.

- Código 05: días calendario inclusivos entre fecha de movimiento y fecha final.
- Código 32: 0,5 días en una sola fecha. Si tiene un intervalo de varias fechas,
  queda pendiente de confirmar, sin inventar una distribución.
- Editar cambia el mismo movimiento; trasladar a otro trabajador traslada su
  consumo. Anular o cambiar a otra operación devuelve los días.
- Repetir un guardado o confirmar otra vez un lote no duplica el descuento.
- Un consumo equivalente ya enlazado, anulado o ambiguo se señala para revisión
  antes de descontar otro registro. La equivalencia exige persona, fechas,
  cantidad, código compatible y observaciones/documento coincidentes.

La ficha se resuelve por vínculo explícito, DNI único o nombre normalizado
inequívoco sin DNI contradictorio. Si no existe y hay DNI inequívoco, se crea sin
asignaciones: no concede derechos y puede mostrar saldo negativo. Falta de
identidad o datos se muestra como pendiente en Consultas y en el control.
Completar los datos y volver a guardar reintenta la sincronización.

El detalle de Consultas muestra el estado del enlace. Los movimientos enlazados
se editan o anulan desde su justificación para mantener ambas vistas consistentes.
Los movimientos manuales o del histórico que no tienen enlace conservan su
edición habitual. Las asignaciones siguen siendo explícitas y editables.

## Conciliación histórica

La migración 0005 añade únicamente EnlaceVacacion, sin recálculo de datos. Antes
de aplicar en producción, verificar respaldo y ensayar en una copia aislada.
La conciliación tiene previa y requiere confirmación y usuario autorizado:

```text
python manage.py conciliar_vacaciones --periodo ID
python manage.py conciliar_vacaciones --periodo ID --confirmar --usuario ADMINISTRADOR
```

Se concilia el periodo administrativo Noviembre 2026, cuyo inicio es 12/10/2026;
no equivale al mes calendario. No se concilia Octubre automáticamente.
Los consumos equivalentes vigentes se enlazan sin modificar los movimientos.
Las diferencias quedan como EXCEPCION, conservando los ajustes, anulaciones y
suspensiones del control por decisión expresa del responsable. Sus observaciones
comparan fechas, cantidades y documentos de ambos módulos y aparecen al final
de la ficha y de los formatos Word. Guardar de nuevo una excepción no sustituye
su ajuste histórico; su resolución exige revisión administrativa explícita.

La relación uno a uno impide enlazar un movimiento a dos justificaciones.
EnlaceVacacion y los cambios de consumo registran auditoría. La conciliación
es idempotente. Para cargas técnicas con bulk_create/QuerySet.update, que omiten
save de Django, se debe invocar explícitamente el servicio de sincronización o
el comando de conciliación; la importación web utiliza save y sí sincroniza.
