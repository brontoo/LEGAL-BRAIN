"""Allowlisted counts and elapsed time only; no document, excerpts, prompts or names."""
def summary(clauses, entities, obligations, findings, elapsed_ms):
    return {'clause_count': len(clauses), 'entity_count': len(entities), 'obligation_count': len(obligations),
            'finding_count': len(findings), 'elapsed_ms': round(elapsed_ms, 3), 'mode': 'deterministic_baseline'}
