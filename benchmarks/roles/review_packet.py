"""RETIRED_FOR_BLINDED_REVIEW: historical key/IDs were committed.
Use validation.review_cli with separate private destinations; history is not purged.
"""
EMPTY_REVIEW_TEMPLATE = {'reviewer_id': None, 'qualification_attested': False, 'annotations': []}


def prepare(output, *, coordinator=None, documents=None, test_only=False):
    if coordinator is None or documents is None:
        raise ValueError('Retired packet: separate external coordinator and approved sources required')
    from validation.secure_review import prepare as secure_prepare
    return secure_prepare(documents, reviewer_dir=output, coordinator_dir=coordinator, test_only=test_only)


if __name__ == '__main__':
    raise SystemExit('RETIRED_FOR_BLINDED_REVIEW: use python -m validation.review_cli')
