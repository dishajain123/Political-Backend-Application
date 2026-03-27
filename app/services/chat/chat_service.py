"""
Chat Service Module
===================
Business logic for the messaging system.
Delegates to split mixins for maintainability.

Author: Political Communication Platform Team
"""

import logging

from app.db.mongodb import get_database
from app.services.translation_service import TranslationService
from app.services.chat.rooms import ChatRoomsMixin
from app.services.chat.messages import ChatMessagesMixin


logger = logging.getLogger("app.services.chat_service")


class ChatService(ChatRoomsMixin, ChatMessagesMixin):

    def __init__(self):
        self.db = get_database()
        self.translation_service = TranslationService()
