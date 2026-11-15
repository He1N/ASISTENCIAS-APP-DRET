from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, RequestFactory
from django.urls import reverse
from .models import CuentaVacacion, MovimientoVacacion
from .context_processors import notificaciones_vacaciones
from .vacaciones import resumen


class NotificacionesTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser('avisos','','clave-prueba')
        self.cuenta=CuentaVacacion.objects.create(nombre='PERSONA FICTICIA',dni='00000001',asignaciones={'2026':'1'})
        self.movimiento=MovimientoVacacion.objects.create(cuenta=self.cuenta,codigo='32',dias=Decimal('1.5'))

    def avisos(self,user=None):
        request=RequestFactory().get('/')
        request.user=user or self.user
        return notificaciones_vacaciones(request).get('notificaciones_vacaciones',[])

    def test_saldo_actual_y_retiro_al_corregir(self):
        self.assertEqual(self.avisos()[0]['pendiente'],resumen(self.cuenta)['pendiente'])
        self.movimiento.dias=1;self.movimiento.save()
        self.assertEqual(self.avisos(),[])
        self.movimiento.dias=Decimal('.5');self.movimiento.save()
        self.assertEqual(self.avisos(),[])
        self.movimiento.dias=2;self.movimiento.save()
        self.assertEqual(len(self.avisos()),1)
        self.movimiento.estado='ANULADO';self.movimiento.save()
        self.assertEqual(self.avisos(),[])

    def test_eliminadas_y_permisos(self):
        self.assertEqual(self.avisos(AnonymousUser()),[])
        consulta=get_user_model().objects.create_user('sin-permiso')
        self.assertEqual(self.avisos(consulta),[])
        self.cuenta.eliminada=True;self.cuenta.save()
        self.assertEqual(self.avisos(),[])

    def test_campana_enlace_y_logo(self):
        self.client.force_login(self.user)
        response=self.client.get(reverse('vacacion_lista'))
        self.assertContains(response,'Notificaciones: 1')
        self.assertContains(response,'PERSONA FICTICIA')
        self.assertContains(response,reverse('vacacion_ficha',args=[self.cuenta.pk]))
        self.assertContains(response,'logo-dret.png')
        self.cuenta.asignaciones={'2026':'2'};self.cuenta.save()
        response=self.client.get(reverse('vacacion_lista'))
        self.assertContains(response,'Notificaciones: 0')
        self.assertContains(response,'No hay trabajadores con saldo negativo.')
