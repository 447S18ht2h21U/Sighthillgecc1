"""Development-only confidential OAuth account verification. Never sends envelopes."""
import base64
import hashlib
import json
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from uuid import UUID
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import DocusignChallenge, DocusignVerification, Role
from .documents import canonical_hash
from .services import audit

AUTH_ORIGIN = 'https://account-d.docusign.com'
BASE_URI = 'https://demo.docusign.net'
CALLBACK_PATH = '/api/docusign/callback/'


def authorize(actor):
    if not actor.is_active or actor.role != Role.COMPTROLLER:
        raise PermissionDenied('Only the Comptroller configures Docusign sandbox verification.')


def configuration():
    client_id = os.getenv('GECC_DOCUSIGN_CLIENT_ID', '')
    account_id = os.getenv('GECC_DOCUSIGN_ACCOUNT_ID', '')
    redirect = os.getenv('GECC_DOCUSIGN_REDIRECT_URI', '')
    client_secret = os.getenv('GECC_DOCUSIGN_CLIENT_SECRET', '')
    blockers = []
    if not settings.DEBUG:
        blockers.append('Sandbox verification is development-only; production identity and credential storage are pending.')
    for key, value in [('client_id', client_id), ('account_id', account_id)]:
        try:
            UUID(value)
        except (ValueError, TypeError):
            blockers.append(f'Configure a valid Docusign {key.replace("_", " ")}.')
    if not client_secret or len(client_secret) > 4096 or '\n' in client_secret or '\r' in client_secret:
        blockers.append('Configure the client secret privately on the backend server.')
    try:
        parsed = urlsplit(redirect)
        port = parsed.port
    except ValueError:
        parsed = urlsplit('')
        port = -1
    local = settings.DEBUG and parsed.hostname in {'localhost', '127.0.0.1'}
    if (parsed.path != CALLBACK_PATH or parsed.query or parsed.fragment or parsed.username or parsed.password
            or port == -1 or parsed.hostname not in settings.ALLOWED_HOSTS
            or not (parsed.scheme == 'https' or local and parsed.scheme == 'http')):
        blockers.append('Configure the exact callback URI on an allowed GECC host; HTTPS is required except local development.')
    return {'client_id': client_id, 'account_id': account_id, 'redirect_uri': redirect,
            'client_secret': client_secret, 'blockers': blockers}


def configuration_digest(config):
    # Pins the configuration used to start the flow without retaining its secret.
    return canonical_hash({key: value for key, value in config.items() if key != 'blockers'})


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@transaction.atomic
def begin(actor, session_key, context=None):
    authorize(actor)
    config = configuration()
    if config['blockers']:
        raise ValidationError({'configuration': config['blockers']})
    if not session_key:
        raise ValidationError('An authenticated GECC session is required.')
    state = secrets.token_urlsafe(32)
    challenge = DocusignChallenge.objects.create(actor=actor, state_digest=digest(state),
        session_digest=digest(session_key), configuration_digest=configuration_digest(config),
        expires_at=timezone.now()+timedelta(minutes=10), context=context or {})
    audit(actor, 'docusign.verification_started', actor.id, {'challenge_id': str(challenge.id), 'environment': 'SANDBOX'})
    url = AUTH_ORIGIN+'/oauth/auth?'+urlencode({'response_type': 'code', 'scope': 'signature',
        'client_id': config['client_id'], 'redirect_uri': config['redirect_uri'], 'state': state})
    return {'authorization_url': url, 'expires_at': challenge.expires_at.isoformat(), 'environment': 'SANDBOX'}


@transaction.atomic
def consume(actor, session_key, state):
    authorize(actor)
    if not isinstance(state, str) or not 32 <= len(state) <= 128 or not session_key:
        raise ValidationError('Invalid or expired authorization state. Start verification again.')
    config = configuration()
    challenge = DocusignChallenge.objects.select_for_update().filter(state_digest=digest(state)).first()
    if (not challenge or challenge.consumed_at or challenge.expires_at <= timezone.now()
            or challenge.actor_id != actor.id or challenge.session_digest != digest(session_key)
            or challenge.configuration_digest != configuration_digest(config) or config['blockers']):
        raise ValidationError('Invalid or expired authorization state. Start verification again.')
    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=['consumed_at'])
    return challenge, config


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValidationError('Docusign returned an unexpected redirect. Start verification again.')


@sensitive_variables()
def request_json(path, authorization, data=None):
    # The caller cannot select a different origin or arbitrary URL.
    if path not in {'/oauth/token', '/oauth/userinfo'}:
        raise ValidationError('Unsupported Docusign verification operation.')
    payload = None if data is None else urlencode(data).encode()
    headers = {'Authorization': authorization, 'Accept': 'application/json'}
    if payload is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    request = Request(AUTH_ORIGIN+path, data=payload, headers=headers)
    try:
        with build_opener(NoRedirects()).open(request, timeout=8) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ValueError()
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError()
            return result
    except Exception:
        # Do not expose provider bodies, tokens, codes, request headers, or raw errors.
        raise ValidationError('Docusign verification could not be completed. Start verification again.') from None


@sensitive_variables()
def finish(actor, session_key, state, code, error=None):
    challenge, config = consume(actor, session_key, state)
    # Consumption commits before network calls. Errors require a fresh authorization flow.
    if error or not isinstance(code, str) or not code or len(code) > 16384:
        raise ValidationError('Authorization was declined or incomplete. Start verification again.')
    basic = base64.b64encode((config['client_id']+':'+config['client_secret']).encode()).decode()
    tokens = request_json('/oauth/token', 'Basic '+basic,
        {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': config['redirect_uri']})
    token = tokens.get('access_token')
    lifetime = tokens.get('expires_in')
    if (not isinstance(token, str) or not token or len(token) > 16384
            or str(tokens.get('token_type', '')).lower() != 'bearer'
            or not isinstance(lifetime, int) or isinstance(lifetime, bool) or not 0 < lifetime <= 86400):
        raise ValidationError('Docusign returned invalid authorization metadata. Start verification again.')
    info = request_json('/oauth/userinfo', 'Bearer '+token)
    # Explicit account selection prevents silently connecting the wrong account.
    accounts = info.get('accounts')
    if not isinstance(accounts, list):
        raise ValidationError('Docusign account verification failed.')
    matches = [a for a in accounts if isinstance(a, dict) and a.get('account_id') == config['account_id']]
    if len(matches) != 1 or matches[0].get('base_uri') != BASE_URI:
        raise ValidationError('The selected account is not the configured Docusign sandbox account.')
    try:
        subject = str(UUID(info.get('sub', '')))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Docusign user verification failed.')
    identity = {'environment': 'SANDBOX', 'client_id': config['client_id'], 'account_id': config['account_id'],
        'subject': subject, 'base_uri': BASE_URI, 'account_name': str(matches[0].get('account_name', ''))[:250],
        'verified_at': timezone.now().isoformat(), 'authorization_expires_at': (timezone.now()+timedelta(seconds=lifetime)).isoformat(),
        'purpose': challenge.context.get('operation', 'SANDBOX_DRAFT_ONLY') if challenge.context else 'ACCOUNT_VERIFICATION_ONLY', 'tokens_retained': False}
    del tokens, info, basic, code
    with transaction.atomic():
        proof = DocusignVerification.objects.create(actor=actor, challenge=challenge, identity=identity, digest=canonical_hash(identity))
        audit(actor, 'docusign.account_verified', actor.id, {'verification_id': str(proof.id), 'identity': identity, 'digest': proof.digest})
    if challenge.context.get('operation') in {'SANDBOX_SIGNING_SEND','SANDBOX_SIGNING_READ'}:
        from .signing_test import finish as finish_test
        return finish_test(actor, challenge, config, token)
    if challenge.context.get('operation') == 'SANDBOX_RECONCILIATION':
        from .reconciliation import finish as reconcile
        return reconcile(actor, challenge, config, token)
    if challenge.context:
        from .sandbox import finish_draft
        return finish_draft(actor, challenge, config, token)
    del token
    return proof


def readiness(actor):
    authorize(actor)
    config = configuration()
    proof = DocusignVerification.objects.filter(actor=actor).first()
    current = proof and proof.identity.get('client_id') == config['client_id'] and proof.identity.get('account_id') == config['account_id'] and canonical_hash(proof.identity) == proof.digest
    return {'environment': 'SANDBOX', 'ready_to_verify': not config['blockers'],
        'configuration_blockers': config['blockers'], 'callback_path': CALLBACK_PATH,
        'redirect_uri': config['redirect_uri'] if not config['blockers'] else None,
        'verification': proof.identity if current else None, 'send_available': False,
        'release_blockers': ['Reusable credential storage, signer-ready release, and provider reconciliation are pending.']}
