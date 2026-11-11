"""Hojas por régimen con títulos repetidos y configuración de impresión A4."""
import json,math,re
from datetime import date,datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZipFile,ZIP_DEFLATED
from .vacaciones_xlsx import NS,tag,column,cell

REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'

def xml_paquete(root):
    # Serializar estas partes OPC con su espacio de nombres predeterminado.
    value=E.tostring(root,encoding='unicode')
    match=re.match(r'<([^: >]+):',value)
    if match:
        prefix=match.group(1)
        value=value.replace(f'<{prefix}:','<').replace(f'</{prefix}:','</').replace(f'xmlns:{prefix}=','xmlns=')
    return value

def libro_agrupado(sheets):
    package=json.loads((Path(__file__).parent/'regimen_export_layout.json').read_text(encoding='utf-8'))
    original=E.fromstring(package['xl/worksheets/sheet1.xml'])
    style={c.get('r'):c.get('s') for c in original.findall('.//'+tag('c'))}
    styles=E.fromstring(package['xl/styles.xml'])
    for xf in styles.find(tag('cellXfs')):
        alignment=xf.find(tag('alignment'))
        if alignment is None:alignment=E.SubElement(xf,tag('alignment'))
        alignment.set('wrapText','1');alignment.set('vertical','center')
    package['xl/styles.xml']=E.tostring(styles,encoding='unicode')
    wb=E.fromstring(package['xl/workbook.xml']);wslist=wb.find(tag('sheets'));wslist.clear()
    defined=wb.find(tag('definedNames'))
    if defined is not None:wb.remove(defined)
    defined=E.Element(tag('definedNames'))
    calc=wb.find(tag('calcPr'))
    wb.insert(list(wb).index(calc) if calc is not None else len(wb),defined)
    relationships=E.fromstring(package['xl/_rels/workbook.xml.rels'])
    for rel in list(relationships):
        if rel.get('Type','').endswith(('/worksheet','/calcChain')):relationships.remove(rel)
    types=E.fromstring(package['[Content_Types].xml'])
    for child in list(types):
        if child.get('PartName','').startswith('/xl/worksheets/') or child.get('PartName','').endswith('calcChain.xml'):types.remove(child)
    package={k:v for k,v in package.items() if not k.startswith('xl/worksheets/') and not k.endswith('calcChain.xml')}
    names=set()
    for index,spec in enumerate(sheets or [dict(nombre='Sin resultados',titulo='Sin resultados',regimen='',headers=['Sin resultados'],rows=[],widths=[40])]):
        name=re.sub(r'[\[\]:*?/\\]',' ',spec['nombre']).strip(" '")[:31] or 'Hoja'
        stem=name;suffix=1
        while name.casefold() in names:
            suffix+=1;name=stem[:27]+f' {suffix}'
        names.add(name.casefold());rid=f'regimenSheet{index+1}'
        E.SubElement(wslist,tag('sheet'),{'name':name,'sheetId':str(index+1),'{'+REL+'}id':rid})
        E.SubElement(relationships,'{'+PKG+'}Relationship',{'Id':rid,'Type':REL+'/worksheet','Target':f'worksheets/sheet{index+1}.xml'})
        E.SubElement(types,'{'+CT+'}Override',{'PartName':f'/xl/worksheets/sheet{index+1}.xml','ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
        headers=spec['headers'];records=spec['rows'];last=column(len(headers));end=3+len(records)
        sheet=E.Element(tag('worksheet'));E.SubElement(sheet,tag('sheetPr')).append(E.Element(tag('pageSetUpPr'),{'fitToPage':'1'}))
        E.SubElement(sheet,tag('dimension'),{'ref':f'A1:{last}{max(end+1,4)}'})
        views=E.SubElement(sheet,tag('sheetViews'));view=E.SubElement(views,tag('sheetView'),{'workbookViewId':'0','showGridLines':'0'})
        E.SubElement(view,tag('pane'),{'ySplit':'3','topLeftCell':'A4','activePane':'bottomLeft','state':'frozen'})
        cols=E.SubElement(sheet,tag('cols'))
        for i,width in enumerate(spec['widths'],1):E.SubElement(cols,tag('col'),{'min':str(i),'max':str(i),'width':str(width),'customWidth':'1'})
        data=E.SubElement(sheet,tag('sheetData'))
        for row_num,values in [(1,[spec['titulo']]),(2,[f'Régimen laboral: {spec["regimen"] or "Sin régimen informado"}. Registros: {len(records)}.']),(3,headers)]:
            row=E.SubElement(data,tag('row'),{'r':str(row_num),'ht':'30' if row_num!=2 else '24','customHeight':'1'})
            for col,value in enumerate(values,1):row.append(cell(row_num,col,value,style.get(f'A{row_num}')))
        for row_num,values in enumerate(records,4):
            lines=max([1]+[math.ceil(len(str(v or ''))/max(width-2,4)) for v,width in zip(values,spec['widths']) if isinstance(v,str)])
            row=E.SubElement(data,tag('row'),{'r':str(row_num),'ht':str(max(24,15*lines)),'customHeight':'1'})
            for col,value in enumerate(values,1):
                st=style.get('C4' if isinstance(value,(date,datetime)) else 'B4' if isinstance(value,(int,float,Decimal)) else 'A4')
                row.append(cell(row_num,col,value,st))
        total_cols=spec.get('totales',[])
        if total_cols:
            row=E.SubElement(data,tag('row'),{'r':str(end+1),'ht':'26','customHeight':'1'})
            row.append(cell(end+1,1,'TOTAL',style.get('A5')))
            for col in total_cols:
                total=sum((Decimal(str(r[col-1] or 0)) for r in records),Decimal(0))
                row.append(cell(end+1,col,total,style.get('B5'),f'SUM({column(col)}4:{column(col)}{end})' if records else '0'))
        E.SubElement(sheet,tag('autoFilter'),{'ref':f'A3:{last}{max(end,3)}'})
        if len(headers)>1:
            merges=E.SubElement(sheet,tag('mergeCells'),{'count':'2'})
            for n in (1,2):E.SubElement(merges,tag('mergeCell'),{'ref':f'A{n}:{last}{n}'})
        E.SubElement(sheet,tag('pageMargins'),dict(left='.25',right='.25',top='.4',bottom='.4',header='.2',footer='.2'))
        E.SubElement(sheet,tag('pageSetup'),{'paperSize':'9','orientation':'landscape','fitToWidth':'1','fitToHeight':'0'})
        footer=E.SubElement(sheet,tag('headerFooter'));E.SubElement(footer,tag('oddFooter')).text='&C&P / &N'
        safe=name.replace("'","''")
        E.SubElement(defined,tag('definedName'),{'name':'_xlnm.Print_Titles','localSheetId':str(index)}).text=f"'{safe}'!$1:$3"
        E.SubElement(defined,tag('definedName'),{'name':'_xlnm.Print_Area','localSheetId':str(index)}).text=f"'{safe}'!$A$1:${last}${max(end+bool(total_cols),4)}"
        package[f'xl/worksheets/sheet{index+1}.xml']=E.tostring(sheet,encoding='unicode')
    package['xl/workbook.xml']=E.tostring(wb,encoding='unicode')
    package['xl/_rels/workbook.xml.rels']=xml_paquete(relationships)
    package['[Content_Types].xml']=xml_paquete(types)
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as archive:
        for name,value in package.items():archive.writestr(name,value)
    return out.getvalue()


def exportar_vacaciones_agrupadas(results):
    groups={}
    for r in results:groups.setdefault(r['cuenta'].regimen_laboral or 'Sin régimen informado',[]).append(r)
    sheets=[]
    for regime,items in sorted(groups.items()):
        ordered=sorted(items,key=lambda r:r['cuenta'].nombre)
        sheets.append(dict(nombre=regime,titulo='CONTROL DE VACACIONES',regimen=regime,
            headers=['DNI','Trabajador','Régimen laboral','Programado','Usado','Saldo','Pendiente 2024','Pendiente 2025'],
            widths=[12,42,22,14,12,12,17,17],totales=[4,5,6,7,8],
            rows=[[r['cuenta'].dni,r['cuenta'].nombre,regime,r['programado'],r['usado'],r['pendiente'],r['por_anio'].get('2024',0),r['por_anio'].get('2025',0)] for r in ordered]))
        movements=[[r['cuenta'].dni,r['cuenta'].nombre,m['periodo'],m['codigo'],m['inicio'],m['fin'],m['dias'],m['observaciones']]
            for r in ordered for m in r['filas'] if m['estado']=='VIGENTE']
        sheets.append(dict(nombre='Detalle '+regime,titulo='MOVIMIENTOS DE VACACIONES',regimen=regime,
            headers=['DNI','Trabajador','Periodo','Código','Del','Al','Días','Observaciones'],
            widths=[12,35,10,9,13,13,9,52],totales=[7],rows=movements))
    return libro_agrupado(sheets)


def exportar_consultas_agrupadas(qs):
    groups={}
    for j in qs:
        groups.setdefault(j.trabajador.regimen_laboral or 'Sin régimen informado',[]).append(j)
    return libro_agrupado([dict(nombre=regime,titulo='CONSULTAS DE ASISTENCIAS',regimen=regime,
        headers=['ID','Trabajador','DNI','Documento','Operación','Del','Al','Días calendario','CUD','Observaciones'],
        widths=[8,36,12,19,24,13,13,12,15,38],rows=[[j.pk,j.trabajador.apellidos_nombres,j.trabajador.dni,
            str(j.tipo_documento),str(j.tipo_operacion),j.fecha_movimiento,j.fecha_final,j.duracion,j.cud,j.observaciones] for j in items]) for regime,items in sorted(groups.items())])
