# Sistema interno de control de justificaciones de asistencia

**Versión:** 1.0 · **Idioma de la aplicación:** español (Perú) · **Zona horaria:** America/Lima  
**Destino:** repositorio GitHub conectado a Codex Cloud  
**Estado:** especificación de implementación del primer producto funcional (MVP).

## 1. Propósito y alcance

Construir una aplicación administrativa para registrar, consultar, corregir, importar y exportar **justificaciones de asistencia** del personal de una entidad pública. Actualmente se usan hojas físicas y un libro de Excel. La aplicación reemplazará la edición diaria del libro cuando resulte conveniente, **sin eliminar** la posibilidad de importar nuevas hojas Excel ni exportar resultados.

Usuarios previstos: aproximadamente 2–3 concurrentes, y otros encargados que asumirán el trabajo en el futuro. Prioridades: integridad histórica, búsquedas rápidas, operación sencilla, continuidad del servicio, trazabilidad y privacidad.

**No construir** un sistema de marcación biométrica, control horario en tiempo real, planillas, cálculos de pago, saldo oficial de vacaciones, ni una web comercial. No asumir que registrar una justificación equivale a que esta surta efectos administrativos.

## 2. Arquitectura y condiciones de ejecución

- Backend: **Python + Django**, versión estable compatible con despliegue previsto; Django ORM, vistas/formularios del servidor. Evitar SPA/Node y complejidad innecesaria.
- Base de datos: **SQLite** para desarrollo y pruebas, **PostgreSQL (Neon)** para producción por variable `DATABASE_URL`. Migraciones Django compatibles con ambos motores; verificar incompatibilidades de SQL y pruebas en PostgreSQL antes de producción.
- Despliegue futuro: **Vercel** para aplicación Django y **Neon** para PostgreSQL; separar configuración por entorno y no asumir almacenamiento persistente local en Vercel. Usar almacenamiento externo solo si en el futuro se autoriza conservar adjuntos.
- Presentación: plantillas Django con HTML accesible, CSS sencillo (propio o framework ligero con archivos locales), JavaScript progresivo mínimo. No exigir un proceso de compilación frontend ni una versión reciente de VS Code.
- Autenticación: sistema de usuarios Django, contraseñas hasheadas, sesiones, protección CSRF. Acceso autenticado para cualquier dato de personal.
- Internacionalización: textos en español; `TIME_ZONE = 'America/Lima'`, `USE_TZ = True`; fechas visibles `dd/mm/aaaa` y horas en formato 24 horas. Guardar fechas como `DateField` y horas como `TimeField`, no strings.
- Privacidad: los datos reales de empleados deben quedar fuera de repositorios, logs y despliegues externos hasta contar con autorización institucional. Probar con datos inventados/anonimizados. No subir el Excel real al GitHub por defecto.
- No incorporar servicios pagos, OCR, IA externa ni procesos automáticos de correo en MVP.

## 3. Terminología y modelo conceptual

### 3.1 Trabajador

Campos: `id` interno (PK), `apellidos_nombres` obligatorio, `dni` opcional (string, preservar ceros iniciales), `area` opcional (texto libre en MVP), `estado` activo/inactivo, `created_at`, `updated_at`.

- Registrar únicamente con nombre, aun si falta DNI y área.
- Autocompletar por **cualquier fragmento del nombre**, sin distinguir mayúsculas ni tildes cuando sea viable; mostrar activos primero, pero permitir seleccionar inactivos.
- Evitar duplicados de manera asistida: advertir por coincidencias normalizadas de nombre y por DNI existente; **no bloquear automáticamente homónimos**. No fijar nombre como único.
- Si alguien regresa, reactivar su ficha histórica en lugar de crear otra; nunca eliminar en cascada sus registros.
- Conservación de nombres: no modificar silenciosamente el texto original o sus posibles errores de codificación; admitir corrección manual.

### 3.2 Catálogo `TipoDocumento`

Campos: `id`, `codigo_externo` opcional, `nombre`, `activo`, timestamps. Valores iniciales detectados en registros: `Papeleta de Permiso | 01`, `Oficio | 03`, `Memorandum | 04`, `Informe | 05`, `Carta | 06`, `Solicitud | 07`, `Otros | 09`. Conservar códigos como texto con ceros a la izquierda y normalizar espacios sin cambiar la semántica. Catalogar otros valores válidos detectados al importar, previa revisión.

### 3.3 Catálogo `TipoOperacion`

Campos: `id`, `codigo_externo` opcional, `nombre`, `requiere_fecha_final` (booleano), `activo`, `grupo_especial` (`NINGUNO`, `VACACIONES`, `SINDICAL`) y timestamps. Precargar desde hoja `OJO` y cotejar con las operaciones de los registros; no inventar código donde `OJO` solo trae nombre. Si falta una regla SI/NO en la hoja, dejarla **pendiente de revisión** antes de fijar obligación; no interpretar celdas vacías como `NO` de forma silenciosa.

- Tipo de operación y tipo de documento son catálogos distintos y **ambos con autocompletado**.
- Administrador puede agregar, editar y desactivar entradas; preservar referencias históricas e impedir eliminación destructiva si ya se usaron.
- Permitir indicar y ajustar si una operación requiere fecha final, incluso cuando inicio y fin sean el mismo día.
- `grupo_especial` alimenta las secciones dedicadas sin acoplarlas al nombre literal. Sembrar `Vacaciones`, `Vacaciones 1/2 Jornada` bajo `VACACIONES` (mostrar subtipo en la interfaz), `Permiso Sindical` bajo `SINDICAL` (interfaz titulada “Licencias sindicales”). Verificar con el usuario cualquier categoría sindical adicional antes de incluirla.

### 3.4 `PeriodoAsistencia`

Campos: `id`, `titulo` (p.ej. «Octubre 2026»), `fecha_inicio`, `fecha_fin` opcional mientras está abierto, `estado` (`ABIERTO`, `CERRADO`, `PROCESADO`), `fecha_cierre` opcional, `fecha_procesamiento` opcional, `notas`, timestamps.

- Los periodos **no coinciden necesariamente con meses naturales**. Ejemplo: periodo octubre 2026, del **07/09/2026 al 09/10/2026**. El siguiente empieza **12/10/2026** y su fecha final no está definida en el Excel.
- El encargado administra rangos y estados; no inferir la fecha final del título de una hoja incompleta.
- Distinguir `CERRADO` (registro ordinario concluido) de `PROCESADO` (información enviada/cargada al sistema externo); la transición es manual con permisos y fecha auditada.
- **Permitir agregar justificaciones a periodos cerrados o procesados**. No cambiar el estado del periodo al hacerlo.
- La asignación al periodo es explícita, editable y visible; no mover automáticamente a otro periodo por fecha de movimiento. Advertir si la fecha cae fuera de su rango, pero permitir excepción motivada, ya que los periodos pueden tener cortes administrativos.
- Evitar solapamientos accidentales entre periodos con aviso en formulario; no bloquear si existe una excepción autorizada.

### 3.5 `Justificacion`

Campos: `id`, `periodo_id` FK PROTECT, `trabajador_id` FK PROTECT, `tipo_documento_id` FK PROTECT, `tipo_operacion_id` FK PROTECT, `fecha_movimiento` opcional durante importación de legados/incompletos (obligatoria para alta manual normal), `fecha_final` opcional/obligatoria según regla del tipo de operación, `hora_salida` opcional, `hora_retorno` opcional, `observaciones` texto opcional, `cud` texto opcional, `fecha_recepcion` opcional (cuándo llegó físicamente), `created_at` (cuándo se registró en la app), `created_by`, `updated_at`, `updated_by`, `es_registro_tardio` derivado o calculado con fecha real de captura y `fecha_cierre`/`fecha_procesamiento`, `fuente` (`MANUAL`, `EXCEL`), `lote_importacion_id` opcional, `fila_origen` opcional, `item_origen` opcional.

- **No equiparar** `fecha_movimiento`, `fecha_recepcion`, `created_at` y `fecha_final`.
- No calcular tardanza de forma retroactiva para registros históricos migrados, pues no se conoce su fecha original de digitación: mostrar `Sin determinar`/`Importado` cuando corresponda.
- La fecha final puede ser igual a fecha de movimiento. Si ambas existen, validar `fecha_final >= fecha_movimiento`; en legados contradictorios, marcar observación de importación sin perder el dato crudo.
- Salida y retorno aplican principalmente a papeletas, pero **no imponer** que solo las papeletas admitan horas: el Excel tiene horas en otros documentos. Horas: permitir nulos independientes y registrar advertencias razonables (sin asumir turnos ni cruce de medianoche).
- `cud` es texto: puede incluir guiones o múltiples códigos; conservar formato literal. Opcional para papeletas y demás documentos; no imponer unicidad global sin definición institucional verificada.
- No calcular saldo vacacional automáticamente. Para vacaciones: fechas y duración **calendaria informativa** si inicio/fin conocidos, etiquetada como tal; evitar contar días hábiles o descontar saldos, sobre todo en `Vacaciones 1/2 Jornada`.
- Edición controlada y auditoría de quién cambió qué. Si se necesita borrar un registro, preferir anulación lógica con motivo, fecha y usuario frente a borrado físico.

### 3.6 `LoteImportacion` y `IncidenciaImportacion`

Lote: archivo/nombre original (sin almacenar contenido sensible indefinidamente), checksum SHA-256, fecha, usuario, hoja, periodo elegido, total leídos, insertados, omitidos, alertas, estado, reglas aplicadas. Incidencia: número de fila, campo, mensaje, severidad, valor original mínimo necesario; evitar volcar PII en logs.

`HistorialCambio`/auditoría: entidad, ID, acción, autor, fecha, campos modificados y valores previos/nuevos con control de acceso. No registrar contraseñas ni secretos.

## 4. Reglas de importación de XLSX (críticas)

**Archivo de referencia facilitado por el usuario:** `FORMATO CONTROL DE ASISTENCIA 2026.xlsx`. **Aclaraciones de referencia:** `asistencias_instructions.txt`. El archivo real se utilizará localmente/privadamente; no subirlo a GitHub ni sembrar la base de datos pública con datos personales.

### 4.1 Estructura real inspeccionada

- Hoja `OJO`: guía y catálogo de operaciones en columnas B/C; encabezados fila 9 (`TIPO`, `LLEVA FECHA FINAL`); operaciones hasta fila 42. También contiene una sección separada de permisos justificados según RDR: no confundirla con catálogo de operaciones; no implementar sus reglas RDR sin requerimiento adicional.
- Hoja `OCTUBRE DEL 7.9.26 AL 9.10.26`: periodo del 07/09/2026 al 09/10/2026. **427 filas de registros identificables** por item numérico y nombre, filas 5–431.
- Hoja `NOVIEMBRE 12.10.26 AL `: periodo desde 12/10/2026, fecha final aún no confirmada. **84 filas identificables**, filas 5–88.
- Total inicial identificable: **511 filas**. Son conteos de filas estructuradas, no garantía de que todas sean completas o válidas.
- Encabezado de dos filas: fila 2 y fila 3. Mapeo de columnas: `A=Items`, `B=Apellidos y Nombres`, `C=Tipo Documento`, `D=Tipo Operación`, `E=Fecha Movimiento`, `F=Salida Hora`, `G=Salida Minuto`, `H=Retorno Hora`, `I=Retorno Minuto`, `J=Observaciones`, `K=Fecha Final`, `L=N° CUD`. No procesar columnas `M:AD` sin inspección explícita.
- `B` contiene en muchos casos `APELLIDOS NOMBRES | DNI`, con DNI opcional y a veces vacío; separar por el **último** delimitador `|`, preservar el nombre y validar que la parte de DNI sea plausible antes de asignarla; en caso contrario no perder el texto crudo.
- `C` y `D` contienen valores `Nombre | código` (p.ej. `Papeleta de Permiso | 01`, `Vacaciones | 05`); preservar código como texto.
- `E`/`K` pueden estar codificadas como fechas Excel; `F:I` son horas/minutos en columnas separadas. Admitir celdas nulas y formatos heterogéneos, con incidencias en vista previa.

### 4.2 Excepción obligatoria de CUD por periodo

- **OCTUBRE 2026:** **ignorar por completo la columna L/CUD durante la importación**, guardar `cud = NULL` en todas las filas de esta hoja, incluso cuando la celda contenga un valor. Motivo: el usuario indica que la columna posiblemente quedó desalineada al ordenar el Excel. Dejar constancia `cud_omitido_por_desalineacion_octubre` a nivel de lote; jamás adjudicar el CUD sospechoso a otro trabajador.
- **NOVIEMBRE 2026:** importar CUD tal como figura, conservándolo como texto. No reasignar ni inferir CUD faltantes.
- En nuevos archivos de periodos posteriores, usar CUD cuando exista y ofrecer configuración específica de la hoja en la vista previa, sin aplicar automáticamente la excepción de octubre a otras hojas.

### 4.3 Flujo seguro de importación

1. Subida XLSX **solo por usuarios autorizados** con límite de tamaño y validación de extensión/contenido; no ejecutar macros ni fórmulas.
2. Detectar hojas relevantes y mostrar selección de hoja(s) y periodo(s). No importar `OJO` como registros.
3. Analizar filas, mostrar previsualización (al menos primeras y todas las problemáticas), cantidades y alertas; opción de omitir incidencias o corregirlas antes de confirmar.
4. Mapear trabajadores/catálogos existentes por identificadores y normalización controlada; ante conflicto/homónimos o códigos inconsistentes, solicitar revisión, no enlazar automáticamente a persona equivocada.
5. Antes de insertar, detectar duplicados de manera **conservadora** por huella normalizada del registro + periodo + origen y avisar; duplicados posibles no deben destruir datos ni impedir registros legítimos distintos. Para reimportar el mismo archivo/hoja sin modificaciones, ofrecer omisión idempotente.
6. Confirmación transaccional (`transaction.atomic`), resumen y registro de incidencias, con posibilidad de deshacer un lote solo si no afectaría cambios posteriores, o mediante anulación auditada.
7. Conservar trazabilidad a lote, hoja/fila/ítem de origen, checksum, pero **no guardar el XLSX permanentemente** por defecto.
8. Los registros históricos no tienen fecha de alta administrativa verificable: no marcarlos automáticamente como tardíos solo porque se importan hoy.
9. No modificar fechas, horas, CUD o texto original sin advertir. Para campos faltantes de origen, permitir importación con estado/alerta `INCOMPLETO_LEGADO` en vez de inventar valores.

## 5. Funcionalidades por pantalla

### 5.1 Acceso

Página de inicio de sesión sin registro público. Sesión con salida y mensaje neutro de error. Control de acceso servidor, no solo ocultación de botones.

### 5.2 Consultas (pantalla principal tras ingresar)

- Buscador persistente por nombre parcial, DNI, CUD, observaciones; filtros independientes por fecha de movimiento (exacta o rango), periodo, tipo de documento, tipo de operación y estado/activo de trabajador cuando proceda.
- Paginación y orden descendente por fecha de movimiento o por último registro; orden estable por ID.
- Tabla compacta con columnas: fecha, trabajador, documento, operación, intervalo/horas relevante, periodo, CUD, acción Ver/Editar.
- Mostrar total de coincidencias y botón `Limpiar filtros`. Conservar filtros al ir a detalle y volver.
- Exportación XLSX **solo de resultados filtrados**, con encabezados claros, sin fórmulas ejecutables. Evitar CSV formula injection si se incorpora CSV.

### 5.3 Nueva justificación / editar

- Formulario vertical agrupado: trabajador (autocompletado y acceso a `Nuevo trabajador`), periodo, documento, operación, fecha de movimiento, fecha final condicional, salida/retorno, CUD, observaciones, fecha de recepción opcional.
- Autocompletado **en los tres**: trabajador, tipo documento, tipo operación. Permitir búsqueda por cualquier parte del texto. Evitar desplegables gigantes y evitar creación de operaciones improvisadas dentro de una entrada normal.
- Fecha final se exige si el catálogo lo indica; mostrar error contextual si falta. Si no se requiere, permitir ingresarla cuando tenga sentido.
- Mensaje discreto si periodo cerrado/procesado: `Este periodo está cerrado. El registro se añadirá al historial.` No bloquear.
- Guardar y `Guardar y registrar otro`; mostrar confirmación corta y específica. Validar servidor y cliente cuando convenga.

### 5.4 Trabajadores

Listado con búsqueda y filtro Activos/Inactivos/Todos; ficha con datos editables, estado y lista de justificaciones relacionadas. Alta con nombre obligatorio, DNI y área opcionales. No perder registros al cambiar de estado.

### 5.5 Vacaciones

Consulta dedicada de operaciones del grupo `VACACIONES`; buscar trabajador, fechas, periodo y subtipo. Mostrar inicio, fin, duración informativa (si calculable), documento y observaciones; detalle. No presentar `saldo restante` sin reglas oficialmente definidas.

### 5.6 Licencias sindicales

Consulta dedicada del grupo `SINDICAL`, inicialmente `Permiso Sindical` del Excel. Filtros equivalentes; no fusionar con vacaciones, no asumir consumo del saldo vacacional.

### 5.7 Periodos

Tabla de periodos, rangos, estado, cantidad de registros, fecha cierre/procesamiento. Crear/editar rangos y cambiar estado según roles. Desde un periodo procesado se puede ingresar un registro tardío, que queda identificado sin modificar el estado del periodo.

### 5.8 Importar / Exportar

Asistente en 3 pantallas funcionales **sin frases promocionales**: seleccionar archivo/hoja/periodo, revisar previsualización/incidencias, confirmar y ver resumen. Exportar filtros desde consultas y listados.

### 5.9 Configuración y usuarios

Catálogos separados de tipos de documento y operación, alta/edición/desactivación; regla de fecha final y grupo especial. Gestión de usuarios/roles exclusiva de administradores. Registro de auditoría legible para administradores.

## 6. Roles y permisos

- **Administrador:** usuarios, permisos, catálogos, trabajadores, periodos, justificaciones, importaciones/exportaciones, auditoría.
- **Operador:** consultar, registrar, editar, importar y exportar, alta/edición de trabajadores; no administrar usuarios/roles; cambios sensibles de catálogos/periodos restringidos según política elegida (por defecto solo administrador).
- **Consulta:** lectura y búsqueda; exportación si administrador habilita permiso específico; sin escritura.
- Django Groups + Permissions y validación en cada vista/endpoints. No registro público, no superusuario hardcodeado.
- Diseñar traspaso al siguiente encargado: otro administrador autorizado puede crear/desactivar cuentas y cambiar contraseña; documentar procedimiento. No utilizar cuenta personal del desarrollador como único administrador institucional.

## 7. Diseño visual y experiencia de uso

**Estética:** administración institucional discreta. Fondo claro blanco/gris suave, texto de alto contraste, un solo color de acento moderado (azul oscuro o verde sobrio), tipografía de sistema, bordes finos, espaciado consistente. Sin degradados llamativos, hero sections, animaciones decorativas, tarjetas gigantes, efectos glassmorphism, ilustraciones innecesarias o fondos estridentes.

**Regla de contenido:** usar etiquetas directas: `Consultas`, `Nueva justificación`, `Trabajadores`, `Vacaciones`, `Licencias sindicales`, `Periodos`, `Importar Excel`, `Catálogos`, `Usuarios`. **Prohibidos eslóganes y texto de marketing** como «La asistencia en tres pasos», «Fácil de usar», «Optimiza tu gestión», «Bienvenido al futuro», etc. No generar relleno explicativo en la pantalla de inicio.

**Distribución:** barra lateral compacta en escritorio, navegación móvil colapsable; barra superior con usuario y `Cerrar sesión`. La pantalla de consultas muestra título, búsqueda, filtros y tabla **sin dashboard decorativo como portada obligatoria**. Filtros prioritarios visibles y avanzados desplegables, botones claramente etiquetados. Formularios de una columna o dos solo en pantallas anchas, buen foco de teclado, errores junto a su campo, estados vacíos informativos. Tablas horizontales desplazables en móvil cuando sea necesario.

Accesibilidad mínima: labels asociadas, navegación por teclado, contraste WCAG AA cuando sea viable, no transmitir estados solo con color. Mantener nombres propios y datos largos legibles. Fechas `dd/mm/aaaa`, hora 24 h, confirmación para acciones destructivas y mensajes breves.

## 8. Validaciones y decisiones prudentes

- Campos de tipo DNI y CUD son texto; no convertir a enteros.
- El nombre es el único campo obligatorio para crear trabajador.
- En nuevo registro manual exigir trabajador, periodo, documento, operación y fecha de movimiento; fecha final según configuración del tipo. En importación legada permitir excepciones con incidencia y sin rellenar artificialmente.
- Puede haber varias justificaciones para una misma persona y fecha; no usar restricción única en `(trabajador, fecha)`.
- Fecha final = fecha inicio es legítima. No asumir duración laboral por días naturales.
- `fecha_recepcion` no sustituye `created_at` y la ausencia de aquella no supone que el documento llegó el día del movimiento.
- Cambios en nombres de catálogos no deben cambiar identidades/códigos históricos sin trazabilidad.
- La clasificación de operación por `grupo_especial` es configurable por admin para ampliar categorías futuras.
- Delimitar cuáles datos personales muestra el rol Consulta; aplicar mínimo privilegio.

## 9. Seguridad, privacidad y despliegue

- Variables de entorno `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`; ejemplo `.env.example` sin valores reales. Nunca versionar `.env`, `db.sqlite3`, XLSX reales, volcados o archivos con datos del personal.
- HTTPS, cookies seguras en producción, cabeceras de seguridad, evitar SQL dinámico y escapes inseguros de HTML. Permisos en servidor; evitar IDOR. Límites de carga de archivos y paginación.
- En Vercel: tratar filesystem como efímero; static files generados en build o servidos con configuración probada, no usarlo como repositorio de adjuntos. Documentar migraciones contra Neon y cómo ejecutarlas desde un ambiente autorizado, **no asumir que el build ejecuta migraciones de forma segura**.
- El proyecto debe poder ejecutarse localmente con SQLite y datos sintéticos antes de disponer de Neon.
- Copia de seguridad y restauración de PostgreSQL: documentar proceso operativo, responsabilidades y ensayo periódico; no prometer que exportar Excel equivale a backup íntegro.
- Como son datos laborales de entidad pública, **no desplegar información real en servicios de terceros sin autorización institucional** y revisión de medidas de protección de datos aplicables.

## 10. Pruebas y criterios de aceptación

Escribir pruebas automatizadas Django de modelos, formularios, permisos, importador y filtros, incluyendo:

1. Trabajador creado solo con nombre; DNI nulo; puede desactivarse y reactivarse conservando historial.
2. Búsqueda/autocompletado parcial de nombre y en ambos tipos; no seleccionar incorrectamente homónimos.
3. Crear justificación de periodo `PROCESADO` no cambia su estado y registra actor/fecha; avisar que se registra fuera de plazo cuando se conozca la fecha de captura.
4. Periodo de octubre 07/09–09/10 y noviembre desde 12/10 con fin sin definir; no derivar mes natural.
5. Operación con `requiere_fecha_final=True` rechaza alta manual sin fecha fin, acepta fin igual a inicio.
6. Importación octubre descarta **todos** los CUD, noviembre los conserva como texto, incluidos códigos alfanuméricos o con guiones.
7. Parseo Excel conserva DNI con ceros iniciales; no convierte `Papeleta de Permiso | 01` a código `1`.
8. Filas de horas incompletas, fecha de movimiento vacía y reglas no definidas producen incidencias, no valores inventados.
9. Reimportar archivo sin cambios no duplica los mismos registros; duplicados ambiguos requieren revisión.
10. Rol Consulta no altera registros ni invoca endpoints administrativos; Operador no modifica cuentas.
11. Filtros combinados por fecha, trabajador, periodo, CUD, documento y operación; exportación respeta resultados.
12. Vacaciones y sindical filtran por grupo especial, sin generar saldo administrativo imaginario.
13. Auditoría registra creador/editor y modificaciones críticas.
14. Cargar 511 filas de prueba sintéticas y verificar paginación y tiempos razonables (sin afirmar un SLA no medido).

**Definición de terminado de MVP:** las vistas anteriores operan de extremo a extremo, los tests pasan, `python manage.py check` pasa, las migraciones se aplican desde cero, interfaz coherente en escritorio/móvil, instrucciones claras de ejecución local, importador verificable con archivos de prueba ficticios, configuración preparada para PostgreSQL y sin credenciales ni información personal en el repositorio.

## 11. Implementación sugerida por fases

**Fase 1 — Cimientos:** inspección de repo, inicialización Django, settings por entorno, autenticación, roles, modelos, migraciones, catálogo y datos sintéticos.

**Fase 2 — Operación diaria:** diseño base, consultas, filtros, trabajadores y nueva/editar justificación, permisos, auditoría.

**Fase 3 — Históricos:** periodos, vacaciones y licencias sindicales, catálogos administrables, importación XLSX con previsualización y excepción CUD de octubre, exportación XLSX.

**Fase 4 — Calidad y despliegue:** pruebas, documentación de uso, README instalación/ejecución, `.env.example`, validación PostgreSQL/Neon y preparación Vercel sin publicar datos reales.

## 12. Entregables que debe producir Codex

- Código funcional Django con migraciones versionadas.
- Tests automatizados (incluidos fixtures sintéticos y prueba de importación XLSX).
- `README.md` con instrucciones precisas de ejecución, tests, migración y exportación.
- `.env.example` y `.gitignore` adecuados.
- `docs/MODELO_DE_DATOS.md`, `docs/IMPORTACION_EXCEL.md`, `docs/MANUAL_USUARIO.md` breves y actualizados al código implementado.
- Resumen final de cambios, comandos verificados, limitaciones reales y próximos pasos. No afirmar que algo está probado sin ejecutarlo.

## 13. Decisiones que **no** están confirmadas

No inventar ni ocultar: (a) fecha final del periodo noviembre; (b) reglas administrativas para descuentos de vacaciones/sindicales y medio día; (c) criterios exactos de cierre/procesamiento en sistema externo; (d) catálogo completo de códigos ajenos al Excel; (e) qué empleados tienen qué áreas o DNI cuando falta; (f) autorización de alojamiento de datos reales en servicios externos. Implementar comportamiento conservador, dejar configuración o notas explícitas y no frenar el MVP por estos puntos.
