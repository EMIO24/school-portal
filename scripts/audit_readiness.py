"""Disposable readiness probes. Run: python scripts/audit_readiness.py.
Assertions describe safe behavior; current failures are unresolved audit findings.
Uses in-memory SQLite and mocked SMS, never deployment data.
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.test'
import django
django.setup()
from django.test.runner import DiscoverRunner
from accounts.test_readiness import ReadinessChecks

if __name__ == '__main__':
    sys.exit(bool(DiscoverRunner(verbosity=2, interactive=False).run_tests(['accounts.test_readiness'])))
