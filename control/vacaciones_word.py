"""Formatos individuales basados solo en los cuadros suministrados."""
from calendar import Calendar
from copy import deepcopy
from datetime import date,timedelta
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZipFile,ZIP_DEFLATED
from .vacaciones import resumen

NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
E.register_namespace('w',NS)
def w(x): return '{'+NS+'}'+x
MONTHS=['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE']
def num(x): return format(Decimal(str(x)).normalize(),'f').replace('.',',')

def anios_disponibles(cuenta):
    years={int(y) for y,v in cuenta.asignaciones.items() if str(y).isdigit() and v is not None and 1900<=int(y)<=9999}
    for m in cuenta.movimientos.all():
        if m.estado!='VIGENTE': continue
        years.update(d.year for d in (m.fecha,m.inicio,m.fin) if d)
        if str(m.periodo).isdigit() and 1900<=int(m.periodo)<=9999: years.add(int(m.periodo))
        if m.inicio and m.fin and m.inicio<=m.fin:
            years.update(range(m.inicio.year,m.fin.year+1))
    return sorted(years)


def saldo_documento(body,cuenta):
    current=resumen(cuenta)
    text=f'Programado: {num(current["programado"])} días. Usado: {num(current["usado"])} días. Saldo acumulado: {num(current["pendiente"])} días.'
    if current['pendiente']<0:
        text+=f' SALDO NEGATIVO. Exceso: {num(-current["pendiente"])} días.'
    paragraph(body,text,size=18)


def movimientos_del_anio(cuenta,anio):
    rows=[]; warnings=[]
    for m in cuenta.movimientos.all():
        if m.estado!='VIGENTE' or m.codigo=='09': continue
        inicio,fin=m.inicio,m.fin
        # La media jornada confirmada ocupa una fecha; los legados suelen
        # conservarla solo en Fecha o Del. No modificar el registro original.
        if m.codigo in {'05','32'} and m.dias==Decimal('.5'):
            inicio=inicio or m.fecha
            fin=fin or inicio
        if not inicio or not fin or fin<inicio:
            # No atribuir a un año un intervalo desconocido.
            if str(m.periodo)==str(anio) or (m.fecha and m.fecha.year==anio):
                warnings.append(f'Registro {m.pk}: {num(m.dias) if m.dias is not None else "sin cantidad de"} días declarados sin Del/Al válidos. No se asignaron fechas ni se incluyó en el total del año.')
            continue
        start=max(inicio,date(anio,1,1)); end=min(fin,date(anio,12,31))
        if start>end: continue
        if m.dias is None:
            warnings.append(f'Registro {m.pk}: sin cantidad de días; no se distribuyó en el calendario.')
            continue
        if m.dias<=0: continue
        quantity=m.dias
        complete=(fin-inicio).days+1
        if start!=inicio or end!=fin:
            if quantity!=complete:
                warnings.append(f'Registro {m.pk}: cruza de año ({inicio:%d/%m/%Y} al {fin:%d/%m/%Y}) y declara {num(quantity)} días para un intervalo de {complete}. Incluido en el consumo acumulado; no se repartió en los cuadros anuales para evitar atribuir días incorrectos. {m.observaciones}')
                continue
            quantity=Decimal((end-start).days+1)
        if m.dias!=complete and not (m.codigo=='32' and complete==1 and m.dias==Decimal('.5')):
            warnings.append(f'Registro {m.pk}, {start:%d/%m/%Y}: {num(quantity)} días declarados; intervalo de {(end-start).days+1} días. Se conserva la cantidad original, sin inventar fechas.')
        if m.codigo=='32': warnings.append(f'Media jornada: {start:%d/%m/%Y}, {num(quantity)} días.')
        rows.append({'obj':m,'inicio':start,'fin':end,'dias':quantity})
    return sorted(rows,key=lambda r:(r['inicio'],r['fin'],r['obj'].pk)),warnings

def fill(cell,value):
    # Conservar propiedades de párrafo y fuente de la celda original.
    p=cell.find(w('p'))
    if p is None: p=E.SubElement(cell,w('p'))
    r=p.find(w('r')); props=deepcopy(r.find(w('rPr'))) if r is not None and r.find(w('rPr')) is not None else None
    for child in list(cell):
        if child.tag!=w('tcPr'): cell.remove(child)
    newp=E.SubElement(cell,w('p'))
    if p.find(w('pPr')) is not None: newp.append(deepcopy(p.find(w('pPr'))))
    run=E.SubElement(newp,w('r'))
    if props is not None: run.append(props)
    E.SubElement(run,w('t')).text=''.join(ch for ch in str(value) if ord(ch)>=32 or ch in '\t\n')

def row_from(template,values,header=False):
    row=deepcopy(template)
    pr=row.find(w('trPr'))
    if pr is None: pr=E.SubElement(row,w('trPr'))
    for child in list(pr):
        if child.tag in {w('trHeight'),w('tblHeader')}: pr.remove(child)
    E.SubElement(pr,w('cantSplit'))
    if header: E.SubElement(pr,w('tblHeader'))
    for cell,value in zip(row.findall(w('tc')),values): fill(cell,value)
    return row

def uniformar_informe(table):
    grid=table.find(w('tblGrid'))
    widths=[int(c.get(w('w'))) for c in grid]
    widths=[widths[0]+420,*[x-60 for x in widths[1:]]]
    widths[1]-=120; widths[2]-=120; widths[3]+=240
    for col,width in zip(grid,widths): col.set(w('w'),str(width))
    for row_index,row in enumerate(table.findall(w('tr'))):
        for i,c in enumerate(row.findall(w('tc'))):
            cp=c.find(w('tcPr')); cp.find(w('tcW')).set(w('w'),str(widths[i]))
            margins=E.SubElement(cp,w('tcMar'))
            for side in ['left','right']: E.SubElement(margins,w(side),{w('w'):'30',w('type'):'dxa'})
            for p in c.findall(w('p')):
                pr=p.find(w('pPr'))
                if pr is None: pr=E.SubElement(p,w('pPr'))
                for old in list(pr):
                    if old.tag in {w('jc'),w('spacing')}: pr.remove(old)
                E.SubElement(pr,w('jc'),{w('val'):'center'})
                E.SubElement(pr,w('spacing'),{w('before'):'60',w('after'):'60'})
                for run in p.findall(w('r')):
                    rp=run.find(w('rPr'))
                    if rp is None: rp=E.SubElement(run,w('rPr'))
                    for old in list(rp):
                        if old.tag in {w('rFonts'),w('sz'),w('b'),w('szCs')}: rp.remove(old)
                    E.SubElement(rp,w('rFonts'),{w('ascii'):'Times New Roman',w('hAnsi'):'Times New Roman'})
                    E.SubElement(rp,w('sz'),{w('val'):'18' if i==0 or row_index==0 else '20'})
                    E.SubElement(rp,w('b'))

def paragraph(body,text,bold=False,size=22):
    p=E.SubElement(body,w('p')); r=E.SubElement(p,w('r')); pr=E.SubElement(r,w('rPr'))
    E.SubElement(pr,w('rFonts'),{w('ascii'):'Arial',w('hAnsi'):'Arial'})
    E.SubElement(pr,w('sz'),{w('val'):str(size)})
    if bold: E.SubElement(pr,w('b'))
    E.SubElement(r,w('t')).text=text


def tabla_datos(headers,rows,widths):
    table=E.Element(w('tbl'));props=E.SubElement(table,w('tblPr'))
    E.SubElement(props,w('tblW'),{w('w'):str(sum(widths)),w('type'):'dxa'})
    E.SubElement(props,w('tblLayout'),{w('type'):'fixed'})
    borders=E.SubElement(props,w('tblBorders'))
    for side in ('top','left','bottom','right','insideH','insideV'):
        E.SubElement(borders,w(side),{w('val'):'single',w('sz'):'4',w('color'):'B7BEC8'})
    grid=E.SubElement(table,w('tblGrid'))
    for width in widths:E.SubElement(grid,w('gridCol'),{w('w'):str(width)})
    for i,values in enumerate([headers,*rows]):
        row=E.SubElement(table,w('tr'));rp=E.SubElement(row,w('trPr'));E.SubElement(rp,w('cantSplit'))
        total=i>0 and str(values[0]).startswith('TOTAL')
        if i==0:E.SubElement(rp,w('tblHeader'))
        for index,(value,width) in enumerate(zip(values,widths)):
            c=E.SubElement(row,w('tc'));cp=E.SubElement(c,w('tcPr'))
            E.SubElement(cp,w('tcW'),{w('w'):str(width),w('type'):'dxa'})
            if i==0 or total:E.SubElement(cp,w('shd'),{w('fill'):'E5E7EB'})
            margins=E.SubElement(cp,w('tcMar'))
            for side in ('top','left','bottom','right'):E.SubElement(margins,w(side),{w('w'):'65',w('type'):'dxa'})
            E.SubElement(cp,w('vAlign'),{w('val'):'center'})
            p=E.SubElement(c,w('p'));pp=E.SubElement(p,w('pPr'))
            E.SubElement(pp,w('spacing'),{w('before'):'20',w('after'):'20'})
            E.SubElement(pp,w('jc'),{w('val'):'left' if i>0 and headers[index]=='SUSTENTO / OBSERVACIÓN' else 'center'})
            r=E.SubElement(p,w('r'));pr=E.SubElement(r,w('rPr'))
            E.SubElement(pr,w('rFonts'),{w('ascii'):'Arial',w('hAnsi'):'Arial'})
            if i==0 or total:E.SubElement(pr,w('b'))
            E.SubElement(pr,w('sz'),{w('val'):'18'})
            E.SubElement(r,w('t')).text=''.join(ch for ch in str(value) if ord(ch)>=32 or ch in '\t\n')
    return table


def distribucion_mensual(rows):
    months=[[Decimal(0) for _ in range(7)] for _ in range(12)]
    dates={};ambiguous=set();undistributed=Decimal(0)
    for item in rows:
        length=(item['fin']-item['inicio']).days+1
        known=item['dias']==length or length==1
        if not known:undistributed+=item['dias']
        day=item['inicio']
        while day<=item['fin']:
            dates.setdefault(day,Decimal(0))
            if known:
                amount=item['dias'] if length==1 else Decimal(1)
                dates[day]+=amount;months[day.month-1][day.weekday()]+=amount
            else:ambiguous.add(day)
            day+=timedelta(days=1)
    return dict(meses=months,fechas=dates,ambiguas=ambiguous,no_distribuido=undistributed,
        total=sum((sum(m) for m in months),Decimal(0)))


def resumen_mensual(body,data):
    paragraph(body,'VACACIONES POR MES',True,20)
    rows=[[MONTHS[i],num(sum(values))] for i,values in enumerate(data['meses']) if sum(values)]
    if data['no_distribuido']:
        rows.append(['Sin mes definido',num(data['no_distribuido'])])
    rows.append(['TOTAL',num(data['total']+data['no_distribuido'])])
    body.append(tabla_datos(['MES','DÍAS'],rows,[3000,1700]))


def generar_docx(cuenta,anio,formato):
    if formato not in {'record','informe'} or not 1900<=anio<=9999: raise ValueError('Formato o año inválido.')
    layout=json.loads((Path(__file__).parent/'vacaciones_word_layout.json').read_text(encoding='utf-8'))[formato]
    source=E.fromstring(layout['table']); templates=source.findall(w('tr'))
    for row in templates: source.remove(row)
    rows,_=movimientos_del_anio(cuenta,anio)
    distribution=distribucion_mensual(rows)
    root=E.Element(w('document')); body=E.SubElement(root,w('body'))
    paragraph(body,('RÉCORD' if formato=='record' else 'INFORME')+f' DE VACACIONES {anio}',True,26)
    paragraph(body,f'{cuenta.nombre} · DNI {cuenta.dni}')
    paragraph(body,f'Régimen laboral: {getattr(cuenta,"regimen_laboral","") or "Sin régimen informado"}.',size=20)
    saldo_documento(body,cuenta)
    if formato=='record':
        current=resumen(cuenta)
        source.append(row_from(templates[0],['N° DOCUMENTO',cuenta.dni,cuenta.nombre],True))
        years=sorted(k for k,v in cuenta.asignaciones.items() if v is not None)
        if not years: years=[str(anio)]
        for offset in range(0,len(years),4):
            chunk=years[offset:offset+4]; labels=chunk+['']*(4-len(chunk))
            source.append(row_from(templates[1],['',*labels,'Total','Saldo'],True))
            source.append(row_from(templates[2],['Programado',*[num(cuenta.asignaciones[y]) if cuenta.asignaciones.get(y) is not None else '' for y in labels],num(current['programado']) if not offset else '',num(current['pendiente']) if not offset else ''],True))
        body.append(source)
        paragraph(body,'',size=6)
        detail=[[item['inicio'].strftime('%d/%m/%Y'),item['fin'].strftime('%d/%m/%Y'),num(item['dias']),item['obj'].periodo,item['obj'].observaciones] for item in rows]
        detail.append(['TOTAL DEL AÑO','',num(sum((item['dias'] for item in rows),Decimal(0))),'',''])
        source=tabla_datos(['DEL','AL','DÍAS','PERIODO','SUSTENTO / OBSERVACIÓN'],detail,[1500,1500,750,1200,3950])
    else:
        source.append(row_from(templates[0],['MES / VACACIONES','LUNES','MARTES','MIÉRCOLES','JUEVES','VIERNES','SÁBADO','DOMINGO'],True))
        for month in range(1,13):
            first=True
            for week in Calendar(firstweekday=0).monthdayscalendar(anio,month):
                if not any(d and date(anio,month,d) in distribution['fechas'] for d in week):continue
                cells=[]
                for d in week:
                    day=date(anio,month,d) if d else None
                    if day not in distribution['fechas']:cells.append('');continue
                    amount=distribution['fechas'][day]
                    cells.append(str(d)+(f' ({num(amount)})' if amount not in (0,1) else ''))
                source.append(row_from(templates[1],[MONTHS[month-1] if first else '',*cells]))
                first=False
        uniformar_informe(source)
    body.append(source)
    if not rows: paragraph(body,'Sin vacaciones registradas para el año.',size=18)
    resumen_mensual(body,distribution)
    body.append(E.fromstring(layout['section']))
    content_types='<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    package={'[Content_Types].xml':content_types,'_rels/.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/_rels/document.xml.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'word/document.xml':E.tostring(root,encoding='utf-8',xml_declaration=True),'word/styles.xml':layout['styles']}
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for name,data in package.items(): z.writestr(name,data)
    return out.getvalue()


def generar_integrado(cuenta):
    years=anios_disponibles(cuenta)
    if not years:
        # Una ficha sin fechas ni asignaciones también debe poder documentarse.
        from django.utils import timezone
        years=[timezone.localdate().year]
    package=None; root=None; body=None; section=None
    for year in years:
        for kind in ('record','informe'):
            with ZipFile(BytesIO(generar_docx(cuenta,year,kind))) as archive:
                parts={name:archive.read(name) for name in archive.namelist()}
            doc=E.fromstring(parts['word/document.xml']); content=doc.find(w('body'))
            next_section=content.find(w('sectPr')); content.remove(next_section)
            if package is None:
                package=parts; root=doc; body=content
                paragraph_intro=E.Element(w('p'))
                intro_run=E.SubElement(paragraph_intro,w('r'))
                E.SubElement(intro_run,w('t')).text='RÉCORD E INFORME INTEGRADOS DE VACACIONES · TODOS LOS AÑOS'
                body.insert(0,paragraph_intro)
            else:
                # Cada cuadro conserva orientación y márgenes de su modelo.
                p=E.SubElement(body,w('p')); props=E.SubElement(p,w('pPr'))
                break_type=section.find(w('type'))
                if break_type is None:
                    break_type=E.Element(w('type')); section.insert(0,break_type)
                break_type.set(w('val'),'nextPage')
                props.append(section)
                body.extend(list(content))
            section=next_section
    body.append(section)
    package['word/document.xml']=E.tostring(root,encoding='utf-8',xml_declaration=True)
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as archive:
        for name,data in package.items(): archive.writestr(name,data)
    return out.getvalue()
