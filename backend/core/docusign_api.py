from django.http import JsonResponse
from django.views.decorators.debug import sensitive_variables
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from . import docusign


def private(response):
    response['Cache-Control'] = 'private, no-store'
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@api_view(['GET'])
def status(request):
    return private(Response(docusign.readiness(request.user)))


@api_view(['POST'])
def connect(request):
    return private(Response(docusign.begin(request.user, request.session.session_key)))


@api_view(['GET'])
@sensitive_variables()
def callback(request):
    # Do not render tracebacks containing authorization codes or request data.
    try:
        proof = docusign.finish(request.user, request.session.session_key,
            request.query_params.get('state'), request.query_params.get('code'), request.query_params.get('error'))
        if isinstance(proof, dict):
            return private(Response(proof))
        return private(Response({'status': 'SANDBOX_ACCOUNT_VERIFIED', 'verification_id': str(proof.id),
            'message': 'Sandbox account verified. No tokens were retained and no signature requests were sent. Return to GECC and refresh Docusign status.'}))
    except APIException as exc:
        return private(Response({'detail': exc.detail}, status=exc.status_code))
    except Exception:
        return private(JsonResponse({'detail': 'Sandbox verification could not be completed. Start again from GECC.'}, status=502))
