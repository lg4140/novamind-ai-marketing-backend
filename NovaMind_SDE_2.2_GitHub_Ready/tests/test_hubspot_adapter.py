"""Contract-style tests using httpx.MockTransport; never use live CRM credentials."""
import httpx
from app.core.config import get_settings
from app.integrations.hubspot import HubSpotCRM


def test_mock_crm_no_network():
    assert HubSpotCRM().upsert_contacts([{'email':'nobody@example.test'}]) == {
        'mode': 'mock', 'contacts_prepared': 1}


def test_hubspot_batches_and_partial_response(monkeypatch):
    monkeypatch.setenv('CRM_PROVIDER', 'hubspot')
    monkeypatch.setenv('ALLOW_LIVE_CRM_SYNC', 'true')
    monkeypatch.setenv('HUBSPOT_ACCESS_TOKEN', 'fake-test-only')
    get_settings.cache_clear()
    batch_sizes = []
    def handler(request: httpx.Request) -> httpx.Response:
        import json
        payload=json.loads(request.content)
        batch_sizes.append(len(payload['inputs']))
        if len(batch_sizes) == 2:
            return httpx.Response(207, json={'errors':[{'category':'VALIDATION_ERROR'}]})
        return httpx.Response(200, json={'results':[]})
    real_client=httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real_client(
        transport=httpx.MockTransport(handler), headers=kw.get('headers')))
    contacts = [{'email':f'user{i}@example.test','firstname':'F','lastname':'L',
                 'company':'C','persona_segment':'ops_lead'} for i in range(102)]
    result=HubSpotCRM().upsert_contacts(contacts)
    assert batch_sizes == [100,2]
    assert result['provider_error_records']==1
    assert result['requires_reconciliation'] is True
