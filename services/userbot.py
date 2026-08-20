import os
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.types import Chat, Channel

logger = logging.getLogger(__name__)


class UserbotService:
    def __init__(self):
        self.api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH", "")
        self.session_name = "data/tutor_userbot_session"
        self.client: TelegramClient = None
        self.is_connected = False

    async def connect(self):
        if not self.api_id or not self.api_hash:
            logger.error("TELEGRAM_API_ID или API_HASH не заданы")
            return False

        try:
            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash,
                system_version="4.16.30-vxCUSTOM"
            )
            await self.client.connect()
            
            # Проверяем, есть ли сохраненная сессия
            if await self.client.is_user_authorized():
                self.is_connected = True
                me = await self.client.get_me()
                logger.info(f"✅ Userbot подключен: {me.first_name}")
                return True
            else:
                logger.info("Userbot требует авторизации")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка подключения userbot: {e}")
            return False

    async def send_code_request(self, phone: str):
        """Отправляем код на номер телефона"""
        try:
            await self.client.send_code_request(phone)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки кода: {e}")
            return False

    async def sign_in(self, phone: str, code: str):
        """Входим по коду"""
        try:
            await self.client.sign_in(phone, code)
            self.is_connected = True
            me = await self.client.get_me()
            logger.info(f"✅ Userbot авторизован: {me.first_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка входа: {e}")
            return False

    async def get_chats(self, limit: int = 20) -> list:
        """Получаем список чатов и каналов"""
        if not self.is_connected:
            return []
        
        try:
            dialogs = await self.client.get_dialogs(limit=limit)
            chats = []
            for dialog in dialogs:
                entity = dialog.entity
                # Берем только группы и супергруппы
                if isinstance(entity, (Chat, Channel)) and not dialog.is_user:
                    chats.append({
                        "id": entity.id,
                        "title": dialog.title or "Без названия",
                        "type": "Канал" if isinstance(entity, Channel) else "Группа"
                    })
            return chats
        except Exception as e:
            logger.error(f"Ошибка получения чатов: {e}")
            return []

    async def send_message_safe(self, chat_id: int, text: str):
        """Безопасная отправка сообщения с рандомной задержкой"""
        if not self.is_connected:
            return False
        
        try:
            # Рандомная задержка 5-30 секунд для имитации человека
            import random
            delay = random.uniform(5, 30)
            await asyncio.sleep(delay)
            
            await self.client.send_message(chat_id, text)
            logger.info(f"✅ Сообщение отправлено в чат {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки в чат {chat_id}: {e}")
            return False

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
            self.is_connected = False


userbot = UserbotService()