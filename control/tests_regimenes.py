from datetime import date
from decimal import Decimal
from io import BytesIO,StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from xml.etree import ElementTree as E
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook,load_workbook
from .models import CuentaVacacion,Trabajador,MovimientoVacacion,HistorialCambio
from .vacaciones import resumen
from .vacaciones_word import distribucion_mensual,movimientos_del_anio,generar_docx,w
from .exportacion_regimen import exportar_vacaciones_agrupadas


class RegimenesTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser('regimen','','clave-ficticia')
        self.worker=Trabajador.objects.create(apellidos_nombres='PERSONA SINTETICA',dni='00000001')
        self.account=CuentaVacacion.objects.create(nombre='PERSONA SINTETICA',dni='00000001',asignaciones={'2026':'2'})
    def test_importacion_solo_regimen_idempotente_y_sin_tocar_saldos(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=4)
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'regimenes.xlsx'
            book=Workbook();sheet=book.active;sheet.title='Resumen'
            sheet.append(['Dni','reg. Labor','Nombre']);sheet.append(['00000001','dec.leg.276','PERSONA SINTETICA'])
            sheet.append(['00000002','NO EXISTE','OTRA PERSONA']);book.save(path)
            call_command('importar_regimenes',str(path),stdout=StringIO())
            self.account.refresh_from_db();self.assertEqual(self.account.regimen_laboral,'')
            for _ in range(2):call_command('importar_regimenes',str(path),confirmar=True,usuario=self.user.username,stdout=StringIO())
        self.account.refresh_from_db();self.worker.refresh_from_db()
        self.assertEqual(self.account.regimen_laboral,'DEC. LEG. 276')
        self.assertEqual(self.worker.regimen_laboral,'DEC. LEG. 276')
        self.assertEqual(resumen(self.account)['pendiente'],-2)
        self.assertEqual(HistorialCambio.objects.filter(accion='importar_regimen').count(),2)
    def test_agrupacion_imprimible_filtros_y_totales_cacheados(self):
        self.account.regimen_laboral='CAS';self.account.save()
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',dias=4,inicio=date(2026,1,1),fin=date(2026,1,4),observaciones='=NO_EJECUTAR')
        other=CuentaVacacion.objects.create(dni='00000002',nombre='OTRA PERSONA',regimen_laboral='LEY 29944')
        data=exportar_vacaciones_agrupadas([resumen(self.account),resumen(other)])
        values=load_workbook(BytesIO(data),data_only=True);formula=load_workbook(BytesIO(data),data_only=False)
        self.assertEqual(values.sheetnames,['CAS','Detalle CAS','LEY 29944','Detalle LEY 29944'])
        self.assertEqual(values['CAS']['F4'].value,-2)
        self.assertEqual(values['CAS']['F5'].value,-2)
        self.assertEqual(formula['CAS']['F5'].value,'=SUM(F4:F4)')
        self.assertEqual(formula['Detalle CAS']['H4'].data_type,'s')
        self.assertEqual(values['Detalle CAS']['E4'].value.date(),date(2026,1,1))
        self.assertEqual(values['CAS']['A4'].value,'00000001')
        self.assertEqual(values['CAS']['A4'].number_format,'@')
        for s in values:
            self.assertEqual(s.page_setup.orientation,'landscape')
            self.assertEqual(s.print_title_rows,'$1:$3')
            self.assertEqual(s.page_setup.fitToWidth,1)
        self.client.force_login(self.user)
        r=self.client.get(reverse('vacacion_lista'),{'regimen_laboral':'CAS'})
        self.assertEqual(r.context['pagina'].paginator.count,1)
        self.assertContains(r,'Excel por régimen laboral')
        r=self.client.get(reverse('vacacion_exportar'),{'regimen_laboral':'CAS','agrupar_regimen':'1'})
        self.assertEqual(load_workbook(BytesIO(r.content)).sheetnames,['CAS','Detalle CAS'])
    def test_totales_mensuales_horizontales_verticales_y_media_jornada(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',inicio=date(2026,1,30),fin=date(2026,2,2),dias=4)
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='32',inicio=date(2026,2,3),fin=date(2026,2,3),dias=Decimal('.5'))
        rows,_=movimientos_del_anio(self.account,2026);d=distribucion_mensual(rows)
        self.assertEqual(sum(d['meses'][0]),2);self.assertEqual(sum(d['meses'][1]),Decimal('2.5'))
        self.assertEqual(d['total'],Decimal('4.5'))
        root=E.fromstring(ZipFile(BytesIO(generar_docx(self.account,2026,'informe'))).read('word/document.xml'))
        rows=root.find('.//'+w('tbl')).findall(w('tr'))
        values=[[''.join(c.itertext()) for c in row.findall(w('tc'))] for row in rows]
        totals=[r for r in values if r[0].startswith('TOTAL')]
        self.assertEqual(totals[-1][-1],'4,5')
        for row in totals:self.assertEqual(sum(Decimal(v.replace(',','.')) for v in row[1:8]),Decimal(row[8].replace(',','.')))
    def test_cantidad_incongruente_no_se_reparte_y_se_explica(self):
        MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',inicio=date(2026,3,1),fin=date(2026,3,5),dias=3)
        rows,_=movimientos_del_anio(self.account,2026);d=distribucion_mensual(rows)
        self.assertEqual(d['no_distribuido'],3);self.assertEqual(d['total'],0)
        text=ZipFile(BytesIO(generar_docx(self.account,2026,'record'))).read('word/document.xml').decode()
        self.assertIn('sin distribución mensual fiable',text)
        self.assertIn('FECHAS',text);self.assertIn('REGISTROS',text)
    def test_regimen_editado_en_ficha_se_refleja_en_trabajador(self):
        self.client.force_login(self.user)
        r=self.client.post(reverse('vacacion_editar',args=[self.account.pk]),dict(
            dni=self.account.dni,nombre=self.account.nombre,regimen_laboral='cas',habilitada='on',
            motivo='Clasificación',version=self.account.updated_at.isoformat(),anio_2026='2'))
        self.assertEqual(r.status_code,302)
        self.worker.refresh_from_db();self.assertEqual(self.worker.regimen_laboral,'CAS')

    def test_consultas_filtra_y_exporta_por_regimen_sin_perder_fechas(self):
        from .models import Justificacion,TipoOperacion,TipoDocumento,PeriodoAsistencia
        self.worker.regimen_laboral='CAS';self.worker.save()
        other=Trabajador.objects.create(apellidos_nombres='OTRA PERSONA',dni='00000002',regimen_laboral='LEY 29944')
        op=TipoOperacion.objects.create(nombre='Operación de prueba',requiere_fecha_final=False)
        for worker in (self.worker,other):
            Justificacion.objects.create(trabajador=worker,tipo_operacion=op,tipo_documento=TipoDocumento.objects.first(),
                periodo=PeriodoAsistencia.objects.first(),fecha_movimiento=date(2026,11,1),fecha_final=date(2026,11,1),created_by=self.user,updated_by=self.user)
        self.client.force_login(self.user)
        r=self.client.get(reverse('consultas'),{'regimen_laboral':'CAS'})
        self.assertEqual(r.context['pagina'].paginator.count,1)
        r=self.client.get(reverse('exportar_consultas'),{'regimen_laboral':'CAS','agrupar_regimen':'1'})
        book=load_workbook(BytesIO(r.content),data_only=True)
        self.assertEqual(book.sheetnames,['CAS'])
        self.assertEqual(book['CAS']['C4'].value,'00000001')
        self.assertEqual(book['CAS']['F4'].value.date(),date(2026,11,1))
