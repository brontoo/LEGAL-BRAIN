"""Independent release categories, never a production-ready boolean."""
def assess(*,engineering_passed=False,gemini_executed=False,supabase_executed=False,
           independent_legal_approval=False,ingress_independently_validated=False):
    return {'engineering':'PASSED_EXECUTED_SCOPE' if engineering_passed else 'NOT_VERIFIED',
            'live_integration':'REQUIRES_RESULT_REVIEW' if gemini_executed and supabase_executed else 'BLOCKED',
            'legal_review':'REQUIRES_SCOPE_REVIEW' if independent_legal_approval else 'NOT_APPROVED',
            'public_deployment':'REQUIRES_SEPARATE_RELEASE_APPROVAL' if all((engineering_passed,gemini_executed,supabase_executed,independent_legal_approval,ingress_independently_validated)) else 'BLOCKED'}
