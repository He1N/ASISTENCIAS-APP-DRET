# Respaldo y restauración PostgreSQL

Un Excel exportado no respalda cuentas, permisos, auditoría, lotes ni migraciones.
El procedimiento usa pg_dump en formato custom y pg_restore en otra base vacía.
No ejecutarlo contra datos reales sin responsable y ventana de mantenimiento.

## Requisitos y responsabilidades

El responsable institucional de operación conserva credenciales y copias; otro
administrador debe poder recuperar el servicio. Instalar clientes PostgreSQL del
mismo major del servidor (17 en el ensayo), Python 3.12 y requirements.txt. Verificar
`pg_dump --version` y `pg_restore --version`. El script no depende de Django settings.

Cargar DIRECT_DATABASE_URL con la conexión **directa**, no pooled, desde un gestor
de secretos o archivo privado del operador. El script no lee .env, no imprime URLs,
usa un pgpass temporal con permisos 0600 y no pasa la contraseña por argumentos.
Los volcados y checksums son 0600, no se sobrescriben archivos existentes y se
retira una salida parcial si falla pg_dump. Los errores del cliente no se publican
porque pueden incluir información sensible. Ante un fallo comprobar conectividad,
versión del cliente, permisos y espacio desde la terminal protegida.

## Crear y verificar un respaldo

Suspender escrituras durante el respaldo anterior a una migración; no basta con
la consistencia interna de pg_dump si se permite seguir escribiendo después.
Desde la raíz del checkout revisado, con DIRECT_DATABASE_URL cargada:

```bash
umask 077
python scripts/postgres_backup.py backups/antes-del-cambio.dump
sha256sum backups/antes-del-cambio.dump
```

Se crea también antes-del-cambio.dump.sha256. Usar un nombre nuevo por operación.
Guardar ambos archivos en almacenamiento institucional cifrado y con acceso
limitado, fuera de Vercel y de este repositorio. El script crea una copia local:
**no cifra ni sube** el respaldo; el checksum detecta alteración accidental, no
sustituye cifrado ni autenticidad. Los temporales de Vercel no sirven como archivo.

## Ensayar restauración

Crear una base separada **nueva y vacía** y cargar RESTORE_DATABASE_URL con su
conexión directa. Nunca apuntarla a la base en servicio. Mantener el destino sin
otras conexiones/escrituras mientras se restaura:

```bash
python scripts/postgres_backup.py backups/antes-del-cambio.dump --restore
```

El script exige checksum válido, rechaza tablas/vistas/secuencias existentes y
restaura en una transacción con --no-owner --no-acl --exit-on-error. No usa --clean,
no elimina bases y no revierte migraciones. Tampoco copia roles globales ni
configuración de infraestructura; los usuarios/permisos del proveedor se gestionan
aparte. Las cuentas/grupos de Django sí están dentro de las tablas respaldadas.

Antes de considerar verificable la copia: apuntar una instancia aislada del mismo
commit a la base restaurada, ejecutar `migrate --check` sin alterar el esquema,
comparar conteos de trabajadores, justificaciones, lotes e historial con la fuente,
probar acceso y comprobar muestras de DNI/CUD, fechas, auditoría y permisos. No
publicar muestras reales en logs. Registrar fecha, commit, versiones PostgreSQL,
checksum, cantidades, duración y responsable del ensayo en un registro protegido.
El ensayo de esta fase comparó el contenido completo de las 18 tablas con datos
sintéticos y comprobó el rechazo de un destino ya ocupado.

## Frecuencia y recuperación

Como punto de partida operativo: copia diaria y antes de cambios, 30 días de
retención y ensayo mensual; el responsable institucional debe ajustar y aprobar
estos valores según las necesidades de pérdida máxima de datos y recuperación.
Se incluyen un servicio y temporizador systemd diarios para un equipo protegido
con almacenamiento persistente. Instalación y seguimiento en MANTENIMIENTO.md.
Su presencia en el repositorio no significa que estén instalados o activos.
Verificar el resultado de cada ejecución. Revisar también la retención/PITR del
plan de Neon; no se asume que un plan incluya una ventana determinada.

Para recuperación real: detener escrituras, preservar el estado actual, elegir
una copia verificada, restaurar en base separada, validar, cambiar DATABASE_URL en
Vercel y redesplegar el código compatible. Documentar las escrituras posteriores
a la copia que podrían faltar y reconciliarlas con el responsable. Mantener la
base anterior hasta terminar la verificación. No sustituirla ni borrarla como
parte automática del script.

Referencia: https://neon.com/docs/manage/backup-pg-dump
