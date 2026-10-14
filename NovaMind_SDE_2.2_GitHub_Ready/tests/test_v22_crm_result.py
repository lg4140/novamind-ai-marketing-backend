"""No live HubSpot calls. Confirmations require IDs correlated to contact email."""
import json
import httpx
from app.core.config import get_settings
from app.integrations.hubspot import HubSpotCRM


def test_crm_does_not_treat_200_empty_results_as_confirmed(monkeypatch):
    monkeypatch.setenv('CRM_PROVIDER', 'hubspot')
    monkeypatch.setenv('ALLOW_LIVE_CRM_SYNC', 'true')
    monkeypatch.setenv('HUBSPOT_ACCESS_TOKEN', 'fake-token-for-test')
    get_settings.cache_clear()
    client = httpx.Client
    def handler(request):
        submitted = json.loads(request.content)['inputs']
        return httpx.Response(200, json={'results': [
            {'id': 'crm-1', 'properties': {'email': submitted[0]['id']}}
        ]})
    monkeypatch.setattr(httpx, 'Client', lambda **opts: client(
        transport=httpx.MockTransport(handler), headers=opts.get('headers')))
    contacts = [{'email': e, 'firstname': 'F', 'lastname': 'L',
                  'company': 'Agency', 'persona_segment': 'ops_lead'}
                for e in ['one@example.test', 'two@example.test']]
    result = HubSpotCRM().upsert_contacts(contacts)
    assert result['submitted_count'] == 2
    assert result['confirmed_count'] == 1
    assert result['unconfirmed_count'] == 1
    assert result['requires_reconciliation'] is True
    assert [x['status'] for x in result['item_results']] == ['CONFIRMED', 'UNCONFIRMED']
