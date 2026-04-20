#!/usr/bin/env python
"""
EPUB Processor Module for Stardock Podium.

This module handles processing EPUB files, extracting content, metadata,
and preparing it for analysis and memory storage.
"""

import os
import logging
import json
import uuid
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Iterator
import html2text

try:
    import ebooklib
    from ebooklib import epub
except ImportError:
    logging.error("EbookLib not found. Please install it with: pip install ebooklib")
    raise

# Setup logging
logger = logging.getLogger(__name__)

class EPUBProcessor:
    """Handler for processing EPUB files for reference ingestion."""
    
    def __init__(self, books_dir: Optional[str] = None, analysis_dir: Optional[str] = None):
        """Initialize the EPUB processor.

        Args:
            books_dir: Directory to store processed book files. When None,
                resolves via ``config.paths.BOOKS_DIR`` which honors the
                ``STARDOCK_BOOKS_DIR`` env var for cloud deployments.
            analysis_dir: Directory to store analysis files. When None,
                resolves via ``config.paths.ANALYSIS_DIR``.
        """
        from config.paths import BOOKS_DIR, ANALYSIS_DIR
        self.books_dir = Path(books_dir) if books_dir else BOOKS_DIR
        self.analysis_dir = Path(analysis_dir) if analysis_dir else ANALYSIS_DIR

        # Create directories if they don't exist
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        
        # HTML to text converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = True
        self.html_converter.ignore_images = True
        self.html_converter.ignore_tables = False
        self.html_converter.body_width = 0  # No wrapping
    
    def process_epub(self, file_path: str) -> Dict[str, Any]:
        """Process an EPUB file, extracting content and metadata.
        
        Args:
            file_path: Path to the EPUB file
        
        Returns:
            Dictionary with book metadata and processing information
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return {}
        
        try:
            # Generate a book ID
            book_id = f"book_{uuid.uuid4().hex[:8]}"
            
            # Read the EPUB file
            book = epub.read_epub(file_path)
            
            # Extract metadata
            metadata = self._extract_metadata(book)
            metadata['book_id'] = book_id
            metadata['file_path'] = str(file_path)
            metadata['processed_at'] = time.time()
            
            # Extract content
            chapters = self._extract_chapters(book)
            
            # Save book data
            book_dir = self.books_dir / book_id
            book_dir.mkdir(exist_ok=True)
            
            # Save metadata
            with open(book_dir / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Save chapters
            for i, chapter in enumerate(chapters):
                chapter_file = book_dir / f"chapter_{i:03d}.json"
                with open(chapter_file, 'w') as f:
                    json.dump(chapter, f, indent=2)
            
            # Save chapter index
            chapter_index = {
                "book_id": book_id,
                "title": metadata.get('title', 'Unknown'),
                "num_chapters": len(chapters),
                "chapters": [{"index": i, "title": ch.get('title', f"Chapter {i+1}")} 
                            for i, ch in enumerate(chapters)]
            }
            
            with open(book_dir / "chapter_index.json", 'w') as f:
                json.dump(chapter_index, f, indent=2)
            
            # Create document sections for more fine-grained reference
            sections = self._create_sections(chapters)
            
            with open(book_dir / "sections.json", 'w') as f:
                json.dump(sections, f, indent=2)
            
            logger.info(f"Successfully processed EPUB: {metadata.get('title', 'Unknown')} (ID: {book_id})")
            
            result = {
                "book_id": book_id,
                "title": metadata.get('title', 'Unknown'),
                "author": metadata.get('creator', 'Unknown'),
                "num_chapters": len(chapters),
                "num_sections": len(sections['sections']),
                "size_bytes": file_path.stat().st_size
            }
            
            return result
        
        except Exception as e:
            logger.exception(f"Error processing EPUB: {e}")
            return {}
    
    def _extract_metadata(self, book: epub.EpubBook) -> Dict[str, str]:
        """Extract metadata from an EPUB book.
        
        Args:
            book: The EpubBook object
        
        Returns:
            Dictionary of metadata
        """
        metadata = {}
        
        # Extract standard Dublin Core metadata
        for key in [
            'title', 'language', 'creator', 'contributor', 'publisher', 
            'identifier', 'source', 'rights', 'date', 'description'
        ]:
            value = book.get_metadata('DC', key)
            if value:
                # Extract value and attributes from the metadata tuple
                metadata[key] = value[0][0]
                
                # Some metadata items may have attributes
                if value[0][1]:
                    for attr_name, attr_value in value[0][1].items():
                        metadata[f"{key}_{attr_name}"] = attr_value
        
        return metadata
    
    def _extract_chapters(self, book: epub.EpubBook) -> List[Dict[str, Any]]:
        """Extract chapters from an EPUB book.
        
        Args:
            book: The EpubBook object
        
        Returns:
            List of chapters with text content
        """
        chapters = []
        
        # Spine returns list of (item_id, linear) tuples
        spine_items = book.spine
        
        for spine_entry in spine_items:
            item_id = spine_entry[0] if isinstance(
                spine_entry, (list, tuple)) else spine_entry
            
            if item_id in ('nav', 'ncx'):
                continue
            
            item = book.get_item_with_id(item_id)
            
            # Skip if item is None or not a document
            if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            
            # Get content
            content = item.get_content().decode('utf-8', errors='ignore')
            
            # Convert HTML to plain text
            text = self.html_converter.handle(content)
            
            # Clean up extra whitespace
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = text.strip()
            
            # Skip if no meaningful content
            if not text or len(text) < 10:
                continue
            
            # Try to determine chapter title
            title = self._extract_title(content, text)
            
            chapter = {
                "id": item_id,
                "title": title,
                "content": text,
                "html_size": len(content),
                "text_size": len(text)
            }
            
            chapters.append(chapter)
        
        return chapters
    
    def _extract_title(self, html_content: str, text_content: str) -> str:
        """Extract the title from chapter content.
        
        Args:
            html_content: HTML content
            text_content: Plain text content
        
        Returns:
            Extracted title or empty string if not found
        """
        # Try to find h1 tag
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.IGNORECASE | re.DOTALL)
        if h1_match:
            title = re.sub(r'<[^>]+>', '', h1_match.group(1))
            return title.strip()
        
        # Try to find first non-empty line
        lines = text_content.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) < 100:  # Assume titles aren't too long
                return line
        
        return ""
    
    def _create_sections(self, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create smaller sections from chapters for more granular indexing.
        
        Args:
            chapters: List of chapter dictionaries
        
        Returns:
            Dictionary with sections information
        """
        sections = []
        section_size = 1000  # Target size in characters
        
        for chapter_idx, chapter in enumerate(chapters):
            content = chapter['content']
            chapter_title = chapter.get('title', f"Chapter {chapter_idx+1}")
            
            # Split content into paragraphs
            paragraphs = re.split(r'\n{2,}', content)
            
            current_section = []
            current_size = 0
            section_idx = 0
            
            for para in paragraphs:
                para_size = len(para)
                
                # If adding this paragraph would exceed target size and we already have content,
                # finalize the current section and start a new one
                if current_size > 0 and current_size + para_size > section_size:
                    section_text = '\n\n'.join(current_section)
                    section = {
                        "chapter_idx": chapter_idx,
                        "section_idx": section_idx,
                        "chapter_title": chapter_title,
                        "section_title": f"{chapter_title} - Section {section_idx+1}",
                        "content": section_text,
                        "size": current_size
                    }
                    sections.append(section)
                    
                    # Reset for next section
                    current_section = []
                    current_size = 0
                    section_idx += 1
                
                # Add paragraph to current section
                current_section.append(para)
                current_size += para_size
            
            # Don't forget the last section
            if current_section:
                section_text = '\n\n'.join(current_section)
                section = {
                    "chapter_idx": chapter_idx,
                    "section_idx": section_idx,
                    "chapter_title": chapter_title,
                    "section_title": f"{chapter_title} - Section {section_idx+1}",
                    "content": section_text,
                    "size": current_size
                }
                sections.append(section)
        
        return {
            "total_sections": len(sections),
            "target_size": section_size,
            "sections": sections
        }
    
    def list_ingested_books(self) -> List[Dict[str, Any]]:
        """List all ingested books.
        
        Returns:
            List of dictionaries with book information
        """
        book_list = []
        
        for book_dir in self.books_dir.iterdir():
            if not book_dir.is_dir():
                continue
            
            metadata_file = book_dir / "metadata.json"
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                book_info = {
                    "book_id": metadata.get('book_id', book_dir.name),
                    "title": metadata.get('title', 'Unknown'),
                    "author": metadata.get('creator', 'Unknown'),
                    "processed_at": metadata.get('processed_at'),
                }
                
                # Check for chapter data
                chapter_index_file = book_dir / "chapter_index.json"
                if chapter_index_file.exists():
                    with open(chapter_index_file, 'r') as f:
                        chapter_index = json.load(f)
                        book_info["num_chapters"] = chapter_index.get('num_chapters', 0)
                
                book_list.append(book_info)
            
            except Exception as e:
                logger.error(f"Error reading book metadata from {metadata_file}: {e}")
        
        return book_list
    
    def get_book_metadata(self, book_id: str) -> Dict[str, Any]:
        """Get metadata for a specific book.
        
        Args:
            book_id: The book ID
        
        Returns:
            Dictionary with book metadata
        """
        book_dir = self.books_dir / book_id
        metadata_file = book_dir / "metadata.json"
        
        if not metadata_file.exists():
            logger.error(f"Metadata file not found for book ID: {book_id}")
            return {}
        
        try:
            with open(metadata_file, 'r') as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Error reading book metadata: {e}")
            return {}
    
    def get_book_chapters(self, book_id: str) -> List[Dict[str, Any]]:
        """Get all chapters for a specific book.
        
        Args:
            book_id: The book ID
        
        Returns:
            List of chapter dictionaries
        """
        book_dir = self.books_dir / book_id
        chapter_index_file = book_dir / "chapter_index.json"
        
        if not chapter_index_file.exists():
            logger.error(f"Chapter index file not found for book ID: {book_id}")
            return []
        
        try:
            with open(chapter_index_file, 'r') as f:
                chapter_index = json.load(f)
            
            num_chapters = chapter_index.get('num_chapters', 0)
            chapters = []
            
            for i in range(num_chapters):
                chapter_file = book_dir / f"chapter_{i:03d}.json"
                
                if chapter_file.exists():
                    with open(chapter_file, 'r') as f:
                        chapter = json.load(f)
                        chapters.append(chapter)
            
            return chapters
        
        except Exception as e:
            logger.error(f"Error reading book chapters: {e}")
            return []
    
    def get_book_sections(self, book_id: str) -> Dict[str, Any]:
        """Get all sections for a specific book.
        
        Args:
            book_id: The book ID
        
        Returns:
            Dictionary with sections information
        """
        book_dir = self.books_dir / book_id
        sections_file = book_dir / "sections.json"
        
        if not sections_file.exists():
            logger.error(f"Sections file not found for book ID: {book_id}")
            return {"total_sections": 0, "sections": []}
        
        try:
            with open(sections_file, 'r') as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Error reading book sections: {e}")
            return {"total_sections": 0, "sections": []}
    
    def get_chapter(self, book_id: str, chapter_idx: int) -> Dict[str, Any]:
        """Get a specific chapter from a book.
        
        Args:
            book_id: The book ID
            chapter_idx: The chapter index
        
        Returns:
            Chapter dictionary or empty dict if not found
        """
        book_dir = self.books_dir / book_id
        chapter_file = book_dir / f"chapter_{chapter_idx:03d}.json"
        
        if not chapter_file.exists():
            logger.error(f"Chapter file not found: {chapter_file}")
            return {}
        
        try:
            with open(chapter_file, 'r') as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Error reading chapter: {e}")
            return {}
    
    def get_section(self, book_id: str, chapter_idx: int, section_idx: int) -> Dict[str, Any]:
        """Get a specific section from a book.
        
        Args:
            book_id: The book ID
            chapter_idx: The chapter index
            section_idx: The section index
        
        Returns:
            Section dictionary or empty dict if not found
        """
        sections = self.get_book_sections(book_id)
        
        for section in sections.get('sections', []):
            if (section.get('chapter_idx') == chapter_idx and 
                section.get('section_idx') == section_idx):
                return section
        
        logger.error(f"Section not found: book_id={book_id}, chapter_idx={chapter_idx}, section_idx={section_idx}")
        return {}
    
    def get_book_content_generator(self, book_id: str) -> Iterator[Dict[str, Any]]:
        """Get a generator that yields sections from a book.
        
        Args:
            book_id: The book ID
        
        Yields:
            Section dictionaries
        """
        sections = self.get_book_sections(book_id)
        
        for section in sections.get('sections', []):
            yield section

# Singleton instance
_processor = None

def get_processor() -> EPUBProcessor:
    """Get the EPUBProcessor singleton instance."""
    global _processor
    
    if _processor is None:
        _processor = EPUBProcessor()
    
    return _processor

def process_epub(file_path: str) -> Dict[str, Any]:
    """Process an EPUB file, extracting content and metadata.
    
    Args:
        file_path: Path to the EPUB file
    
    Returns:
        Dictionary with book metadata and processing information
    """
    processor = get_processor()
    return processor.process_epub(file_path)

def list_books() -> List[Dict[str, Any]]:
    """List all ingested books.
    
    Returns:
        List of dictionaries with book information
    """
    processor = get_processor()
    return processor.list_ingested_books()

def get_book_content(book_id: str) -> Dict[str, Any]:
    """Get all content for a book.
    
    Args:
        book_id: The book ID
    
    Returns:
        Dictionary with book metadata, chapters, and sections
    """
    processor = get_processor()
    
    metadata = processor.get_book_metadata(book_id)
    chapters = processor.get_book_chapters(book_id)
    sections = processor.get_book_sections(book_id)
    
    return {
        "metadata": metadata,
        "chapters": chapters,
        "sections": sections
    }