from datetime import date
from io import StringIO
from unittest.mock import patch
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import (HistorialCambio, Justificacion, PeriodoAsistencia, TipoDocumento,
                     TipoOperacion, Trabajador)


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False,
                   CSRF_COOKIE_SECURE=False)
class GestionWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('preparar_roles', stdout=StringIO())
        cls.usuarios = {}
        for rol in ('Administrador', 'Operador', 'Consulta'):
            u = User.objects.create_user(rol.lower(), password='clave-ficticia-de-pruebas')
            u.groups.add(Group.objects.get(name=rol))
            cls.usuarios[rol] = u
        cls.trabajador = Trabajador.objects.create(apellidos_nombres='FICTICIO Pérez', dni='00123456', area='Pruebas')
        cls.inactivo = Trabajador.objects.create(apellidos_nombres='FICTICIO Inactivo', activo=False)

    def login(self, rol='Administrador'):
        self.client.force_login(self.usuarios[rol])

    def url(self, accion, tipo='trabajadores', pk=None):
        kwargs = {'tipo': tipo}
        if pk is not None:
            kwargs['pk'] = pk
        return reverse('maestro_' + accion, kwargs=kwargs)

    def version(self, tipo, pk):
        return self.client.get(self.url('editar', tipo, pk)).context['form']['version'].value()

    def test_rutas_publicas_y_login_neutro(self):
        for tipo in ('trabajadores', 'documentos', 'operaciones', 'periodos'):
            for accion, pk in [('lista', None), ('nuevo', None), ('detalle', 1), ('editar', 1)]:
                response = self.client.get(self.url(accion, tipo, pk))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/ingresar/?next='))
        response = self.client.post(reverse('login'), {'username':'inexistente', 'password':'incorrecta'})
        self.assertContains(response, 'No se pudo iniciar sesión.')
        self.assertNotContains(response, 'usuario no existe')

    def test_login_sin_staff_y_logout_solo_post(self):
        response = self.client.post(reverse('login'), {'username':'operador','password':'clave-ficticia-de-pruebas'})
        self.assertRedirects(response, reverse('inicio'), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('inicio')), self.url('lista'))
        self.assertEqual(self.client.get(reverse('logout')).status_code,405)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_no_redirige_a_dominio_externo(self):
        response = self.client.post(reverse('login'), {'username':'operador','password':'clave-ficticia-de-pruebas','next':'https://example.com'})
        self.assertRedirects(response, reverse('inicio'), fetch_redirect_response=False)

    def test_permisos_servidor_y_botones(self):
        for rol in ('Consulta','Operador','Administrador'):
            self.login(rol)
            for tipo in ('trabajadores','documentos','operaciones','periodos'):
                response=self.client.get(self.url('lista',tipo))
                self.assertEqual(response.status_code,200)
                write = rol == 'Administrador' or (rol == 'Operador' and tipo == 'trabajadores')
                if write:
                    self.assertContains(response, self.url('nuevo',tipo))
                else:
                    self.assertNotContains(response, self.url('nuevo',tipo))
                    for accion,pk in [('nuevo',None),('editar',1)]:
                        url=self.url(accion,tipo,pk)
                        self.assertEqual(self.client.get(url).status_code,403)
                        self.assertEqual(self.client.post(url,{}).status_code,403)
        self.assertEqual(HistorialCambio.objects.count(),0)

    def test_sin_permisos_no_hay_datos(self):
        u=User.objects.create_user('sin_permisos')
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse('inicio')).status_code,403)
        self.assertEqual(self.client.get(self.url('detalle',pk=self.trabajador.pk)).status_code,403)

    def test_busqueda_parcial_estados_y_paginacion(self):
        self.login('Consulta')
        response=self.client.get(self.url('lista'),{'q':'EREZ','activo':'1'})
        self.assertContains(response, 'FICTICIO Pérez')
        self.assertNotContains(response, self.inactivo.apellidos_nombres)
        self.assertEqual(response.context['pagina'].paginator.count,1)
        response=self.client.get(self.url('lista'),{'activo':'0'})
        self.assertContains(response,self.inactivo.apellidos_nombres)
        response=self.client.get(self.url('lista'),{'q':'0012'})
        self.assertEqual(response.context['pagina'].paginator.count,1)
        for n in range(30): Trabajador.objects.create(apellidos_nombres=f'FICTICIO PAGINA {n:02}')
        response=self.client.get(self.url('lista'),{'q':'PAGINA','activo':'1','page':'2'})
        self.assertEqual(len(response.context['filas']),5)
        self.assertContains(response,'q=PAGINA&amp;activo=1&amp;page=1')
        self.assertContains(response,'q=PAGINA&amp;activo=1&amp;page=2')
        response=self.client.get(self.url('lista'),{'activo':'invalido'})
        self.assertTrue(response.context['filtros'].errors)
        self.assertEqual(response.context['pagina'].paginator.count,0)

    def test_alta_nombre_dni_opcional_y_coincidencias(self):
        self.login('Operador')
        url=self.url('nuevo')
        response=self.client.post(url,{'apellidos_nombres':'PRUEBA ALTA','activo':'on'})
        self.assertEqual(response.status_code,302)
        t=Trabajador.objects.get(apellidos_nombres='PRUEBA ALTA')
        self.assertIsNone(t.dni)
        self.assertEqual(HistorialCambio.objects.get(objeto_id=t.pk,entidad='trabajador').autor,self.usuarios['Operador'])
        data={'apellidos_nombres':'ficticio perez','dni':'00123456','activo':'on'}
        response=self.client.post(url,data)
        self.assertContains(response,'Hay fichas coincidentes')
        self.assertEqual(Trabajador.objects.filter(dni='00123456').count(),1)
        data['confirmar_coincidencias']='on'
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.assertEqual(Trabajador.objects.filter(dni='00123456').count(),2)
        self.assertContains(self.client.post(url,{'apellidos_nombres':'PRUEBA DNI','dni':'123'}),'8 dígitos')

    def test_estado_y_version_preservan_historial(self):
        self.login('Operador')
        t=self.trabajador
        version=self.version('trabajadores',t.pk)
        self.client.post(self.url('editar',pk=t.pk),{'apellidos_nombres':t.apellidos_nombres,'dni':t.dni,'version':version})
        t.refresh_from_db(); self.assertFalse(t.activo)
        response=self.client.post(self.url('editar',pk=t.pk),{'apellidos_nombres':'CAMBIO OBSOLETO','version':version,'activo':'on'})
        self.assertContains(response,'La ficha cambió en otra sesión')
        t.refresh_from_db(); self.assertEqual(t.apellidos_nombres,'FICTICIO Pérez')
        version=self.version('trabajadores',t.pk)
        self.client.post(self.url('editar',pk=t.pk),{'apellidos_nombres':t.apellidos_nombres,'dni':t.dni,'activo':'on','version':version})
        t.refresh_from_db(); self.assertTrue(t.activo)
        changes=HistorialCambio.objects.filter(entidad='trabajador',objeto_id=t.pk)
        self.assertEqual(changes.count(),2)
        self.assertEqual(changes.first().cambios['activo'],{'antes':'False','despues':'True'})

    def test_version_requerida_y_datos_no_guardados_en_get(self):
        self.login('Operador')
        self.client.get(self.url('editar',pk=self.trabajador.pk),{'activo':'0'})
        self.trabajador.refresh_from_db(); self.assertTrue(self.trabajador.activo)
        response=self.client.post(self.url('editar',pk=self.trabajador.pk),{'apellidos_nombres':'PRUEBA SIN VERSION'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['form'].errors.get('version'))
        self.assertEqual(HistorialCambio.objects.count(),0)

    def test_guardado_y_auditoria_atomicos(self):
        self.login('Operador')
        with patch('control.views.registrar',side_effect=RuntimeError('fallo de prueba')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url('nuevo'),{'apellidos_nombres':'PRUEBA ROLLBACK'})
        self.assertFalse(Trabajador.objects.filter(apellidos_nombres='PRUEBA ROLLBACK').exists())

    def test_catalogos_separados_codigos_y_reglas(self):
        self.login()
        self.assertEqual(self.client.post(self.url('nuevo','documentos'),{'nombre':'PRUEBA DOC','codigo_externo':'001','activo':'on'}).status_code,302)
        d=TipoDocumento.objects.get(nombre='PRUEBA DOC'); self.assertEqual(d.codigo_externo,'001')
        response=self.client.get(self.url('lista','documentos'),{'q':'001'})
        self.assertContains(response,'PRUEBA DOC')
        o=TipoOperacion.objects.get(nombre='Vacaciones')
        response=self.client.get(self.url('detalle','operaciones',o.pk))
        self.assertContains(response,'Pendiente de revisión')
        version=self.version('operaciones',o.pk)
        self.client.post(self.url('editar','operaciones',o.pk),{'nombre':o.nombre,'codigo_externo':'05','grupo_especial':'VACACIONES','requiere_fecha_final':'2','version':version})
        o.refresh_from_db(); self.assertTrue(o.requiere_fecha_final); self.assertFalse(o.activo)
        self.assertEqual(o.codigo_externo,'05')
        self.assertTrue(HistorialCambio.objects.filter(entidad='tipooperacion').exists())
        self.assertContains(self.client.get(self.url('lista','operaciones'),{'activo':'0'}),o.nombre)

    def test_periodos_validacion_excepcion_y_transiciones(self):
        self.login()
        data={'titulo':'PRUEBA SOLAPE','fecha_inicio':'2026-10-01','fecha_fin':'2026-10-02','estado':'ABIERTO'}
        response=self.client.post(self.url('nuevo','periodos'),data)
        self.assertContains(response,'El rango se solapa')
        data.update(autorizar_solapamiento='on',notas='Excepción ficticia autorizada')
        self.assertEqual(self.client.post(self.url('nuevo','periodos'),data).status_code,302)
        data['fecha_fin']='2026-09-01'
        self.assertContains(self.client.post(self.url('nuevo','periodos'),data),'anterior al inicio')
        p=PeriodoAsistencia.objects.get(titulo='Octubre 2026')
        data={'titulo':p.titulo,'fecha_inicio':'07/09/2026','fecha_fin':'09/10/2026','estado':'PROCESADO','version':self.version('periodos',p.pk),'fecha_cierre':'2000-01-01','autorizar_solapamiento':'on','notas':'Excepción ficticia autorizada'}
        self.assertEqual(self.client.post(self.url('editar','periodos',p.pk),data).status_code,302)
        p.refresh_from_db(); corte=p.fecha_cierre
        self.assertEqual(p.estado,'PROCESADO'); self.assertIsNotNone(p.fecha_procesamiento)
        self.assertNotEqual(p.fecha_cierre.year,2000)
        data.update(estado='ABIERTO',version=self.version('periodos',p.pk))
        self.client.post(self.url('editar','periodos',p.pk),data)
        p.refresh_from_db(); self.assertEqual(p.fecha_cierre,corte)
        n=PeriodoAsistencia.objects.get(titulo='Noviembre 2026')
        self.assertIsNone(n.fecha_fin)
        response=self.client.get(self.url('lista','periodos'),{'q':'Noviembre','estado':'ABIERTO'})
        self.assertContains(response,'12/10/2026'); self.assertContains(response,'Sin definir')
        self.assertNotContains(response,'Octubre 2026')

    def test_historial_relacionado_restringido_y_conservado(self):
        t=self.trabajador
        j=Justificacion.objects.create(trabajador=t,periodo=PeriodoAsistencia.objects.first(),tipo_documento=TipoDocumento.objects.first(),tipo_operacion=TipoOperacion.objects.first(),created_by=self.usuarios['Administrador'],updated_by=self.usuarios['Administrador'],fuente='EXCEL',fecha_movimiento=date(2026,10,1))
        self.login('Consulta')
        response=self.client.get(self.url('detalle',pk=t.pk))
        self.assertNotIn('relacionados',response.context)
        self.assertContains(response, 'Última modificación')
        self.assertNotContains(response, 'Updated at')
        self.assertContains(response,'no tiene permiso para consultar el detalle')
        self.login()
        self.assertContains(self.client.get(self.url('detalle',pk=t.pk)),'01/10/2026')
        version=self.version('trabajadores',t.pk)
        self.client.post(self.url('editar',pk=t.pk),{'apellidos_nombres':t.apellidos_nombres,'version':version})
        j.refresh_from_db(); self.assertEqual(j.trabajador_id,t.pk)
        self.assertEqual(t.justificacion_set.count(),1)

    def test_csrf_cache_metodos_y_404(self):
        c=Client(enforce_csrf_checks=True); c.force_login(self.usuarios['Operador'])
        self.assertEqual(c.post(self.url('nuevo'),{'apellidos_nombres':'PRUEBA CSRF'}).status_code,403)
        self.login()
        response=self.client.get(self.url('lista'))
        self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(self.client.post(self.url('lista')).status_code,405)
        self.assertEqual(self.client.post(self.url('detalle',pk=self.trabajador.pk)).status_code,405)
        self.assertEqual(self.client.delete(self.url('editar',pk=self.trabajador.pk)).status_code,405)
        self.assertEqual(self.client.get(self.url('detalle',pk=99999)).status_code,404)
        self.assertEqual(self.client.post('/trabajadores/1/eliminar/').status_code,404)

    def test_escape_y_conservacion_filtros(self):
        self.login('Operador')
        t=Trabajador.objects.create(apellidos_nombres='<script>PRUEBA</script>')
        response=self.client.get(self.url('detalle',pk=t.pk),{'q':'PRUEBA','activo':'1','page':'2','next':'https://example.com'})
        self.assertContains(response,'&lt;script&gt;PRUEBA&lt;/script&gt;')
        self.assertNotContains(response,'<script>PRUEBA</script>')
        self.assertContains(response,'q=PRUEBA&amp;activo=1&amp;page=2')
        self.assertNotContains(response,'https://example.com')
