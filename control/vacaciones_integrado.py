"""Récord global seguido por informes anuales, según referencia del responsable."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZipFile,ZIP_DEFLATED
from django.utils import timezone
from .vacaciones import resumen
from .vacaciones_word import w,num,anios_disponibles,movimientos_del_anio,generar_docx,row_from,paragraph as word_paragraph,distribucion_mensual,MONTHS


REL_DOCUMENTO = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL_PAQUETE = 'http://schemas.openxmlformats.org/package/2006/relationships'
TIPOS_PAQUETE = 'http://schemas.openxmlformats.org/package/2006/content-types'
ID_PIE = 'rIdPieGeneracion'


def agregar_pie(package, generado):
    footer = E.Element(w('ftr'))
    word_paragraph(footer, f'Generado el {generado:%d/%m/%Y a las %H:%M:%S} (hora de Perú)', size=16)
    props = E.Element(w('pPr'))
    E.SubElement(props, w('spacing'), {w('before'): '0', w('after'): '0'})
    E.SubElement(props, w('jc'), {w('val'): 'left'})
    footer[0].insert(0, props)
    package['word/footer1.xml'] = E.tostring(footer, encoding='utf-8', xml_declaration=True)
    rels = E.fromstring(package['word/_rels/document.xml.rels'])
    E.SubElement(rels, f'{{{REL_PAQUETE}}}Relationship',
                 Id=ID_PIE, Type=f'{REL_DOCUMENTO}/footer', Target='footer1.xml')
    package['word/_rels/document.xml.rels'] = E.tostring(rels, encoding='utf-8', xml_declaration=True)
    tipos = E.fromstring(package['[Content_Types].xml'])
    E.SubElement(tipos, f'{{{TIPOS_PAQUETE}}}Override', PartName='/word/footer1.xml',
                 ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml')
    package['[Content_Types].xml'] = E.tostring(tipos, encoding='utf-8', xml_declaration=True)


def seccion_con_pie(xml):
    section = E.fromstring(xml)
    footer = E.Element(w('footerReference'), {w('type'): 'default', f'{{{REL_DOCUMENTO}}}id': ID_PIE})
    section.insert(0, footer)
    section.find(w('pgMar')).set(w('footer'), '340')
    return section


def agregar_columna_usado(table, templates):
    grid = table.find(w('tblGrid'))
    grid.insert(len(grid)-1, deepcopy(grid[-2]))
    for row in templates[1:]:
        cells = row.findall(w('tc'))
        row.insert(list(row).index(cells[-1]), deepcopy(cells[-2]))
    identidad = templates[0].findall(w('tc'))[-1].find(w('tcPr'))
    span = identidad.find(w('gridSpan'))
    span.set(w('val'), str(int(span.get(w('val'))) + 1))
    width = identidad.find(w('tcW'))
    width.set(w('w'), str(int(width.get(w('w'))) + int(grid[-2].get(w('w')))))


def generar(cuenta):
    generado = timezone.localtime()
    layout=json.loads((Path(__file__).parent/'vacaciones_integrado_layout.json').read_text(encoding='utf-8'))
    def table(key):
        t=E.fromstring(layout[key]);rows=t.findall(w('tr'))
        for r in rows:t.remove(r)
        return t,rows
    def paragraph(text,index=2):
        p=E.fromstring(layout['parrafos'][index]);rp=p.find('.//'+w('rPr'))
        for c in list(p):
            if c.tag!=w('pPr'):p.remove(c)
        r=E.SubElement(p,w('r'))
        if rp is not None:r.append(deepcopy(rp))
        E.SubElement(r,w('t')).text=text
        return p
    years=anios_disponibles(cuenta)
    annual={year:movimientos_del_anio(cuenta,year)[0] for year in years}
    annual={year:rows for year,rows in annual.items() if rows}
    # Cada cantidad queda una sola vez en el récord, incluso si no hay fechas
    # suficientes para incluirla en un calendario anual.
    groups={year:list(rows) for year,rows in annual.items()}
    covered={r['obj'].pk for rows in annual.values() for r in rows}
    for m in cuenta.movimientos.all():
        if m.estado!='VIGENTE' or m.codigo=='09' or m.pk in covered:continue
        if m.dias==0:continue
        d=m.inicio or m.fecha
        year=d.year if d else int(m.periodo) if str(m.periodo).isdigit() and 1900<=int(m.periodo)<=9999 else None
        groups.setdefault(year,[]).append(dict(obj=m,inicio=m.inicio,fin=m.fin,dias=m.dias))
    base_year=years[0] if years else generado.year
    with ZipFile(BytesIO(generar_docx(cuenta,base_year,'record'))) as archive:
        package={name:archive.read(name) for name in archive.namelist()}
    agregar_pie(package, generado)
    root=E.Element(w('document'));body=E.SubElement(root,w('body'))
    body.append(paragraph('RÉCORD E INFORME INTEGRADOS DE VACACIONES · TODOS LOS AÑOS',0))
    body.append(paragraph('RÉCORD DE VACACIONES',1))
    identity=f'{cuenta.nombre} · DNI {cuenta.dni}'
    regime=f'Régimen laboral: {getattr(cuenta,"regimen_laboral","") or "Sin régimen informado"}.'
    body.append(paragraph(identity));body.append(paragraph(regime,3))
    current=resumen(cuenta)
    alloc,templates=table('asignaciones')
    agregar_columna_usado(alloc, templates)
    alloc.append(row_from(templates[0],['N° DOCUMENTO',cuenta.dni,cuenta.nombre],True))
    assigned=sorted(y for y,v in cuenta.asignaciones.items() if v is not None)
    for offset in range(0,max(1,len(assigned)),4):
        labels=assigned[offset:offset+4];labels+=['']*(4-len(labels))
        alloc.append(row_from(templates[1],['',*labels,'Total','Usado','Saldo']))
        alloc.append(row_from(templates[2],['Programado',*[num(cuenta.asignaciones[y]) if y else '' for y in labels],num(current['programado']) if not offset else '',num(current['usado']) if not offset else '',num(current['pendiente']) if not offset else '']))
    body.append(alloc)
    body.append(paragraph(''))
    record,templates=table('record');record.append(row_from(templates[0],['DEL','AL','DÍAS','PERIODO','SUSTENTO / OBSERVACIÓN'],True))
    def fmt(d):return d.strftime('%d/%m/%Y') if d else '—'
    for year in sorted(groups,key=lambda y:(y is None,y or 0)):
        rows=sorted(groups[year],key=lambda r:(r['inicio'] or r['obj'].fecha or date.max,r['obj'].pk))
        for item in rows:
            m=item['obj']
            record.append(row_from(templates[1],[fmt(item['inicio']),fmt(item['fin']),num(item['dias']) if item['dias'] is not None else '—',m.periodo,m.observaciones or 'NO HAY SUSTENTO']))
        subtotal=sum((item['dias'] or Decimal(0) for item in rows),Decimal(0))
        record.append(row_from(templates[2],[f'TOTAL DEL AÑO {year}' if year else 'TOTAL SIN AÑO DEFINIDO','',num(subtotal),'','']))
    record.append(row_from(templates[-2],['TOTAL','',num(current['usado']),'Días','']))
    record.append(row_from(templates[-1],['SALDO','',num(current['pendiente']),'Días','']))
    body.append(record)
    if current['pendiente']<0:
        body.append(paragraph(f'SALDO NEGATIVO. Exceso: {num(-current["pendiente"])} días.'))
    section=seccion_con_pie(layout['seccion_record'])
    for year,rows in sorted(annual.items()):
        p=E.SubElement(body,w('p'));pr=E.SubElement(p,w('pPr'))
        section.insert(1, E.Element(w('type'), {w('val'): 'nextPage'}))
        pr.append(section)
        body.append(paragraph(f'INFORME DE VACACIONES {year}',4))
        body.append(paragraph(identity));body.append(paragraph(regime,3))
        # Reutilizar las reglas de calendario y cantidades del informe anual.
        with ZipFile(BytesIO(generar_docx(cuenta,year,'informe'))) as z:
            source=E.fromstring(z.read('word/document.xml')).find(w('body')).find(w('tbl'))
        calendar,templates=table('informe')
        for i,row in enumerate(source.findall(w('tr'))):
            values=[''.join(c.itertext()) for c in row.findall(w('tc'))]
            new=row_from(templates[0 if i==0 else 1],values,i==0)
            cp=new.findall(w('tc'))[0].find(w('tcPr'))
            for merge in list(cp.findall(w('vMerge'))):cp.remove(merge)
            if i>0:E.SubElement(cp,w('vMerge'),{w('val'):'restart' if values[0] else 'continue'})
            calendar.append(new)
        body.append(calendar)
        body.append(paragraph('VACACIONES POR MES',1))
        distribution=distribucion_mensual(rows)
        monthly,templates=table('mensual');monthly.append(row_from(templates[0],['MES','DÍAS'],True))
        for i,values in enumerate(distribution['meses']):
            if sum(values):monthly.append(row_from(templates[1],[MONTHS[i],num(sum(values))]))
        if distribution['no_distribuido']:monthly.append(row_from(templates[1],['Sin mes definido',num(distribution['no_distribuido'])]))
        monthly.append(row_from(templates[-1],['TOTAL',num(distribution['total']+distribution['no_distribuido'])]))
        body.append(monthly)
        section=seccion_con_pie(layout['seccion_informe'])
    body.append(section)
    package['word/document.xml']=E.tostring(root,encoding='utf-8',xml_declaration=True)
    package['word/styles.xml']=layout['styles']
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as archive:
        for name,data in package.items():archive.writestr(name,data)
    return out.getvalue()
