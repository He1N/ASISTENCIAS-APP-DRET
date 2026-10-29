# Operación y mantenimiento

## Estado al 29/10/2026

El responsable confirmó Vercel + Neon, datos cargados y funcionamiento correcto
en https://asistencias-app-dret.vercel.app. El diseño queda como mejora posterior.
Esta confirmación no acredita por sí sola revisión completa del Excel/OJO,
concurrencia, respaldos o recuperación. No repetir importaciones para verificarlo.

| Tarea | Estado | Evidencia de cierre |
| --- | --- | --- |
| Despliegue y carga | Confirmados por el responsable | Confirmación del 29/10/2026 |
| Purga diaria | Workflow preparado; activación por verificar | Primera ejecución correcta y siguientes ejecuciones programadas |
| Respaldo diario | Servicio y timer preparados; instalación pendiente | Copia y checksum en almacenamiento persistente cifrado |
| Recuperación | Procedimiento disponible; ensayo real pendiente | Restauración en base aislada y registro privado del ensayo |
| Retención/PITR Neon | Sin acceso al panel para verificar | Ventana y plan documentados por el responsable |

## Activar y verificar la purga diaria

Integrar `.github/workflows/mantenimiento.yml` en la rama por defecto. En GitHub,
Settings → Secrets and variables → Actions, verificar que `NEON_DATABASE_URL`
apunta a la base correcta con TLS (es el mismo nombre usado para el primer
administrador). No copiar el valor en Git, capturas ni incidencias.

En Actions → Purgar previsualizaciones caducadas → Run workflow, ejecutar una vez
y comprobar estado verde. Luego verificar una ejecución programada: 03:17 Lima,
todos los días. GitHub puede retrasarla y puede desactivar schedules de repositorios
públicos inactivos; revisar que continúe habilitada. La ausencia de ejecuciones
no cuenta como éxito. Habilitar avisos personales de fallos de Actions y asignar
un responsable que revise las ejecuciones.

Solo se vacían `datos_temporales` y se marca `EXPIRADO` en lotes SELECCION/PREVIA
de más de 24 horas. Se conservan lotes, justificaciones, usuarios y auditoría.
No se ejecutan migraciones: se comprueba que estén aplicadas. Un secreto ausente,
conexión fallida o esquema atrasado detiene la tarea con error sin imprimir datos.
La clave efímera del proceso no cambia SECRET_KEY ni sesiones de la aplicación.

## Instalar el respaldo diario

Requiere un equipo Linux permanente bajo control del responsable, disco cifrado
y clientes PostgreSQL compatibles con el servidor. No instalar el timer en el
runtime efímero de Vercel. Las copias no se suben como artifacts de GitHub.

Preparar un checkout revisado en `/opt/asistencias` con entorno virtual `.venv`
y `requirements.txt` instalados. Mantener código y entorno virtual administrados
por root, legibles por la cuenta del servicio. En el equipo elegido:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin asistencias-backup
sudo install -d -m 0700 /etc/asistencias
sudo install -d -m 0700 -o asistencias-backup -g asistencias-backup /var/lib/asistencias-backups
sudo install -m 0600 /dev/null /etc/asistencias/mantenimiento.env
sudoedit /etc/asistencias/mantenimiento.env
```

Si la cuenta o el archivo ya existen, conservarlos; no repetir el comando que
vacía el archivo. Escribir en él, privadamente, estas dos variables (reemplazar
el marcador por la conexión **directa** de Neon con TLS):

```text
DIRECT_DATABASE_URL=CONEXION_DIRECTA_PRIVADA_CON_TLS
BACKUP_DIR=/var/lib/asistencias-backups
```

No usar `export` en EnvironmentFile. El directorio de copias debe residir en el
volumen cifrado y disponer de espacio; el script no cifra ni transfiere archivos.
Instalar y ensayar primero el servicio desde la raíz del checkout:

```bash
sudo install -m 0644 deploy/systemd/asistencias-backup.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/asistencias-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start asistencias-backup.service
sudo systemctl status asistencias-backup.service
sudo journalctl -u asistencias-backup.service --since today
```

Comprobar copia `.dump` y `.sha256`, permisos 0600 y restauración en base aislada
según [RESPALDOS.md](RESPALDOS.md). Tras la primera copia válida:

```bash
sudo systemctl enable --now asistencias-backup.timer
sudo systemctl list-timers asistencias-backup.timer
```

El horario es 02:45 Lima (07:45 UTC), con hasta cinco minutos adicionales.
Persistent=true ejecuta una tarea omitida al volver a encender el equipo. Se
generan nombres nuevos y no se borran copias automáticamente. Revisar diariamente
el último resultado, espacio disponible y una segunda copia cifrada fuera del
equipo. Retención propuesta: 30 días, ajustada por el responsable; eliminar solo
conforme a esa política y conservando copias verificadas.

## Recuperación y seguimiento

Revisar en Neon la retención y recuperación disponibles en el plan actual; no se
asume una ventana determinada. Ensayar mensualmente y antes de cambios relevantes
la restauración en una base nueva aislada; nunca usar producción como destino.
Usar una instancia privada del mismo commit y validar esquema, acceso, permisos,
conteos y muestras sin publicar información personal. No ejecutar migraciones,
reiniciar roles ni crear datos sintéticos en producción como parte del ensayo.

Registrar en almacenamiento privado: responsable y suplente, fecha de última
copia válida, checksum, ubicación cifrada, fecha y duración de restauración,
resultado de validación, retención Neon y pérdida máxima/tiempo de recuperación
aceptados. Ante incidentes seguir [RESPALDOS.md](RESPALDOS.md); el rollback de
Vercel no restaura datos.

En esta actualización no se dispone de credenciales Neon/Vercel ni de un destino
institucional de copias. Se prepara la automatización y el procedimiento; no se
afirma que estén activos ni que exista una copia real verificada.
