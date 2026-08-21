import os
import asyncio
import logging
import random
from typing import Optional
from telethon import TelegramClient
from telethon.tl.types import Chat, Channel
from telethon.errors import UsernameInvalidError, UsernameNotOccupiedError
logger = logging.getLogger(__name__)
class UserbotService:
    def __init__(self):
        self.api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH", "")
        self.phone = os.getenv("TELEGRAM_PHONE", "")
        self.session_name = "data/tutor_userbot_session"
        self.client: Optional[TelegramClient] = None
        self.is_connected = False
    async def connect(self):
        """Подключение userbot. Если есть сохранённая сессия — подключается автоматически."""
        if not self.api_id or not self.api_hash:
            logger.warning("Userbot: TELEGRAM_API_ID или API_HASH не заданы — пропускаем")
            return False
        try:
            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash,
                system_version="4.16.30-vxCUSTOM"
            )
            await self.client.connect()
            if await self.client.is_user_authorized():
                self.is_connected = True
                me = await self.client.get_me()
                logger.info(f"✅ Userbot подключен: {me.first_name} ({me.phone})")
                return True
            else:
                logger.info(
                    "Userbot: нет сохранённой сессии. "
                    "Авторизуйтесь через админ-панель (/admin → Рассылки → Userbot)"
                )
                return False
        except Exception as e:
            logger.error(f"Userbot: ошибка подключения: {e}")
            return False
    async def send_code_request(self, phone: str) -> bool:
        """Отправляем код подтверждения на номер телефона."""
        if not self.client:
            try:
                self.client = TelegramClient(
                    self.session_name,
                    self.api_id,
                    self.api_hash,
                    system_version="4.16.30-vxCUSTOM"
                )
                await self.client.connect()
            except Exception as e:
                logger.error(f"Userbot: не удалось создать клиент: {e}")
                return False
        try:
            await self.client.send_code_request(phone)
            logger.info(f"Userbot: код отправлен на {phone}")
            return True
        except Exception as e:
            logger.error(f"Userbot: ошибка отправки кода на {phone}: {e}")
            return False
    async def sign_in(self, phone: str, code: str) -> bool:
        """Входим по коду подтверждения."""
        if not self.client:
            logger.error("Userbot: клиент не инициализирован")
            return False
        try:
            await self.client.sign_in(phone, code)
            self.is_connected = True
            me = await self.client.get_me()
            logger.info(f"✅ Userbot авторизован: {me.first_name} ({me.phone})")
            return True
        except Exception as e:
            logger.error(f"Userbot: ошибка входа: {e}")
            return False
    async def get_chats(self, limit: int = 50) -> list:
        """Получаем список групп и каналов для рассылки."""
        if not self.is_connected or not self.client:
            logger.warning("Userbot: не подключен")
            return []
        try:
            dialogs = await self.client.get_dialogs(limit=limit)
            chats = []
            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, (Chat, Channel)) and not dialog.is_user:
                    member_count = getattr(entity, 'participants_count', None) or 0
                    username = getattr(entity, 'username', None) or None
                    chats.append({
                        "id": entity.id,
                        "title": dialog.title or "Без названия",
                        "username": username,
                        "type": "Канал" if isinstance(entity, Channel) else "Группа",
                        "members": member_count
                    })
            logger.info(f"Userbot: найдено {len(chats)} чатов")
            return chats
        except Exception as e:
            logger.error(f"Userbot: ошибка получения чатов: {e}")
            return []
    async def get_chat_by_username(self, username: str) -> Optional[dict]:
        """Найти чат по @username и вернуть его данные."""
        if not self.is_connected or not self.client:
            logger.warning("Userbot: не подключен")
            return None
        clean_username = username.lstrip("@")
        try:
            entity = await self.client.get_entity(clean_username)
            if isinstance(entity, (Chat, Channel)):
                member_count = getattr(entity, 'participants_count', None) or 0
                chat_username = getattr(entity, 'username', None) or None
                result = {
                    "id": entity.id,
                    "title": getattr(entity, 'title', 'Без названия'),
                    "username": chat_username,
                    "type": "Канал" if isinstance(entity, Channel) else "Группа",
                    "members": member_count
                }
                logger.info(f"Userbot: найден чат по @{clean_username}: {result['title']}")
                return result
            else:
                logger.warning(f"Userbot: @{clean_username} — это не группа/канал")
                return None
        except UsernameInvalidError:
            logger.error(f"Userbot: неверный формат username: @{clean_username}")
            return None
        except UsernameNotOccupiedError:
            logger.error(f"Userbot: username @{clean_username} не существует")
            return None
        except Exception as e:
            logger.error(f"Userbot: ошибка поиска @{clean_username}: {e}")
            return None
    async def send_message_safe(self, chat_id: int, text: str,
                                min_delay: float = 5.0,
                                max_delay: float = 30.0) -> bool:
        """Безопасная отправка сообщения с рандомной задержкой.

        ИСПРАВЛЕНО: обрабатываем FloodWaitError (лимит Telegram) —
        ждём нужное время и повторяем вместо мгновенного отказа.
        """
        if not self.is_connected or not self.client:
            return False
        try:
            from telethon.errors import FloodWaitError
        except ImportError:
            FloodWaitError = None
        try:
            if max_delay > 0:
                delay = random.uniform(min_delay, max_delay)
                await asyncio.sleep(delay)
            try:
                await self.client.send_message(chat_id, text)
            except FloodWaitError as e:
                wait = int(e.seconds)
                if wait > 3600:
                    logger.warning(
                        f"Userbot: flood-wait {wait}с в чат {chat_id} — пропускаем"
                    )
                    return False
                logger.info(f"Userbot: flood-wait {wait}с, ждём и повторяем...")
                await asyncio.sleep(wait + 5)
                await self.client.send_message(chat_id, text)
            logger.info(f"✅ Userbot: сообщение отправлено в чат {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Userbot: ошибка отправки в чат {chat_id}: {e}")
            return False
    async def send_mailing_to_chats(
        self,
        chat_ids: list[int],
        text: str,
        delay_between: float = 10.0,
    ) -> dict:
        """Массовая рассылка по чатам от имени репетитора."""
        if not self.is_connected or not self.client:
            return {"sent": 0, "errors": len(chat_ids), "errors_list": ["Не подключен"]}
        sent = 0
        errors = 0
        errors_list = []
        total = len(chat_ids)
        for i, chat_id in enumerate(chat_ids):
            jitter = min(5.0, delay_between / 4) if delay_between > 0 else 0
            result = await self.send_message_safe(
                chat_id, text, min_delay=0, max_delay=jitter
            )
            if result:
                sent += 1
            else:
                errors += 1
                errors_list.append(str(chat_id))
            if delay_between > 0 and i < total - 1:
                await asyncio.sleep(delay_between)
        logger.info(f"Userbot рассылка: отправлено {sent}, ошибок {errors}")
        return {"sent": sent, "errors": errors, "errors_list": errors_list}
    async def disconnect(self):
        """Отключение userbot."""
        if self.client:
            try:
                await self.client.disconnect()
                self.is_connected = False
                logger.info("Userbot: отключен")
            except Exception as e:
                logger.error(f"Userbot: ошибка отключения: {e}")
userbot = UserbotService()
