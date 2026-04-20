#!/usr/bin/env python
"""
Reference Memory Sync Module for Stardock Podium.

This module synchronizes processed reference materials (books, papers, etc.)
with the mem0 vector database for semantic search and retrieval.
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import concurrent.futures
from tqdm import tqdm

# Local imports
from epub_processor import get_processor, list_books
from mem0_client import get_mem0_client

# Setup logging
logger = logging.getLogger(__name__)

class ReferenceMemorySync:
    """Synchronizes reference materials with vector memory database."""
    
    def __init__(self):
        """Initialize the reference memory sync."""
        self.epub_processor = get_processor()
        self.mem0_client = get_mem0_client()
        
        # Create sync status directory (honors STARDOCK_DATA_DIR override)
        from config.paths import SYNC_STATUS_DIR
        self.sync_dir = SYNC_STATUS_DIR
        self.sync_dir.mkdir(exist_ok=True, parents=True)
    
    def sync_book(self, book_id: str, force: bool = False) -> Dict[str, Any]:
        """Sync a specific book to memory.
        
        Args:
            book_id: ID of the book to sync
            force: Whether to force sync even if already synced
        
        Returns:
            Dictionary with sync results
        """
        # Check if book is already synced
        sync_file = self.sync_dir / f"{book_id}_sync.json"
        
        if sync_file.exists() and not force:
            try:
                with open(sync_file, 'r') as f:
                    sync_status = json.load(f)
                    if sync_status.get("completed", False):
                        logger.info(f"Book {book_id} already synced. Use force=True to resync.")
                        return sync_status
            except Exception as e:
                logger.error(f"Error reading sync status: {e}")
        
        # Get book metadata
        metadata = self.epub_processor.get_book_metadata(book_id)
        if not metadata:
            logger.error(f"Book metadata not found for ID: {book_id}")
            return {"error": "Book metadata not found"}
        
        title = metadata.get('title', 'Unknown Title')
        author = metadata.get('creator', 'Unknown Author')
        
        logger.info(f"Syncing book '{title}' by {author} (ID: {book_id}) to memory")
        
        # Get book sections
        sections = self.epub_processor.get_book_sections(book_id)
        if not sections or not sections.get('sections'):
            logger.error(f"No sections found for book {book_id}")
            return {"error": "No sections found"}
        
        # Initialize sync status
        sync_status = {
            "book_id": book_id,
            "title": title,
            "author": author,
            "started_at": time.time(),
            "completed": False,
            "total_sections": len(sections.get('sections', [])),
            "synced_sections": 0,
            "failed_sections": 0,
            "memory_ids": []
        }
        
        # Save initial sync status
        try:
            with open(sync_file, 'w') as f:
                json.dump(sync_status, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving sync status: {e}")
        
        # Process each section in parallel
        section_results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for section in sections.get('sections', []):
                section_content = section.get('content', '')
                section_title = section.get('section_title', '')
                chapter_title = section.get('chapter_title', '')
                
                futures.append(
                    executor.submit(
                        self._add_section_to_memory,
                        book_id=book_id,
                        title=title,
                        author=author,
                        section_content=section_content,
                        section_title=section_title,
                        chapter_title=chapter_title
                    )
                )
            
            # Process results as they complete
            for future in tqdm(concurrent.futures.as_completed(futures),
                             total=len(futures),
                             desc=f"Syncing {title}"):
                try:
                    result = future.result()
                    section_results.append(result)
                    
                    # Update sync status
                    if result.get("success"):
                        sync_status["synced_sections"] += 1
                        sync_status["memory_ids"].append(result.get("memory_id"))
                    else:
                        sync_status["failed_sections"] += 1
                    
                    # Periodically save sync status
                    if (sync_status["synced_sections"] + 
                        sync_status["failed_sections"]) % 10 == 0:
                        with open(sync_file, 'w') as f:
                            json.dump(sync_status, f, indent=2)
                
                except Exception as e:
                    logger.error(f"Error processing section: {e}")
                    sync_status["failed_sections"] += 1
        
        # Update and save final sync status
        sync_status["completed"] = True
        sync_status["completed_at"] = time.time()
        sync_status["success_rate"] = (sync_status["synced_sections"] / 
                                      sync_status["total_sections"] 
                                      if sync_status["total_sections"] > 0 else 0)
        
        try:
            with open(sync_file, 'w') as f:
                json.dump(sync_status, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving final sync status: {e}")
        
        return sync_status
    
    def _add_section_to_memory(self, book_id: str, title: str, author: str,
                              section_content: str, section_title: str,
                              chapter_title: str) -> Dict[str, Any]:
        """Add a section to vector memory.
        
        Args:
            book_id: ID of the book
            title: Book title
            author: Book author
            section_content: Content of the section
            section_title: Title of the section
            chapter_title: Title of the chapter
        
        Returns:
            Dictionary with result information
        """
        try:
            # Prepare metadata
            metadata = {
                "book_id": book_id,
                "book_title": title,
                "author": author,
                "section_title": section_title,
                "chapter_title": chapter_title
            }
            
            # Add to memory
            result = self.mem0_client.add_reference_material(
                content=section_content,
                source=f"{title} by {author}",
                metadata=metadata
            )
            
            return {
                "success": True,
                "book_id": book_id,
                "section_title": section_title,
                "memory_id": result.get("id") if isinstance(result, dict) else None
            }
        
        except Exception as e:
            logger.error(f"Error adding section to memory: {e}")
            return {
                "success": False,
                "book_id": book_id,
                "section_title": section_title,
                "error": str(e)
            }
    
    def sync_all_books(self, force: bool = False) -> Dict[str, Any]:
        """Sync all available books to memory.
        
        Args:
            force: Whether to force sync even if already synced
        
        Returns:
            Dictionary with sync results
        """
        # Get all available books
        books = list_books()
        
        if not books:
            logger.warning("No books found to sync")
            return {"error": "No books found"}
        
        # Process each book
        results = {}
        
        for book in books:
            book_id = book.get("book_id")
            if not book_id:
                continue
            
            result = self.sync_book(book_id, force=force)
            results[book_id] = result
        
        # Create a summary
        summary = {
            "total_books": len(books),
            "successful_syncs": sum(1 for result in results.values() 
                                   if result.get("completed", False)),
            "failed_syncs": sum(1 for result in results.values() 
                               if not result.get("completed", False)),
            "total_sections_synced": sum(result.get("synced_sections", 0) 
                                        for result in results.values()),
            "completed_at": time.time()
        }
        
        # Save overall sync status
        try:
            with open(self.sync_dir / "all_books_sync.json", 'w') as f:
                json.dump({
                    "summary": summary,
                    "book_results": results
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving all books sync status: {e}")

        # Auto-trigger Tier 1 extraction after all books are synced
        if summary.get("total_sections_synced", 0) > 0:
            try:
                logger.info(
                    "All books synced — running series bible extraction..."
                )
                from book_knowledge import (
                    SeriesBibleExtractor,
                    reload_knowledge_context,
                )
                extractor = SeriesBibleExtractor()
                extractor.extract_from_all_books(force=False)
                reload_knowledge_context()
                logger.info(
                    "Series bible extracted and knowledge context reloaded."
                )
            except Exception as e:
                logger.warning(
                    "Series bible extraction failed (non-critical, "
                    "episodes will still generate): %s",
                    e,
                )

        return {
            "summary": summary,
            "book_results": results
        }
    
    def get_sync_status(self, book_id: Optional[str] = None) -> Dict[str, Any]:
        """Get sync status for a book or all books.
        
        Args:
            book_id: Optional ID of the book to check
        
        Returns:
            Dictionary with sync status
        """
        if book_id:
            # Get status for a specific book
            sync_file = self.sync_dir / f"{book_id}_sync.json"
            
            if not sync_file.exists():
                return {"book_id": book_id, "synced": False, "error": "Not synced"}
            
            try:
                with open(sync_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading sync status: {e}")
                return {"book_id": book_id, "error": f"Error reading status: {e}"}
        else:
            # Get status for all books
            all_sync_file = self.sync_dir / "all_books_sync.json"
            
            if all_sync_file.exists():
                try:
                    with open(all_sync_file, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error reading all books sync status: {e}")
            
            # If no overall status, collect individual statuses
            statuses = {}
            for sync_file in self.sync_dir.glob("*_sync.json"):
                if sync_file.name == "all_books_sync.json":
                    continue
                
                try:
                    with open(sync_file, 'r') as f:
                        book_status = json.load(f)
                        book_id = book_status.get("book_id")
                        if book_id:
                            statuses[book_id] = book_status
                except Exception as e:
                    logger.error(f"Error reading sync file {sync_file}: {e}")
            
            return {
                "individual_statuses": statuses,
                "total_books_synced": len(statuses)
            }
    
    def search_references(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search reference materials based on semantic similarity.
        
        Args:
            query: The search query
            limit: Maximum number of results to return
        
        Returns:
            List of relevant reference materials
        """
        return self.mem0_client.search_reference_materials(query, limit=limit)

# Create singleton instance
_memory_sync = None

def get_memory_sync() -> ReferenceMemorySync:
    """Get the ReferenceMemorySync singleton instance."""
    global _memory_sync
    
    if _memory_sync is None:
        _memory_sync = ReferenceMemorySync()
    
    return _memory_sync

def sync_references(
    book_id: Optional[str] = None,
    force: bool = False,
    force_bible: bool = False,
) -> Dict[str, Any]:
    """Sync reference materials to memory.

    Args:
        book_id: Optional ID of a specific book to sync
        force: Whether to force sync even if already synced
        force_bible: Re-run series bible extraction after a single-book sync

    Returns:
        Dictionary with sync results
    """
    memory_sync = get_memory_sync()

    if book_id:
        result = memory_sync.sync_book(book_id, force=force)
        if force_bible:
            try:
                from book_knowledge import (
                    SeriesBibleExtractor,
                    reload_knowledge_context,
                )
                SeriesBibleExtractor().extract_from_all_books(force=True)
                reload_knowledge_context()
            except Exception as e:
                logger.warning("Force bible extraction failed: %s", e)
        return result
    else:
        return memory_sync.sync_all_books(force=force)

def get_sync_status(book_id: Optional[str] = None) -> Dict[str, Any]:
    """Get sync status for a book or all books.
    
    Args:
        book_id: Optional ID of the book to check
    
    Returns:
        Dictionary with sync status
    """
    memory_sync = get_memory_sync()
    return memory_sync.get_sync_status(book_id)

def search_references(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search reference materials based on semantic similarity.
    
    Args:
        query: The search query
        limit: Maximum number of results to return
    
    Returns:
        List of relevant reference materials
    """
    memory_sync = get_memory_sync()
    return memory_sync.search_references(query, limit=limit)