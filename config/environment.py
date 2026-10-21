"""Configuración sin conexiones ni efectos sobre la base al importar."""
import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def database_config(base_dir, debug):
    url = os.getenv('DATABASE_URL', '').strip()
    if not url:
        if not debug or os.getenv('VERCEL') == '1':
            raise ImproperlyConfigured('Configure DATABASE_URL PostgreSQL en producción.')
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': base_dir / 'db.sqlite3'}
    try:
        config = dj_database_url.parse(url, conn_max_age=0, conn_health_checks=True)
    except (ValueError, KeyError):
        raise ImproperlyConfigured('DATABASE_URL no es una URL PostgreSQL válida.') from None
    if config['ENGINE'] != 'django.db.backends.postgresql' or not config.get('NAME'):
        raise ImproperlyConfigured('DATABASE_URL debe identificar una base PostgreSQL.')
    options = config.setdefault('OPTIONS', {})
    if not debug:
        options.setdefault('sslmode', 'require')
        if options['sslmode'] not in ('require', 'verify-ca', 'verify-full'):
            raise ImproperlyConfigured('PostgreSQL requiere TLS en producción.')
    options.setdefault('connect_timeout', 10)
    options['prepare_threshold'] = None
    config['DISABLE_SERVER_SIDE_CURSORS'] = True
    return config
