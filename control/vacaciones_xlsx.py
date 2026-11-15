"""Escribe valores en una plantilla OOXML sin alterar su diseño ni incluir macros."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
E.register_namespace('',NS)
def tag(n): return '{'+NS+'}'+n


def normalizar_hoja(sheet):
    """Descartar metadatos de Office cuyo prefijo/relación ya no existe.

    ElementTree cambia x14ac por ns2, pero no cambia el valor literal de
    mc:Ignorable. Excel rechaza la hoja si ese prefijo no está declarado.
    dyDescent y las relaciones a impresoras no forman parte del diseño usado.
    """
    for node in sheet.iter():
        for attr in list(node.attrib):
            if attr.startswith('{') and not attr.startswith(('{'+NS+'}', '{http://www.w3.org/XML/1998/namespace}')):
                del node.attrib[attr]
    for view in sheet.findall('.//'+tag('sheetView')):
        view.set('topLeftCell','A1')
        view.set('zoomScale','100')
        view.set('zoomScaleNormal','100')
        for selection in view.findall(tag('selection')):
            selection.set('activeCell','A1')
            selection.set('sqref','A1')


def column(n):
    result=''
    while n:
        n,r=divmod(n-1,26); result=chr(65+r)+result
    return result


def cell(row,col,value,style=None,formula=None):
    a={'r':column(col)+str(row)}
    if style is not None: a['s']=style
    node=E.Element(tag('c'),a)
    if value is None: return node
    if formula is not None:
        E.SubElement(node,tag('f')).text=formula
        E.SubElement(node,tag('v')).text=str(value)
    elif isinstance(value,bool):
        node.set('t','b')
        E.SubElement(node,tag('v')).text='1' if value else '0'
    elif isinstance(value,(Decimal,int,float)):
        E.SubElement(node,tag('v')).text=str(value)
    else:
        if isinstance(value,(date,datetime)):
            day=value.date() if isinstance(value,datetime) else value
            E.SubElement(node,tag('v')).text=str((day-date(1899,12,30)).days)
        else:
            node.set('t','inlineStr')
            # Literal strings protect DNI, leading zeroes and Excel formula injection.
            E.SubElement(E.SubElement(node,tag('is')),tag('t')).text=ILLEGAL_CHARACTERS_RE.sub('',str(value))
    return node


def exportar_control(results):
    layout=json.loads((Path(__file__).parent/'vacaciones_layout.json').read_text(encoding='utf-8'))
    package=layout['package'].copy()
    allrows=[(r,m) for r in results for m in r['filas'] if m['estado']=='VIGENTE']
    # Los DNI que solo estaban en DETALLE no generan filas inventadas en RESUMEN.
    summary=[r for r in results if not r['cuenta'].origen.get('sin_resumen')]
    for name,header,records in [('Resumen',3,summary),('detalle',2,allrows)]:
        key=layout['sheets'][name]
        sheet=E.fromstring(package[key]); data=sheet.find(tag('sheetData'))
        templates={int(r.get('r')):deepcopy(r) for r in data}
        for row in list(data):
            if int(row.get('r'))>header: data.remove(row)
        header_row=next(r for r in data if int(r.get('r'))==header)
        regimen_col=34 if name=='Resumen' else 56
        header_row.append(cell(header,regimen_col,'Régimen laboral'))
        for i,record in enumerate(records,header+1):
            r=record if name=='Resumen' else record[0]
            c=r['cuenta']; origin=c.origen if name=='Resumen' else record[1]['origen']
            template=templates.get(origin.get('fila'),templates.get(header+1))
            attrs=dict(template.attrib) if template is not None else {}
            attrs['r']=str(i)
            attrs['spans']='1:33' if name=='Resumen' else '1:55'
            node=E.SubElement(data,tag('row'),attrs)
            styles={''.join(ch for ch in x.get('r','') if ch.isalpha()):x.get('s') for x in template} if template is not None else {}
            values={}; formulas={}
            if name=='Resumen':
                raw=c.origen.get('valores',{})
                values={int(k):v for k,v in raw.items() if int(k)>18}
                values.update({1:c.dni,2:c.nombre,3:c.tipo,4:c.estado})
                values.update({5+y-2022:Decimal(c.asignaciones[str(y)]) if c.asignaciones.get(str(y)) is not None else None for y in range(2022,2031)})
                values.update({14:r['programado'],15:r['usado'],16:r['pendiente'],
                               17:r['por_anio'].get('2024',0),18:r['por_anio'].get('2025',0)})
                end=max(3,len(allrows)+2)
                formulas={14:f'SUM(E{i}:M{i})',15:f'SUMIFS(detalle!$G$3:$G${end},detalle!$A$3:$A${end},A{i})',16:f'N{i}-O{i}',
                          17:f'MAX(0,G{i}-MAX(0,O{i}-SUM(E{i}:F{i})))',
                          18:f'MAX(0,H{i}-MAX(0,O{i}-SUM(E{i}:G{i})))'}
                if '28' in raw:
                    values[28]=sum((Decimal(str(values[k])) for k in range(19,28) if isinstance(values.get(k),(int,float,Decimal))),Decimal(0))
                    formulas[28]=f'SUM(S{i}:AA{i})'
                if '29' in raw:
                    values[29]=r['usado']-Decimal(str(values.get(28) or 0)); formulas[29]=f'O{i}-AB{i}'
                if '31' in raw and isinstance(values.get(30),(int,float,Decimal)):
                    values[31]=r['usado']-Decimal(str(values[30])); formulas[31]=f'O{i}-AD{i}'
            else:
                m=record[1]; raw=m['origen'].get('valores',{})
                values={int(k):v for k,v in raw.items() if int(k)>15}
                values.update({1:c.dni,2:m['periodo'],3:m['codigo'],4:m['fecha'],5:m['inicio'],6:m['fin'],
                    7:0 if m['codigo']=='09' else m['dias'],8:m['dias_ley'] if m['codigo']=='09' else m['permiso'],9:m['observaciones'],10:c.nombre,11:m['inicio'],12:m['fin'],
                    13:str(m['fecha'].year) if m['fecha'] else None,
                    14:f'{m["fecha"].month:02}' if m['fecha'] else None,
                    15:f'{m["fecha"].day:02}' if m['fecha'] else None})
            values[regimen_col]=c.regimen_laboral
            for col in sorted(set(values)|set(range(1,35 if name=='Resumen' else 57))):
                node.append(cell(i,col,values.get(col),styles.get(column(col)),formulas.get(col)))
        dimension=sheet.find(tag('dimension'))
        if dimension is not None: dimension.set('ref',f'A1:{"AH" if name=="Resumen" else "BD"}{max(header,len(records)+header)}')
        normalizar_hoja(sheet)
        if name=='Resumen': ampliar_resumen(sheet,summary,package)
        package[key]=E.tostring(sheet,encoding='unicode')
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for key,value in package.items(): z.writestr(key,value)
    return out.getvalue()


def ampliar_resumen(sheet,results,package):
    """Insertar B:D y fila de resolución; trasladar referencias locales."""
    import re
    from openpyxl.formula.tokenizer import Tokenizer
    from openpyxl.utils.cell import column_index_from_string
    def mover_ref(ref):
        def cambio(match):
            col=column_index_from_string(match[2]);row=int(match[4])
            return f'{match[1]}{column(col+3 if col>=2 else col)}{match[3]}{row+1 if row>=3 else row}'
        return re.sub(r'(\$?)([A-Z]+)(\$?)([0-9]+)',cambio,ref)
    def mover_formula(formula):
        tokens=Tokenizer('='+formula).items
        for token in tokens:
            if token.type=='OPERAND' and token.subtype=='RANGE':
                if '!' in token.value:
                    name,ref=token.value.rsplit('!',1)
                    if name.strip("'")=='Resumen': token.value=name+'!'+mover_ref(ref)
                else: token.value=mover_ref(token.value)
        return ''.join(token.value for token in tokens)
    data=sheet.find(tag('sheetData'))
    for row in data:
        row.set('r',str(int(row.get('r'))+(int(row.get('r'))>=3)))
        row.set('spans','1:36')
        for c in list(row):
            if re.match(r'^AH[0-9]+$',c.get('r','')): row.remove(c);continue
            c.set('r',mover_ref(c.get('r')))
            f=c.find(tag('f'))
            if f is not None and f.text:f.text=mover_formula(f.text)
    for node in sheet.iter():
        for attr in ('ref','sqref','activeCell','topLeftCell'):
            if node.tag!=tag('c') and attr in node.attrib: node.set(attr,mover_ref(node.get(attr)))
    cols=sheet.find(tag('cols'))
    for c in cols:
        for key in ('min','max'):
            v=int(c.get(key));c.set(key,str(v+3 if v>=2 else v))
    for index,width in ((2,22),(3,25),(4,19)):
        E.SubElement(cols,tag('col'),{'min':str(index),'max':str(index),'width':str(width),'customWidth':'1'})
    for c in cols:
        if int(c.get('min'))<=11<=int(c.get('max')): c.set('width','20')
    cols[:]=sorted(cols,key=lambda c:int(c.get('min')))
    header=next(r for r in data if r.get('r')=='4')
    header_style=next(c.get('s') for c in header if c.get('r')=='E4')
    for col,label in ((2,'Régimen laboral'),(3,'Condición'),(4,'Fin de contrato')): header.append(cell(4,col,label,header_style))
    name_header=next(c for c in header if c.get('r')=='E4')
    name_header.find('.//'+tag('t')).text='Apellidos y Nombres'
    header.set('ht','30');header.set('customHeight','1')
    rdr=E.Element(tag('row'),{'r':'3','ht':'23','customHeight':'1'});rdr.append(cell(3,11,'RDR 3015-2025',header_style));data.insert(2,rdr)
    # Fecha tipada con formato legible; estados BAJA/NO EXISTE siguen siendo texto.
    styles=E.fromstring(package['xl/styles.xml']);formats=styles.find(tag('numFmts'))
    if formats is None: formats=E.Element(tag('numFmts'));styles.insert(0,formats)
    fid=max([163]+[int(n.get('numFmtId')) for n in formats])+1
    E.SubElement(formats,tag('numFmt'),{'numFmtId':str(fid),'formatCode':'dd/mm/yyyy'});formats.set('count',str(len(formats)))
    xfs=styles.find(tag('cellXfs'))
    body_row=next((r for r in data if r.get('r')=='5'),header)
    body_style=next((c.get('s') for c in body_row if c.get('r','').startswith('E')),header_style)
    base=deepcopy(xfs[int(body_style)])
    base.set('numFmtId',str(fid));base.set('applyNumberFormat','1');date_style=str(len(xfs));xfs.append(base);xfs.set('count',str(len(xfs)))
    fonts=styles.find(tag('fonts'));font_id=len(fonts)
    font=E.SubElement(fonts,tag('font'))
    E.SubElement(font,tag('b'));E.SubElement(font,tag('sz'),{'val':'11'})
    E.SubElement(font,tag('color'),{'rgb':'FF1F2937'});E.SubElement(font,tag('name'),{'val':'Arial'})
    fonts.set('count',str(len(fonts)))
    fills=styles.find(tag('fills'));fill_id=len(fills)
    pattern=E.SubElement(E.SubElement(fills,tag('fill')),tag('patternFill'),{'patternType':'solid'})
    E.SubElement(pattern,tag('fgColor'),{'rgb':'FFFFFF00'})
    E.SubElement(pattern,tag('bgColor'),{'indexed':'64'});fills.set('count',str(len(fills)))
    title_style=deepcopy(xfs[0]);title_style.set('fontId',str(font_id));title_style.set('fillId',str(fill_id))
    title_style.set('numFmtId','0');title_style.set('applyFont','1');title_style.set('applyFill','1');title_style.set('applyAlignment','1')
    old_alignment=title_style.find(tag('alignment'))
    if old_alignment is not None: title_style.remove(old_alignment)
    E.SubElement(title_style,tag('alignment'),{'horizontal':'center','vertical':'center','wrapText':'1'})
    rdr[0].set('s',str(len(xfs)));xfs.append(title_style);xfs.set('count',str(len(xfs)))
    package['xl/styles.xml']=E.tostring(styles,encoding='unicode')
    for i,result in enumerate(results,5):
        row=next(r for r in data if r.get('r')==str(i));account=result['cuenta']
        style=next(c.get('s') for c in row if c.get('r')=='E'+str(i))
        end=getattr(account,'fin_contrato','');date_value=None
        for fmt in ('%d/%m/%Y','%Y-%m-%d'):
            try: date_value=datetime.strptime(end,fmt).date();break
            except (ValueError,TypeError):pass
        for col,value in ((2,account.regimen_laboral),(3,getattr(account,'condicion_laboral','')),(4,date_value or end)):
            row.append(cell(i,col,value,date_style if col==4 and date_value else style))
    for row in data: row[:]=sorted(row,key=lambda c:column_index_from_string(re.sub('[0-9]','',c.get('r'))))
    # Excel requiere filas en orden ascendente; no omitir la resolución al abrir.
    data[:]=sorted(data,key=lambda row:int(row.get('r')))
    # Todas las columnas quedan dentro del área filtrable; sin duplicar el régimen al final.
    auto=sheet.find(tag('autoFilter'))
    if auto is None:
        auto=E.Element(tag('autoFilter'));sheet.insert(list(sheet).index(sheet.find(tag('mergeCells'))),auto)
    auto.set('ref',f'A4:AJ{max(4,len(results)+4)}')
    sheet.find(tag('dimension')).set('ref',f'A1:AJ{max(4,len(results)+4)}')
