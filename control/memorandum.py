"""Descarga editable del memorándum de vacaciones a partir del movimiento guardado."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header

from .vacaciones_word import MONTHS, num


def descargar_memorandum(movimiento):
    fecha = timezone.localdate(movimiento.created_at)
    unidad = 'día' if movimiento.dias == 1 else 'días'
    variables = {
        'NOMBRE': movimiento.cuenta.nombre,
        'CUD': movimiento.cud or '...',
        'FECHA': f'{fecha.day} de {MONTHS[fecha.month-1].lower()} del {fecha.year}',
        'ANIO': str(fecha.year),
        'RANGO': f'{movimiento.inicio:%d/%m/%Y} al {movimiento.fin:%d/%m/%Y} ({num(movimiento.dias)} {unidad})',
    }
    output = BytesIO()
    plantilla = Path(__file__).with_name('memorandum_vacaciones.docx')
    with ZipFile(plantilla) as source, ZipFile(output, 'w', ZIP_DEFLATED) as result:
        for name in source.namelist():
            content = source.read(name)
            if name == 'word/document.xml':
                document = content.decode('utf-8')
                for key, value in variables.items():
                    document = document.replace('{{' + key + '}}', escape(value))
                content = document.encode('utf-8')
            result.writestr(name, content)
    response = HttpResponse(output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = content_disposition_header(
        True, f'Memorandum_vacaciones_{movimiento.pk}.docx')
    return response
