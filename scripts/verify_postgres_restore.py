"""CI check for the isolated portal_restore_ci database; never changes data."""
import os
import psycopg2

with psycopg2.connect(os.environ['DATABASE_URL']) as source:
    with source.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM tenants_school')
        expected = cursor.fetchone()[0]
from urllib.parse import urlsplit, urlunsplit
url = urlsplit(os.environ['DATABASE_URL'])
restored_url = urlunsplit((url.scheme, url.netloc, '/portal_restore_ci', url.query, url.fragment))
with psycopg2.connect(restored_url) as restored:
    with restored.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM tenants_school')
        assert cursor.fetchone()[0] == expected >= 2
        cursor.execute("SELECT COUNT(*) FROM tenants_school WHERE slug IN ('recovery-a', 'recovery-b')")
        assert cursor.fetchone()[0] == 2
print('PostgreSQL recovery verified: both schools restored.')
