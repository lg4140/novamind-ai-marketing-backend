"""Contact synchronization is explicit opt-in. No live marketing send exists.

Batch responses and transient failures are accounted for; real portal permissions,
rate limits, custom properties and incomplete batch outcomes require staging checks.
"""
import time
from app.core.config import get_settings


class HubSpotCRM:
    BATCH_SIZE = 100
    MAX_RETRIES = 3

    def upsert_contacts(self, contacts: list[dict]) -> dict:
        settings = get_settings()
        if settings.crm_provider != 'hubspot' or not settings.allow_live_crm_sync:
            return {'mode': 'mock', 'contacts_prepared': len(contacts)}
        import httpx
        url = f'{settings.hubspot_base_url.rstrip("/")}/crm/v3/objects/contacts/batch/upsert'
        sent = 0
        failed_items = 0
        batches = 0
        item_statuses = []
        confirmed_count = 0
        unconfirmed_count = 0
        with httpx.Client(timeout=20.0, headers={
            'Authorization': f'Bearer {settings.hubspot_access_token}',
            'Content-Type': 'application/json',
        }) as client:
            for start in range(0, len(contacts), self.BATCH_SIZE):
                batch = contacts[start:start + self.BATCH_SIZE]
                inputs = [{'id': c['email'], 'idProperty': 'email', 'properties': {
                    k: c[k] for k in ('email', 'firstname', 'lastname', 'company', 'persona_segment')
                }} for c in batch]
                response = None
                for attempt in range(self.MAX_RETRIES):
                    try:
                        response = client.post(url, json={'inputs': inputs})
                        if response.status_code not in (429, 500, 502, 503, 504):
                            response.raise_for_status()
                            break
                        response.raise_for_status()
                    except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError):
                        # 4xx other than 429: permanent input/permission error.
                        if response is not None and response.status_code not in (429, 500, 502, 503, 504):
                            raise
                        if attempt + 1 == self.MAX_RETRIES:
                            raise
                        retry_after = response.headers.get('Retry-After') if response else None
                        delay = float(retry_after) if retry_after and retry_after.isdecimal() else 2 ** attempt
                        time.sleep(min(30, delay))
                if response is None:
                    raise RuntimeError('HubSpot did not return a response.')
                body = response.json()
                if not isinstance(body, dict):
                    raise RuntimeError('Unexpected HubSpot batch response.')
                # 207/multi-status and errors must not be treated as full successes.
                errors = body.get('errors') or []
                if not isinstance(errors, list):
                    raise RuntimeError('Unexpected HubSpot batch error structure.')
                results = body.get('results') or []
                if not isinstance(results, list):
                    raise RuntimeError('Unexpected HubSpot batch results structure.')
                confirmed = {}
                for record in results:
                    if not isinstance(record, dict):
                        continue
                    address = (record.get('properties') or {}).get('email')
                    if isinstance(address, str):
                        confirmed[address.casefold()] = record.get('id')
                # Error payloads differ across HubSpot features. Never infer an
                # individual failure from an uncorrelated errors array.
                for contact in batch:
                    email = contact['email'].casefold()
                    if email in confirmed:
                        confirmed_count += 1
                        item_statuses.append({'email': email, 'status': 'CONFIRMED',
                                              'provider_record_id': confirmed[email]})
                    else:
                        unconfirmed_count += 1
                        item_statuses.append({'email': email, 'status': 'UNCONFIRMED',
                                              'provider_record_id': None})
                failed_items += len(errors)
                sent += len(batch)
                batches += 1
        return {'mode': 'hubspot', 'contacts_prepared': len(contacts),
                'submitted_count': sent, 'confirmed_count': confirmed_count,
                'unconfirmed_count': unconfirmed_count,
                'item_results': item_statuses, 'provider_error_records': failed_items,
                'batches': batches, 'requires_reconciliation': unconfirmed_count > 0 or failed_items > 0}


class MockMailer:
    """No outbound network call or delivery claim."""
    def send(self, _contact: dict, _newsletter: dict) -> str:
        return 'SIMULATED'
