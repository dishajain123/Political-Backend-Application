"""
Sentiment Analysis Utilities Module
===================================
Provides hooks for sentiment analysis on text content.
Can be integrated with NLP services or libraries.

Author: Political Communication Platform Team
"""

from typing import Optional, Dict
from app.utils.enums import SentimentType
import re


def analyze_sentiment(text: str) -> SentimentType:
    """
    Analyze sentiment of text content.
    
    This is a simple rule-based implementation.
    For production, integrate with NLP services like:
    - TextBlob
    - VADER
    - Cloud NLP APIs (Google, AWS)
    
    Args:
        text (str): Text to analyze
        
    Returns:
        SentimentType: Detected sentiment
        
    Example:
        >>> analyze_sentiment("Great work! Very happy with the service")
        <SentimentType.POSITIVE: 'positive'>
    """
    if not text or len(text.strip()) == 0:
        return SentimentType.NEUTRAL
    
    text_lower = text.lower()
    
    # Simple keyword-based sentiment analysis
    positive_keywords = [
        'good', 'great', 'excellent', 'happy', 'satisfied', 'thank',
        'appreciate', 'wonderful', 'amazing', 'best', 'love', 'perfect'
    ]
    
    negative_keywords = [
        'bad', 'poor', 'terrible', 'worst', 'hate', 'angry', 'disappointed',
        'unhappy', 'useless', 'pathetic', 'horrible', 'awful', 'failure'
    ]
    
    # Count keyword occurrences
    positive_count = sum(1 for word in positive_keywords if word in text_lower)
    negative_count = sum(1 for word in negative_keywords if word in text_lower)
    
    # Determine sentiment
    if positive_count > negative_count and positive_count > 0:
        return SentimentType.POSITIVE
    elif negative_count > positive_count and negative_count > 0:
        return SentimentType.NEGATIVE
    elif positive_count > 0 and negative_count > 0:
        return SentimentType.MIXED
    else:
        return SentimentType.NEUTRAL


def get_sentiment_score(text: str) -> Dict[str, float]:
    """
    Get detailed sentiment scores.
    
    Args:
        text (str): Text to analyze
        
    Returns:
        Dict[str, float]: Sentiment scores for positive, negative, neutral
        
    Example:
        >>> get_sentiment_score("Service is okay but could be better")
        {'positive': 0.2, 'negative': 0.3, 'neutral': 0.5}
    """
    # Placeholder implementation
    # In production, use proper NLP library
    
    sentiment = analyze_sentiment(text)
    
    if sentiment == SentimentType.POSITIVE:
        return {"positive": 0.7, "negative": 0.1, "neutral": 0.2}
    elif sentiment == SentimentType.NEGATIVE:
        return {"positive": 0.1, "negative": 0.7, "neutral": 0.2}
    elif sentiment == SentimentType.MIXED:
        return {"positive": 0.4, "negative": 0.4, "neutral": 0.2}
    else:
        return {"positive": 0.2, "negative": 0.2, "neutral": 0.6}


def extract_keywords(text: str, max_keywords: int = 5) -> list[str]:
    """
    Extract important keywords from text.
    
    Args:
        text (str): Text to process
        max_keywords (int): Maximum number of keywords to extract
        
    Returns:
        list[str]: List of extracted keywords
    """
    if not text:
        return []
    
    # Remove special characters and convert to lowercase
    text_clean = re.sub(r'[^\w\s]', ' ', text.lower())
    
    # Split into words
    words = text_clean.split()
    
    # Remove common stop words
    stop_words = {
        'the', 'is', 'at', 'which', 'on', 'a', 'an', 'as', 'are', 'was',
        'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
        'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must',
        'can', 'of', 'to', 'in', 'for', 'with', 'by', 'from', 'and', 'or'
    }
    
    # Filter and count words
    word_freq = {}
    for word in words:
        if word not in stop_words and len(word) > 2:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in sorted_words[:max_keywords]]