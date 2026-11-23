from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from unittest.mock import patch
from xml.etree import ElementTree as ET
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook
from .models import CuentaVacacion, MovimientoVacacion, Trabajador, Justificacion, TipoOperacion, TipoDocumento, PeriodoAsistencia
from .vacaciones import resumen
from .vacaciones_xlsx import exportar_control


class ControlVacacionesTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser('prueba','', 'clave-ficticia')
        self.worker=Trabajador.objects.create(apellidos_nombres='PERSONA FICTICIA',dni='00000001')
        self.account=CuentaVacacion.objects.create(trabajador=self.worker,dni='00000001',nombre='PERSONA FICTICIA',
            asignaciones={'2022':None,'2023':None,'2024':'10','2025':'30'})

    def test_descargas_pdf_individual_integrado_y_zip(self):
        self.client.force_login(self.user)
        url=reverse('vacacion_formatos',args=[self.account.pk])
        for kind in ('record','informe','integrado'):
            response=self.client.get(url,dict(generar='1',anio=2026,formato=kind,tipo_archivo='pdf'))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response['Content-Type'],'application/pdf')
            self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertContains(self.client.get(url),'Formato de archivo')
        self.assertContains(self.client.get(url),'ejemplo-record.svg')
        self.assertContains(self.client.get(url),'ejemplo-informe.svg')

    def test_filtros_ficha_anios_multiples_tipo_y_saldo_completo(self):
        self.client.force_login(self.user)
        for anio,codigo,dias in [('2023','05',2),('2024','05',3),('2022','09',0),('2025','32',Decimal('.5'))]:
            MovimientoVacacion.objects.create(cuenta=self.account,periodo=anio,codigo=codigo,dias=dias)
        url=reverse('vacacion_ficha',args=[self.account.pk])
        response=self.client.get(url,{'anio':['2023','2024'],'tipo_movimiento':'05'})
        self.assertEqual(len(response.context['filas_visibles']),2)
        self.assertEqual(response.context['total_visible'],5)
        self.assertEqual(response.context['r']['usado'],Decimal('5.5'))
        self.assertEqual(response.context['r']['pendiente'],Decimal('34.5'))
        response=self.client.get(url,{'anio':'2025','tipo_movimiento':'05'})
        self.assertEqual(response.context['filas_visibles'],[])
        self.assertContains(response,'No hay movimientos para los filtros seleccionados.')
        response = self.client.get(url)
        self.assertEqual(len(response.context['filas_visibles']), 3)
        self.assertNotIn(('2022', '2022'), response.context['anios_movimientos'])
        self.assertNotIn(('09', 'Permiso Ley'), response.context['tipos_movimientos'])
        self.assertNotContains(response, 'Permiso Ley')
        self.assertEqual(self.client.get(url, {'tipo_movimiento': '09'}).context['filas_visibles'], [])

    def test_exportacion_columnas_laborales_y_referencias(self):
        self.account.regimen_laboral='DEC. LEG. 276'
        self.account.condicion_laboral='NOMBRADO';self.account.fin_contrato='31/12/2027';self.account.save()
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=Decimal('0.5'))
        data=exportar_control([resumen(self.account)])
        book=load_workbook(BytesIO(data));sheet=book['Resumen']
        self.assertEqual([sheet[f'{c}4'].value for c in 'ABCDE'],['Dni','Régimen laboral','Condición','Fin de contrato','Apellidos y Nombres'])
        self.assertEqual(sheet['K3'].value,'RDR 3015-2025')
        with ZipFile(BytesIO(data)) as archive:
            root=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows=[int(row.get('r')) for row in root.find('s:sheetData',ns)]
            self.assertEqual(rows,sorted(set(rows)))
        self.assertTrue(sheet['K3'].font.bold)
        self.assertEqual(sheet['K3'].fill.fgColor.rgb,'FFFFFF00')
        self.assertEqual(sheet['K4'].value,2025)
        self.assertEqual(sheet['C5'].value,'NOMBRADO')
        self.assertEqual(sheet['D5'].value.date(),date(2027,12,31))
        self.assertEqual(sheet['Q5'].value,'=SUM(H5:P5)')
        self.assertIn('detalle!$G$',sheet['R5'].value)
        self.assertEqual(sheet['S5'].value,'=Q5-R5')
        self.assertEqual(sheet['D5'].number_format,'dd/mm/yyyy')
        self.account.fin_contrato='BAJA'
        sheet=load_workbook(BytesIO(exportar_control([resumen(self.account)])))['Resumen']
        self.assertEqual(sheet['D5'].value,'BAJA')

    def test_importar_datos_laborales_solo_metadatos_con_previa(self):
        self.account.condicion_laboral='CONTRATADO';self.account.fin_contrato='BAJA';self.account.save()
        data=exportar_control([resumen(self.account)])
        self.account.condicion_laboral='';self.account.fin_contrato='';self.account.save()
        asignaciones=self.account.asignaciones.copy()
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'fuente.xlsx';path.write_bytes(data)
            call_command('importar_datos_laborales',str(path),stdout=StringIO())
            self.account.refresh_from_db();self.assertEqual(self.account.condicion_laboral,'')
            call_command('importar_datos_laborales',str(path),confirmar=True,usuario=self.user.username,stdout=StringIO())
            self.account.refresh_from_db()
            self.assertEqual(self.account.condicion_laboral,'CONTRATADO')
            self.assertEqual(self.account.fin_contrato,'BAJA')
            self.assertEqual(self.account.asignaciones,asignaciones)
            self.assertEqual(MovimientoVacacion.objects.count(),0)
            count=self.account.updated_at
            call_command('importar_datos_laborales',str(path),confirmar=True,usuario=self.user.username,stdout=StringIO())
            self.account.refresh_from_db();self.assertEqual(self.account.updated_at,count)

    def test_integrado_record_unico_subtotales_y_exclusion_ley276(self):
        from .vacaciones_word import generar_integrado,w,anios_disponibles
        self.account.regimen_laboral='DEC. LEG. 276';self.account.save()
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=3,inicio=date(2024,12,31),fin=date(2025,1,2),periodo='2024',observaciones='SUSTENTO NORMAL')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='32',dias=Decimal('.5'),fecha=date(2025,2,1),observaciones='MEDIA JORNADA')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='88',dias=2,periodo='2023',observaciones='SIN FECHAS')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='09',dias=8,permiso_ley=99,fecha=date(2035,1,1),observaciones='LEY EXCLUIDA')
        self.assertNotIn(2035,anios_disponibles(self.account))
        with patch('django.utils.timezone.now', return_value=datetime(2026, 11, 22, 2, 3, 4, tzinfo=timezone.utc)):
            data=generar_integrado(self.account)
        with ZipFile(BytesIO(data)) as archive:
            root=ET.fromstring(archive.read('word/document.xml'))
            footer=ET.fromstring(archive.read('word/footer1.xml'))
            self.assertEqual(''.join(footer.itertext()), 'Generado el 21/11/2026 a las 21:03:04 (hora de Perú)')
            self.assertIn(b'Target="footer1.xml"', archive.read('word/_rels/document.xml.rels'))
            self.assertIn(b'/word/footer1.xml', archive.read('[Content_Types].xml'))
        for section in root.iter(w('sectPr')):
            self.assertIsNotNone(section.find(w('footerReference')))
        paragraphs=[''.join(p.itertext()) for p in root.findall('./'+w('body')+'/'+w('p'))]
        self.assertEqual(paragraphs.count('RÉCORD DE VACACIONES'),1)
        self.assertIn('INFORME DE VACACIONES 2024',paragraphs)
        self.assertIn('INFORME DE VACACIONES 2025',paragraphs)
        self.assertNotIn('INFORME DE VACACIONES 2023',paragraphs)
        tables=root.findall('./'+w('body')+'/'+w('tbl'))
        allocation=tables[0].findall(w('tr'))
        self.assertEqual(len(tables[0].find(w('tblGrid'))), 8)
        self.assertEqual([''.join(cell.itertext()) for cell in allocation[1].findall(w('tc'))[-3:]],
                         ['Total', 'Usado', 'Saldo'])
        self.assertEqual([''.join(cell.itertext()) for cell in allocation[2].findall(w('tc'))[-3:]],
                         ['40', '5,5', '34,5'])
        values=[[''.join(c.itertext()) for c in row.findall(w('tc'))] for row in tables[1].findall(w('tr'))]
        self.assertIn(['TOTAL DEL AÑO 2024','','1','',''],values)
        self.assertIn(['TOTAL DEL AÑO 2025','','2,5','',''],values)
        self.assertIn(['TOTAL','','5,5','Días',''],values)
        self.assertIn(['SALDO','','34,5','Días',''],values)
        text=ET.tostring(root,encoding='unicode')
        self.assertNotIn('LEY EXCLUIDA',text)
        self.assertNotIn('Ley 276',text)
        self.assertIn('SIN FECHAS',text)
        self.assertEqual(MovimientoVacacion.objects.count(),4)

    def test_lista_muestra_nombre_corregido_aunque_faltara_en_resumen(self):
        self.client.force_login(self.user)
        self.account.nombre='PERSONA CON NOMBRE CORREGIDO'
        self.account.origen={'sin_resumen':True};self.account.habilitada=False;self.account.save()
        response=self.client.get(reverse('vacacion_lista'),{'q':'00000001'})
        self.assertContains(response,'PERSONA CON NOMBRE CORREGIDO')
        self.assertNotContains(response,'Sin nombre en RESUMEN')
        self.assertContains(response,'Inhabilitado')
        self.assertContains(self.client.get(reverse('vacacion_ficha',args=[self.account.pk])),'PERSONA CON NOMBRE CORREGIDO')

    def test_fifo_y_medios_dias(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='32',dias=Decimal('10.5'))
        r=resumen(self.account)
        self.assertEqual(r['por_anio']['2024'],0)
        self.assertEqual(r['por_anio']['2025'],Decimal('29.5'))

    def test_formatos_word_vigentes_anio_y_fines_de_semana(self):
        from .vacaciones_word import generar_docx,movimientos_del_anio,w
        m=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=6,
            inicio=date(2025,12,29),fin=date(2026,1,3),periodo='2024',observaciones='VIGENTE SINTETICO')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=1,estado='ANULADO',
            inicio=date(2026,1,4),fin=date(2026,1,4),observaciones='ANULADO NO EXPORTAR')
        rows,_=movimientos_del_anio(self.account,2026)
        self.assertEqual(rows[0]['inicio'],date(2026,1,1)); self.assertEqual(rows[0]['dias'],3)
        self.assertEqual(movimientos_del_anio(self.account,2025)[0][0]['dias'],3)
        data=generar_docx(self.account,2026,'informe')
        root=ET.fromstring(ZipFile(BytesIO(data)).read('word/document.xml'))
        table=root.find('.//'+w('tbl')); row=table.findall(w('tr'))[1]
        values=[''.join(c.itertext()) for c in row.findall(w('tc'))]
        self.assertEqual(values,['ENERO','','','','1','2','3',''])
        record=ZipFile(BytesIO(generar_docx(self.account,2026,'record'))).read('word/document.xml').decode()
        self.assertNotIn('ANULADO NO EXPORTAR',record)
        self.assertIn('01/01/2026',record); self.assertNotIn('29/12/2025',record)

    def test_formatos_ambos_permisos_y_ajustes_no_repartibles(self):
        self.client.force_login(self.user)
        url=reverse('vacacion_formatos',args=[self.account.pk])
        self.assertContains(self.client.get(url),'Año de las fechas Del/Al')
        response=self.client.get(url,{'generar':'1','anio':'2026','formato':'ambos'})
        self.assertEqual(response.status_code,200)
        self.assertIn('formato',response.context['form'].errors)
        self.assertContains(self.client.get(url,{'generar':'1','anio':'xx','formato':'record'}),'Introduzca')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=2,
            inicio=date(2025,12,29),fin=date(2026,1,3))
        response=self.client.get(url,{'generar':'1','anio':'2026','formato':'informe'})
        self.assertEqual(response['Content-Type'],'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        text=ZipFile(BytesIO(response.content)).read('word/document.xml').decode()
        self.assertNotIn('cruza de año',text)
        self.assertNotIn('OBSERVACIONES',text)
        user=get_user_model().objects.create_user('sin_exportacion',password='sintetica')
        self.client.force_login(user); self.assertEqual(self.client.get(url).status_code,403)

    def test_informe_incluye_sabados_domingos_y_no_duplica_fecha(self):
        from .vacaciones_word import generar_docx,w
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=11,
            inicio=date(2026,1,9),fin=date(2026,1,19))
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='32',dias=Decimal('.5'),
            inicio=date(2026,1,9),fin=date(2026,1,9))
        root=ET.fromstring(ZipFile(BytesIO(generar_docx(self.account,2026,'informe'))).read('word/document.xml'))
        rows=root.find('.//'+w('tbl')).findall(w('tr'))[1:]
        values=[[''.join(c.itertext()) for c in r.findall(w('tc'))] for r in rows]
        self.assertEqual(values[0][-2:],['10','11'])
        self.assertEqual(values[1][-2:],['17','18'])
        self.assertEqual(sum(sum(v.startswith('9 (') for v in row[1:8]) for row in values if not row[0].startswith('TOTAL')),1)

    def test_detalle_cronologico_por_fecha_con_sin_fecha_al_final(self):
        newer=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=1,
            fecha=date(2026,10,1),inicio=date(2026,1,1))
        older=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=1,
            fecha=date(2025,10,1),inicio=date(2026,11,1))
        unknown=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=0)
        self.assertEqual([r['pk'] for r in resumen(self.account)['filas']],[older.pk,newer.pk,unknown.pk])

    def test_pendientes_anuales_y_detalle_de_descuentos(self):
        self.client.force_login(self.user)
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=Decimal('10.5'))
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=5,estado='CANCELADO')
        listing=self.client.get(reverse('vacacion_lista'))
        self.assertContains(listing,'Pendiente 2024')
        self.assertContains(listing,'Pendiente 2025')
        self.assertContains(listing,reverse('vacacion_ficha',args=[self.account.pk]))
        self.assertContains(listing,'role="switch"')
        response=self.client.get(reverse('vacacion_ficha',args=[self.account.pk]))
        r=response.context['r']
        self.assertEqual(r['por_anio']['2024'],0)
        self.assertEqual(r['por_anio']['2025'],Decimal('29.5'))
        self.assertEqual(r['usado'],Decimal('10.5'))
        self.assertEqual(len(r['filas']),2)
        self.assertContains(response,'Movimientos que sustentan el consumo')
        self.assertContains(response,'Total descontado:')
        self.assertContains(response,'Cancelado')

    def test_cancelado_no_consume_y_se_conserva(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=20,estado='CANCELADO')
        self.assertEqual(resumen(self.account)['usado'],0)
        self.assertEqual(len(resumen(self.account)['filas']),1)

    def test_codigo_88_no_se_interpreta(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='88',dias=54,pendiente_revision=True)
        r=resumen(self.account)
        self.assertEqual(r['usado'],54)
        self.assertTrue(r['incidencias'])

    def test_exportacion_dos_hojas_formulas_cache_y_texto_seguro(self):
        self.account.nombre='=FORMULA NO EJECUTABLE'
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='32',dias=Decimal('0.5'),inicio=date(2026,1,2))
        data=exportar_control([resumen(self.account)])
        wb=load_workbook(BytesIO(data),data_only=False)
        self.assertEqual(wb.sheetnames,['Resumen','detalle'])
        self.assertEqual(wb['Resumen']['A5'].value,'00000001')
        self.assertEqual(wb['Resumen']['E5'].data_type,'s')
        self.assertIn('I2:P2',str(wb['Resumen'].merged_cells))
        cached=load_workbook(BytesIO(data),data_only=True)
        self.assertEqual(cached['Resumen']['R5'].value,.5)
        self.assertEqual(cached['Resumen']['S5'].value,39.5)
        self.assertEqual(cached['detalle']['E3'].value.date(),date(2026,1,2))

    def test_xml_compatible_y_hojas_visibles_desde_a1(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=1)
        data=exportar_control([resumen(self.account)])
        ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        with ZipFile(BytesIO(data)) as archive:
            for path in ['xl/worksheets/sheet1.xml','xl/worksheets/sheet3.xml']:
                payload=archive.read(path)
                declared={prefix for _,(prefix,uri) in ET.iterparse(BytesIO(payload),events=['start-ns'])}
                root=ET.fromstring(payload)
                for node in root.iter():
                    for key,value in node.attrib.items():
                        if key.endswith('}Ignorable'):
                            self.assertTrue(set(value.split()) <= declared)
                view=root.find(ns+'sheetViews/'+ns+'sheetView')
                self.assertEqual(view.get('topLeftCell'),'A1')
                self.assertEqual(view.find(ns+'selection').get('activeCell'),'A1')
        self.assertEqual(load_workbook(BytesIO(data),data_only=True)['detalle']['G3'].value,1)

    def test_nombre_archivo_individual_con_nombre_trabajador(self):
        self.client.force_login(self.user)
        response=self.client.get(reverse('vacacion_exportar_individual',args=[self.account.pk]))
        self.assertEqual(response['Content-Disposition'],'attachment; filename="PERSONA FICTICIA.xlsx"')
        self.account.nombre='PERSONA ÁLVAREZ / PRUEBA'
        self.account.save()
        response=self.client.get(reverse('vacacion_exportar_individual',args=[self.account.pk]))
        self.assertIn("filename*=utf-8''PERSONA%20%C3%81LVAREZ%20PRUEBA.xlsx",response['Content-Disposition'])

    def test_permisos(self):
        user=get_user_model().objects.create_user('lector',password='ficticia')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('vacacion_lista')).status_code,403)
        self.assertEqual(self.client.get(reverse('vacacion_exportar')).status_code,403)

    def test_exportacion_permite_datos_originales_sin_revision(self):
        self.client.force_login(self.user)
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=50)
        response=self.client.get(reverse('vacacion_exportar'))
        self.assertEqual(response.status_code,200)
        wb=load_workbook(BytesIO(response.content),data_only=True)
        self.assertEqual(wb['Resumen']['S5'].value,-10)

    def test_eliminar_no_borra_historial_y_no_se_exporta(self):
        self.client.force_login(self.user)
        m=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=3)
        url=reverse('vacacion_eliminar',args=[self.account.pk])
        self.assertEqual(self.client.get(url).status_code,200)
        self.account.refresh_from_db(); self.assertFalse(self.account.eliminada)
        response=self.client.post(url,{'version':self.account.updated_at.isoformat()})
        self.assertEqual(response.status_code,302)
        self.account.refresh_from_db(); self.assertTrue(self.account.eliminada)
        self.assertTrue(MovimientoVacacion.objects.filter(pk=m.pk).exists())
        self.assertNotContains(self.client.get(reverse('vacacion_lista')),'PERSONA FICTICIA')
        self.assertEqual(self.client.get(reverse('vacacion_exportar_individual',args=[self.account.pk])).status_code,404)

    def test_exportar_busqueda_incluye_todos_los_resultados_no_solo_pagina(self):
        self.client.force_login(self.user)
        for i in range(26):
            CuentaVacacion.objects.create(dni=f'{i+100:08}',nombre=f'OTRA PERSONA {i}')
        response=self.client.get(reverse('vacacion_exportar'),{'q':'OTRA PERSONA'})
        wb=load_workbook(BytesIO(response.content),data_only=True)
        self.assertEqual(wb['Resumen'].max_row,30)

    def test_lista_sin_mensajes_de_revision_y_con_acciones(self):
        self.client.force_login(self.user)
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='88',dias=2,pendiente_revision=True)
        response=self.client.get(reverse('vacacion_lista'))
        self.assertNotContains(response,'requieren revisión')
        self.assertContains(response,reverse('vacacion_editar',args=[self.account.pk]))
        self.assertContains(response,reverse('vacacion_eliminar',args=[self.account.pk]))
        self.assertContains(response,'bootstrap-table-1.27.3.min.js')

    def test_formulario_permite_crear_y_agravar_saldo_negativo_con_auditoria(self):
        self.client.force_login(self.user)
        response=self.client.post(reverse('vacacion_movimiento_nuevo',args=[self.account.pk]),
            {'cuenta':self.account.pk,'periodo':'2026','inicio':'2026-11-19','fin':'2026-11-19','dias':'41',
             'codigo':'09','permiso_ley':'3','estado':'ANULADO','motivo':'No corresponde al alta'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(resumen(self.account)['pendiente'],Decimal('-1'))
        m=MovimientoVacacion.objects.get()
        self.assertEqual((m.codigo, m.estado, m.permiso_ley, m.motivo), ('05', 'VIGENTE', Decimal(0), ''))
        response=self.client.post(reverse('vacacion_movimiento_editar',args=[self.account.pk,m.pk]),
            {'cuenta':self.account.pk,'codigo':'05','dias':'45.5','permiso_ley':'0','estado':'VIGENTE',
             'motivo':'Exceso confirmado','version':m.updated_at.isoformat()})
        self.assertEqual(response.status_code,302)
        self.assertEqual(resumen(self.account)['pendiente'],Decimal('-5.5'))
        from .models import HistorialCambio
        self.assertEqual(HistorialCambio.objects.filter(entidad='movimientovacacion').count(),2)

    def test_alta_calcula_dias_inclusivos_y_valida_periodo_y_rango(self):
        self.client.force_login(self.user)
        url = reverse('vacacion_movimiento_nuevo', args=[self.account.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Fecha del CUD del documento')
        self.assertEqual(response.context['form']['cud'].value(), '')
        self.assertNotContains(response, 'DatabaseDefault')
        self.assertEqual(list(response.context['form'].fields),
                         ['cuenta', 'periodo', 'fecha', 'cud', 'inicio', 'fin', 'dias', 'observaciones', 'token_alta'])
        data = {'cuenta': self.account.pk, 'periodo': '2026',
                'inicio': '2026-11-19', 'fin': '2026-11-19', 'dias': '', 'cud': '00123'}
        self.assertEqual(self.client.post(url, {**data, 'fin': '2026-11-18'}).status_code, 200)
        self.assertEqual(self.client.post(url, {**data, 'periodo': '2027'}).status_code, 200)
        self.assertFalse(MovimientoVacacion.objects.exists())
        self.assertEqual(self.client.post(url, data).status_code, 302)
        movimiento = MovimientoVacacion.objects.get()
        self.assertEqual(movimiento.dias, Decimal(1))
        self.assertEqual(movimiento.cud, '00123')
        self.assertContains(self.client.get(reverse('vacacion_ficha', args=[self.account.pk])), 'CUD 00123')
        self.assertEqual(self.client.post(url, {**data, 'dias': '0.5', 'cud': ''}).status_code, 302)
        self.assertTrue(MovimientoVacacion.objects.filter(dias=Decimal('0.5'), cud='').exists())

    def test_imprimir_memorandum_guarda_una_vez_y_descarga_word_editable(self):
        self.client.force_login(self.user)
        self.account.nombre = 'PERSONA & FICTICIA'
        self.account.save(update_fields=['nombre'])
        url = reverse('vacacion_movimiento_nuevo', args=[self.account.pk])
        alta = self.client.get(url)
        self.assertContains(alta, 'Imprimir Memorándum')
        datos = {
            'cuenta': self.account.pk, 'periodo': '2026', 'cud': '03456',
            'inicio': '2026-12-10', 'fin': '2026-12-10', 'dias': '0.5',
            'token_alta': str(alta.context['form']['token_alta'].value()),
            'imprimir_memorandum': '1',
        }
        invalida = self.client.post(url, {**datos, 'fin': '2026-12-09'})
        self.assertContains(invalida, 'La fecha final es anterior al inicio.')
        self.assertFalse(MovimientoVacacion.objects.exists())

        with patch('django.utils.timezone.now', return_value=datetime(2026, 11, 23, 2, tzinfo=timezone.utc)):
            for _ in range(2):
                response = self.client.post(url, datos)
                self.assertEqual(response.status_code, 200)
                self.assertIn('.docx', response['Content-Disposition'])
                self.assertEqual(response['Content-Type'],
                                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                with ZipFile(BytesIO(response.content)) as archivo:
                    doc = ET.fromstring(archivo.read('word/document.xml'))
                from .vacaciones_word import w
                texto = ''.join(n.text or '' for n in doc.iter(w('t')))
                self.assertEqual(texto.count('PERSONA & FICTICIA'), 2)
                self.assertEqual(texto.count('Calana, 22 de noviembre del 2026'), 2)
                self.assertEqual(texto.count('10/12/2026 al 10/12/2026 (0,5 días)'), 2)
                self.assertEqual(texto.count('CUD. N° 20260031003456'), 2)
                self.assertEqual(texto.count('ABOG. CARMEN LIDIA TOALA ANDIA'), 2)
                self.assertNotIn('{{', texto)
        self.assertEqual(MovimientoVacacion.objects.count(), 1)
        self.assertEqual(MovimientoVacacion.objects.get().dias, Decimal('0.5'))

    def test_saldo_y_observaciones_en_ambos_formatos_e_integrado(self):
        from .vacaciones_word import generar_docx,generar_integrado,anios_disponibles
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=45,
            inicio=date(2025,1,1),fin=date(2025,2,14),periodo='2024',observaciones='FUT: SOLICITO PERMISO A CUENTA DE VACACIONES EL DIA DE 19')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='32',dias=Decimal('.5'),
            inicio=date(2025,1,1),fin=date(2025,1,1),periodo='2025')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='88',dias=2,periodo='2023')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=2,
            inicio=date(2026,12,31),fin=date(2028,1,1),periodo='2026')
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=90,estado='ANULADO',periodo='2020')
        self.assertEqual(anios_disponibles(self.account),[2023,2024,2025,2026,2027,2028])
        for kind in ('record','informe','integrado'):
            data=generar_integrado(self.account) if kind=='integrado' else generar_docx(self.account,2025,kind)
            text=ZipFile(BytesIO(data)).read('word/document.xml').decode()
            self.assertIn('SALDO NEGATIVO',text)
            self.assertIn('Exceso: 9,5 días',text)
            self.assertNotIn('OBSERVACIONES',text)
            self.assertNotIn('observaciones',text.casefold())
            if kind=='informe':
                self.assertNotIn('FUT: SOLICITO PERMISO A CUENTA DE VACACIONES EL DIA DE 19',text)
                self.assertNotIn('SUSTENTO / OBSERVACIÓN',text)
            else:
                self.assertIn('FUT: SOLICITO PERMISO A CUENTA DE VACACIONES EL DIA DE 19',text)
                self.assertIn('SUSTENTO / OBSERVACIÓN',text)
            self.assertNotIn('Posible superposición',text)
            self.assertNotIn('sin Del/Al válidos',text)
            if kind=='integrado':
                self.assertIn('RÉCORD DE VACACIONES',text)
                self.assertNotIn('RÉCORD DE VACACIONES 2027',text)
                self.assertNotIn('INFORME DE VACACIONES 2028',text)
                self.assertNotIn('OBSERVACIONES GENERALES',text)
        self.client.force_login(self.user)
        url=reverse('vacacion_formatos',args=[self.account.pk])
        response=self.client.get(url,{'generar':'1','formato':'integrado'})
        self.assertEqual(response.status_code,200)
        self.assertIn('todos_los_anios.docx',response['Content-Disposition'])
        self.assertContains(self.client.get(url,{'generar':'1','formato':'record'}),'Indique el año')

    def test_integrado_sin_asignaciones_y_sin_movimientos(self):
        from .vacaciones_word import generar_integrado
        self.account.asignaciones={};self.account.save()
        for with_movement in (False,True):
            if with_movement:
                MovimientoVacacion.objects.create(cuenta=self.account,codigo='88',dias=2,periodo='2023')
            data=generar_integrado(self.account)
            text=ZipFile(BytesIO(data)).read('word/document.xml').decode()
            self.assertIn('Programado',text)
            if with_movement:
                self.assertIn('TOTAL DEL AÑO 2023',text)
                self.assertIn('Exceso: 2 días',text)

    def test_formulario_cancela_y_audita(self):
        self.client.force_login(self.user)
        m=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=3)
        response=self.client.post(reverse('vacacion_movimiento_editar',args=[self.account.pk,m.pk]),
            {'cuenta':self.account.pk,'codigo':'05','dias':'3','permiso_ley':'0','estado':'CANCELADO','motivo':'Cancelado a petición',
             'version':m.updated_at.isoformat()})
        self.assertEqual(response.status_code,302)
        m.refresh_from_db()
        self.assertEqual(m.estado,'CANCELADO')
        self.assertEqual(resumen(self.account)['usado'],0)

    def test_justificaciones_actualizan_solo_su_consumo_sin_alterar_excel(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=3)
        op=TipoOperacion.objects.create(nombre='VACACION FICTICIA',codigo_externo='05',grupo_especial='VACACIONES',requiere_fecha_final=True)
        obj=Justificacion(trabajador=self.worker,tipo_operacion=op,
            tipo_documento=TipoDocumento.objects.first(),periodo=PeriodoAsistencia.objects.first(),
            created_by=self.user,updated_by=self.user,
            fecha_movimiento=date(2026,1,1),fecha_final=date(2026,2,15))
        obj.full_clean()
        obj.save()
        self.assertEqual(resumen(self.account)['usado'],49)
        obj.fecha_final=date(2026,3,15); obj.save()
        self.assertEqual(resumen(self.account)['usado'],77)
        obj.anulada=True; obj.save()
        self.assertEqual(resumen(self.account)['usado'],3)
        self.assertEqual(len(resumen(self.account)['filas']),2)

    def test_edicion_obsoleta_rechazada(self):
        self.client.force_login(self.user)
        m=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=3)
        response=self.client.post(reverse('vacacion_movimiento_editar',args=[self.account.pk,m.pk]),
            {'cuenta':self.account.pk,'codigo':'05','dias':'2','permiso_ley':'0','estado':'VIGENTE','motivo':'Prueba','version':'obsoleta'})
        self.assertContains(response,'La ficha cambió')
        m.refresh_from_db(); self.assertEqual(m.dias,3)

    def test_carga_inicial_previa_idempotencia_e_independencia(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='32',dias=Decimal('0.5'))
        content=exportar_control([resumen(self.account)])
        MovimientoVacacion.objects.all().delete()
        self.account.delete()
        with TemporaryDirectory() as directory:
            path=Path(directory)/'ficticio.xlsx'
            path.write_bytes(content)
            call_command('importar_control_vacaciones',str(path),stdout=StringIO())
            self.assertEqual(CuentaVacacion.objects.count(),0)
            for _ in range(2):
                call_command('importar_control_vacaciones',str(path),confirmar=True,
                             usuario=self.user.username,stdout=StringIO())
            self.assertEqual(CuentaVacacion.objects.count(),1)
            self.assertEqual(MovimientoVacacion.objects.count(),1)
            account=CuentaVacacion.objects.get()
            self.assertIsNone(account.trabajador_id)
            self.assertEqual(account.dni,'00000001')
            self.assertEqual(resumen(account)['usado'],Decimal('0.5'))
            self.assertEqual(Justificacion.objects.count(),0)

    def test_carga_rechaza_dni_duplicado_sin_insertar(self):
        r=resumen(self.account)
        content=exportar_control([r,r])
        self.account.delete()
        with TemporaryDirectory() as directory:
            path=Path(directory)/'duplicado.xlsx'; path.write_bytes(content)
            with self.assertRaises(CommandError):
                call_command('importar_control_vacaciones',str(path),confirmar=True,
                             usuario=self.user.username,stdout=StringIO())
        self.assertEqual(CuentaVacacion.objects.count(),0)

    def test_permiso_nuevo_conserva_personalizaciones(self):
        group=Group.objects.create(name='Consulta')
        custom=Permission.objects.get(codename='change_trabajador')
        group.permissions.add(custom)
        call_command('preparar_roles',solo_vacaciones=True,stdout=StringIO())
        self.assertTrue(group.permissions.filter(pk=custom.pk).exists())
        self.assertTrue(group.permissions.filter(codename='view_cuentavacacion').exists())
        self.assertFalse(group.permissions.filter(codename='change_cuentavacacion').exists())

    def test_no_permite_mover_consumos_a_ficha_eliminada(self):
        from .vacaciones_forms import MovimientoForm
        deleted=CuentaVacacion.objects.create(nombre='FICHA RETIRADA',dni='00000002',eliminada=True)
        form=MovimientoForm({'cuenta':deleted.pk,'codigo':'05','dias':'1','permiso_ley':'0',
                             'estado':'VIGENTE','motivo':'Prueba'})
        self.assertFalse(form.is_valid())
        self.assertIn('cuenta',form.errors)
