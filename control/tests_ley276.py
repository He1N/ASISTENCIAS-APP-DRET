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
        self.assertContains(self.client.get(reverse('vacacion_ficha',args=[self.c.pk])),'Ley 276')
        self.c.regimen_laboral='CAS';self.c.save()
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
