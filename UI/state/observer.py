"""
Observer pattern: Subject with pub/sub capabilities.

No game knowledge, just a simple event system that UI components can subscribe to.
"""
from __future__ import annotations
from typing import Callable, TypeVar, Generic, Any
from dataclasses import dataclass


EventType = TypeVar('EventType')


class Subject(Generic[EventType]):
    """
    Simple event subject with subscriptions.
    
    Responsibilities:
      - Allow callbacks to subscribe to events
      - Publish events to all subscribers
      - No game logic, just glue
    """
    
    def __init__(self):
        self._subscribers: list[Callable[[EventType], None]] = []
    
    def subscribe(self, callback: Callable[[EventType], None]) -> None:
        """
        Add a callback to be called when events are published.
        
        :param callback: function taking one event argument
        """
        self._subscribers.append(callback)
    
    def publish(self, event: EventType) -> None:
        """
        Notify all subscribers of an event.
        
        :param event: the event object to pass to all callbacks
        """
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception as e:
                # Log but don't crash if a subscriber fails
                print(f"Error in subscriber: {e}")
