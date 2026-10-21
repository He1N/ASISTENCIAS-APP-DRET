import unicodedata
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def normalizar(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', value or '') if not unicodedata.combining(c)).casefold().split())


class Fechado(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class Trabajador(Fechado):
    apellidos_nombres = models.CharField('Apellidos y nombres', max_length=250)
    nombre_busqueda = models.CharField(max_length=300, db_index=True, editable=False)
    dni = models.CharField('DNI', max_length=20, blank=True, null=True, db_index=True)
    area = models.CharField('Área', max_length=200, blank=True)
    activo = models.BooleanField('Activo', default=True)
    class Meta:
        ordering = ['-activo', 'apellidos_nombres', 'pk']
        verbose_name = 'trabajador'
        verbose_name_plural = 'trabajadores'
    def save(self, *args, **kwargs):
        self.nombre_busqueda = normalizar(self.apellidos_nombres)
        self.dni = self.dni or None
        super().save(*args, **kwargs)
    def __str__(self):
        return self.apellidos_nombres


class Catalogo(Fechado):
    nombre = models.CharField('Nombre', max_length=200)
    nombre_busqueda = models.CharField(max_length=250, db_index=True, editable=False)
    codigo_externo = models.CharField('Código externo', max_length=40, blank=True, db_index=True)
    activo = models.BooleanField('Activo', default=True)
    class Meta:
        abstract = True
        ordering = ['nombre', 'pk']
    def save(self, *args, **kwargs):
        self.nombre = ' '.join(self.nombre.split())
        self.codigo_externo = ' '.join(self.codigo_externo.split())
        self.nombre_busqueda = normalizar(self.nombre)
        super().save(*args, **kwargs)
    def __str__(self):
        return self.nombre + (f' | {self.codigo_externo}' if self.codigo_externo else '')


class TipoDocumento(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = 'tipo de documento'
        verbose_name_plural = 'tipos de documento'


class TipoOperacion(Catalogo):
    GRUPOS = [('NINGUNO', 'Ninguno'), ('VACACIONES', 'Vacaciones'), ('SINDICAL', 'Licencias sindicales')]
    requiere_fecha_final = models.BooleanField('Requiere fecha final', null=True, default=None, help_text='Desconocido: pendiente de revisión; no equivale a No.')
    grupo_especial = models.CharField('Grupo especial', max_length=12, choices=GRUPOS, default='NINGUNO')
    class Meta(Catalogo.Meta):
        verbose_name = 'tipo de operación'
        verbose_name_plural = 'tipos de operación'


class PeriodoAsistencia(Fechado):
    ESTADOS = [('ABIERTO', 'Abierto'), ('CERRADO', 'Cerrado'), ('PROCESADO', 'Procesado')]
    titulo = models.CharField('Título', max_length=150)
    fecha_inicio = models.DateField('Fecha inicio')
    fecha_fin = models.DateField('Fecha fin', blank=True, null=True)
    estado = models.CharField('Estado', max_length=12, choices=ESTADOS, default='ABIERTO')
    fecha_cierre = models.DateTimeField('Fecha de cierre', blank=True, null=True, editable=False)
    fecha_procesamiento = models.DateTimeField('Fecha de procesamiento', blank=True, null=True, editable=False)
    notas = models.TextField('Notas', blank=True)
    class Meta:
        ordering = ['-fecha_inicio', '-pk']
        verbose_name = 'periodo de asistencia'
        verbose_name_plural = 'periodos de asistencia'
        constraints = [models.CheckConstraint(condition=models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=models.F('fecha_inicio')), name='periodo_rango_valido')]
    def clean(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({'fecha_fin': 'La fecha fin no puede ser anterior al inicio.'})
    def __str__(self):
        return self.titulo


class LoteImportacion(models.Model):
    archivo_nombre = models.CharField(max_length=255)
    checksum = models.CharField(max_length=64, db_index=True)
    hoja = models.CharField(max_length=100)
    periodo = models.ForeignKey(PeriodoAsistencia, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    total_leidos = models.PositiveIntegerField(default=0)
    insertados = models.PositiveIntegerField(default=0)
    omitidos = models.PositiveIntegerField(default=0)
    alertas = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=20, default='PREVIA')
    reglas_aplicadas = models.JSONField(default=list)
    # Solo filas normalizadas de vista previa, nunca el workbook. Se purga al confirmar/cancelar.
    datos_temporales = models.JSONField(default=dict, editable=False)
    class Meta:
        permissions = [('importar_excel', 'Puede importar Excel'), ('exportar_resultados', 'Puede exportar resultados')]
        constraints = [models.UniqueConstraint(fields=['checksum', 'hoja', 'periodo'], name='lote_archivo_hoja_periodo_unico')]


class Justificacion(Fechado):
    periodo = models.ForeignKey(PeriodoAsistencia, on_delete=models.PROTECT, verbose_name='Periodo')
    trabajador = models.ForeignKey(Trabajador, on_delete=models.PROTECT, verbose_name='Trabajador')
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.PROTECT, verbose_name='Tipo de documento')
    tipo_operacion = models.ForeignKey(TipoOperacion, on_delete=models.PROTECT, verbose_name='Tipo de operación')
    fecha_movimiento = models.DateField('Fecha de movimiento', null=True, blank=True, db_index=True)
    fecha_final = models.DateField('Fecha final', null=True, blank=True)
    hora_salida = models.TimeField('Hora salida', null=True, blank=True)
    hora_retorno = models.TimeField('Hora retorno', null=True, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    cud = models.TextField('CUD', null=True, blank=True)
    fecha_recepcion = models.DateField('Fecha de recepción', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='justificaciones_creadas')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='justificaciones_editadas')
    fuente = models.CharField(max_length=10, choices=[('MANUAL', 'Manual'), ('EXCEL', 'Excel')], default='MANUAL')
    lote_importacion = models.ForeignKey(LoteImportacion, on_delete=models.PROTECT, null=True, blank=True)
    fila_origen = models.PositiveIntegerField(null=True, blank=True)
    item_origen = models.CharField(max_length=40, blank=True)
    huella = models.CharField(max_length=64, blank=True, db_index=True)
    estado_calidad = models.CharField(max_length=30, default='COMPLETO')
    anulada = models.BooleanField(default=False)
    motivo_anulacion = models.TextField(blank=True)
    anulada_at = models.DateTimeField(null=True, blank=True)
    anulada_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='justificaciones_anuladas')
    class Meta:
        ordering = ['-fecha_movimiento', '-pk']
        permissions = [('anular_justificacion', 'Puede anular justificación')]
        indexes = [models.Index(fields=['periodo', 'fecha_movimiento'])]
        constraints = [models.CheckConstraint(condition=models.Q(fecha_final__isnull=True) | models.Q(fecha_movimiento__isnull=True) | models.Q(fecha_final__gte=models.F('fecha_movimiento')), name='justificacion_fechas_validas')]
    def clean(self):
        errors = {}
        if self.fuente == 'MANUAL' and not self.fecha_movimiento:
            errors['fecha_movimiento'] = 'Ingrese la fecha de movimiento.'
        if self.tipo_operacion_id and self.fuente == 'MANUAL':
            if self.tipo_operacion.requiere_fecha_final is None:
                errors['tipo_operacion'] = 'La regla de fecha final está pendiente de revisión por un administrador.'
            elif self.tipo_operacion.requiere_fecha_final and not self.fecha_final:
                errors['fecha_final'] = 'Esta operación requiere fecha final.'
        if self.fecha_final and self.fecha_movimiento and self.fecha_final < self.fecha_movimiento:
            errors['fecha_final'] = 'La fecha final no puede ser anterior al movimiento.'
        if errors:
            raise ValidationError(errors)
    @property
    def es_registro_tardio(self):
        if self.fuente == 'EXCEL':
            return None
        corte = self.periodo.fecha_cierre or self.periodo.fecha_procesamiento
        if not corte and self.periodo.estado != 'ABIERTO':
            return None
        return bool(corte and self.created_at and self.created_at > corte)
    @property
    def plazo(self):
        if self.fuente == 'EXCEL':
            return 'Importado / sin determinar'
        return 'Sin determinar' if self.es_registro_tardio is None else ('Tardío' if self.es_registro_tardio else 'Ordinario')
    @property
    def duracion(self):
        if self.fecha_movimiento and self.fecha_final and self.fecha_final >= self.fecha_movimiento:
            return (self.fecha_final - self.fecha_movimiento).days + 1
        return None
    def __str__(self):
        return f'{self.trabajador} — {self.tipo_operacion}'


class IncidenciaImportacion(models.Model):
    lote = models.ForeignKey(LoteImportacion, on_delete=models.PROTECT, related_name='incidencias')
    fila = models.PositiveIntegerField(default=0)
    campo = models.CharField(max_length=60)
    mensaje = models.TextField()
    severidad = models.CharField(max_length=10, choices=[('ALERTA', 'Alerta'), ('ERROR', 'Error')])
    valor_original = models.TextField(blank=True)


class HistorialCambio(models.Model):
    entidad = models.CharField(max_length=80)
    objeto_id = models.PositiveBigIntegerField()
    accion = models.CharField(max_length=50)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    cambios = models.JSONField(default=dict)
    class Meta:
        ordering = ['-fecha', '-pk']
        default_permissions = ('view',)
