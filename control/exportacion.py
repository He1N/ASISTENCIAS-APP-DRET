"""Exportación de resultados completos filtrados, nunca solo la página visible."""
from datetime import date, datetime, time
from tempfile import SpooledTemporaryFile
from django.http import FileResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE


def respuesta_xlsx(nombre, encabezados, rows):
    wb = Workbook(write_only=True)
    ws = wb.create_sheet('Resultados')
    def celdas(values):
        output = []
        for value in values:
            if isinstance(value, datetime) and timezone.is_aware(value):
                value = timezone.localtime(value).replace(tzinfo=None)
            if isinstance(value, str):
                value = ILLEGAL_CHARACTERS_RE.sub('', value)
            cell = WriteOnlyCell(ws, value=value)
            if isinstance(value, str):
                # Tipo literal incluso para =, +, -, @, URL o cadenas con tabulador.
                cell.data_type = 's'
            elif isinstance(value, datetime): cell.number_format = 'dd/mm/yyyy hh:mm'
            elif isinstance(value, date): cell.number_format = 'dd/mm/yyyy'
            elif isinstance(value, time): cell.number_format = 'hh:mm'
            output.append(cell)
        return output
    ws.append(celdas(encabezados))
    for row in rows:
        ws.append(celdas(row))
    archivo = SpooledTemporaryFile(max_size=2 * 1024 * 1024)
    wb.save(archivo); archivo.seek(0)
    response = FileResponse(archivo, as_attachment=True, filename=nombre,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Cache-Control'] = 'private, no-store'
    return response


def exportar_justificaciones(qs):
    headers = ['ID', 'Trabajador', 'DNI', 'Periodo', 'Documento', 'Código documento', 'Operación',
        'Código operación', 'Grupo', 'Fecha inicial', 'Fecha final', 'Días calendario (informativos)',
        'Salida', 'Retorno', 'CUD', 'Observaciones', 'Fecha recepción', 'Captura', 'Plazo', 'Estado']
    def rows():
        for obj in qs.iterator(chunk_size=500):
            yield [obj.pk, obj.trabajador.apellidos_nombres, obj.trabajador.dni, obj.periodo.titulo,
                obj.tipo_documento.nombre, obj.tipo_documento.codigo_externo, obj.tipo_operacion.nombre,
                obj.tipo_operacion.codigo_externo, obj.tipo_operacion.get_grupo_especial_display(),
                obj.fecha_movimiento, obj.fecha_final, obj.duracion, obj.hora_salida, obj.hora_retorno,
                obj.cud, obj.observaciones, obj.fecha_recepcion, obj.created_at, obj.plazo,
                'Anulada' if obj.anulada else 'Vigente']
    return respuesta_xlsx('justificaciones.xlsx', headers, rows())
