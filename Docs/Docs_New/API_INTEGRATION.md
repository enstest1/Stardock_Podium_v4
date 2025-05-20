# API Integration Guide

## Overview

This guide covers the integration and configuration of external APIs used in the system. For TTS-specific API integration, see `WORKFLOW.md`.

## API Services

### OpenAI/OpenRouter
1. **Purpose**
   - Text generation
   - Script creation
   - Character development

2. **Setup**
   ```bash
   # Add to .env
   OPENAI_API_KEY=your_key_here
   OPENROUTER_API_KEY=your_key_here
   ```

3. **Usage**
   ```python
   from openai import OpenAI
   
   client = OpenAI()
   response = client.chat.completions.create(
       model="gpt-4",
       messages=[{"role": "user", "content": "Your prompt"}]
   )
   ```

### Mem0 Vector Database
1. **Purpose**
   - Semantic memory storage
   - Book vectorization
   - Episode continuity

2. **Setup**
   ```bash
   # Add to .env
   MEM0_API_KEY=your_key_here
   ```

3. **Usage**
   ```python
   from mem0_client import Mem0Client
   
   client = Mem0Client()
   client.store_vector("key", vector_data)
   ```

## Configuration

### Environment Variables
1. **Required Variables**
   ```
   OPENAI_API_KEY=your_key_here
   OPENROUTER_API_KEY=your_key_here
   MEM0_API_KEY=your_key_here
   ```

2. **Optional Variables**
   ```
   OPENAI_MODEL=gpt-4
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   MEM0_BASE_URL=https://api.mem0.ai
   ```

### API Settings
1. **Rate Limiting**
   ```python
   # Example rate limiting
   from ratelimit import limits, sleep_and_retry
   
   @sleep_and_retry
   @limits(calls=60, period=60)
   def api_call():
       pass
   ```

2. **Error Handling**
   ```python
   try:
       response = api_call()
   except RateLimitError:
       # Handle rate limit
   except APIError:
       # Handle API error
   ```

## Security

### API Key Management
1. **Storage**
   - Use `.env` file
   - Never commit keys
   - Rotate keys regularly

2. **Access Control**
   - Restrict key access
   - Monitor usage
   - Set up alerts

## Integration Points

### Text Generation
1. **Script Generation**
   ```python
   def generate_script(prompt):
       response = openai_client.chat.completions.create(
           model="gpt-4",
           messages=[{"role": "user", "content": prompt}]
       )
       return response.choices[0].message.content
   ```

2. **Character Development**
   ```python
   def develop_character(traits):
       response = openai_client.chat.completions.create(
           model="gpt-4",
           messages=[{"role": "user", "content": f"Develop character: {traits}"}]
       )
       return response.choices[0].message.content
   ```

### Memory Management
1. **Book Vectorization**
   ```python
   def vectorize_book(content):
       vectors = mem0_client.create_vectors(content)
       mem0_client.store_vectors("book", vectors)
   ```

2. **Episode Tracking**
   ```python
   def track_episode(episode_data):
       vectors = mem0_client.create_vectors(episode_data)
       mem0_client.store_vectors("episode", vectors)
   ```

## Best Practices

### API Usage
1. **Efficiency**
   - Cache responses
   - Batch requests
   - Use async when possible

2. **Error Handling**
   - Implement retries
   - Log errors
   - Monitor failures

3. **Monitoring**
   - Track usage
   - Set up alerts
   - Monitor costs

### Performance
1. **Optimization**
   - Use connection pooling
   - Implement caching
   - Optimize requests

2. **Scaling**
   - Handle rate limits
   - Implement backoff
   - Monitor resources

## Troubleshooting

### Common Issues
1. **Rate Limiting**
   - Implement backoff
   - Cache responses
   - Monitor usage

2. **Authentication**
   - Verify keys
   - Check permissions
   - Rotate keys

3. **Network Issues**
   - Handle timeouts
   - Implement retries
   - Monitor connectivity

### Monitoring
1. **Usage Tracking**
   - Monitor API calls
   - Track costs
   - Set up alerts

2. **Error Tracking**
   - Log errors
   - Monitor failures
   - Set up notifications

## Development

### Testing
1. **Unit Tests**
   ```python
   def test_api_call():
       response = api_call()
       assert response.status_code == 200
   ```

2. **Integration Tests**
   ```python
   def test_full_flow():
       result = generate_script("Test prompt")
       assert result is not None
   ```

### Debugging
1. **Logging**
   ```python
   import logging
   
   logging.basicConfig(level=logging.DEBUG)
   logger = logging.getLogger(__name__)
   ```

2. **Error Handling**
   ```python
   try:
       response = api_call()
   except Exception as e:
       logger.error(f"API call failed: {e}")
   ``` 