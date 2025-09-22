"""
File: notification_system.py
Author: [Tarakeshwar NC] / Claude Code
Date: September 11, 2025
Description: Core notification system classes with structured objects, validation, and logging for TeZ trading platform
"""
# Copyright (c) [2025] [Tarakeshwar N.C]
# This file is part of the Tez project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__author__ = "Tarakeshwar N.C"
__copyright__ = "2025"
__date__ = "2025/9/11"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"


from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time
import logging

from .notification_types import NotificationID, NotificationCategory, NotificationPriority


@dataclass  
class Notification:
    """Structured notification with comprehensive metadata"""
    id: NotificationID
    category: NotificationCategory
    priority: NotificationPriority
    message: str
    data: Optional[Dict[str, Any]] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: Optional[str] = None
    target: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for port transmission"""
        return {
            'notification_id': self.id.value,
            'notification_name': self.id.name,
            'category': self.category.value,
            'priority': self.priority.value,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp,
            'source': self.source,
            'target': self.target,
            'correlation_id': self.correlation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        """Create from dictionary received via port"""
        return cls(
            id=NotificationID(data['notification_id']),
            category=NotificationCategory(data['category']),
            priority=NotificationPriority(data['priority']),
            message=data['message'],
            data=data.get('data', {}),
            timestamp=data.get('timestamp', time.time()),
            source=data.get('source'),
            target=data.get('target'),
            correlation_id=data.get('correlation_id')
        )
    
    def is_critical(self) -> bool:
        """Check if notification requires immediate attention"""
        return self.priority >= NotificationPriority.CRITICAL
    
    def is_high_priority(self) -> bool:
        """Check if notification is high priority or above"""
        return self.priority >= NotificationPriority.HIGH
    
    def get_log_level(self) -> int:
        """Map priority to logging level"""
        priority_to_level = {
            NotificationPriority.LOW: logging.DEBUG,
            NotificationPriority.NORMAL: logging.INFO,
            NotificationPriority.HIGH: logging.WARNING,
            NotificationPriority.CRITICAL: logging.ERROR,
            NotificationPriority.EMERGENCY: logging.CRITICAL
        }
        return priority_to_level.get(self.priority, logging.INFO)
    
    def get_log_level_name(self) -> str:
        """Get string name of log level"""
        level = self.get_log_level()
        return logging.getLevelName(level)
    
    def __str__(self) -> str:
        """String representation for logging"""
        return (f"Notification(id={self.id.name}, category={self.category.value}, "
                f"priority={self.priority.name}, source={self.source}, "
                f"correlation_id={self.correlation_id})")
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (f"Notification(id={self.id.name}({self.id.value}), "
                f"category={self.category.value}, priority={self.priority.name}({self.priority.value}), "
                f"message='{self.message}', source={self.source}, target={self.target}, "
                f"correlation_id={self.correlation_id}, timestamp={self.timestamp})")


class NotificationValidator:
    """Validator for notification data integrity"""
    
    @staticmethod
    def validate_notification(notification: Notification) -> bool:
        """Validate notification structure and data"""
        try:
            # Check required fields
            if not isinstance(notification.id, NotificationID):
                return False
            if not isinstance(notification.category, NotificationCategory):
                return False
            if not isinstance(notification.priority, NotificationPriority):
                return False
            if not notification.message:
                return False
            
            # Validate data structure
            if notification.data is not None and not isinstance(notification.data, dict):
                return False
            
            # Validate timestamp
            if notification.timestamp <= 0:
                return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def validate_dict_format(data: Dict[str, Any]) -> bool:
        """Validate dictionary format for notification creation"""
        required_fields = ['notification_id', 'category', 'priority', 'message']
        
        try:
            # Check required fields exist
            for field in required_fields:
                if field not in data:
                    return False
            
            # Validate enum values
            NotificationID(data['notification_id'])
            NotificationCategory(data['category'])
            NotificationPriority(data['priority'])
            
            return True
            
        except (ValueError, KeyError):
            return False


class NotificationLogger:
    """Enhanced logging for notifications"""
    
    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)
    
    def log_notification(self, notification: Notification, action: str = "processed"):
        """Log notification with appropriate level and structured format"""
        log_level = notification.get_log_level()
        
        # Create structured log message
        log_msg = (
            f"Notification {action}: {notification.id.name} "
            f"[{notification.category.value.upper()}] "
            f"Priority={notification.priority.name} "
            f"Source={notification.source} "
            f"Target={notification.target or 'N/A'} "
            f"Correlation={notification.correlation_id or 'N/A'}"
        )
        
        # Add message if not too long
        if len(notification.message) <= 100:
            log_msg += f" Message='{notification.message}'"
        else:
            log_msg += f" Message='{notification.message[:97]}...'"
        
        self.logger.log(log_level, log_msg)
    
    def log_notification_error(self, error: Exception, context: str = ""):
        """Log notification-related errors"""
        error_msg = f"Notification error"
        if context:
            error_msg += f" in {context}"
        error_msg += f": {str(error)}"
        
        self.logger.error(error_msg)
    
    def log_notification_validation_failed(self, data: Dict[str, Any], reason: str = ""):
        """Log validation failures"""
        log_msg = f"Notification validation failed"
        if reason:
            log_msg += f": {reason}"
        
        # Include safe data preview
        safe_data = {k: v for k, v in data.items() if k in ['notification_id', 'category', 'priority', 'source']}
        log_msg += f" Data preview: {safe_data}"
        
        self.logger.warning(log_msg)