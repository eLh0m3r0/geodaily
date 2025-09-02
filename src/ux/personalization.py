"""
User experience enhancements with personalization and feedback mechanisms.
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from ..models import AIAnalysis, ContentType


class UserPreference(Enum):
    """User content preferences."""
    BREAKING_NEWS = "breaking_news"
    ANALYSIS = "analysis"
    TREND = "trend"
    ECONOMICS = "economics"
    SECURITY = "security"
    DIPLOMACY = "diplomacy"
    TECHNOLOGY = "technology"


class FeedbackType(Enum):
    """Types of user feedback."""
    RELEVANCE = "relevance"
    QUALITY = "quality"
    TIMELINESS = "timeliness"
    USEFULNESS = "usefulness"


@dataclass
class UserProfile:
    """User profile with preferences and history."""
    user_id: str
    preferences: Dict[UserPreference, float] = field(default_factory=dict)
    content_history: List[Dict[str, Any]] = field(default_factory=list)
    feedback_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def __post_init__(self):
        # Initialize default preferences if empty
        if not self.preferences:
            for pref in UserPreference:
                self.preferences[pref] = 0.5  # Neutral preference

    def update_preference(self, preference: UserPreference, score: float):
        """Update user preference score."""
        self.preferences[preference] = max(0.0, min(1.0, score))
        self.last_updated = time.time()

    def record_content_interaction(self, content_id: str, interaction_type: str, score: float):
        """Record user interaction with content."""
        interaction = {
            'content_id': content_id,
            'interaction_type': interaction_type,
            'score': score,
            'timestamp': time.time()
        }
        self.content_history.append(interaction)

        # Keep only last 100 interactions
        if len(self.content_history) > 100:
            self.content_history = self.content_history[-100:]

        self.last_updated = time.time()

    def record_feedback(self, content_id: str, feedback_type: FeedbackType, rating: float, comment: Optional[str] = None):
        """Record user feedback."""
        feedback = {
            'content_id': content_id,
            'feedback_type': feedback_type.value,
            'rating': rating,
            'comment': comment,
            'timestamp': time.time()
        }
        self.feedback_history.append(feedback)

        # Keep only last 50 feedback entries
        if len(self.feedback_history) > 50:
            self.feedback_history = self.feedback_history[-50:]

        self.last_updated = time.time()

    def get_personalized_score(self, content_type: ContentType, topics: List[str]) -> float:
        """Calculate personalized relevance score for content."""
        base_score = 0.5

        # Content type preference
        content_type_pref = self.preferences.get(UserPreference(content_type.value), 0.5)
        base_score = (base_score + content_type_pref) / 2

        # Topic preferences
        topic_boost = 0.0
        topic_count = 0

        topic_mapping = {
            'economics': UserPreference.ECONOMICS,
            'security': UserPreference.SECURITY,
            'diplomacy': UserPreference.DIPLOMACY,
            'technology': UserPreference.TECHNOLOGY
        }

        for topic in topics:
            topic_lower = topic.lower()
            if topic_lower in topic_mapping:
                pref = self.preferences.get(topic_mapping[topic_lower], 0.5)
                topic_boost += pref
                topic_count += 1

        if topic_count > 0:
            topic_score = topic_boost / topic_count
            base_score = (base_score + topic_score) / 2

        return base_score


@dataclass
class PersonalizedNewsletter:
    """Personalized newsletter content."""
    user_id: str
    base_newsletter: Any  # Newsletter object
    personalized_stories: List[AIAnalysis] = field(default_factory=list)
    recommended_stories: List[AIAnalysis] = field(default_factory=list)
    user_profile: UserProfile = None
    personalization_score: float = 0.0


class PersonalizationEngine:
    """
    Engine for personalizing newsletter content based on user preferences.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("personalization_engine")
        self.user_profiles: Dict[str, UserProfile] = {}
        self.content_cache: Dict[str, Dict[str, Any]] = {}

        # Load existing user profiles
        self._load_user_profiles()

    def get_or_create_user_profile(self, user_id: str) -> UserProfile:
        """Get existing user profile or create new one."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id=user_id)
            self.logger.info("Created new user profile",
                           structured_data={'user_id': user_id})

        return self.user_profiles[user_id]

    def personalize_newsletter(self, user_id: str, stories: List[AIAnalysis]) -> PersonalizedNewsletter:
        """
        Personalize newsletter content for a specific user.

        Args:
            user_id: User identifier
            stories: List of available stories

        Returns:
            Personalized newsletter content
        """
        user_profile = self.get_or_create_user_profile(user_id)

        # Score stories based on user preferences
        scored_stories = []
        for story in stories:
            # Extract topics from story content
            topics = self._extract_topics_from_story(story)

            # Calculate personalized score
            personal_score = user_profile.get_personalized_score(story.content_type, topics)

            scored_stories.append({
                'story': story,
                'personal_score': personal_score,
                'topics': topics
            })

        # Sort by personalized score
        scored_stories.sort(key=lambda x: x['personal_score'], reverse=True)

        # Select top stories for personalized newsletter
        top_stories = [item['story'] for item in scored_stories[:4]]  # Top 4 stories
        recommended_stories = [item['story'] for item in scored_stories[4:8]]  # Next 4 as recommendations

        # Calculate overall personalization score
        avg_personal_score = sum(item['personal_score'] for item in scored_stories[:4]) / len(scored_stories[:4]) if scored_stories else 0

        personalized_newsletter = PersonalizedNewsletter(
            user_id=user_id,
            base_newsletter=None,  # Would be set by caller
            personalized_stories=top_stories,
            recommended_stories=recommended_stories,
            user_profile=user_profile,
            personalization_score=avg_personal_score
        )

        self.logger.info("Personalized newsletter created",
                        structured_data={
                            'user_id': user_id,
                            'stories_selected': len(top_stories),
                            'recommendations': len(recommended_stories),
                            'personalization_score': avg_personal_score
                        })

        return personalized_newsletter

    def process_user_feedback(self, user_id: str, content_id: str, feedback_type: FeedbackType, rating: float, comment: Optional[str] = None):
        """
        Process user feedback and update preferences.

        Args:
            user_id: User identifier
            content_id: Content identifier
            feedback_type: Type of feedback
            rating: Rating score (0.0 to 1.0)
            comment: Optional feedback comment
        """
        user_profile = self.get_or_create_user_profile(user_id)

        # Record feedback
        user_profile.record_feedback(content_id, feedback_type, rating, comment)

        # Update preferences based on feedback
        self._update_preferences_from_feedback(user_profile, content_id, feedback_type, rating)

        # Save updated profile
        self._save_user_profile(user_profile)

        self.logger.info("User feedback processed",
                        structured_data={
                            'user_id': user_id,
                            'content_id': content_id,
                            'feedback_type': feedback_type.value,
                            'rating': rating
                        })

    def _extract_topics_from_story(self, story: AIAnalysis) -> List[str]:
        """Extract relevant topics from story content."""
        content = f"{story.story_title} {story.why_important} {story.what_overlooked}".lower()
        topics = []

        # Define topic keywords
        topic_keywords = {
            'economics': ['economic', 'trade', 'finance', 'market', 'currency', 'bank', 'investment'],
            'security': ['security', 'military', 'defense', 'conflict', 'war', 'terrorism', 'intelligence'],
            'diplomacy': ['diplomatic', 'negotiation', 'treaty', 'alliance', 'summit', 'embassy', 'minister'],
            'technology': ['technology', 'cyber', 'digital', 'ai', 'innovation', 'research', 'semiconductor']
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in content for keyword in keywords):
                topics.append(topic)

        return topics

    def _update_preferences_from_feedback(self, user_profile: UserProfile, content_id: str, feedback_type: FeedbackType, rating: float):
        """Update user preferences based on feedback."""
        # Find the content in cache to get its characteristics
        content_info = self.content_cache.get(content_id)
        if not content_info:
            return

        content_type = content_info.get('content_type')
        topics = content_info.get('topics', [])

        # Update content type preference
        if content_type:
            try:
                pref = UserPreference(content_type)
                current_score = user_profile.preferences.get(pref, 0.5)

                # Adjust preference based on feedback
                if feedback_type == FeedbackType.RELEVANCE:
                    # Higher relevance rating increases preference
                    new_score = current_score + (rating - 0.5) * 0.1
                elif feedback_type == FeedbackType.QUALITY:
                    # Quality affects preference less directly
                    new_score = current_score + (rating - 0.5) * 0.05
                else:
                    new_score = current_score

                user_profile.update_preference(pref, new_score)

            except ValueError:
                pass  # Invalid content type

        # Update topic preferences
        topic_mapping = {
            'economics': UserPreference.ECONOMICS,
            'security': UserPreference.SECURITY,
            'diplomacy': UserPreference.DIPLOMACY,
            'technology': UserPreference.TECHNOLOGY
        }

        for topic in topics:
            if topic in topic_mapping:
                pref = topic_mapping[topic]
                current_score = user_profile.preferences.get(pref, 0.5)

                # Adjust topic preference
                adjustment = (rating - 0.5) * 0.05
                new_score = current_score + adjustment
                user_profile.update_preference(pref, new_score)

    def cache_content_info(self, content_id: str, content_type: str, topics: List[str]):
        """Cache content information for personalization."""
        self.content_cache[content_id] = {
            'content_type': content_type,
            'topics': topics,
            'cached_at': time.time()
        }

        # Clean old cache entries (older than 7 days)
        current_time = time.time()
        self.content_cache = {
            cid: info for cid, info in self.content_cache.items()
            if current_time - info['cached_at'] < 604800  # 7 days
        }

    def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """Get insights about user preferences and behavior."""
        user_profile = self.user_profiles.get(user_id)
        if not user_profile:
            return {'error': 'User profile not found'}

        # Analyze preferences
        top_preferences = sorted(
            user_profile.preferences.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        # Analyze feedback trends
        feedback_summary = {}
        for feedback in user_profile.feedback_history[-20:]:  # Last 20 feedback entries
            fb_type = feedback['feedback_type']
            if fb_type not in feedback_summary:
                feedback_summary[fb_type] = []
            feedback_summary[fb_type].append(feedback['rating'])

        avg_feedback = {}
        for fb_type, ratings in feedback_summary.items():
            avg_feedback[fb_type] = sum(ratings) / len(ratings) if ratings else 0

        return {
            'user_id': user_id,
            'top_preferences': [{'preference': p.value, 'score': s} for p, s in top_preferences],
            'average_feedback': avg_feedback,
            'total_feedback': len(user_profile.feedback_history),
            'total_interactions': len(user_profile.content_history),
            'profile_age_days': (time.time() - user_profile.created_at) / 86400
        }

    def _load_user_profiles(self):
        """Load user profiles from persistent storage."""
        try:
            # In a real implementation, this would load from a database
            # For now, we'll start with empty profiles
            pass
        except Exception as e:
            self.logger.warning(f"Failed to load user profiles: {e}")

    def _save_user_profile(self, user_profile: UserProfile):
        """Save user profile to persistent storage."""
        try:
            # In a real implementation, this would save to a database
            # For now, we'll keep it in memory
            pass
        except Exception as e:
            self.logger.warning(f"Failed to save user profile: {e}")


class FeedbackCollector:
    """
    Collects and processes user feedback for continuous improvement.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("feedback_collector")
        self.feedback_data: List[Dict[str, Any]] = []
        self.insights_cache: Dict[str, Any] = {}

    def collect_feedback(self, user_id: str, content_id: str, feedback_data: Dict[str, Any]):
        """
        Collect feedback from user.

        Args:
            user_id: User identifier
            content_id: Content identifier
            feedback_data: Feedback information
        """
        feedback_entry = {
            'user_id': user_id,
            'content_id': content_id,
            'timestamp': time.time(),
            **feedback_data
        }

        self.feedback_data.append(feedback_entry)

        # Keep only last 1000 feedback entries
        if len(self.feedback_data) > 1000:
            self.feedback_data = self.feedback_data[-1000:]

        self.logger.info("Feedback collected",
                        structured_data={
                            'user_id': user_id,
                            'content_id': content_id,
                            'feedback_type': feedback_data.get('type', 'unknown')
                        })

    def generate_feedback_report(self) -> Dict[str, Any]:
        """Generate comprehensive feedback report."""
        if not self.feedback_data:
            return {'error': 'No feedback data available'}

        # Analyze feedback by type
        feedback_by_type = {}
        ratings_by_type = {}

        for entry in self.feedback_data:
            fb_type = entry.get('type', 'unknown')

            if fb_type not in feedback_by_type:
                feedback_by_type[fb_type] = 0
                ratings_by_type[fb_type] = []

            feedback_by_type[fb_type] += 1

            if 'rating' in entry:
                ratings_by_type[fb_type].append(entry['rating'])

        # Calculate averages
        avg_ratings = {}
        for fb_type, ratings in ratings_by_type.items():
            if ratings:
                avg_ratings[fb_type] = sum(ratings) / len(ratings)

        # Content performance analysis
        content_ratings = {}
        for entry in self.feedback_data:
            content_id = entry['content_id']
            if content_id not in content_ratings:
                content_ratings[content_id] = []
            if 'rating' in entry:
                content_ratings[content_id].append(entry['rating'])

        top_content = sorted(
            [(cid, sum(ratings)/len(ratings), len(ratings)) for cid, ratings in content_ratings.items() if ratings],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            'total_feedback': len(self.feedback_data),
            'feedback_by_type': feedback_by_type,
            'average_ratings': avg_ratings,
            'top_rated_content': [
                {'content_id': cid, 'avg_rating': rating, 'votes': votes}
                for cid, rating, votes in top_content
            ],
            'time_range': {
                'oldest': min(entry['timestamp'] for entry in self.feedback_data),
                'newest': max(entry['timestamp'] for entry in self.feedback_data)
            }
        }


# Global instances
personalization_engine = PersonalizationEngine()
feedback_collector = FeedbackCollector()