import os
import re
import pdfplumber
from typing import List, Dict


def get_grade_and_subject(filename: str) -> Dict:
    """Infer grade and subject from the PDF filename."""
    name = filename.lower()
    grade = None
    subject = None

    grade_match = re.search(r'grade(\d+)', name)
    if grade_match:
        grade = int(grade_match.group(1))

    if any(k in name for k in ['math', 'number', 'count', 'shape']):
        subject = 'Math'
    elif any(k in name for k in ['english', 'grammar', 'vocabulary']):
        subject = 'English'
    elif any(k in name for k in ['science', 'plant', 'animal']):
        subject = 'Science'

    return {"grade": grade, "subject": subject}


def clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\f', '\n\n', text)
    return text.strip()


def infer_topic(text: str, subject: str) -> str:
    """Keyword-based topic detection per subject."""
    t = text.lower()

    if subject == 'Math':
        if any(w in t for w in ['triangle', 'circle', 'square', 'rectangle', 'shape', 'polygon', 'sides']):
            return 'Shapes'
        if any(w in t for w in ['add', 'sum', 'plus', 'addition', 'total']):
            return 'Addition'
        if any(w in t for w in ['subtract', 'minus', 'difference', 'take away']):
            return 'Subtraction'
        if any(w in t for w in ['count', 'number', 'digit', 'one', 'two', 'three', 'zero']):
            return 'Numbers and Counting'
        return 'Mathematics'

    if subject == 'English':
        if any(w in t for w in ['noun', 'verb', 'adjective', 'pronoun', 'adverb', 'preposition']):
            return 'Parts of Speech'
        if any(w in t for w in ['sentence', 'punctuation', 'paragraph', 'capital letter']):
            return 'Sentence Structure'
        if any(w in t for w in ['vocabulary', 'word meaning', 'definition', 'synonym', 'antonym']):
            return 'Vocabulary'
        if any(w in t for w in ['tense', 'past', 'present', 'future']):
            return 'Tenses'
        return 'Grammar'

    if subject == 'Science':
        if any(w in t for w in ['plant', 'leaf', 'root', 'stem', 'flower', 'seed', 'photosynthesis', 'chlorophyll']):
            return 'Plants'
        if any(w in t for w in ['animal', 'mammal', 'reptile', 'bird', 'fish', 'insect', 'amphibian']):
            return 'Animals'
        if any(w in t for w in ['food chain', 'ecosystem', 'habitat', 'predator', 'prey']):
            return 'Ecosystem'
        return 'Life Science'

    return 'General'


def chunk_text(text: str, max_words: int = 300) -> List[str]:
    """Split text into chunks of approximately max_words words."""
    paragraphs = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]
    chunks: List[str] = []
    current: List[str] = []
    word_count = 0

    for para in paragraphs:
        wc = len(para.split())
        if word_count + wc > max_words and current:
            chunks.append('\n\n'.join(current))
            current = [para]
            word_count = wc
        else:
            current.append(para)
            word_count += wc

    if current:
        chunks.append('\n\n'.join(current))

    # Filter chunks that are too short to be useful
    return [c for c in chunks if len(c.split()) >= 20]


def extract_from_pdf(file_path: str, source_id: str) -> Dict:
    """Extract text from a PDF and return structured chunks."""
    filename = os.path.basename(file_path)
    meta = get_grade_and_subject(filename)
    grade = meta['grade']
    subject = meta['subject'] or 'General'

    raw_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                raw_text += page_text + "\n\n"

    raw_text = clean_text(raw_text)
    text_chunks = chunk_text(raw_text)

    chunks = []
    for i, chunk_content in enumerate(text_chunks):
        chunk_id = f"{source_id}_CH_{str(i + 1).zfill(2)}"
        topic = infer_topic(chunk_content, subject)
        chunks.append({
            "chunk_id": chunk_id,
            "source_id": source_id,
            "grade": grade,
            "subject": subject,
            "topic": topic,
            "text": chunk_content,
        })

    return {
        "source_id": source_id,
        "filename": filename,
        "grade": grade,
        "subject": subject,
        "chunks": chunks,
    }
