"""Exact ordinal-slot comparison: no fuzzy matching, best-match scoring or deduplication."""
from collections import defaultdict
import re
from clause_intelligence.classification import fold

FIELDS = ('actor', 'action', 'beneficiary', 'object', 'modality', 'polarity', 'conditional',
          'trigger', 'condition', 'exception', 'deadline')
EXTRACTION = ('actor', 'action', 'beneficiary', 'object', 'trigger', 'condition', 'exception', 'deadline')


def normalize(value, field):
    if isinstance(value, (tuple, list)):
        values = sorted(normalize(v, field) for v in value if v)
        return ' | '.join(values) or None
    if value is None or type(value) is bool:
        return value
    value = re.sub(r'\s+', ' ', fold(value)).strip(' .;؛,،')
    if field in ('actor', 'beneficiary'):
        value = re.sub(r'^the\s+', '', value)
        if value.startswith('لل'):
            value = 'ال'+value[2:]
    return value or None


def empty_counts():
    return {'slots': 0, 'full_correct': 0, 'partial': 0,
            'fields': {f: {'tp': 0, 'fp': 0, 'fn': 0, 'correct': 0} for f in FIELDS},
            'actor_action_correct': 0, 'action_beneficiary_correct': 0}


def add(count, gold, predicted):
    count['slots'] += 1
    correct = {}
    for field in FIELDS:
        expected = normalize(gold.get(field), field) if gold else None
        actual = normalize(predicted.get(field), field) if predicted else None
        equal = gold is not None and predicted is not None and expected == actual
        correct[field] = equal
        count['fields'][field]['correct'] += equal
        if field in EXTRACTION:
            if expected is not None and equal:
                count['fields'][field]['tp'] += 1
            else:
                count['fields'][field]['fp'] += actual is not None
                count['fields'][field]['fn'] += expected is not None
    count['full_correct'] += all(correct.values())
    count['partial'] += any(correct.values()) and not all(correct.values())
    count['actor_action_correct'] += correct['actor'] and correct['action']
    count['action_beneficiary_correct'] += correct['action'] and correct['beneficiary']
    return [field for field, equal in correct.items() if not equal]


def finalize(count):
    result = {'slots': count['slots'], 'full_correct': count['full_correct'], 'partial': count['partial'],
              'full_role_tuple_accuracy': count['full_correct']/count['slots'] if count['slots'] else None,
              'actor_action_pair_accuracy': count['actor_action_correct']/count['slots'] if count['slots'] else None,
              'action_beneficiary_pair_accuracy': count['action_beneficiary_correct']/count['slots'] if count['slots'] else None}
    for field, values in count['fields'].items():
        tp, fp, fn = (values[k] for k in ('tp', 'fp', 'fn'))
        result[field] = {**values, 'accuracy': values['correct']/count['slots'] if count['slots'] else None}
        if field in EXTRACTION:
            result[field].update(precision=tp/(tp+fp) if tp+fp else None, recall=tp/(tp+fn) if tp+fn else None,
                                 f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
    return result
