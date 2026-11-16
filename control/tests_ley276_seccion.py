from datetime import date
from decimal import Decimal
from io import BytesIO
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase,Client
from django.urls import reverse
from openpyxl import load_workbook
from .models import CuentaVacacion,MovimientoVacacion,HistorialCambio


class Ley276SeccionTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('leyadmin','','prueba')
        self.client.force_login(self.admin)
        self.c=CuentaVacacion.objects.create(nombre='PERSONA LEY',dni='00000001',regimen_laboral='DEC.LEG.276',asignaciones={'2025':'30','2026':'30'})
        self.other=CuentaVacacion.objects.create(nombre='PERSONA CAS',dni='00000002',regimen_laboral='CAS',asignaciones={'2025':'30'})
        self.disabled=CuentaVacacion.objects.create(nombre='LEY INACTIVA',dni='00000003',regimen_laboral='DEC. LEG. 276',habilitada=False,asignaciones={'2025':'30'})
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='09',dias=0,permiso_ley=Decimal('1.5'),fecha=date(2026,1,1),observaciones='SUSTENTO LEY')
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='09',dias=0,permiso_ley=1,estado='ANULADO',observaciones='ANULADO LEY')
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='05',dias=7,observaciones='SOLO VACACIONES')

    def test_lista_busqueda_detalle_y_regimen(self):
        response=self.client.get(reverse('ley276_lista'))
        self.assertContains(response,'PERSONA LEY');self.assertContains(response,'LEY INACTIVA')
        self.assertNotContains(response,'PERSONA CAS')
        self.assertEqual(len(self.client.get(reverse('ley276_lista'),{'q':'00000001'}).context['filas']),1)
        response=self.client.get(reverse('ley276_ficha',args=[self.c.pk]))
        self.assertContains(response,'SUSTENTO LEY');self.assertContains(response,'ANULADO LEY')
        self.assertNotContains(response,'SOLO VACACIONES')
        self.assertEqual(response.context['r']['ley_276']['usado'],Decimal('1.5'))
        self.assertEqual(self.client.get(reverse('ley276_ficha',args=[self.other.pk])).status_code,404)

    def test_excel_general_individual_filtrado_e_inactivos(self):
        for route,args in [('ley276_exportar',[]),('ley276_exportar_individual',[self.c.pk])]:
            response=self.client.get(reverse(route,args=args))
            book=load_workbook(BytesIO(response.content),data_only=True)
            self.assertEqual(book.sheetnames,['Resumen','detalle'])
            self.assertEqual([book['Resumen'].cell(4,i).value for i in range(1,6)],['00000001','PERSONA LEY',6,1.5,4.5])
            self.assertEqual(book['detalle']['H4'].value,1.5)
            self.assertEqual(book['detalle']['H5'].value,0)
            self.assertEqual(book['detalle']['H6'].value,1.5)
            self.assertEqual(book['detalle']['D4'].value.date(),date(2026,1,1))
        response=self.client.get(reverse('ley276_exportar'),{'q':'sin coincidencias'})
        self.assertEqual(load_workbook(BytesIO(response.content))['Resumen']['A4'].value,'TOTAL')
        for route in ['ley276_exportar_individual','vacacion_exportar_individual']:
            self.assertEqual(self.client.get(reverse(route,args=[self.disabled.pk])).status_code,404)
        book=load_workbook(BytesIO(self.client.get(reverse('vacacion_exportar')).content),data_only=True)
        self.assertEqual(book['Resumen'].max_row,6)
        self.assertNotIn('00000003',[book['Resumen'].cell(r,1).value for r in range(5,7)])

    def test_switch_permiso_csrf_version_auditoria_y_reactivacion(self):
        url=reverse('vacacion_habilitacion',args=[self.c.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url,{'version':'anterior','habilitada':'0'}).status_code,409)
        c=Client(enforce_csrf_checks=True);c.force_login(self.admin)
        self.assertEqual(c.post(url,{}).status_code,403)
        response=self.client.post(url,{'version':self.c.updated_at.isoformat(),'habilitada':'0'})
        self.assertEqual(response.status_code,302);self.c.refresh_from_db();self.assertFalse(self.c.habilitada)
        self.assertEqual(MovimientoVacacion.objects.filter(cuenta=self.c).count(),3)
        self.assertTrue(HistorialCambio.objects.filter(objeto_id=self.c.pk,accion='inhabilitar').exists())
        self.assertEqual(self.client.get(reverse('vacacion_exportar_individual',args=[self.c.pk])).status_code,404)
        self.client.post(url,{'version':self.c.updated_at.isoformat(),'habilitada':'1'})
        self.c.refresh_from_db();self.assertTrue(self.c.habilitada)
        self.assertEqual(self.client.get(reverse('vacacion_exportar_individual',args=[self.c.pk])).status_code,200)
        self.assertTrue(HistorialCambio.objects.filter(objeto_id=self.c.pk,accion='habilitar').exists())

    def test_permisos(self):
        user=get_user_model().objects.create_user('consulta')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('ley276_lista')).status_code,403)
        user.user_permissions.add(Permission.objects.get(codename='view_cuentavacacion'))
        self.assertEqual(self.client.get(reverse('ley276_lista')).status_code,200)
        self.assertEqual(self.client.get(reverse('ley276_exportar')).status_code,403)
        self.assertEqual(self.client.post(reverse('vacacion_habilitacion',args=[self.c.pk]),{}).status_code,403)
        html=self.client.get(reverse('vacacion_lista')).content.decode()
        self.assertNotIn('role="switch"',html)

    def test_nombre_navegable_y_switch_sin_ojo(self):
        response=self.client.get(reverse('vacacion_lista'))
        self.assertContains(response,'role="switch"');self.assertContains(response,'aria-checked="true"')
        self.assertContains(response,'aria-checked="false"')
        self.assertNotContains(response,'Ver detalle de PERSONA LEY')
        self.assertContains(response,reverse('vacacion_ficha',args=[self.c.pk]))
