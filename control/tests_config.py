"""La configuración se prueba en procesos aislados, sin contactar servidores."""
import json
import os
from pathlib import Path
import subprocess
import sys
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import FileResponse, HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from .excel_forms import SubirExcelForm
from .middleware import LimitesPlataformaMiddleware
from .xlsx_parser import ErrorXLSX, leer_archivo


class ConfiguracionTests(SimpleTestCase):
    def config(self, **changes):
        env = os.environ.copy()
        for key in ('DATABASE_URL', 'SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS', 'VERCEL'):
            env.pop(key, None)
        env.update(changes)
        code = '''
import json
from config import settings as s
db = s.DATABASES['default']
print(json.dumps({
    'engine': db['ENGINE'], 'options': db.get('OPTIONS'),
    'age': db.get('CONN_MAX_AGE'), 'cursors': db.get('DISABLE_SERVER_SIDE_CURSORS'),
    'health': db.get('CONN_HEALTH_CHECKS'),
    'proxy': s.SECURE_PROXY_SSL_HEADER, 'upload': s.XLSX_UPLOAD_MAX_BYTES,
    'secure': s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE and s.SECURE_SSL_REDIRECT,
    'storage': s.STORAGES['staticfiles']['BACKEND'],
}))
'''
        return subprocess.run([sys.executable, '-c', code], env=env,
                              cwd=Path(__file__).resolve().parent.parent,
                              capture_output=True, text=True)

    def production(self, **changes):
        values = dict(DEBUG='False', SECRET_KEY='abc123XYZ!@#' * 8,
                      ALLOWED_HOSTS='asistencias.example.org',
                      CSRF_TRUSTED_ORIGINS='https://asistencias.example.org',
                      DATABASE_URL='postgresql://test:password@localhost/dret?sslmode=require')
        values.update(changes)
        return self.config(**values)

    def test_sqlite_solo_desarrollo(self):
        result = self.config(DEBUG='True')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['engine'], 'django.db.backends.sqlite3')
        self.assertNotEqual(self.production(DATABASE_URL='').returncode, 0)

    def test_postgres_pooling_tls_y_estaticos(self):
        result = self.production(VERCEL='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(config['engine'], 'django.db.backends.postgresql')
        self.assertEqual(config['age'], 0)
        self.assertTrue(config['health']); self.assertTrue(config['cursors'])
        self.assertIsNone(config['options']['prepare_threshold'])
        self.assertEqual(config['options']['sslmode'], 'require')
        self.assertEqual(config['proxy'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertTrue(config['secure'])
        self.assertIn('CompressedManifest', config['storage'])
        self.assertEqual(config['upload'], 4_000_000)
        result = self.production(DATABASE_URL='postgres://test:password@localhost/dret')
        self.assertEqual(json.loads(result.stdout)['options']['sslmode'], 'require')
        self.assertIsNone(json.loads(result.stdout)['proxy'])

    def test_produccion_rechaza_configuraciones_inseguras(self):
        for changes in (
            {'SECRET_KEY': ''}, {'SECRET_KEY': 'corta'}, {'ALLOWED_HOSTS': ''},
            {'ALLOWED_HOSTS': '*'}, {'ALLOWED_HOSTS': '.vercel.app'},
            {'CSRF_TRUSTED_ORIGINS': 'http://asistencias.example.org'},
            {'CSRF_TRUSTED_ORIGINS': 'https://*.vercel.app'},
            {'DATABASE_URL': 'sqlite:///db.sqlite3'},
            {'DATABASE_URL': 'postgresql://test:password@localhost/dret?sslmode=disable'},
            {'VERCEL': '1', 'DEBUG': 'True'},
        ):
            with self.subTest(changes=tuple(changes)):
                self.assertNotEqual(self.production(**changes).returncode, 0)

    def test_url_invalida_no_muestra_credenciales(self):
        result = self.production(DATABASE_URL='invalid://test:SECRETO_QUE_NO_DEBE_APARECER@localhost/dret')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('SECRETO_QUE_NO_DEBE_APARECER', result.stderr)


@override_settings(HTTP_REQUEST_MAX_BYTES=100, HTTP_RESPONSE_MAX_BYTES=100,
                   STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class LimitesTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/')

    def test_entrada_excesiva_no_ejecuta_vista(self):
        def vista(request):
            self.fail('No debe procesar el archivo')
        self.request.META['CONTENT_LENGTH'] = '101'
        response = LimitesPlataformaMiddleware(vista)(self.request)
        self.assertEqual(response.status_code, 413)
        self.assertContains(response, 'Tamaño excedido', status_code=413)

    def test_salida_html_y_archivo_excesivos_no_se_truncan(self):
        for response in (HttpResponse('x' * 101), FileResponse(BytesIO(b'x' * 101))):
            result = LimitesPlataformaMiddleware(lambda r: response)(self.request)
            self.assertEqual(result.status_code, 413)
            self.assertTrue(response.closed)
            self.assertEqual(result['Cache-Control'], 'private, no-store')

    def test_archivo_dentro_del_limite_se_conserva(self):
        response = FileResponse(BytesIO(b'x' * 100))
        self.assertIs(LimitesPlataformaMiddleware(lambda r: response)(self.request), response)
        response.close()

    @override_settings(XLSX_UPLOAD_MAX_BYTES=10)
    def test_importador_y_formulario_comparten_limite(self):
        archivo = SimpleUploadedFile('sintetico.xlsx', b'x' * 11)
        form = SubirExcelForm()
        form.cleaned_data = {'archivo': archivo}
        from django.forms import ValidationError
        with self.assertRaises(ValidationError):
            form.clean_archivo()
        with self.assertRaises(ErrorXLSX):
            leer_archivo(archivo)
