import importlib.util
import sys
from pathlib import Path

from langchain_core.documents import Document

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
SENTENCE_SPLITTER_PATH = BACKEND_DIR / 'open_webui' / 'retrieval' / 'sentence_splitter.py'
spec = importlib.util.spec_from_file_location('sentence_splitter', SENTENCE_SPLITTER_PATH)
sentence_splitter = importlib.util.module_from_spec(spec)
sys.modules['sentence_splitter'] = sentence_splitter
assert spec.loader is not None
spec.loader.exec_module(sentence_splitter)

split_doc_to_sentence_chunks = sentence_splitter.split_doc_to_sentence_chunks
split_doc_to_smart_chunks = sentence_splitter.split_doc_to_smart_chunks
split_text_into_sentences = sentence_splitter.split_text_into_sentences


def test_sentence_splitter_preserves_common_abbreviations():
    text = 'Dr. Smith reviewed the U.S. report. This is the next sentence. Et al. should stay together.'

    assert split_text_into_sentences(text) == [
        'Dr. Smith reviewed the U.S. report.',
        'This is the next sentence.',
        'Et al. should stay together.',
    ]


def test_sentence_chunks_overlap_complete_sentences_and_preserve_metadata():
    doc = Document(
        page_content='Alpha sentence. Beta sentence is longer. Gamma sentence follows. Delta closes.',
        metadata={'source': 'unit', 'file_id': 'file-1'},
    )

    chunks = split_doc_to_sentence_chunks(doc, chunk_size=2, overlap_sentences=1)

    assert [chunk.page_content for chunk in chunks] == [
        'Alpha sentence. Beta sentence is longer.',
        'Beta sentence is longer. Gamma sentence follows.',
        'Gamma sentence follows. Delta closes.',
    ]
    assert all(chunk.metadata['source'] == 'unit' for chunk in chunks)
    assert all(chunk.metadata['file_id'] == 'file-1' for chunk in chunks)
    assert [chunk.metadata['start_index'] for chunk in chunks] == [0, 16, 41]


def test_sentence_chunks_keep_long_single_sentence_intact():
    text = 'This sentence is intentionally much longer than the configured chunk size. Short one.'
    doc = Document(page_content=text, metadata={})

    chunks = split_doc_to_sentence_chunks(doc, chunk_size=1, overlap_sentences=0)

    assert chunks[0].page_content == 'This sentence is intentionally much longer than the configured chunk size.'
    assert chunks[1].page_content == 'Short one.'


def test_sentence_overlap_is_capped_below_chunk_size():
    doc = Document(page_content='One. Two. Three.', metadata={})

    chunks = split_doc_to_sentence_chunks(doc, chunk_size=2, overlap_sentences=20)

    assert [chunk.page_content for chunk in chunks] == [
        'One. Two.',
        'Two. Three.',
    ]


def test_sentence_chunks_fall_back_to_lines_for_code_like_text():
    doc = Document(
        page_content='def alpha():\n    return 1\ndef beta():\n    return alpha()',
        metadata={'source': 'code.py'},
    )

    chunks = split_doc_to_sentence_chunks(doc, chunk_size=2, overlap_sentences=1)

    assert [chunk.page_content for chunk in chunks] == [
        'def alpha():\n    return 1',
        '    return 1\ndef beta():',
        'def beta():\n    return alpha()',
    ]
    assert all(chunk.metadata['source'] == 'code.py' for chunk in chunks)


def test_sentence_chunks_use_lines_for_code_with_docstring_sentences():
    doc = Document(
        page_content='''"""Builds a memory graph. Keeps details intact."""

from datetime import datetime


class Filter:
    def inlet(self, body):
        """Runs before the model. Preserves state."""
        return body
''',
        metadata={'content_type': 'text/x-python', 'name': 'filter.py'},
    )

    chunks = split_doc_to_sentence_chunks(doc, chunk_size=3, overlap_sentences=1)

    assert chunks[0].page_content == '"""Builds a memory graph. Keeps details intact."""\nfrom datetime import datetime\nclass Filter:'
    assert chunks[1].page_content == 'class Filter:\n    def inlet(self, body):\n        """Runs before the model. Preserves state."""'
    assert all('\n' in chunk.page_content for chunk in chunks)


def test_smart_chunks_pack_prose_sentences_to_max_size():
    doc = Document(
        page_content='Alpha sentence. Beta sentence follows. Gamma sentence is here. Delta sentence closes.',
        metadata={'source': 'notes.md'},
    )

    chunks = split_doc_to_smart_chunks(doc, max_chunk_size=60, overlap_units=1)

    assert [chunk.page_content for chunk in chunks] == [
        'Alpha sentence. Beta sentence follows.',
        'Beta sentence follows. Gamma sentence is here.',
        'Gamma sentence is here. Delta sentence closes.',
    ]
    assert all(chunk.metadata['chunking_strategy'] == 'auto:sentence' for chunk in chunks)
    assert all(len(chunk.page_content) <= 60 for chunk in chunks)


def test_smart_chunks_use_lines_for_code_and_respect_max_size():
    doc = Document(
        page_content='def alpha():\n    return 1\ndef beta():\n    return alpha()\ndef gamma():\n    return beta()',
        metadata={'source': 'code.py'},
    )

    chunks = split_doc_to_smart_chunks(doc, max_chunk_size=55, overlap_units=1)

    assert [chunk.page_content for chunk in chunks] == [
        'def alpha():\n    return 1\ndef beta():',
        'def beta():\n    return alpha()\ndef gamma():',
        'def gamma():\n    return beta()',
    ]
    assert all(chunk.metadata['chunking_strategy'] == 'auto:line' for chunk in chunks)
    assert all(len(chunk.page_content) <= 55 for chunk in chunks)