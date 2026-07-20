"""
파일 파싱 유틸리티
PDF, Markdown, TXT 파일의 텍스트 추출을 지원합니다.
"""

import os
import re
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    텍스트 파일을 읽습니다. UTF-8 디코딩에 실패하면 인코딩을 자동 탐지합니다.
    
    다단계 폴백 전략:
    1. UTF-8 디코딩 시도
    2. `charset_normalizer`로 인코딩 탐지
    3. 실패 시 `chardet`로 재탐지
    4. 최종적으로 UTF-8 + `errors='replace'` 적용
    
    Args:
        file_path: 파일 경로
        
    Returns:
        디코딩된 텍스트
    """
    data = Path(file_path).read_bytes()
    
    # 우선 UTF-8 시도
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # charset_normalizer로 인코딩 탐지
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # chardet로 폴백
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # 최종 폴백: UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """파일 파서"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        파일에서 텍스트를 추출합니다.
        
        Args:
            file_path: 파일 경로
            
        Returns:
            추출된 텍스트
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"파일이 존재하지 않습니다: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"지원하지 않는 파일 형식입니다: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        
        raise ValueError(f"처리할 수 없는 파일 형식입니다: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """PDF에서 텍스트를 추출합니다."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF가 필요합니다: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """Extract text from a PDF using the best lightweight candidate."""
        candidates = []

        for name, extractor in (
            ("pymupdf", FileParser._extract_pdf_pymupdf),
            ("pypdf", FileParser._extract_pdf_pypdf),
            ("pdfplumber", FileParser._extract_pdf_pdfplumber),
        ):
            try:
                text = extractor(file_path)
            except Exception:
                continue

            for variant in FileParser._text_variants(text):
                candidates.append((FileParser._text_quality_score(variant), name, variant))

        if not candidates:
            raise ValueError("PDF text extraction failed for all available engines.")

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][2]

    @staticmethod
    def _extract_pdf_pymupdf(file_path: str) -> str:
        import fitz  # PyMuPDF

        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_pdf_pypdf(file_path: str) -> str:
        from pypdf import PdfReader

        text_parts = []
        reader = PdfReader(file_path)
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                text_parts.append(text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_pdf_pdfplumber(file_path: str) -> str:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    text_parts.append(text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _text_variants(text: str) -> List[str]:
        variants = [text]
        try:
            import ftfy
            fixed = ftfy.fix_text(text)
            if fixed != text:
                variants.append(fixed)
        except Exception:
            pass
        return variants

    @staticmethod
    def _text_quality_score(text: str) -> float:
        if not text or not text.strip():
            return -1_000_000

        total = max(len(text), 1)
        hangul = len(re.findall(r'[\uac00-\ud7a3]', text))
        ascii_letters = len(re.findall(r'[A-Za-z]', text))
        replacement = text.count('\ufffd')
        mojibake = len(re.findall(r'[ìíîïëêð]', text))
        question_noise = len(re.findall(r'\?{2,}', text))
        control = len(re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', text))
        words = len(re.findall(r'\S+', text))

        score = len(text) * 0.01
        score += hangul * 2.0
        score += ascii_letters * 0.15
        score += words * 0.2
        score -= replacement * 8.0
        score -= mojibake * 2.0
        score -= question_noise * 5.0
        score -= control * 10.0

        if hangul / total > 0.05:
            score += 100
        if replacement / total > 0.01:
            score -= 250
        if mojibake / total > 0.03:
            score -= 250

        return score

    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Markdown에서 텍스트를 추출합니다(자동 인코딩 탐지 지원)."""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """TXT에서 텍스트를 추출합니다(자동 인코딩 탐지 지원)."""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        여러 파일에서 텍스트를 추출해 병합합니다.
        
        Args:
            file_paths: 파일 경로 목록
            
        Returns:
            병합된 텍스트
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== 문서 {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== 문서 {i}: {file_path} (추출 실패: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    텍스트를 작은 청크로 분할합니다.
    
    Args:
        text: 원본 텍스트
        chunk_size: 청크당 문자 수
        overlap: 겹침 문자 수
        
    Returns:
        텍스트 청크 목록
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # 가능한 경우 문장 경계에서 분할
        if end < len(text):
            # 가장 가까운 문장 종료 구분자 찾기
            for sep in ['.', '!', '?', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # 다음 청크는 overlap만큼 겹치게 시작
        start = end - overlap if end < len(text) else len(text)
    
    return chunks
