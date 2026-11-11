from datetime import date
from decimal import Decimal
from io import StringIO,BytesIO
from zipfile import ZipFile
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import (CuentaVacacion,MovimientoVacacion,EnlaceVacacion,Justificacion,Trabajador,
    TipoDocumento,TipoOperacion,PeriodoAsistencia,HistorialCambio)
from .vacaciones import resumen
from .vacaciones_sync import sincronizar


class EnlaceVacacionesTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser('sync','', 'clave-ficticia')
        self.worker=Trabajador.objects.create(apellidos_nombres='PERSONA SINTETICA',dni='00000234')
        self.account=CuentaVacacion.objects.create(nombre='PERSONA SINTETICA',dni='00000234',asignaciones={'2026':'2'})
        self.op=TipoOperacion.objects.create(nombre='Vacaciones prueba',codigo_externo='05',grupo_especial='VACACIONES',requiere_fecha_final=True)
        self.half=TipoOperacion.objects.create(nombre='Media jornada prueba',codigo_externo='32',grupo_especial='VACACIONES',requiere_fecha_final=False)
        self.doc=TipoDocumento.objects.first();self.period=PeriodoAsistencia.objects.get(titulo='Noviembre 2026')
    def source(self,**kwargs):
        values=dict(trabajador=self.worker,tipo_operacion=self.op,tipo_documento=self.doc,periodo=self.period,
            fecha_movimiento=date(2026,11,1),fecha_final=date(2026,11,3),created_by=self.user,updated_by=self.user,
            observaciones='MEMO DE PRUEBA')
        values.update(kwargs);return Justificacion.objects.create(**values)
    def test_alta_edicion_anulacion_y_saldo_negativo(self):
        j=self.source();self.assertEqual(resumen(self.account)['pendiente'],-1)
        for _ in range(2): j.save()
        self.assertEqual(MovimientoVacacion.objects.count(),1)
        j.fecha_final=date(2026,11,5);j.save()
        self.assertEqual(resumen(self.account)['usado'],5)
        j.anulada=True;j.save()
        self.assertEqual(resumen(self.account)['usado'],0)
        self.assertEqual(j.enlace_vacacion.movimiento.estado,'ANULADO')
    def test_media_jornada_y_intervalo_ambiguo(self):
        j=self.source(tipo_operacion=self.half,fecha_final=date(2026,11,1))
        self.assertEqual(resumen(self.account)['usado'],Decimal('.5'))
        j.fecha_final=date(2026,11,2);j.save()
        self.assertEqual(resumen(self.account)['usado'],0)
        self.assertEqual(EnlaceVacacion.objects.get(justificacion=j).estado,'PENDIENTE')
    def test_transferir_trabajador_y_cambiar_operacion(self):
        j=self.source()
        other=Trabajador.objects.create(apellidos_nombres='OTRA PERSONA',dni='00000235')
        j.trabajador=other;j.save()
        target=CuentaVacacion.objects.get(dni='00000235')
        self.assertEqual(target.asignaciones,{})
        self.assertEqual(resumen(self.account)['usado'],0)
        self.assertEqual(resumen(target)['pendiente'],-3)
        j.tipo_operacion=TipoOperacion.objects.create(nombre='Otra operación',requiere_fecha_final=False);j.save()
        self.assertEqual(resumen(target)['usado'],0)
    def test_identidad_ambigua_no_descuenta_y_reintento_resuelve(self):
        other=Trabajador.objects.create(apellidos_nombres='HOMONIMO',dni=self.worker.dni)
        j=self.source()
        self.assertFalse(MovimientoVacacion.objects.exists())
        self.assertEqual(j.enlace_vacacion.estado,'PENDIENTE')
        other.dni='00000235';other.save();j.save()
        self.assertEqual(resumen(self.account)['usado'],3)
    def test_equivalente_existente_no_se_duplica_y_otro_documento_igual_se_senala(self):
        m=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',inicio=date(2026,11,1),
            fin=date(2026,11,3),dias=3,observaciones='MEMO DE PRUEBA')
        j=self.source()
        self.assertEqual(j.enlace_vacacion.movimiento_id,m.pk)
        duplicate=self.source()
        self.assertEqual(duplicate.enlace_vacacion.estado,'PENDIENTE')
        self.assertEqual(MovimientoVacacion.objects.count(),1)
        self.assertEqual(resumen(self.account)['usado'],3)
    def test_transaccion_no_deja_justificacion_sin_consumo_ante_error(self):
        with patch('control.vacaciones_sync.MovimientoVacacion.save',side_effect=RuntimeError('prueba')):
            with self.assertRaises(RuntimeError): self.source()
        self.assertFalse(Justificacion.objects.exists());self.assertFalse(EnlaceVacacion.objects.exists())
    def test_conciliacion_historica_conserva_ajustes_y_es_idempotente(self):
        with patch('control.vacaciones_sync.sincronizar'):
            j=self.source(tipo_operacion=self.half,fecha_final=date(2026,11,1))
            suspended=self.source(fecha_movimiento=None,fecha_final=None,fuente='EXCEL')
        m=MovimientoVacacion.objects.create(cuenta=self.account,codigo='05',inicio=date(2026,11,1),
            fin=date(2026,11,1),dias=Decimal('.5'),observaciones=j.observaciones)
        initial=m.updated_at
        call_command('conciliar_vacaciones',periodo=self.period.pk,stdout=StringIO())
        self.assertFalse(EnlaceVacacion.objects.exists())
        for _ in range(2):
            call_command('conciliar_vacaciones',periodo=self.period.pk,confirmar=True,usuario=self.user.username,stdout=StringIO())
        self.assertEqual(EnlaceVacacion.objects.count(),2)
        self.assertEqual(EnlaceVacacion.objects.get(justificacion=j).estado,'SINCRONIZADO')
        self.assertEqual(EnlaceVacacion.objects.get(justificacion=suspended).estado,'EXCEPCION')
        self.assertEqual(MovimientoVacacion.objects.count(),1)
        m.refresh_from_db();self.assertEqual(m.updated_at,initial)
        suspended.fecha_movimiento=date(2026,11,4);suspended.fecha_final=date(2026,11,5);suspended.save()
        self.assertEqual(resumen(self.account)['usado'],Decimal('.5'))
        from .vacaciones_word import generar_docx
        text=ZipFile(BytesIO(generar_docx(self.account,2026,'informe'))).read('word/document.xml').decode()
        self.assertNotIn('Consultas, registro',text)
        self.assertNotIn('OBSERVACIONES',text)
        self.assertTrue(EnlaceVacacion.objects.get(justificacion=suspended).observaciones)
    def test_edicion_directa_del_control_enlazado_no_modifica_consumo(self):
        j=self.source();m=j.enlace_vacacion.movimiento
        self.client.force_login(self.user)
        for route in ('vacacion_movimiento_editar','vacacion_movimiento_eliminar'):
            r=self.client.post(reverse(route,args=[self.account.pk,m.pk]),{'version':m.updated_at.isoformat(),'dias':'99'})
            self.assertContains(r,'Movimiento vinculado a Consultas')
        self.assertEqual(resumen(self.account)['usado'],3)
    def test_formulario_web_informa_descontado_y_anula(self):
        self.client.force_login(self.user)
        r=self.client.post(reverse('justificacion_nueva'),dict(trabajador=self.worker.pk,periodo=self.period.pk,
            tipo_documento=self.doc.pk,tipo_operacion=self.op.pk,fecha_movimiento='2026-11-01',fecha_final='2026-11-03'))
        self.assertEqual(r.status_code,302)
        j=Justificacion.objects.get();self.assertEqual(resumen(self.account)['usado'],3)
        self.assertContains(self.client.get(reverse('justificacion_detalle',args=[j.pk])),'Sincronizado')
        r=self.client.post(reverse('justificacion_anular',args=[j.pk]),dict(version=j.updated_at.isoformat(),motivo='Prueba de anulación'))
        self.assertEqual(r.status_code,302);self.assertEqual(resumen(self.account)['usado'],0)
