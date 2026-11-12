"""Set metrics with explicit denominators. No fixture-specific prediction logic."""
def counts(expected, predicted):
    return {'tp': len(expected & predicted), 'fp': len(predicted - expected), 'fn': len(expected - predicted)}


def scores(count):
    tp, fp, fn = (count[k] for k in ('tp', 'fp', 'fn'))
    precision = tp/(tp+fp) if tp+fp else None
    recall = tp/(tp+fn) if tp+fn else None
    return {**count, 'precision': precision, 'recall': recall,
            'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'false_discovery_rate': fp/(tp+fp) if tp+fp else None,
            'false_negative_rate': fn/(tp+fn) if tp+fn else None}
