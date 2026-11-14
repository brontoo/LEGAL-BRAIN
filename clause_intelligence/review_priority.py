"""Review/test priority, not a legal-risk rating or probability model."""
ERROR_TAXONOMY = {
    'critical_documentary_error': ('wrong_actor', 'reversed_negation', 'lost_condition', 'ignored_contrary_evidence', 'invalid_quote_or_version'),
    'material_analysis_error': ('missed_obligation', 'missed_exception', 'wrong_beneficiary', 'wrong_trigger', 'unsupported_entitlement'),
    'review_required_ambiguity': ('ambiguous_definition', 'incomplete_reference', 'language_divergence', 'unverified_applicability'),
    'minor_classification_issue': ('secondary_topic_mismatch', 'missing_descriptive_label'),
}


def priority_for(fields):
    if set(fields) & {'actor', 'polarity', 'conditional'}:
        return 'critical_documentary_error'
    return 'material_analysis_error'
