"""Analysis engine protocols and implementations."""

from dokimos.engines.base import AiLikelihoodEngine, PlagiarismEngine, SourceIndexer
from dokimos.engines.local_indexer import LocalSourceIndexer
from dokimos.engines.placeholder_ai import PlaceholderAiEngine
from dokimos.engines.placeholder_indexer import PlaceholderSourceIndexer
from dokimos.engines.placeholder_plagiarism import PlaceholderPlagiarismEngine
from dokimos.engines.remote_plagiarism import HybridPlagiarismEngine, RemotePlagiarismEngine
from dokimos.engines.shingling import make_shingles
from dokimos.engines.shingling_plagiarism import ShinglingPlagiarismEngine
from dokimos.engines.stylometric_ai import StylometricAiEngine

__all__ = [
    "AiLikelihoodEngine",
    "HybridPlagiarismEngine",
    "LocalSourceIndexer",
    "PlaceholderAiEngine",
    "PlaceholderPlagiarismEngine",
    "PlaceholderSourceIndexer",
    "PlagiarismEngine",
    "RemotePlagiarismEngine",
    "ShinglingPlagiarismEngine",
    "SourceIndexer",
    "StylometricAiEngine",
    "make_shingles",
]
