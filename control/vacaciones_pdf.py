"""PDF de los mismos cuadros y valores utilizados por los formatos Word."""
from io import BytesIO
from xml.etree import ElementTree as E
from xml.sax.saxutils import escape
from zipfile import ZipFile
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from .vacaciones_word import w


def convertir_docx(data):
    with ZipFile(BytesIO(data)) as archive:
        body=E.fromstring(archive.read('word/document.xml')).find(w('body'))
        footer_text = ''
        if 'word/footer1.xml' in archive.namelist():
            footer = E.fromstring(archive.read('word/footer1.xml'))
            footer_text = ''.join(node.text or '' for node in footer.iter(w('t')))
    output=BytesIO()
    doc=SimpleDocTemplate(output,pagesize=A4,leftMargin=36,rightMargin=36,topMargin=36,bottomMargin=36)
    normal=ParagraphStyle('normal',fontName='Helvetica',fontSize=9,leading=12,spaceAfter=7)
    cell_style=ParagraphStyle('cell',parent=normal,fontSize=8,leading=10,spaceAfter=0)
    def text(node): return ''.join(node.itertext())
    def paragraph(node,style): return Paragraph(escape(text(node)).replace('\n','<br/>'),style)
    story=[]
    for node in body:
        if node.tag==w('p'):
            if node.find('.//'+w('sectPr')) is not None:
                story.append(PageBreak())
            elif text(node):
                bold=node.find('.//'+w('b')) is not None
                style=ParagraphStyle('heading',parent=normal,fontName='Helvetica-Bold',fontSize=11,leading=14) if bold else normal
                story.append(paragraph(node,style))
        elif node.tag==w('tbl'):
            grid=node.find(w('tblGrid'))
            widths=[int(c.get(w('w'))) for c in grid]
            scale=min(doc.width/sum(widths),1/20)
            widths=[v*scale for v in widths]
            rows=[]; spans=[]; backgrounds=[]; vertical={}
            for ri,row in enumerate(node.findall(w('tr'))):
                cells=[]
                for cell in row.findall(w('tc')):
                    ci=len(cells)
                    span=cell.find('./'+w('tcPr')+'/'+w('gridSpan'))
                    count=int(span.get(w('val'))) if span is not None else 1
                    merge=cell.find('./'+w('tcPr')+'/'+w('vMerge'))
                    if merge is not None and merge.get(w('val'),'continue')!='restart' and ci in vertical:
                        start=vertical[ci];spans.append(('SPAN',(ci,start),(ci,ri)))
                        # Reemplazar el tramo anterior por la extensión completa.
                        spans[:]=[span for span in spans if span[0]!='SPAN' or span[1]!=(ci,start) or span[2]==(ci,ri)]
                    else: vertical.pop(ci,None)
                    if merge is not None and merge.get(w('val'))=='restart':vertical[ci]=ri
                    bold=cell.find('.//'+w('b')) is not None
                    align=cell.find('.//'+w('jc'))
                    style=ParagraphStyle('cell_variant',parent=cell_style,fontName='Helvetica-Bold' if bold else 'Helvetica',alignment=1 if align is not None and align.get(w('val'))=='center' else 0)
                    cells.append(paragraph(cell,style));cells.extend(['']*(count-1))
                    if count>1: spans.append(('SPAN',(ci,ri),(ci+count-1,ri)))
                    shade=cell.find('./'+w('tcPr')+'/'+w('shd'))
                    fill=shade.get(w('fill')) if shade is not None else None
                    if fill and len(fill)==6: backgrounds.append(('BACKGROUND',(ci,ri),(ci+count-1,ri),colors.HexColor('#'+fill)))
                cells.extend(['']*(len(widths)-len(cells)));rows.append(cells)
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor('#a8b3c2')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),*spans,*backgrounds]))
            story.extend([table,Spacer(1,10)])
    def draw_footer(canvas, document):
        if footer_text:
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            canvas.drawString(document.leftMargin, 17, footer_text)
            canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return output.getvalue()
