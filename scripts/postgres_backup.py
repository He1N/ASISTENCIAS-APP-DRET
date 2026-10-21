"""Respaldo PostgreSQL y restauración únicamente en una base vacía.

Requiere clientes pg_dump/pg_restore del mismo major que el servidor.
No imprime URLs, no pasa contraseñas por argumentos y no carga archivos .env.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

import psycopg
from psycopg.conninfo import conninfo_to_dict


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def execute(path, restore=False):
    variable = 'RESTORE_DATABASE_URL' if restore else 'DIRECT_DATABASE_URL'
    url = os.environ.get(variable, '')
    if not url:
        raise ValueError(f'Configure {variable} con una conexión directa.')
    params = conninfo_to_dict(url)
    if not all(params.get(key) for key in ('host', 'dbname', 'user')):
        raise ValueError('La conexión debe indicar host, usuario y base.')
    if '-pooler' in params['host']:
        raise ValueError('Use la conexión directa de Neon, sin pooler.')
    sidecar = path.with_name(path.name + '.sha256')
    if restore:
        if not sidecar.exists() or checksum(path) != sidecar.read_text().strip():
            raise ValueError('Falta el checksum o el respaldo fue alterado.')
        with psycopg.connect(url, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
                    AND c.relkind IN ('r','p','v','m','S','f'))""")
                if cursor.fetchone()[0]:
                    raise ValueError('La restauración requiere una base nueva y vacía.')
    elif path.exists() or sidecar.exists():
        raise ValueError('El destino ya existe; no se sobrescriben respaldos.')

    with tempfile.TemporaryDirectory(prefix='dret-pg-') as directory:
        passfile = Path(directory) / 'pgpass'
        parts = [params['host'], params.get('port', '5432'), params['dbname'],
                 params['user'], params.get('password', '')]
        if any('\n' in part or '\r' in part for part in parts):
            raise ValueError('La conexión contiene caracteres incompatibles con pgpass.')
        passfile.touch(mode=0o600)
        passfile.write_text(':'.join(part.replace('\\', '\\\\').replace(':', '\\:') for part in parts) + '\n')
        env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
        env['PGPASSFILE'] = str(passfile)
        mapping = {'host': 'PGHOST', 'port': 'PGPORT', 'dbname': 'PGDATABASE', 'user': 'PGUSER',
                   'sslmode': 'PGSSLMODE', 'sslrootcert': 'PGSSLROOTCERT', 'sslcert': 'PGSSLCERT',
                   'sslkey': 'PGSSLKEY', 'channel_binding': 'PGCHANNELBINDING', 'options': 'PGOPTIONS'}
        env.update({variable: params[key] for key, variable in mapping.items() if key in params})
        env['PGCONNECT_TIMEOUT'] = '10'
        if restore:
            subprocess.run(['pg_restore', '--no-owner', '--no-acl', '--exit-on-error',
                            '--single-transaction', '--dbname', params['dbname'], str(path)],
                           env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Abrir fuera del bloque de limpieza: un archivo preexistente nunca
            # debe eliminarse, incluso si aparece después de la comprobación.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            checksum_created = False
            try:
                with os.fdopen(descriptor, 'wb') as output:
                    subprocess.run(['pg_dump', '--format=custom', '--no-owner', '--no-acl'],
                                   env=env, check=True, stdout=output, stderr=subprocess.DEVNULL)
                descriptor = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                checksum_created = True
                with os.fdopen(descriptor, 'w') as output:
                    output.write(checksum(path) + '\n')
            except BaseException:
                path.unlink(missing_ok=True)
                if checksum_created:
                    sidecar.unlink(missing_ok=True)
                raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--restore', action='store_true', help='Restaurar en RESTORE_DATABASE_URL vacía')
    arguments = parser.parse_args()
    try:
        execute(arguments.archivo, arguments.restore)
    except (ValueError, OSError, psycopg.Error, subprocess.SubprocessError):
        # Los errores del cliente pueden contener nombres o credenciales.
        parser.exit(1, 'Operación fallida: revise conexión directa, permisos, clientes PostgreSQL, checksum y destino vacío. No se muestran credenciales.\n')
    print('Restauración completada.' if arguments.restore else 'Respaldo y checksum creados; ensaye la restauración antes de considerarlo verificable.')
