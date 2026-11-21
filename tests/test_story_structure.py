#!/usr/bin/env python
"""
Tests for story_structure module.

These tests verify the functionality of the story structure module,
including beat sheet calculations, episode generation, and script generation.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import module to test
from story_structure import (
    StoryStructure, 
    generate_episode, 
    get_episode,
    list_episodes
)

class TestStoryStructure(unittest.TestCase):
    """Test cases for story_structure module."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for episodes
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'OPENAI_API_KEY': 'fake_key',
            'MEM0_API_KEY': 'fake_key'
        })
        self.env_patcher.start()
        
        # Create patchers for external dependencies
        self.mem0_patcher = patch('story_structure.get_mem0_client')
        self.openai_patcher = patch('story_structure.OpenAI')
        self.async_openai_patcher = patch('story_structure.AsyncOpenAI')
        self.knowledge_patcher = patch('story_structure.get_knowledge_context')
        
        # Start patchers
        self.mock_mem0 = self.mem0_patcher.start()
        self.mock_openai = self.openai_patcher.start()
        self.mock_async_openai = self.async_openai_patcher.start()
        self.mock_knowledge = self.knowledge_patcher.start()
        self.mock_knowledge.return_value.series_bible = {}
        self.mock_knowledge.return_value.is_ready.return_value = True
        self.mock_knowledge.return_value.get_rag_context.return_value = ''
        self.mock_knowledge.return_value.build_system_prompt.side_effect = lambda base: base
        
        # Configure mocks
        self.mock_mem0_client = MagicMock()
        self.mock_mem0_client.add_story_structure.return_value = True
        self.mock_mem0_client.search_memory.return_value = []
        self.mock_mem0.return_value = self.mock_mem0_client
        self.mock_mem0_client.for_project.return_value = self.mock_mem0_client  # GEN-003
        
        self.mock_openai_client = MagicMock()
        self.mock_openai.return_value = self.mock_openai_client
        
        self.mock_async_openai_client = MagicMock()
        self.mock_async_openai.return_value = self.mock_async_openai_client
        
        # Configure chat completions response
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test Episode Title"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        self.mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Set up story structure with test directory
        self.story_structure = StoryStructure(episodes_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop patchers
        self.env_patcher.stop()
        self.mem0_patcher.stop()
        self.openai_patcher.stop()
        self.async_openai_patcher.stop()
        self.knowledge_patcher.stop()
        
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_beat_sheet_structure(self):
        """Test that the beat sheet has the correct structure."""
        # The beat sheet should be a list of dictionaries
        self.assertIsInstance(self.story_structure.BEAT_SHEET, list)
        
        # Each beat should have the required keys
        required_keys = ['name', 'description', 'percentage', 'duration_factor']
        for beat in self.story_structure.BEAT_SHEET:
            for key in required_keys:
                self.assertIn(key, beat)
        
        # The beat sheet should cover the whole story
        total_duration = sum(beat['duration_factor'] for beat in self.story_structure.BEAT_SHEET)
        self.assertAlmostEqual(total_duration, 1.0, places=2)
    
    def test_calculate_beat_durations(self):
        """Test calculating beat durations based on target length."""
        # Test with 30 minute episode
        beats = self.story_structure._calculate_beat_durations(30)
        
        # Should have same number of beats as the beat sheet
        self.assertEqual(len(beats), len(self.story_structure.BEAT_SHEET))
        
        # Each beat should have duration_seconds, start_time, and end_time
        for beat in beats:
            self.assertIn('duration_seconds', beat)
            self.assertIn('start_time', beat)
            self.assertIn('end_time', beat)
            
            # Duration should be positive
            self.assertGreater(beat['duration_seconds'], 0)
            
            # End time should be after start time
            self.assertGreater(beat['end_time'], beat['start_time'])
        
        # Total duration should approximately match target
        total_seconds = sum(beat['duration_seconds'] for beat in beats)
        self.assertAlmostEqual(total_seconds, 30 * 60, delta=30)  # Allow 30 seconds margin
    
    def test_generate_episode_structure(self):
        """Test generating an episode structure."""
        # Test data
        episode_data = {
            'title': 'Test Episode',
            'theme': 'time travel',
            'series': 'Test Series',
            'target_duration': 30
        }
        
        # Generate episode
        episode = self.story_structure.generate_episode_structure(episode_data)
        
        # Check basic structure
        self.assertIn('episode_id', episode)
        self.assertEqual(episode['title'], 'Test Episode')
        self.assertEqual(episode['series'], 'Test Series')
        self.assertEqual(episode['theme'], 'time travel')
        self.assertEqual(episode['target_duration_minutes'], 30)
        self.assertEqual(episode['status'], 'draft')
        
        # Check beats
        self.assertIn('beats', episode)
        self.assertGreater(len(episode['beats']), 0)
        
        # Check file was saved
        episode_file = Path(self.temp_dir) / episode['episode_id'] / "structure.json"
        self.assertTrue(episode_file.exists())
        
        # Check mem0 was called
        self.mock_mem0_client.add_story_structure.assert_called_once()
    
    def test_generate_title(self):
        """Test generating an episode title."""
        # Mock response
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "The Temporal Paradox"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        self.mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Generate title
        title = self.story_structure._generate_title(
            theme="time travel",
            series="Test Series",
            episode_number=1
        )
        
        # Check title
        self.assertEqual(title, "The Temporal Paradox")
        
        # Check OpenAI was called
        self.mock_openai_client.chat.completions.create.assert_called_once()
        
        # Test fallback when API fails
        self.mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        # Generate title - should use fallback
        title = self.story_structure._generate_title(
            theme="time travel",
            series="Test Series",
            episode_number=1
        )
        
        # Check fallback title format
        self.assertEqual(title, "Episode 1: time travel")
    
    def test_save_and_get_episode(self):
        """Test saving and retrieving an episode."""
        # Create test episode
        episode = {
            'episode_id': 'test_episode',
            'title': 'Test Episode',
            'series': 'Test Series',
            'theme': 'test theme',
            'created_at': 1234567890,
            'target_duration_minutes': 30,
            'status': 'draft',
            'beats': [{'name': 'Opening Image', 'duration_seconds': 30}],
            'characters': [],
            'scenes': [],
            'script': None,
            'audio': None,
            'metadata': {}
        }
        
        # Save episode
        self.story_structure._save_episode(episode)
        
        # Retrieve episode
        retrieved = self.story_structure.get_episode('test_episode')
        
        # Check retrieved episode matches original
        self.assertEqual(retrieved['episode_id'], episode['episode_id'])
        self.assertEqual(retrieved['title'], episode['title'])
        self.assertEqual(retrieved['series'], episode['series'])
        
        # Test retrieving non-existent episode
        retrieved = self.story_structure.get_episode('nonexistent_episode')
        self.assertIsNone(retrieved)
    
    def test_list_episodes(self):
        """Test listing episodes."""
        # Create test episodes
        episodes = [
            {
                'episode_id': 'test_episode_1',
                'title': 'Test Episode 1',
                'series': 'Test Series A',
                'episode_number': 1,
                'created_at': 1234567890,
                'status': 'draft'
            },
            {
                'episode_id': 'test_episode_2',
                'title': 'Test Episode 2',
                'series': 'Test Series A',
                'episode_number': 2,
                'created_at': 1234567891,
                'status': 'complete'
            },
            {
                'episode_id': 'test_episode_3',
                'title': 'Test Episode 3',
                'series': 'Test Series B',
                'episode_number': 1,
                'created_at': 1234567892,
                'status': 'draft'
            }
        ]
        
        # Save episodes
        for episode in episodes:
            episode_dir = Path(self.temp_dir) / episode['episode_id']
            episode_dir.mkdir(exist_ok=True)
            
            with open(episode_dir / "structure.json", 'w') as f:
                json.dump(episode, f)
        
        # List all episodes
        results = self.story_structure.list_episodes()
        self.assertEqual(len(results), 3)
        
        # List episodes filtered by series
        results = self.story_structure.list_episodes(series="Test Series A")
        self.assertEqual(len(results), 2)
        
        results = self.story_structure.list_episodes(series="Test Series B")
        self.assertEqual(len(results), 1)
        
        # Test non-existent series
        results = self.story_structure.list_episodes(series="Nonexistent Series")
        self.assertEqual(len(results), 0)

if __name__ == '__main__':
    unittest.main()