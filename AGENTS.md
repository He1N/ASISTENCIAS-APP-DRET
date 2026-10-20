# Instrucciones para Codex — Control de asistencias

Lee **`ESPECIFICACION.md`** completa antes de empezar. Es la fuente de verdad del producto; no sustituyas reglas de negocio por suposiciones.

## Objetivo
Implementar una aplicación Django de gestión interna de justificaciones de asistencia con interfaz administrativa sobria en español. Debe permitir registro web, importación Excel y exportación de búsquedas filtradas. Preparar PostgreSQL/Neon y despliegue futuro en Vercel, con SQLite local para pruebas.

## Reglas no negociables

1. No usar lenguaje de marketing, frases decorativas, ilustraciones hero, UI extravagante, dashboards vacíos ni SPA innecesaria.
2. El nombre es suficiente para crear trabajador; DNI/área opcionales; trabajador activo/inactivo con posible reactivación e historial conservado.
3. Autocompletar trabajador, tipo de documento y tipo de operación.
4. Los periodos no son meses naturales y se pueden agregar justificaciones a periodos ya cerrados/procesados sin reabrirlos.
5. `fecha_movimiento`, `fecha_final`, `fecha_recepcion` y fecha de captura son datos distintos; no deducir fecha de recepción de forma automática.
6. Vacaciones y licencias sindicales tienen pantallas dedicadas; **no calcular saldos oficiales**.
7. Excel octubre 2026: ignorar TODOS los CUD por posible desalineación; noviembre: preservar CUD. No ajustar los códigos a ojo.
8. Importación siempre con previsualización, incidencias, validación y control de reimportaciones.
9. Proteger rutas con roles, auditoría, CSRF, autenticación. No publicar ni commitear datos personales, `.env` o workbook real.
10. No convertir DNI/CUD/códigos con ceros a la izquierda a enteros. Preservar integridad histórica.

## Modo de trabajo

- Primero inspecciona el repositorio (si está vacío, inicializa proyecto); informa brevemente el plan y después **implementa**, no te quedes únicamente en diseño.
- Avanza por fases funcionales y confirma con migraciones, tests y `manage.py check`. Prioriza una ruta completa funcional antes de estética adicional.
- Usa dependencias mínimas y controladas, código claro en Python/Django y Django templates.
- El repositorio puede no contener el XLSX original por privacidad. Por tanto implementa importador parametrizado y tests con XLSX **sintético**, según mapeo de `ESPECIFICACION.md`. No inventes datos reales.
- Nunca ejecutas cambios peligrosos sobre datos reales sin una copia de seguridad verificable.
- Deja comandos exactos y entorno reproducible. Si falta una decisión no crítica, toma una opción conservadora y anótala; no interrumpas el desarrollo con muchas preguntas.
- Al terminar explica: qué implementaste, qué probaste realmente, qué quedó pendiente, cómo ejecutarlo, y qué datos/secretos se deben configurar.
