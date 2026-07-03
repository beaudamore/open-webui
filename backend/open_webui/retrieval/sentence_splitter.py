import re

from langchain_core.documents import Document


SENTENCE_BOUNDARY_RE = re.compile(r'(?<=[.!?])\s+')
CODE_FILE_EXTENSIONS = {
    '.c',
    '.cc',
    '.cpp',
    '.cs',
    '.css',
    '.go',
    '.h',
    '.hpp',
    '.java',
    '.js',
    '.jsx',
    '.kt',
    '.lua',
    '.php',
    '.py',
    '.rb',
    '.rs',
    '.scala',
    '.sh',
    '.sql',
    '.swift',
    '.ts',
    '.tsx',
}
CODE_CONTENT_TYPE_PARTS = {
    'javascript',
    'python',
    'shellscript',
    'typescript',
    'x-c',
    'x-c++',
    'x-java',
    'x-php',
    'x-python',
    'x-ruby',
    'x-sh',
}
SENTENCE_ABBREVIATIONS = {
    'adm.',
    'al.',
    'capt.',
    'cf.',
    'col.',
    'dr.',
    'e.g.',
    'etc.',
    'fig.',
    'gen.',
    'gov.',
    'hon.',
    'i.e.',
    'inc.',
    'jr.',
    'ltd.',
    'maj.',
    'mr.',
    'mrs.',
    'ms.',
    'mt.',
    'no.',
    'prof.',
    'rep.',
    'rev.',
    'sen.',
    'sr.',
    'st.',
    'u.k.',
    'u.s.',
    'u.s.a.',
    'vs.',
}


def should_split_sentence_after(candidate: str) -> bool:
    prefix = candidate.rstrip()
    if not prefix:
        return False

    tail = prefix.split()[-1].lower()
    if tail in SENTENCE_ABBREVIATIONS:
        return False

    if re.match(r'^[a-z]\.\Z', tail):
        return False

    if re.match(r'^(?:[a-z]\.){2,}\Z', tail):
        return False

    return True


def split_text_into_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0

    for boundary in SENTENCE_BOUNDARY_RE.finditer(text):
        candidate = text[start : boundary.start()]
        if not should_split_sentence_after(candidate):
            continue

        sentence = re.sub(r'\s+', ' ', candidate).strip()
        if sentence:
            sentences.append(sentence)
        start = boundary.end()

    remaining = re.sub(r'\s+', ' ', text[start:]).strip()
    if remaining:
        sentences.append(remaining)

    return sentences


def split_text_into_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def join_units(units: list[str], separator: str) -> str:
    content = separator.join(units)
    return content.strip() if separator == ' ' else content.rstrip()


def metadata_indicates_code(metadata: dict) -> bool:
    content_type = str(metadata.get('content_type') or metadata.get('file_content_type') or '').lower()
    if any(part in content_type for part in CODE_CONTENT_TYPE_PARTS):
        return True

    names = [metadata.get(key) for key in ('name', 'source', 'file_name', 'filename', 'path')]
    return any(str(name).lower().endswith(tuple(CODE_FILE_EXTENSIONS)) for name in names if name)


def text_looks_like_code(text: str) -> bool:
    lines = split_text_into_lines(text)
    if len(lines) < 4:
        return False

    code_like_lines = 0
    for line in lines[:80]:
        stripped = line.lstrip()
        if line.startswith((' ', '\t')):
            code_like_lines += 1
        elif re.match(r'^(async\s+def|class|def|from\s+\S+\s+import|import\s+\S+)', stripped):
            code_like_lines += 1
        elif re.search(r'[{};]\s*$', stripped):
            code_like_lines += 1

    return code_like_lines >= min(8, max(3, len(lines[:80]) // 4))


def text_looks_like_line_records(text: str) -> bool:
    lines = split_text_into_lines(text)
    if len(lines) < 4:
        return False

    sample = lines[:80]
    sentence_endings = sum(1 for line in sample if re.search(r'[.!?]["\')\]]?\s*$', line))
    delimited_lines = sum(1 for line in sample if line.count(',') >= 2 or '\t' in line or '|' in line)
    key_value_lines = sum(1 for line in sample if re.match(r'^\s*[\w.-]+\s*[:=]', line))

    if sentence_endings / len(sample) > 0.5:
        return False

    return delimited_lines + key_value_lines >= max(3, len(sample) // 3)


def split_text_into_sentence_units(text: str, metadata: dict | None = None) -> tuple[list[str], str]:
    if metadata_indicates_code(metadata or {}) or text_looks_like_code(text):
        lines = split_text_into_lines(text)
        if lines:
            return lines, '\n'

    sentences = split_text_into_sentences(text)
    normalized_text = re.sub(r'\s+', ' ', text).strip()
    if len(sentences) == 1 and sentences[0] == normalized_text:
        lines = split_text_into_lines(text)
        if len(lines) > 1:
            return lines, '\n'

    return sentences, ' '


def split_text_into_smart_units(text: str, metadata: dict | None = None) -> tuple[list[str], str, str]:
    if metadata_indicates_code(metadata or {}) or text_looks_like_code(text) or text_looks_like_line_records(text):
        lines = split_text_into_lines(text)
        if lines:
            return lines, '\n', 'line'

    sentences = split_text_into_sentences(text)
    if len(sentences) > 1:
        return sentences, ' ', 'sentence'

    lines = split_text_into_lines(text)
    if len(lines) > 1:
        return lines, '\n', 'line'

    return sentences, ' ', 'sentence'


def split_doc_to_sentence_chunks(doc: Document, chunk_size: int, overlap_sentences: int) -> list[Document]:
    units, separator = split_text_into_sentence_units(doc.page_content, doc.metadata)
    if not units:
        return []

    sentences_per_chunk = max(1, chunk_size)
    overlap_sentences = min(max(0, overlap_sentences), max(0, sentences_per_chunk - 1))
    chunks: list[Document] = []
    search_start = 0

    def emit_chunk(chunk_sentences: list[str]) -> None:
        nonlocal search_start
        content = join_units(chunk_sentences, separator)
        if not content.strip():
            return

        metadata = {**doc.metadata}
        start_index = doc.page_content.find(chunk_sentences[0], search_start)
        if start_index >= 0:
            metadata['start_index'] = start_index
            search_start = start_index + 1

        chunks.append(Document(page_content=content, metadata=metadata))

    step = max(1, sentences_per_chunk - overlap_sentences)
    for start in range(0, len(units), step):
        emit_chunk(units[start : start + sentences_per_chunk])
        if start + sentences_per_chunk >= len(units):
            break

    return chunks


def split_docs_by_sentence(docs: list[Document], chunk_size: int, overlap_sentences: int) -> list[Document]:
    split_docs: list[Document] = []
    for doc in docs:
        split_docs.extend(split_doc_to_sentence_chunks(doc, chunk_size, overlap_sentences))
    return split_docs


def split_long_unit(unit: str, max_chunk_size: int, overlap_chars: int) -> list[str]:
    if len(unit) <= max_chunk_size:
        return [unit]

    chunk_size = max(1, max_chunk_size)
    overlap_chars = min(max(0, overlap_chars), max(0, chunk_size - 1))
    step = max(1, chunk_size - overlap_chars)
    chunks = []
    for start in range(0, len(unit), step):
        chunk = unit[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(unit):
            break

    return chunks


def split_doc_to_smart_chunks(doc: Document, max_chunk_size: int, overlap_units: int) -> list[Document]:
    units, separator, unit_type = split_text_into_smart_units(doc.page_content, doc.metadata)
    if not units:
        return []

    max_chunk_size = max(1, max_chunk_size)
    overlap_units = max(0, overlap_units)
    chunks: list[Document] = []
    search_start = 0

    def emit_chunk(chunk_units: list[str]) -> None:
        nonlocal search_start
        content = join_units(chunk_units, separator)
        if not content.strip():
            return

        metadata = {
            **doc.metadata,
            'chunking_strategy': f'auto:{unit_type}',
            'chunk_unit': unit_type,
        }
        start_index = doc.page_content.find(chunk_units[0], search_start)
        if start_index >= 0:
            metadata['start_index'] = start_index
            search_start = start_index + 1

        chunks.append(Document(page_content=content, metadata=metadata))

    start = 0
    while start < len(units):
        chunk_units: list[str] = []
        index = start
        while index < len(units):
            candidate_units = [*chunk_units, units[index]]
            candidate = join_units(candidate_units, separator)
            if chunk_units and len(candidate) > max_chunk_size:
                break
            chunk_units = candidate_units
            index += 1
            if len(candidate) >= max_chunk_size:
                break

        if not chunk_units:
            for split_unit in split_long_unit(units[start], max_chunk_size, 0):
                emit_chunk([split_unit])
            start += 1
            continue

        if len(chunk_units) == 1 and len(chunk_units[0]) > max_chunk_size:
            for split_unit in split_long_unit(chunk_units[0], max_chunk_size, 0):
                emit_chunk([split_unit])
        else:
            emit_chunk(chunk_units)

        if index >= len(units):
            break

        consumed = max(1, index - start)
        start = start + max(1, consumed - min(overlap_units, consumed - 1))

    return chunks


def split_docs_smart(docs: list[Document], max_chunk_size: int, overlap_units: int) -> list[Document]:
    split_docs: list[Document] = []
    for doc in docs:
        split_docs.extend(split_doc_to_smart_chunks(doc, max_chunk_size, overlap_units))
    return split_docs