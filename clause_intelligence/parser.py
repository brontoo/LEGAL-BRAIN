"""Document structure entry point."""
from .segmentation import segment


def parse(document):
    return segment(document)
