import json
import logging
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Union
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class UserSettings:
    """User personalization settings"""
    hidden_message_types: List[str] = field(default_factory=list)  # Message types to hide
    custom_cwd: Optional[str] = None  # Custom working directory
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UserSettings':
        """Create from dictionary"""
        return cls(**data)


class SettingsManager:
    """Manages user personalization settings with JSON persistence"""
    
    def __init__(self, settings_file: str = "user_settings.json"):
        self.settings_file = Path(settings_file)
        self.settings: Dict[Union[int, str], UserSettings] = {}
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from JSON file"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    for user_id_str, user_data in data.items():
                        # Try to convert to int for Telegram, keep as string for Slack
                        try:
                            user_id = int(user_id_str)
                        except ValueError:
                            user_id = user_id_str
                        self.settings[user_id] = UserSettings.from_dict(user_data)
                logger.info(f"Loaded settings for {len(self.settings)} users")
            else:
                logger.info("No settings file found, starting with empty settings")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.settings = {}
    
    def _save_settings(self):
        """Save settings to JSON file"""
        try:
            data = {
                str(user_id): settings.to_dict() 
                for user_id, settings in self.settings.items()
            }
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def get_user_settings(self, user_id: Union[int, str]) -> UserSettings:
        """Get settings for a specific user"""
        if user_id not in self.settings:
            self.settings[user_id] = UserSettings()
            self._save_settings()
        return self.settings[user_id]
    
    def update_user_settings(self, user_id: Union[int, str], settings: UserSettings):
        """Update settings for a specific user"""
        self.settings[user_id] = settings
        self._save_settings()
    
    def toggle_hidden_message_type(self, user_id: Union[int, str], message_type: str) -> bool:
        """Toggle a message type in hidden list, returns new state"""
        settings = self.get_user_settings(user_id)
        
        if message_type in settings.hidden_message_types:
            settings.hidden_message_types.remove(message_type)
            is_hidden = False
        else:
            settings.hidden_message_types.append(message_type)
            is_hidden = True
        
        self.update_user_settings(user_id, settings)
        return is_hidden
    
    def set_custom_cwd(self, user_id: int, cwd: str):
        """Set custom working directory for user"""
        settings = self.get_user_settings(user_id)
        settings.custom_cwd = cwd
        self.update_user_settings(user_id, settings)
    
    def get_custom_cwd(self, user_id: int) -> Optional[str]:
        """Get custom working directory for user"""
        settings = self.get_user_settings(user_id)
        return settings.custom_cwd
    
    def is_message_type_hidden(self, user_id: int, message_type: str) -> bool:
        """Check if a message type is hidden for user"""
        settings = self.get_user_settings(user_id)
        return message_type in settings.hidden_message_types
    
    def get_available_message_types(self) -> List[str]:
        """Get list of available message types that can be hidden"""
        return [
            "system",
            "user",
            "assistant",
            "result"
        ]
    
    def get_message_type_display_names(self) -> Dict[str, str]:
        """Get display names for message types"""
        return {
            "system": "System",
            "user": "Response",  # Renamed from 'user' for clarity
            "assistant": "Assistant",
            "result": "Result"
        }