"""Read-only aggregate provenance audit. Never performs metadata backfill."""
import argparse
import json
import os
from retrieval.schemas import FAMILIES

KEYS=('records','known_jurisdiction','unknown_jurisdiction','with_source_url','without_source_url',
      'with_instrument_id','with_temporal_metadata','manual_review')


def audit(client,family):
    payload=client.rpc('hybrid_metadata_audit_v1',{'p_family':family}).execute().data
    # Supabase scalar-json RPC shape; test clients may return the scalar under audit.
    if isinstance(payload,list) and len(payload)==1 and 'audit' in payload[0]:payload=payload[0]['audit']
    if not isinstance(payload,dict) or set(payload)!=set(KEYS) or any(type(v) is not int or v<0 for v in payload.values()):
        raise ValueError('Unexpected aggregate audit contract')
    return {key:payload[key] for key in KEYS}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family',choices=FAMILIES)
    args=parser.parse_args()
    if not all(os.environ.get(key) for key in ('SUPABASE_URL','SUPABASE_KEY')):
        raise SystemExit('BLOCKED: configure authorized read-only Supabase access securely; no values are accepted in chat/arguments')
    try:
        from supabase import create_client
        client=create_client(os.environ['SUPABASE_URL'],os.environ['SUPABASE_KEY'])
        results={family:audit(client,family) for family in ([args.family] if args.family else FAMILIES)}
    except Exception:
        raise SystemExit('Audit unavailable; check authorized access and the manual migration. Provider details withheld.') from None
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
