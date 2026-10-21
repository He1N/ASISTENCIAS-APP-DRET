import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase
from scripts.postgres_backup import checksum, execute


@patch.dict(os.environ, {'DIRECT_DATABASE_URL': 'postgresql://test:synthetic@localhost/dret'})
class RespaldoTests(SimpleTestCase):
    def test_dump_privado_checksum_y_sin_credenciales_en_argumentos(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'test.dump'
            def dump(args, **kwargs):
                self.assertNotIn('synthetic', ' '.join(args))
                self.assertNotIn('PGPASSWORD', kwargs['env'])
                passfile = Path(kwargs['env']['PGPASSFILE'])
                self.assertEqual(passfile.stat().st_mode & 0o777, 0o600)
                kwargs['stdout'].write(b'respaldo sintetico')
            with patch('scripts.postgres_backup.subprocess.run', side_effect=dump):
                execute(path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.with_name(path.name + '.sha256').read_text().strip(), checksum(path))
            with self.assertRaises(ValueError):
                execute(path)
            self.assertEqual(path.read_bytes(), b'respaldo sintetico')

    def test_fallo_del_cliente_no_deja_respaldo_parcial(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'test.dump'
            with patch('scripts.postgres_backup.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'pg_dump')):
                with self.assertRaises(subprocess.CalledProcessError):
                    execute(path)
            self.assertFalse(path.exists())

    @patch.dict(os.environ, {'RESTORE_DATABASE_URL': 'postgresql://test:synthetic@localhost/destino'})
    def test_restore_rechaza_checksum_alterado_y_destino_ocupado(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'test.dump'; path.write_bytes(b'sintetico')
            sidecar = path.with_name(path.name + '.sha256'); sidecar.write_text('invalido')
            with patch('scripts.postgres_backup.psycopg.connect') as connect:
                with self.assertRaises(ValueError):
                    execute(path, restore=True)
                connect.assert_not_called()
                sidecar.write_text(checksum(path))
                connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = (True,)
                with patch('scripts.postgres_backup.subprocess.run') as run:
                    with self.assertRaises(ValueError):
                        execute(path, restore=True)
                    run.assert_not_called()

    @patch.dict(os.environ, {'DIRECT_DATABASE_URL': 'postgresql://test:synthetic@ep-test-pooler.neon.tech/dret'})
    def test_no_admite_pooler_para_respaldos(self):
        with self.assertRaises(ValueError):
            execute(Path('no-se-crea.dump'))
