# Fase 5 — Preparación de Vercel y Neon

Esta fase prepara el código; no crea proyectos ni publica la aplicación. Usar
primero datos sintéticos. Los datos laborales reales requieren autorización
institucional según ESPECIFICACION.md. Resultado de las pruebas en VALIDACION.md.

## Entornos y variables

Python 3.12, dependencias fijadas en requirements.txt. `.env.example` es una guía,
no se lee automáticamente. Configurar variables en el proceso o en el panel del
proveedor; nunca incluir credenciales en comandos compartidos, Git o capturas.
Para un archivo local propio y confiable: `set -a; source .env; set +a` (Bash).

| Variable | Desarrollo | Producción |
| --- | --- | --- |
| DEBUG | True | False, obligatorio en Vercel |
| SECRET_KEY | Clave local de desarrollo si se omite | Aleatoria, mínimo 50 caracteres; conservar entre despliegues |
| ALLOWED_HOSTS | localhost,127.0.0.1 | Lista separada por comas de dominios exactos, sin esquema, ruta ni comodines |
| CSRF_TRUSTED_ORIGINS | Vacía | Orígenes HTTPS exactos separados por comas; incluir el dominio desde el que se usa la app |
| DATABASE_URL | Vacía: SQLite; o PostgreSQL desechable | PostgreSQL con TLS; URL pooled de Neon para el servidor |
| VERCEL | No establecer | La establece Vercel en 1; habilita proxy y límites de plataforma |
| DIRECT_DATABASE_URL | Solo para ensayo de respaldo | Conexión directa de Neon, solo terminal de mantenimiento |
| RESTORE_DATABASE_URL | Base vacía separada | Solo terminal de restauración; jamás reutilizar la base en servicio |

Generar una clave en una terminal privada: `python -c 'import secrets; print(secrets.token_urlsafe(64))'`.
Copiar la clave al gestor de secretos/panel sin compartir su salida. No cambiarla
en cada build: invalida sesiones. Contraseñas con caracteres especiales deben
estar codificadas como parte de la URL; usar la conexión que entrega Neon.

Sin DATABASE_URL solo se permite SQLite con DEBUG=True y fuera de Vercel. URLs de
otros motores se rechazan. En producción se agrega `sslmode=require` si falta y
se rechazan `disable`, `allow` y `prefer`. Puede usarse `verify-full` con la CA
correspondiente. `require` cifra, pero no equivale a verificar la identidad del
servidor; conservar las opciones TLS de la conexión recomendada por Neon.

Se usa psycopg 3, CONN_MAX_AGE=0, comprobaciones de conexión y cursores de servidor
desactivados; también se desactivan sentencias preparadas para compatibilidad con
pooling de transacciones. No se consulta la base al importar settings/compilar.
La base contiene sesiones, lotes temporales, registros y auditoría. No hay
adjuntos persistidos en disco; los temporales de Excel son efímeros.

## Preparar los proyectos, después de revisar y fusionar el PR

1. Crear en Neon un proyecto y una base de producción vacía (PostgreSQL 17 es el
   major ensayado). Guardar por separado conexión pooled y directa. Elegir región
   cercana al runtime y revisar la política de recuperación del plan contratado.
2. Preparar otra base/rama independiente para pruebas/Preview. No conectar los
   despliegues de ramas o PR a producción. La cuenta de ejecución no necesita
   CREATEDB; las pruebas usan una cuenta y base desechables separadas.
3. Importar `He1N/ASISTENCIAS-APP-DRET` en Vercel, raíz del repositorio, rama de
   producción main, preset **Django**, Python 3.12. Mantener build/output por
   defecto: el soporte Django nativo detecta manage.py y config.wsgi.application.
   vercel.json declara Django y limita la función a 60 s. No agregar rewrites de
   todas las rutas a /api ni un servidor de desarrollo.
4. Cargar las variables de producción anteriores. Reservar el dominio exacto
   `proyecto.vercel.app` y/o institucional en ALLOWED_HOSTS y CSRF_TRUSTED_ORIGINS.
   Para Preview usar sus propios secretos y dominios explícitos o un alias
   estable; no autorizar `*` ni `.vercel.app`.
5. Ejecutar las migraciones desde la terminal autorizada como se indica abajo,
   antes de habilitar el acceso al primer despliegue. La compilación **no ejecuta
   migrate, preparar_roles ni createsuperuser**.
6. Desplegar y probar con fichas ficticias: login/logout, permisos, nueva
   justificación, filtros, XLSX, auditoría, CSS de la app y de Admin. Comprobar
   HTTPS, cookies Secure, CSRF y acceso denegado sin sesión. Revisar logs sin
   publicar datos personales ni credenciales. Solo después acordar la puesta en
   servicio y el ingreso de datos institucionales.

### Estáticos y HTTPS

STATIC_ROOT es staticfiles/, STATIC_URL es /static/. El preset Django nativo de
Vercel ejecuta collectstatic durante el build y sirve sus archivos por CDN. El
backend CompressedManifestStaticFilesStorage genera nombres con hash; WhiteNoise
permite servirlos también al ejecutar WSGI fuera de Vercel. No versionar staticfiles/.
Para ensayar localmente, con variables de producción cargadas:

```bash
python manage.py check --deploy --fail-level ERROR
python manage.py collectstatic --noinput
```

Estos comandos no necesitan una conexión de base disponible. El servidor sí la
necesita. Se exige HTTPS, cookies Secure/HttpOnly de sesión, CSRF, DENY para frames,
nosniff y referrer same-origin. El protocolo reenviado se confía solo si VERCEL=1;
no habilitarlo en un servidor expuesto directamente con cabeceras controladas por
el cliente. Otro proxy requiere su propia revisión de confianza.

HSTS empieza en 3600 segundos. `check --deploy` conserva dos recomendaciones
esperadas: W005 (includeSubDomains) y W021 (preload). No se silencian: no se activa
una política para subdominios ni precarga del dominio antes de conocer sus usos.
Revisarlas con quien administra el dominio; no son fallos de TLS/cookies de esta
aplicación. Cualquier otro aviso debe investigarse antes de publicar.

### Límites de Excel en Vercel

Las funciones admiten 4,5 MB por solicitud/respuesta. En VERCEL=1, el XLSX admite
**4.000.000 bytes (4 MB)** y el cuerpo HTTP hasta 4.250.000 bytes, dejando margen
para multipart. Las respuestas HTML y descargas conocidas se limitan a 4 MB: se
muestra un error 413 en español y no se descarga un archivo truncado. Si la carga
ya excede el máximo del proveedor, Vercel puede rechazarla antes de Django.

Una previsualización con muchas filas/textos puede exceder el límite aunque el
XLSX comprimido sea pequeño. Dividir el archivo antes de cargarlo. Para descargas,
aplicar filtros por periodo/fechas/trabajador. Fuera de Vercel se conserva el máximo
local de 10 MiB y 5000 filas. No se incorporó almacenamiento externo ni trabajos en
segundo plano. El máximo de 60 s también requiere probar importaciones en el
servicio real; las pruebas locales no garantizan tiempos en Vercel.

## Migraciones

Desde un checkout del commit revisado, entorno virtual con requirements.txt y
variables de producción cargadas de forma privada. En la terminal de mantenimiento
cambiar DATABASE_URL por la conexión **directa**, nunca derivar el host a mano:

```bash
export DATABASE_URL="$DIRECT_DATABASE_URL"
python manage.py check --deploy --fail-level ERROR
python manage.py showmigrations --plan
python manage.py migrate --plan
```

Si ya hay datos: suspender escrituras, crear respaldo y restaurarlo en una base
vacía (RESPALDOS.md). Revisar el plan y compatibilidad con la versión en servicio.
Una sola persona/proceso ejecuta las migraciones, fuera del build:

```bash
python manage.py migrate --noinput
python manage.py migrate --check
# Primera instalación; también al cambiar la política de permisos:
python manage.py preparar_roles
# Primera instalación, cuenta individual, contraseña interactiva:
python manage.py createsuperuser
```

preparar_roles restablece los permisos de los grupos: revisar antes de repetirlo
si hubo ajustes institucionales. Crear un segundo administrador individual y
probar su acceso. No ejecutar crear_datos_sinteticos en una base institucional.
En este PR no hay migraciones nuevas; al actualizar desde fase 4, migrate es no-op.

Desplegar el commit revisado, comprobar los flujos y habilitar escrituras. Si
falla el cambio: mantener las escrituras suspendidas y analizar compatibilidad
antes de volver al código anterior. Un rollback de Vercel **no revierte** el
esquema ni los datos. No ejecutar migrate hacia atrás a ciegas; restaurar primero
en otra base y planificar el cambio de conexión con el responsable institucional.

## Pruebas y mantenimiento

```bash
export DEBUG=True
# DATABASE_URL vacía para SQLite, o PostgreSQL exclusivamente de pruebas.
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test --noinput
```

En PostgreSQL Django crea/elimina test_<nombre>; usar base y usuario de pruebas con
CREATEDB, nunca credenciales productivas. CI ejecuta la suite con SQLite y un
servicio PostgreSQL 17. Cada job revisa también seguridad y collectstatic sin base.

El responsable de operación debe ejecutar diariamente desde un entorno protegido:
`python manage.py purgar_previsualizaciones` (caducidad de 24 horas). No se ha
creado un cron externo. Asignar responsable de respaldos, revisar accesos y
ensayar restauraciones. Neon/TLS/PgBouncer y el primer despliegue siguen
pendientes de validación contra los proyectos reales.

Referencias oficiales consultadas:
- https://vercel.com/docs/frameworks/full-stack/django
- https://vercel.com/docs/functions/limitations
- https://neon.com/docs/guides/django
- https://docs.djangoproject.com/en/5.2/ref/databases/#transaction-pooling-and-server-side-cursors
