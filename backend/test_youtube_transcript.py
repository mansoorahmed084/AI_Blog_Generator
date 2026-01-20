#!/usr/bin/env python3
"""
Test script for YouTube transcript API (direct fetching, no cookies needed!)
"""

import sys
import os

# Add the config directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.blog_generator import YouTubeBlogGenerator

def test_youtube_transcript():
    """Test fetching transcript directly from YouTube"""
    print("=" * 60)
    print("YouTube Transcript API Test")
    print("=" * 60)
    
    # Test URL (use a video that likely has transcripts)
    test_url = input("Enter YouTube URL (or press Enter for default): ").strip()
    if not test_url:
        test_url = "https://www.youtube.com/watch?v=skMzCAga-dg"
    
    print(f"\nTesting URL: {test_url}")
    print("-" * 60)
    
    generator = YouTubeBlogGenerator()
    
    # Test direct transcript fetching
    print("\n1. Testing direct YouTube transcript fetch...")
    transcript = generator.get_youtube_transcript(test_url)
    
    if transcript:
        print(f"✓ SUCCESS! Got transcript ({len(transcript)} characters)")
        print(f"\nFirst 200 characters:")
        print(transcript[:200] + "...")
    else:
        print("✗ FAILED: Could not get transcript directly")
        print("  (Video may not have auto-generated transcripts)")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == '__main__':
    test_youtube_transcript()
