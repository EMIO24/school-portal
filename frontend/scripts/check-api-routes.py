"""Run inside the backend container; argv[1] is base64-encoded candidate JSON.

Only resolves URL patterns. Does not authenticate, send HTTP requests, or write data.
"""
import base64
import json
import os
import sys
from pathlib import Path

if __file__ != '<stdin>':
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
import django

django.setup()
from django.urls import Resolver404, resolve

rows = json.loads(base64.b64decode(sys.argv[1])) if len(sys.argv) > 1 else json.load(sys.stdin)
for row in rows:
    try:
        match = resolve(row['path'])
        row['resolves'] = True
        actions = getattr(match.func, 'actions', None)
        view = getattr(match.func, 'cls', None) or getattr(match.func, 'view_class', None)
        if actions is not None:
            methods = [m for m in actions if m in view.http_method_names]
        elif view:
            methods = [m for m in view.http_method_names if hasattr(view, m)]
        else:
            methods = ['get']
        row['allowed_methods'] = [m.upper() for m in methods]
        row['method_allowed'] = row['method'] in row['allowed_methods']
    except Resolver404:
        row['resolves'] = False
        row['method_allowed'] = False
print(json.dumps(rows))
