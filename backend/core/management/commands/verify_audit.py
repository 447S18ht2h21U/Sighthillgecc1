import hashlib
import json
from django.core.management.base import BaseCommand, CommandError
from core.models import AuditEvent, AuditHead
class Command(BaseCommand):
    help = 'Verify the committed audit hash chain (external anchoring is a later integration).'
    def handle(self, *args, **options):
        previous, sequence = '0' * 64, 0
        for event in AuditEvent.objects.order_by('sequence').iterator():
            sequence += 1
            body = {'sequence': event.sequence, 'actor': str(event.actor_id), 'action': event.action, 'entity_id': str(event.entity_id), 'payload': event.payload, 'previous_hash': event.previous_hash}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            if event.sequence != sequence or event.previous_hash != previous or event.digest != digest:
                raise CommandError(f'Invalid audit event {event.id}')
            previous = digest
        head = AuditHead.objects.get(pk=1)
        if (head.sequence, head.digest) != (sequence, previous):
            raise CommandError('Audit head does not match chain.')
        self.stdout.write(f'Verified {sequence} audit events.')
