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
                    7:m['dias'],8:m['permiso'],9:m['observaciones'],10:c.nombre,11:m['inicio'],12:m['fin'],
                    13:str(m['fecha'].year) if m['fecha'] else None,
                    14:f'{m["fecha"].month:02}' if m['fecha'] else None,
                    15:f'{m["fecha"].day:02}' if m['fecha'] else None})
            for col in sorted(set(values)|set(range(1,34 if name=='Resumen' else 56))):
                node.append(cell(i,col,values.get(col),styles.get(column(col)),formulas.get(col)))
        dimension=sheet.find(tag('dimension'))
        if dimension is not None: dimension.set('ref',f'A1:{"AG" if name=="Resumen" else "BC"}{max(header,len(records)+header)}')
        normalizar_hoja(sheet)
        package[key]=E.tostring(sheet,encoding='unicode')
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for key,value in package.items(): z.writestr(key,value)
    return out.getvalue()
