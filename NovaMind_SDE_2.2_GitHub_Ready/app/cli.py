"""Run local no-API-key demonstration, seed data, or dispatch Celery outbox."""
import argparse
import csv
import json
import logging
import time
from pathlib import Path
from uuid import uuid4
from app.db.session import init_database, session_factory
from app.schemas import CampaignCreate, ContactIn
from app.services.campaigns import (approve_campaign, create_campaign,
    import_contacts, process_dispatch, process_generation, recover_stale)
from app.services.analytics import campaign_metrics, analyze_campaign

def seed_csv(path: str) -> int:
    with open(path, newline='',encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    # Important: existing original CSV does not prove consent. Missing means False.
    items = [ContactIn(**{**row,'marketing_consent':str(row.get('marketing_consent','false')).lower() == 'true'})
             for row in rows]
    with session_factory()() as db:
        return import_contacts(db, items)

def demo():
    sample = Path(__file__).resolve().parents[1] / 'data' / 'sample_contacts.csv'
    imported = seed_csv(str(sample))
    with session_factory()() as db:
        campaign, _ = create_campaign(db, CampaignCreate(topic='AI in creative automation'),
                                       'demo-'+str(uuid4()))
        process_generation(db,campaign.id)
        approve_campaign(db,campaign.id)  # Demo convenience; real API requires explicit review.
        process_dispatch(db,campaign.id)
        results = campaign_metrics(db,campaign.id)
        summary = analyze_campaign(db,campaign.id)
        print(json.dumps({'imported':imported,'campaign_id':campaign.id,
                          'metrics':results,'summary':summary},indent=2))

def main():
    parser = argparse.ArgumentParser(description='NovaMind engineering demo/maintenance')
    parser.add_argument('command',choices=['demo','seed','dispatch-outbox','recover-stale'])
    parser.add_argument('--csv',default='data/sample_contacts.csv')
    parser.add_argument('--loop',action='store_true')
    args = parser.parse_args()
    init_database()
    if args.command == 'demo': demo()
    elif args.command == 'seed': print(f'Imported {seed_csv(args.csv)} contacts.')
    elif args.command == 'recover-stale':
        while True:
            try:
                with session_factory()() as db:
                    print(f'Recovered {recover_stale(db)} stale campaigns.', flush=True)
            except Exception as exc:
                logging.getLogger('novamind.recovery').warning(
                    'Recovery pass failed: %s', type(exc).__name__)
                if not args.loop:
                    raise
            if not args.loop:
                break
            time.sleep(10)
    elif args.command == 'dispatch-outbox':
        from app.workers.outbox import publish_pending
        logger = logging.getLogger('novamind.dispatcher')
        logging.basicConfig(level=logging.INFO)
        while True:
            try:
                print(f'Published {publish_pending()} event(s).', flush=True)
            except Exception as exc:
                logger.warning('Dispatcher iteration failed: %s', type(exc).__name__)
                if not args.loop:
                    raise
            if not args.loop:
                break
            time.sleep(2)

if __name__ == '__main__':
    main()
