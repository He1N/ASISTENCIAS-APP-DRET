# Importación Excel — pendiente de fase posterior

Esta fase solo crea modelos de lote e incidencias; no acepta archivos ni ejecuta
importaciones. No se ha probado ningún importador. El workbook real no se copia
al repositorio. No hay dependencia openpyxl todavía.

El futuro asistente debe implementar selección, previsualización, confirmación
transaccional, incidencias, revisión de coincidencias y reimportación idempotente.
Debe descartar TODOS los CUD de octubre 2026 y preservar literalmente los de
noviembre, mantener DNI/códigos con ceros iniciales y no inferir fechas faltantes.
Debe verificar la guía OJO antes de completar reglas de fecha final. Se probará
con XLSX sintético según el mapeo de ESPECIFICACION.md, incluyendo 511 filas.
