# Validación — fase 2

## Comandos ejecutados

En Python 3.12 con las dependencias fijadas de requirements.txt:

```bash
export DEBUG=True
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
```

Resultados: check sin incidencias, ninguna migración pendiente y 26 pruebas
aprobadas (11 de cimientos y 15 web). La base de pruebas SQLite se crea desde cero
con las migraciones de fase 1 y se elimina al terminar. También se verificó
`migrate --noinput` en una SQLite nueva aislada para la revisión de navegador.

## Cobertura automatizada

Las pruebas web verifican login sin is_staff, logout POST, redirección externa
rechazada, protección de lectura/escritura por rol, anonimato, CSRF, 404 y métodos
permitidos; búsqueda parcial normalizada y por DNI; filtros/paginación y retorno;
alta con solo nombre, DNI con ceros, coincidencias confirmables y validación;
desactivación/reactivación sin perder relaciones; códigos de catálogo, regla final
pendiente/verdadera y grupos especiales; periodo abierto sin fin, validación de
rangos/solapamientos y transiciones con fechas servidor; auditoría y rollback
si falla, rechazo de versiones obsoletas, escape HTML y respuestas sin caché.

## Revisión en navegador

Flujo ejecutado con Playwright y Chromium local, usando una base separada con
fichas ficticias y una cuenta de prueba sin is_staff. Escritorio 1440×1000 y móvil
390×844: iniciar sesión, crear trabajador con DNI textual, editar/inactivar,
buscar sin tilde y filtrar inactivos, navegar por ambos catálogos y periodos,
consultar noviembre sin fin, plegar menú, validar formulario vacío y cerrar sesión.
Se verificó ausencia de desbordamiento horizontal de la página móvil (la tabla
mantiene su propio desplazamiento) y ausencia de errores JavaScript.
La herramienta de navegador solo se instaló en el entorno de revisión; no es una
dependencia de ejecución del proyecto. No se emplearon datos reales.

## Límites

No se probó PostgreSQL, concurrencia simultánea bajo ese motor, Vercel ni Neon.
Tampoco importación/exportación Excel o flujos diarios de justificaciones, que
permanecen pendientes. No se afirma una auditoría completa de accesibilidad ni
compatibilidad con todos los navegadores. La suite CI reutiliza los comandos de
Django; los resultados locales no garantizan por sí solos el estado remoto.
