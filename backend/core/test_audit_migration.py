"""Upgrade a separate SQLite fixture containing a genuine pre-context chain."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from django.test import SimpleTestCase


class AuditUpgradeTests(SimpleTestCase):
    def test_legacy_chain_survives_upgrade_and_guards_remain_installed(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            env = dict(os.environ, GECC_DEV='1', GECC_SQLITE_PATH=str(Path(directory) / 'legacy.sqlite3'))
            for name in ['PGHOST', 'PGDATABASE', 'PGUSER', 'PGPORT', 'PGPASSWORD']:
                env.pop(name, None)
            def run(*args):
                result = subprocess.run([sys.executable, str(root / 'manage.py'), *args], env=env, text=True, capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout
            run('migrate', 'core', '0009', '--noinput')
            run('shell', '-c', '''
import hashlib,json,uuid
from core.models import User,Role,AuditEvent,AuditHead
u=User.objects.create_user(username='legacy',role=Role.SALES_ASSOCIATE,initials='LG')
entity=uuid.uuid4(); payload={'note':'Unchanged legacy fixture'}
body={'sequence':1,'actor':str(u.id),'action':'customer.updated','entity_id':str(entity),'payload':payload,'previous_hash':'0'*64}
digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
AuditEvent.objects.create(sequence=1,actor=u,action=body['action'],entity_id=entity,payload=payload,previous_hash='0'*64,digest=digest)
AuditHead.objects.filter(pk=1).update(sequence=1,digest=digest)
''')
            run('migrate', '--noinput')
            run('shell', '-c', '''
from django.db import transaction,DatabaseError
from core.models import AuditEvent
from core.services import audit
from core.audit_context import NO_RESOURCE
old=AuditEvent.objects.get(sequence=1)
assert old.payload=={'note':'Unchanged legacy fixture'}
before=(old.id,old.digest,old.actor_id,old.created_at)
audit(None,'auth.login_failed',NO_RESOURCE,{'reason':'Synthetic invalid credentials'})
old.refresh_from_db();assert (old.id,old.digest,old.actor_id,old.created_at)==before
for operation in ['update','delete']:
 try:
  with transaction.atomic():
   qs=AuditEvent.objects.filter(pk=old.pk)
   qs.update(payload={}) if operation=='update' else qs.delete()
 except DatabaseError:
  pass
 else:
  raise AssertionError('Audit guard missing')
''')
            self.assertIn('Verified 2 audit events.', run('verify_audit'))
