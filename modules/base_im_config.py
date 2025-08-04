from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class BaseIMConfig(ABC):
    """Abstract base class for IM platform configurations"""
    
    @classmethod
    @abstractmethod
    def from_env(cls) -> 'BaseIMConfig':
        """Create configuration from environment variables"""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate the configuration
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        pass