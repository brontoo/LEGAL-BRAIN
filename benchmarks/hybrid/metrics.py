"""Explicit eligible-only metrics, with fixed-denominator Precision@K."""
import math


def score(identities,labels,k):
    retrieved=identities[:k]
    eligible={key:value['grade'] for key,value in labels.items() if value['status']=='relevant_eligible'}
    hits=[key in eligible for key in retrieved]
    first=next((i for i,key in enumerate(retrieved,1) if key in eligible),None)
    dcg=sum((2**eligible.get(key,0)-1)/math.log2(i+1) for i,key in enumerate(retrieved,1))
    ideal=sum((2**grade-1)/math.log2(i+1) for i,grade in enumerate(sorted(eligible.values(),reverse=True)[:k],1))
    return {'recall_at_k':sum(hits)/len(eligible) if eligible else 0.0,
            'precision_at_k':sum(hits)/k,'mrr':1/first if first else 0.0,
            'ndcg_at_k':dcg/ideal if ideal else 0.0,'hit_rate_at_k':float(any(hits)),
            'false_positives':[key for key in retrieved if key not in eligible],
            'false_negatives':sorted(set(eligible)-set(retrieved))}


def aggregate(rows):
    keys=('recall_at_k','precision_at_k','mrr','ndcg_at_k','hit_rate_at_k')
    return {key:sum(row[key] for row in rows)/len(rows) if rows else 0.0 for key in keys}
