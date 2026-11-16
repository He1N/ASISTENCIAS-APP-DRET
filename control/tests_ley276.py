from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import CuentaVacacion,MovimientoVacacion,HistorialCambio
from .vacaciones import resumen


class Ley276Tests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser('ley','','clave-prueba')
        self.client.force_login(self.user)
        self.c=CuentaVacacion.objects.create(nombre='PRUEBA',dni='00000001',regimen_laboral='DEC.LEG.276',asignaciones={'2023':'30','2024':'30','2025':'30','2026':None})

    def test_saldos_separados_cantidades_y_estados(self):
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='05',dias=30)
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='09',dias=0,permiso_ley=2)
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='09',dias=1)
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='09',dias=None)
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='09',dias=0,permiso_ley=7,estado='ANULADO')
        r=resumen(self.c)
        self.assertEqual(r['usado'],30);self.assertEqual(r['pendiente'],60)
        self.assertEqual(r['ley_276']['programado'],9)
        self.assertEqual(r['ley_276']['pendiente'],6)
        self.assertNotContains(self.client.get(reverse('vacacion_ficha',args=[self.c.pk])),'<dt>Ley 276</dt>',html=True)
        self.assertContains(self.client.get(reverse('ley276_ficha',args=[self.c.pk])),'Días totales asignados')
        self.c.regimen_laboral='CAS';self.c.save()
        self.assertIsNone(resumen(self.c)['ley_276'])

    def test_total_automatico_manual_cero_y_retorno(self):
        from .vacaciones_forms import CuentaForm
        MovimientoVacacion.objects.create(cuenta=self.c,codigo='09',dias=0,permiso_ley=2)
        self.assertEqual(CuentaForm(instance=self.c).initial['asignacion_ley276'],9)
        self.assertTrue(CuentaForm(instance=self.c).initial['ley276_automatico'])
        url=reverse('vacacion_editar',args=[self.c.pk])
        def payload(**extra):
            self.c.refresh_from_db()
            return dict(dni=self.c.dni,nombre=self.c.nombre,regimen_laboral=self.c.regimen_laboral,
                        anio_2023='30',anio_2024='30',anio_2025='30',motivo='Ajuste de derechos Ley 276',
                        version=self.c.updated_at.isoformat(),**extra)
        for amount,expected in [('5.5',Decimal('3.5')),('0',Decimal('-2'))]:
            response=self.client.post(url,payload(asignacion_ley276=amount))
            self.assertEqual(response.status_code,302)
            self.c.refresh_from_db()
            self.assertEqual(self.c.asignacion_ley276,Decimal(amount))
            r=resumen(self.c)
            self.assertEqual(r['ley_276']['pendiente'],expected)
            self.assertEqual(r['programado'],90);self.assertEqual(r['usado'],0)
        self.assertEqual(self.client.get(reverse('ley276_ficha',args=[self.c.pk])).context['r']['ley_276']['pendiente'],-2)
        self.assertEqual(HistorialCambio.objects.filter(objeto_id=self.c.pk,accion='editar').count(),2)
        response=self.client.post(url,payload(ley276_automatico='on',asignacion_ley276='0'))
        self.assertEqual(response.status_code,302);self.c.refresh_from_db()
        self.assertIsNone(self.c.asignacion_ley276)
        self.c.asignaciones['2026']='30';self.c.save()
        self.assertEqual(resumen(self.c)['ley_276']['programado'],12)

    def test_total_manual_no_admite_negativo_ni_vacio(self):
        from .vacaciones_forms import CuentaForm
        data=dict(dni=self.c.dni,nombre=self.c.nombre,regimen_laboral=self.c.regimen_laboral,motivo='Prueba')
        for value in ('-1',''):
            form=CuentaForm(dict(data,asignacion_ley276=value),instance=self.c)
            self.assertFalse(form.is_valid());self.assertIn('asignacion_ley276',form.errors)
        form=CuentaForm(dict(data,ley276_automatico='on',asignacion_ley276=''),instance=self.c)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertIsNone(form.cleaned_data['asignacion_ley276'])

    def test_override_no_cambia_formatos_ni_otro_regimen(self):
        from .vacaciones_word import generar_integrado
        self.c.asignacion_ley276=Decimal('99.5');self.c.save()
        before=generar_integrado(self.c)
        self.c.asignacion_ley276=None;self.c.save()
        from zipfile import ZipFile
        from io import BytesIO
        self.assertEqual(ZipFile(BytesIO(before)).read('word/document.xml'),ZipFile(BytesIO(generar_integrado(self.c))).read('word/document.xml'))
        self.c.regimen_laboral='CAS';self.c.asignacion_ley276=99;self.c.save()
        self.assertIsNone(resumen(self.c)['ley_276'])

    def test_borrado_permanente_confirmacion_auditoria_y_version(self):
        m=MovimientoVacacion.objects.create(cuenta=self.c,codigo='09',dias=0,permiso_ley=1)
        pk=m.pk;url=reverse('vacacion_movimiento_eliminar',args=[self.c.pk,pk])
        self.assertContains(self.client.get(url),'Eliminar permanentemente')
        data=dict(version=m.updated_at.isoformat(),accion='permanente',motivo='Duplicado')
        self.client.post(url,data);self.assertTrue(MovimientoVacacion.objects.filter(pk=pk).exists())
        data['confirmar']='ELIMINAR';data['version']='antigua'
        self.client.post(url,data);self.assertTrue(MovimientoVacacion.objects.filter(pk=pk).exists())
        data['version']=m.updated_at.isoformat();response=self.client.post(url,data)
        self.assertEqual(response.status_code,302)
        self.assertFalse(MovimientoVacacion.objects.filter(pk=pk).exists())
        audit=HistorialCambio.objects.get(accion='eliminar_permanentemente',objeto_id=pk)
        self.assertEqual(audit.cambios['registro_eliminado']['despues']['codigo'],'09')
        self.assertEqual(resumen(self.c)['ley_276']['pendiente'],9)

    def test_borrado_sin_permiso_y_csrf(self):
        from django.contrib.auth.models import Permission
        from django.test import Client
        user=get_user_model().objects.create_user('operador')
        user.user_permissions.add(Permission.objects.get(codename='change_cuentavacacion'))
        m=MovimientoVacacion.objects.create(cuenta=self.c,codigo='05',dias=1)
        url=reverse('vacacion_movimiento_eliminar',args=[self.c.pk,m.pk])
        self.client.force_login(user)
        self.assertNotContains(self.client.get(url),'Eliminar permanentemente')
        self.assertEqual(self.client.post(url,dict(version=m.updated_at.isoformat(),accion='permanente',confirmar='ELIMINAR',motivo='Prueba')).status_code,403)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.user)
        self.assertEqual(csrf.post(url,dict(version=m.updated_at.isoformat(),accion='permanente')).status_code,403)
        self.assertTrue(MovimientoVacacion.objects.filter(pk=m.pk).exists())
