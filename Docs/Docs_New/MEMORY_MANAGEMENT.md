# Memory Management Guide

## Overview

This guide covers the memory management system used for narrative continuity and character development. The system uses Mem0 as a vector database for semantic memory storage.

## Vector Memory System

### Mem0 Integration
1. **Setup**
   ```bash
   # Add to .env
   MEM0_API_KEY=your_key_here
   MEM0_BASE_URL=https://api.mem0.ai
   ```

2. **Client Initialization**
   ```python
   from mem0_client import Mem0Client
   
   client = Mem0Client()
   ```

## Memory Types

### Book Memory
1. **Purpose**
   - Store reference materials
   - Vectorize book content
   - Maintain style references

2. **Structure**
   ```python
   book_memory = {
       "content": "Book text content",
       "vectors": [...],  # Vectorized content
       "metadata": {
           "title": "Book Title",
           "author": "Author Name",
           "style": "Writing Style"
       }
   }
   ```

### Episode Memory
1. **Purpose**
   - Track episode events
   - Maintain continuity
   - Store character interactions

2. **Structure**
   ```python
   episode_memory = {
       "content": "Episode content",
       "vectors": [...],  # Vectorized content
       "metadata": {
           "episode_number": 1,
           "characters": ["Character1", "Character2"],
           "events": ["Event1", "Event2"]
       }
   }
   ```

### Character Memory
1. **Purpose**
   - Store character traits
   - Track development
   - Maintain consistency

2. **Structure**
   ```python
   character_memory = {
       "content": "Character description",
       "vectors": [...],  # Vectorized content
       "metadata": {
           "name": "Character Name",
           "traits": ["Trait1", "Trait2"],
           "development": "Character arc"
       }
   }
   ```

## Memory Operations

### Book Ingestion
1. **Vectorization**
   ```python
   def vectorize_book(content):
       vectors = client.create_vectors(content)
       return vectors
   ```

2. **Storage**
   ```python
   def store_book_memory(book_data):
       vectors = vectorize_book(book_data["content"])
       client.store_vectors("book", vectors, book_data["metadata"])
   ```

### Episode Tracking
1. **Vectorization**
   ```python
   def vectorize_episode(content):
       vectors = client.create_vectors(content)
       return vectors
   ```

2. **Storage**
   ```python
   def store_episode_memory(episode_data):
       vectors = vectorize_episode(episode_data["content"])
       client.store_vectors("episode", vectors, episode_data["metadata"])
   ```

### Character Development
1. **Vectorization**
   ```python
   def vectorize_character(content):
       vectors = client.create_vectors(content)
       return vectors
   ```

2. **Storage**
   ```python
   def store_character_memory(character_data):
       vectors = vectorize_character(character_data["content"])
       client.store_vectors("character", vectors, character_data["metadata"])
   ```

## Memory Retrieval

### Context Search
1. **Semantic Search**
   ```python
   def search_context(query):
       results = client.search_vectors(query)
       return results
   ```

2. **Filtering**
   ```python
   def filter_by_type(results, memory_type):
       return [r for r in results if r["type"] == memory_type]
   ```

### Continuity Check
1. **Episode Continuity**
   ```python
   def check_episode_continuity(episode_data):
       previous = client.get_latest_episode()
       return compare_episodes(previous, episode_data)
   ```

2. **Character Consistency**
   ```python
   def check_character_consistency(character_data):
       history = client.get_character_history(character_data["name"])
       return compare_character_states(history, character_data)
   ```

## Best Practices

### Memory Organization
1. **Structure**
   - Use consistent metadata
   - Maintain clear hierarchies
   - Implement proper indexing

2. **Performance**
   - Optimize vector operations
   - Implement caching
   - Batch operations

3. **Maintenance**
   - Regular cleanup
   - Version control
   - Backup strategy

### Integration Points
1. **Script Generation**
   ```python
   def generate_with_context(prompt):
       context = client.search_context(prompt)
       return generate_script(prompt, context)
   ```

2. **Episode Planning**
   ```python
   def plan_episode(episode_number):
       previous = client.get_episode_history()
       return plan_next_episode(previous)
   ```

3. **Quality Control**
   ```python
   def verify_continuity(content):
       context = client.search_context(content)
       return check_continuity(content, context)
   ```

## Troubleshooting

### Common Issues
1. **Vector Generation**
   - Check input format
   - Verify API connection
   - Monitor rate limits

2. **Storage Issues**
   - Check disk space
   - Verify permissions
   - Monitor API limits

3. **Retrieval Problems**
   - Verify search parameters
   - Check indexing
   - Monitor performance

### Recovery
1. **Data Recovery**
   ```python
   def recover_memory(memory_id):
       backup = client.get_backup(memory_id)
       return restore_memory(backup)
   ```

2. **System Recovery**
   ```python
   def recover_system():
       client.reset_connection()
       verify_connections()
       test_operations()
   ```

## Development

### Testing
1. **Unit Tests**
   ```python
   def test_memory_operations():
       test_data = create_test_data()
       result = store_memory(test_data)
       assert result is not None
   ```

2. **Integration Tests**
   ```python
   def test_memory_flow():
       book = ingest_book("test_book")
       episode = create_episode(book)
       assert verify_continuity(episode)
   ```

### Monitoring
1. **Performance**
   - Track operation times
   - Monitor memory usage
   - Check API limits

2. **Quality**
   - Verify vector quality
   - Check search results
   - Monitor consistency 