"""
WSGI config for academy_core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academy_core.settings')

application = get_wsgi_application()
app = application

# Auto-initialize database on Vercel serverless /tmp if fresh
if 'VERCEL' in os.environ:
    try:
        from django.core.management import call_command
        from django.db import connection
        with connection.cursor() as cursor:
            table_names = connection.introspection.table_names(cursor)
        if 'accounts_user' not in table_names:
            call_command('migrate', interactive=False)
            call_command('seed_courses', interactive=False)
    except Exception as e:
        print(f"Vercel startup init notice: {e}")

