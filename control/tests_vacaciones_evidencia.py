from io import BytesIO

from PIL import Image
from reportlab.pdfgen import canvas
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import CuentaVacacion, EvidenciaVacacion, HistorialCambio, MovimientoVacacion


class EvidenciaVacacionTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser('editor', password='prueba')
        self.client.force_login(admin)
        self.cuenta = CuentaVacacion.objects.create(nombre='PERSONA DE PRUEBA', dni='00000001')
        self.movimiento = MovimientoVacacion.objects.create(cuenta=self.cuenta, codigo='05', dias=1)
        args = [self.cuenta.pk, self.movimiento.pk]
        self.subir = reverse('vacacion_evidencia_subir', args=args)
        self.ver = reverse('vacacion_evidencia_ver', args=args)
        self.ficha = reverse('vacacion_ficha', args=args[:1])

    def test_subir_pdf_y_verlo_desde_ficha_sin_sobrescribir(self):
        self.assertContains(self.client.get(self.ficha), 'Subir evidencia')
        data = BytesIO()
        pdf = canvas.Canvas(data)
        pdf.drawString(50, 50, 'Firma de prueba')
        pdf.save()
        contenido = data.getvalue()
        for _ in range(2):
            archivo = SimpleUploadedFile('firmado.pdf', contenido, content_type='application/pdf')
            self.assertRedirects(self.client.post(self.subir, {'archivo': archivo}), self.ficha)
        self.assertEqual(EvidenciaVacacion.objects.count(), 1)
        self.assertEqual(HistorialCambio.objects.filter(accion='subir_evidencia').count(), 1)
        self.assertContains(self.client.get(self.ficha), 'Ver evidencia')
        self.assertNotContains(self.client.get(self.ficha), 'Subir evidencia')
        response = self.client.get(self.ver)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Content-Disposition'], 'inline; filename="firmado.pdf"')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response.content, contenido)

    def test_validacion_imagen_limite_y_permisos(self):
        html = SimpleUploadedFile('falso.png', b'<svg onload="alert(1)"/>', content_type='image/png')
        self.assertContains(self.client.post(self.subir, {'archivo': html}), 'imagen JPG, PNG o WebP válida')
        grande = SimpleUploadedFile('grande.pdf', b'0' * 4_000_001, content_type='application/pdf')
        self.assertContains(self.client.post(self.subir, {'archivo': grande}), 'supera los 4 MB')
        self.assertFalse(EvidenciaVacacion.objects.exists())

        contenido = BytesIO()
        Image.new('RGB', (4, 4)).save(contenido, format='PNG')
        archivo = SimpleUploadedFile('escaneo.png', contenido.getvalue())
        self.client.post(self.subir, {'archivo': archivo})
        cuenta_ajena = CuentaVacacion.objects.create(nombre='OTRA PERSONA', dni='00000002')
        url_ajena = reverse('vacacion_evidencia_ver', args=[cuenta_ajena.pk, self.movimiento.pk])
        self.assertEqual(self.client.get(url_ajena).status_code, 404)

        consulta = get_user_model().objects.create_user('consulta')
        self.client.force_login(consulta)
        self.assertEqual(self.client.get(self.ver).status_code, 403)
        consulta.user_permissions.add(Permission.objects.get(codename='view_cuentavacacion'))
        self.assertEqual(self.client.get(self.subir).status_code, 403)
        response = self.client.get(self.ver)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response.content, contenido.getvalue())
