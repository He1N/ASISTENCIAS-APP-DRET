from datetime import date
from io import StringIO
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from .models import *
from .forms import TrabajadorForm, PeriodoForm

@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CimientosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('preparar_roles', stdout=StringIO())
        cls.admin = User.objects.create_superuser('admin_prueba', password='clave-sintetica-segura')
        for rol in ('Operador', 'Consulta'):
            u = User.objects.create_user(rol, password='clave-sintetica-segura', is_staff=True)
            u.groups.add(Group.objects.get(name=rol))

    def test_nombre_unico_obligatorio(self):
        f = TrabajadorForm({'apellidos_nombres':'PERSONA FICTICIA', 'activo':True})
        self.assertTrue(f.is_valid(), f.errors)
        t = f.save()
        self.assertIsNone(t.dni)
        f = TrabajadorForm({'apellidos_nombres':'persona ficticia', 'activo':True})
        self.assertFalse(f.is_valid())
        f = TrabajadorForm({'apellidos_nombres':'persona ficticia', 'activo':True, 'confirmar_coincidencias':True})
        self.assertTrue(f.is_valid(), f.errors)

    def test_dni_y_codigos_texto(self):
        t = Trabajador.objects.create(apellidos_nombres='Prueba', dni='00123456')
        t.refresh_from_db()
        self.assertEqual(t.dni, '00123456')
        self.assertEqual(TipoDocumento.objects.get(nombre='Papeleta de Permiso').codigo_externo, '01')

    def test_periodos_y_reglas_desconocidas(self):
        p = PeriodoAsistencia.objects.get(titulo='Octubre 2026')
        self.assertEqual((p.fecha_inicio,p.fecha_fin),(date(2026,9,7),date(2026,10,9)))
        self.assertIsNone(PeriodoAsistencia.objects.get(titulo='Noviembre 2026').fecha_fin)
        self.assertIsNone(TipoOperacion.objects.get(nombre='Vacaciones').requiere_fecha_final)

    def crear_justificacion(self):
        t = Trabajador.objects.create(apellidos_nombres='PRUEBA')
        p = PeriodoAsistencia.objects.get(titulo='Octubre 2026')
        p.estado='PROCESADO'; p.fecha_cierre=timezone.now(); p.save()
        o = TipoOperacion.objects.create(nombre='Prueba', requiere_fecha_final=True)
        return Justificacion(trabajador=t, periodo=p, tipo_operacion=o, tipo_documento=TipoDocumento.objects.first(), created_by=self.admin, updated_by=self.admin, fecha_movimiento=date(2026,10,1))

    def test_justificacion_validacion_e_historial(self):
        j=self.crear_justificacion()
        with self.assertRaises(ValidationError): j.full_clean()
        j.fecha_final=j.fecha_movimiento; j.full_clean(); j.save()
        self.assertTrue(j.es_registro_tardio)
        j.periodo.refresh_from_db(); self.assertEqual(j.periodo.estado,'PROCESADO')
        self.assertIsNone(j.fecha_recepcion)
        t=j.trabajador; t.activo=False; t.save(); t.activo=True; t.save()
        self.assertEqual(t.justificacion_set.count(),1)
        with self.assertRaises(ProtectedError): t.delete()
        j.fuente='EXCEL'; self.assertIsNone(j.es_registro_tardio)

    def test_rango_invalido_y_solapamiento(self):
        f=PeriodoForm({'titulo':'Prueba','fecha_inicio':'2026-10-01','fecha_fin':'2026-09-01','estado':'ABIERTO'})
        self.assertFalse(f.is_valid())
        f=PeriodoForm({'titulo':'Prueba','fecha_inicio':'2026-10-01','fecha_fin':'2026-10-02','estado':'ABIERTO'})
        self.assertFalse(f.is_valid())
        f=PeriodoForm({'titulo':'Prueba','fecha_inicio':'2026-10-01','fecha_fin':'2026-10-02','estado':'ABIERTO','autorizar_solapamiento':True,'notas':'Excepción ficticia autorizada'})
        self.assertTrue(f.is_valid(),f.errors)

    def test_roles_y_rutas(self):
        self.assertEqual(self.client.get(reverse('admin:control_trabajador_changelist')).status_code,302)
        for rol in ('Consulta','Operador'):
            self.client.force_login(User.objects.get(username=rol))
            self.assertEqual(self.client.get(reverse('admin:control_trabajador_changelist')).status_code,200)
            self.assertEqual(self.client.get(reverse('admin:auth_user_changelist')).status_code,403)
            self.assertEqual(self.client.post(reverse('admin:control_periodoasistencia_add'),{}).status_code,403)
        self.client.force_login(User.objects.get(username='Consulta'))
        self.assertEqual(self.client.post(reverse('admin:control_trabajador_add'),{'apellidos_nombres':'No autorizado'}).status_code,403)
        self.assertFalse(Trabajador.objects.filter(apellidos_nombres='No autorizado').exists())

    def test_operador_alta_y_auditoria(self):
        self.client.force_login(User.objects.get(username='Operador'))
        response=self.client.post(reverse('admin:control_trabajador_add'),{'apellidos_nombres':'PRUEBA DE ALTA','activo':'on','_save':'Guardar'})
        self.assertEqual(response.status_code,302)
        h=HistorialCambio.objects.get(entidad='trabajador')
        self.assertEqual(h.autor.username,'Operador')
        self.assertIn('apellidos_nombres',h.cambios)

    def test_fechas_estado_auditadas(self):
        self.client.force_login(self.admin)
        p=PeriodoAsistencia.objects.get(titulo='Octubre 2026')
        response=self.client.post(reverse('admin:control_periodoasistencia_change',args=[p.pk]),{'titulo':p.titulo,'fecha_inicio':'2026-09-07','fecha_fin':'2026-10-09','estado':'PROCESADO','_save':'Guardar'})
        self.assertEqual(response.status_code,302)
        p.refresh_from_db(); self.assertIsNotNone(p.fecha_cierre); self.assertIsNotNone(p.fecha_procesamiento)
        self.assertTrue(HistorialCambio.objects.filter(entidad='periodoasistencia').exists())

    def test_busqueda_sin_tildes(self):
        t=Trabajador.objects.create(apellidos_nombres='FICTICIO Pérez')
        self.client.force_login(self.admin)
        response=self.client.get(reverse('admin:control_trabajador_changelist'),{'q':'PEREZ'})
        self.assertContains(response,t.apellidos_nombres)

    def test_csrf_y_login_logout(self):
        c=Client(enforce_csrf_checks=True)
        c.force_login(self.admin)
        self.assertEqual(c.post(reverse('admin:control_trabajador_add'),{'apellidos_nombres':'PRUEBA'}).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('admin:logout')).status_code,200)
        self.assertNotIn('_auth_user_id',self.client.session)
        self.assertFalse(self.client.login(username='admin_prueba',password='incorrecta'))
        self.assertTrue(self.admin.password.startswith('pbkdf2_'))

    def test_roles_y_datos_idempotentes(self):
        call_command('preparar_roles',stdout=StringIO())
        self.assertEqual(Group.objects.count(),3)
        self.assertFalse(User.objects.get(username='Consulta').has_perm('control.exportar_resultados'))
        call_command('crear_datos_sinteticos',stdout=StringIO()); call_command('crear_datos_sinteticos',stdout=StringIO())
        self.assertEqual(Trabajador.objects.count(),3)
