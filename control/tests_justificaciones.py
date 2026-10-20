from datetime import date, time, timedelta
from io import StringIO
from unittest.mock import patch
from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from .justificacion_forms import JustificacionForm
from .models import (HistorialCambio, Justificacion, PeriodoAsistencia, TipoDocumento,
                     TipoOperacion, Trabajador)


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False,
                   CSRF_COOKIE_SECURE=False)
class JustificacionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('preparar_roles', stdout=StringIO())
        cls.users = {}
        for rol in ('Administrador', 'Operador', 'Consulta'):
            u = User.objects.create_user(rol.lower(), password='clave-ficticia-de-pruebas')
            u.groups.add(Group.objects.get(name=rol)); cls.users[rol] = u
        cls.trabajador = Trabajador.objects.create(apellidos_nombres='FICTICIO Pérez', dni='00123456')
        cls.homonimo = Trabajador.objects.create(apellidos_nombres='FICTICIO Pérez', activo=False)
        cls.documento = TipoDocumento.objects.get(codigo_externo='01')
        cls.operacion = TipoOperacion.objects.create(nombre='Operación ficticia', codigo_externo='001', requiere_fecha_final=False)
        cls.con_final = TipoOperacion.objects.create(nombre='Operación ficticia con fin', requiere_fecha_final=True)
        cls.periodo = PeriodoAsistencia.objects.get(titulo='Octubre 2026')

    def login(self, rol='Operador'):
        self.client.force_login(self.users[rol])

    def payload(self, **extra):
        data = {'trabajador': self.trabajador.pk, 'periodo': self.periodo.pk,
                'tipo_documento': self.documento.pk, 'tipo_operacion': self.operacion.pk,
                'fecha_movimiento': '2026-10-01', 'cud': '00-ABC / 002'}
        data.update(extra); return data

    def registro(self, **extra):
        data = dict(trabajador=self.trabajador, periodo=self.periodo, tipo_documento=self.documento,
            tipo_operacion=self.operacion, fecha_movimiento=date(2026,10,1),
            created_by=self.users['Operador'], updated_by=self.users['Operador'], cud='00-ABC / 002')
        data.update(extra)
        return Justificacion.objects.create(**data)

    def editar(self, obj):
        return reverse('justificacion_editar', args=[obj.pk])

    def version(self, obj):
        return self.client.get(self.editar(obj)).context['form']['version'].value()

    def test_alta_manual_actor_fechas_y_cud_literal(self):
        self.login()
        data=self.payload(cud=' 00-ABC / 002 ', created_by=self.users['Administrador'].pk,
                          fuente='EXCEL', anulada='on', fecha_recepcion='')
        response=self.client.post(reverse('justificacion_nueva'),data)
        self.assertEqual(response.status_code,302)
        obj=Justificacion.objects.get()
        self.assertEqual(obj.created_by,self.users['Operador'])
        self.assertEqual(obj.updated_by,self.users['Operador'])
        self.assertEqual(obj.fuente,'MANUAL'); self.assertFalse(obj.anulada)
        self.assertIsNone(obj.fecha_recepcion); self.assertIsNotNone(obj.created_at)
        self.assertEqual(obj.cud,' 00-ABC / 002 ')
        self.assertEqual(HistorialCambio.objects.get(entidad='justificacion').autor,self.users['Operador'])
        self.assertRedirects(response,reverse('justificacion_detalle',args=[obj.pk]))

    def test_campos_obligatorios_y_fecha_invalida(self):
        self.login()
        for field in ('trabajador','periodo','tipo_documento','tipo_operacion','fecha_movimiento'):
            data=self.payload(); del data[field]
            response=self.client.post(reverse('justificacion_nueva'),data)
            self.assertIn(field,response.context['form'].errors)
        response=self.client.post(reverse('justificacion_nueva'),self.payload(fecha_movimiento='31/02/2026'))
        self.assertIn('fecha_movimiento',response.context['form'].errors)
        self.assertEqual(Justificacion.objects.count(),0)

    def test_final_obligatoria_igual_inicio_y_orden(self):
        self.login()
        response=self.client.post(reverse('justificacion_nueva'),self.payload(tipo_operacion=self.con_final.pk))
        self.assertIn('fecha_final',response.context['form'].errors)
        response=self.client.post(reverse('justificacion_nueva'),self.payload(tipo_operacion=self.con_final.pk,fecha_final='2026-09-30'))
        self.assertIn('fecha_final',response.context['form'].errors)
        self.assertEqual(self.client.post(reverse('justificacion_nueva'),self.payload(tipo_operacion=self.con_final.pk,fecha_final='2026-10-01')).status_code,302)
        self.assertEqual(Justificacion.objects.get().fecha_final,date(2026,10,1))

    def test_regla_pendiente_no_equivale_a_no(self):
        self.login()
        pendiente=TipoOperacion.objects.get(nombre='Vacaciones')
        response=self.client.post(reverse('justificacion_nueva'),self.payload(tipo_operacion=pendiente.pk))
        self.assertIn('tipo_operacion',response.context['form'].errors)
        self.assertContains(response,'pendiente de revisión')
        self.assertEqual(Justificacion.objects.count(),0)

    def test_horas_independientes_y_no_exclusivas_de_papeleta(self):
        self.login()
        oficio=TipoDocumento.objects.get(nombre='Oficio')
        data=self.payload(tipo_documento=oficio.pk,hora_salida='23:15',hora_retorno='01:10')
        self.assertEqual(self.client.post(reverse('justificacion_nueva'),data).status_code,302)
        obj=Justificacion.objects.get(); self.assertEqual(obj.hora_salida,time(23,15))
        self.assertEqual(obj.hora_retorno,time(1,10))
        self.assertContains(self.client.get(reverse('justificacion_detalle',args=[obj.pk])),'no se presume un turno')
        data=self.payload(hora_retorno='10:05',hora_salida='')
        self.assertEqual(self.client.post(reverse('justificacion_nueva'),data).status_code,302)
        obj=Justificacion.objects.latest('pk'); self.assertIsNone(obj.hora_salida)
        self.assertEqual(obj.hora_retorno,time(10,5))
        response=self.client.post(reverse('justificacion_nueva'),self.payload(hora_salida='25:99'))
        self.assertIn('hora_salida',response.context['form'].errors)

    def test_periodos_cerrados_y_procesados_admiten_registro_tardio(self):
        self.login()
        for estado in ('CERRADO','PROCESADO'):
            p=self.periodo; p.estado=estado; p.fecha_cierre=timezone.now()-timedelta(days=1); p.save()
            response=self.client.get(reverse('justificacion_nueva'),{'periodo':p.pk})
            self.assertContains(response,'El registro se añadirá al historial')
            self.assertEqual(self.client.post(reverse('justificacion_nueva'),self.payload()).status_code,302)
            obj=Justificacion.objects.latest('pk'); self.assertTrue(obj.es_registro_tardio)
            p.refresh_from_db(); self.assertEqual(p.estado,estado)
        self.assertEqual(Justificacion.objects.count(),2)  # misma persona/fecha no es única

    def test_plazo_sin_corte_y_legado_indeterminados(self):
        self.periodo.estado='CERRADO'; self.periodo.save()
        obj=self.registro(); self.assertIsNone(obj.es_registro_tardio); self.assertEqual(obj.plazo,'Sin determinar')
        obj=self.registro(fuente='EXCEL'); self.assertIsNone(obj.es_registro_tardio)
        self.assertEqual(obj.plazo,'Importado / sin determinar')

    def test_excepcion_rango_motivada_y_no_reasignacion(self):
        self.login()
        data=self.payload(fecha_movimiento='2026-10-15')
        response=self.client.post(reverse('justificacion_nueva'),data)
        self.assertIn('motivo_excepcion',response.context['form'].errors)
        data['motivo_excepcion']='Corte administrativo ficticio autorizado'
        self.assertEqual(self.client.post(reverse('justificacion_nueva'),data).status_code,302)
        obj=Justificacion.objects.get(); self.assertEqual(obj.periodo_id,self.periodo.pk)
        audit=HistorialCambio.objects.get(entidad='justificacion')
        self.assertEqual(audit.cambios['motivo_excepcion']['despues'],data['motivo_excepcion'])

    def test_edicion_motivo_version_creador_y_recepcion(self):
        obj=self.registro(); original=obj.created_at
        self.login('Administrador'); version=self.version(obj)
        data=self.payload(version=version,fecha_recepcion='2026-10-05')
        response=self.client.post(self.editar(obj),data)
        self.assertIn('motivo_edicion',response.context['form'].errors)
        data['motivo_edicion']='Corrección ficticia documentada'
        self.assertEqual(self.client.post(self.editar(obj),data).status_code,302)
        obj.refresh_from_db(); self.assertEqual(obj.created_at,original)
        self.assertEqual(obj.created_by,self.users['Operador'])
        self.assertEqual(obj.updated_by,self.users['Administrador'])
        self.assertEqual(obj.fecha_recepcion,date(2026,10,5))
        response=self.client.post(self.editar(obj),data)
        self.assertContains(response,'cambió en otra sesión')
        self.assertEqual(HistorialCambio.objects.filter(entidad='justificacion').count(),1)

    def test_guardar_y_otro_y_buscar_sin_escribir(self):
        self.login()
        data=self.payload(accion='buscar',trabajador_buscar='erez',observaciones='Texto conservado')
        response=self.client.post(reverse('justificacion_nueva'),data)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['form']['observaciones'].value(),'Texto conservado')
        self.assertFalse(Justificacion.objects.exists())
        data['accion']='otro'
        self.assertRedirects(self.client.post(reverse('justificacion_nueva'),data),reverse('justificacion_nueva'))
        self.assertEqual(Justificacion.objects.count(),1)

    def test_busquedas_autocompletado_y_homonimos(self):
        self.login()
        for campo,q in [('trabajador','EREZ'),('tipo_documento','permiso'),('tipo_operacion','FICTICIA')]:
            response=self.client.get(reverse('autocompletar',args=[campo]),{'q':q})
            self.assertEqual(response.status_code,200)
            options=response.json()['results']; self.assertGreater(len(options),0)
            if campo=='trabajador':
                self.assertEqual([x['id'] for x in options],[self.trabajador.pk,self.homonimo.pk])
                self.assertIn('00123456',options[0]['label'])
            if campo=='tipo_operacion': self.assertIn('requiere_fecha_final',options[0])
        self.assertContains(self.client.get(reverse('justificacion_nueva')),'name="tipo_documento_buscar"')
        self.assertContains(self.client.get(reverse('justificacion_nueva')),'name="tipo_operacion_buscar"')
        self.assertEqual(self.client.post(reverse('justificacion_nueva'),self.payload(trabajador=self.homonimo.pk)).status_code,302)
        self.assertEqual(Justificacion.objects.get().trabajador_id,self.homonimo.pk)

    def test_autocompletado_acotado_y_catalogos_inactivos(self):
        self.login()
        for n in range(30): Trabajador.objects.create(apellidos_nombres=f'FICTICIO LIMITE {n}')
        response=self.client.get(reverse('autocompletar',args=['trabajador']),{'q':'LIMITE'})
        self.assertEqual(len(response.json()['results']),20)
        self.operacion.activo=False; self.operacion.save()
        url=reverse('autocompletar',args=['tipo_operacion'])
        self.assertNotIn(self.operacion.pk,[x['id'] for x in self.client.get(url).json()['results']])
        self.assertIn(self.operacion.pk,[x['id'] for x in self.client.get(url,{'modo':'consulta'}).json()['results']])
        response=self.client.post(reverse('justificacion_nueva'),self.payload())
        self.assertIn('tipo_operacion',response.context['form'].errors)
        obj=self.registro(); data=self.payload(version=self.version(obj),motivo_edicion='Conservar catálogo histórico')
        self.assertEqual(self.client.post(self.editar(obj),data).status_code,302)

    def test_filtros_combinados_y_estado_trabajador(self):
        self.login('Consulta')
        obj=self.registro(observaciones='Observación ficticia')
        self.registro(trabajador=self.homonimo,cud='DISTINTO')
        data={'q':'EREZ','trabajador':self.trabajador.pk,'dni':'0012','fecha':'2026-10-01',
              'desde':'2026-09-01','hasta':'2026-10-09','periodo':self.periodo.pk,
              'tipo_documento':self.documento.pk,'tipo_operacion':self.operacion.pk,'cud':'00-ABC','activo':'1'}
        response=self.client.get(reverse('consultas'),data)
        self.assertEqual(response.context['pagina'].paginator.count,1)
        self.assertEqual(response.context['filas'][0]['obj'].pk,obj.pk)
        for query in ('00123456','00-ABC','Observación'):
            self.assertEqual(self.client.get(reverse('consultas'),{'q':query}).context['pagina'].paginator.count,1)
        response=self.client.get(reverse('consultas'),{'activo':'0'})
        self.assertEqual(response.context['pagina'].paginator.count,1)

    def test_filtros_invalidos_no_devuelven_todos(self):
        self.registro(); self.login('Consulta')
        for query in ({'desde':'2026-10-10','hasta':'2026-10-01'},{'fecha':'invalida'},
                      {'trabajador':99999},{'periodo':'xx'},{'orden':'sql malicioso'}):
            response=self.client.get(reverse('consultas'),query)
            self.assertTrue(response.context['filtros'].errors)
            self.assertEqual(response.context['pagina'].paginator.count,0)

    def test_paginacion_511_sinteticos_orden_estable_y_null_al_final(self):
        data=dict(trabajador=self.trabajador, periodo=self.periodo, tipo_documento=self.documento,
            tipo_operacion=self.operacion, created_by=self.users['Operador'], updated_by=self.users['Operador'])
        Justificacion.objects.bulk_create([Justificacion(**data,fecha_movimiento=date(2026,10,1)) for _ in range(510)] + [Justificacion(**data,fuente='EXCEL')])
        self.login('Consulta')
        with CaptureQueriesContext(connection) as consultas_sql:
            response=self.client.get(reverse('consultas'),{'page':21})
        self.assertLessEqual(len(consultas_sql), 20)  # Evita N+1 al cargar las relaciones
        self.assertEqual(response.context['pagina'].paginator.count,511)
        self.assertEqual(len(response.context['filas']),11)
        self.assertIsNone(response.context['filas'][-1]['obj'].fecha_movimiento)
        response=self.client.get(reverse('consultas'),{'orden':'captura'})
        self.assertEqual(response.context['filas'][0]['obj'].pk,Justificacion.objects.latest('pk').pk)

    def test_permiso_consulta_solo_lectura_operador_no_anula(self):
        obj=self.registro()
        self.login('Consulta')
        self.assertEqual(self.client.get(reverse('consultas')).status_code,200)
        self.assertEqual(self.client.get(reverse('justificacion_detalle',args=[obj.pk])).status_code,200)
        for url in (reverse('justificacion_nueva'),self.editar(obj),reverse('justificacion_anular',args=[obj.pk])):
            self.assertEqual(self.client.get(url).status_code,403)
            self.assertEqual(self.client.post(url,self.payload()).status_code,403)
        self.login('Operador')
        self.assertEqual(self.client.post(reverse('justificacion_anular',args=[obj.pk]),{}).status_code,403)
        self.assertFalse(HistorialCambio.objects.exists())

    def test_anonimos_y_solo_maestro_no_acceden(self):
        obj=self.registro()
        urls=[reverse('consultas'),reverse('justificacion_nueva'),self.editar(obj),
              reverse('justificacion_detalle',args=[obj.pk]),reverse('autocompletar',args=['trabajador'])]
        for url in urls: self.assertEqual(self.client.get(url).status_code,302)
        u=User.objects.create_user('solo_maestro')
        u.user_permissions.add(Permission.objects.get(codename='view_trabajador'))
        self.client.force_login(u)
        for url in urls: self.assertEqual(self.client.get(url).status_code,403)

    def test_anulacion_logica_motivada_y_auditada(self):
        self.login('Administrador'); obj=self.registro()
        url=reverse('justificacion_anular',args=[obj.pk])
        response=self.client.get(url); version=response.context['form']['version'].value()
        self.client.get(url); obj.refresh_from_db(); self.assertFalse(obj.anulada)
        self.assertIn('motivo',self.client.post(url,{'version':version}).context['form'].errors)
        self.assertEqual(self.client.post(url,{'version':version,'motivo':'Anulación ficticia motivada'}).status_code,302)
        obj.refresh_from_db(); self.assertTrue(obj.anulada)
        self.assertEqual(obj.anulada_by,self.users['Administrador'])
        self.assertEqual(HistorialCambio.objects.get(entidad='justificacion').accion,'anular')
        self.assertEqual(self.client.get(self.editar(obj)).status_code,403)
        self.assertEqual(self.client.get(reverse('consultas')).context['pagina'].paginator.count,0)
        self.assertEqual(self.client.get(reverse('consultas'),{'estado':'ANULADAS'}).context['pagina'].paginator.count,1)
        self.assertEqual(Justificacion.objects.count(),1)

    def test_auditoria_restringida_y_atomicidad(self):
        self.login()
        with patch('control.justificacion_views.registrar',side_effect=RuntimeError('prueba de rollback')):
            with self.assertRaises(RuntimeError): self.client.post(reverse('justificacion_nueva'),self.payload())
        self.assertFalse(Justificacion.objects.exists())
        self.client.post(reverse('justificacion_nueva'),self.payload())
        obj=Justificacion.objects.get()
        url=reverse('justificacion_detalle',args=[obj.pk])
        self.assertNotIn('auditoria',self.client.get(url).context)
        self.login('Administrador')
        self.assertContains(self.client.get(url),'Historial de cambios')

    def test_filtros_persisten_y_escape_html(self):
        self.login(); obj=self.registro(observaciones='<script>PRUEBA</script>')
        response=self.client.get(reverse('consultas'),{'cud':'00-ABC','page':1})
        self.assertContains(response,'cud=00-ABC&amp;page=1')
        url=reverse('justificacion_detalle',args=[obj.pk])
        response=self.client.get(url,{'cud':'00-ABC','page':1,'next':'https://example.com'})
        self.assertContains(response,'cud=00-ABC&amp;page=1')
        self.assertNotContains(response,'https://example.com')
        self.assertContains(response,'&lt;script&gt;PRUEBA&lt;/script&gt;')

    def test_csrf_metodos_cache_y_404(self):
        self.login(); obj=self.registro()
        c=Client(enforce_csrf_checks=True); c.force_login(self.users['Operador'])
        self.assertEqual(c.post(reverse('justificacion_nueva'),self.payload()).status_code,403)
        self.assertEqual(c.post(self.editar(obj),self.payload()).status_code,403)
        self.assertEqual(self.client.post(reverse('consultas')).status_code,405)
        self.assertEqual(self.client.post(reverse('autocompletar',args=['trabajador'])).status_code,405)
        self.assertIn('no-store',self.client.get(reverse('consultas'))['Cache-Control'])
        self.assertEqual(self.client.get(reverse('justificacion_detalle',args=[99999])).status_code,404)
        self.assertEqual(self.client.get(reverse('autocompletar',args=['inexistente'])).status_code,404)
        self.assertEqual(self.client.delete(self.editar(obj)).status_code,405)

    def test_editar_legado_conserva_origen_y_faltantes(self):
        self.login()
        obj=self.registro(fuente='EXCEL',fecha_movimiento=None,tipo_operacion=TipoOperacion.objects.get(nombre='Vacaciones'))
        data=self.payload(tipo_operacion=obj.tipo_operacion_id,fecha_movimiento='',version=self.version(obj),motivo_edicion='Corrección de observación',observaciones='Dato legado conservado')
        self.assertEqual(self.client.post(self.editar(obj),data).status_code,302)
        obj.refresh_from_db(); self.assertEqual(obj.fuente,'EXCEL'); self.assertIsNone(obj.fecha_movimiento)
