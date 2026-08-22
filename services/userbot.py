import os
import asyncio
import logging
import random
from typing import Optional, Tuple
from telethon import TelegramClient
from telethon.tl.types import Chat, Channel
from telethon.errors import (
    UsernameInvalidError, UsernameNotOccupiedError,
    SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, FloodWaitError, RPCError,
)
logger = logging.getLogger(__name__)

def normalize_phone(phone: str) -> str:
    """Возвращает номер в виде '+<цифры>' для сравнения.
    '+1 (555) 123-4567' → '+15551234567', '+79991234567' → '+79991234567'."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    return ("+" + digits) if digits else ""
class UserbotService:
    def __init__(self):
        self.api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH", "")
        self.phone = os.getenv("TELEGRAM_PHONE", "")
        self.session_name = os.getenv("USERBOT_SESSION_PATH", "data/tutor_userbot_session")
        self.client: Optional[TelegramClient] = None
        self.is_connected = False
        # v3.2: хэш кода, который Telethon понадобится при sign_in.
        # Без передачи этого хэша Telegraph часто возвращает PhoneCodeExpiredError
        # даже для свежего кода (особенно на +1-номерах).
        self.phone_code_hash: Optional[str] = None
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
                system_version="4.16.30-vxCUSTOM",
                device_model="Desktop",
                app_version="1.0",
                lang_code="en",
                system_lang_code="en-US",
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
    def _fresh_client(self) -> TelegramClient:
        return TelegramClient(
            self.session_name,
            self.api_id,
            self.api_hash,
            system_version="4.16.30-vxCUSTOM",
            device_model="Desktop",
            app_version="1.0",
            lang_code="en",
            system_lang_code="en-US",
        )

    def session_exists(self) -> bool:
        return os.path.exists(self.session_name + ".session")

    async def current_account_phone(self) -> Optional[str]:
        """Номер текущего (если есть) подключённого аккаунта."""
        if not self.client or not self.is_connected:
            return None
        try:
            me = await self.client.get_me()
            return normalize_phone(me.phone or "")
        except Exception:
            return None

    async def reset_session(self) -> bool:
        """ИСПРАВЛЕНИЕ (v3): полное отвязывание аккаунта.

        Раньше «🔌 Отключить» закрывал только соединение, а файл сессии
        data/tutor_userbot_session.* оставался с авторизацией СТАРОГО
        аккаунта. Из-за этого новый номер (например, американский)
        привязать было невозможно: Telethon по-прежнему «видел» себя
        авторизованным в другом аккаунте, запрос кода/вход падали с
        неясной ошибкой, а после перезапуска бота старая привязка
        возвращалась сама. Теперь сессия удаляется физически."""
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.warning(f"Userbot: ошибка при обрыве соединения: {e}")
        self.client = None
        self.is_connected = False
        for f in (self.session_name + ".session", self.session_name):
            try:
                if os.path.exists(f):
                    os.remove(f)
                    logger.info(f"Userbot: файл сессии {f} удалён")
            except Exception as e:
                logger.warning(f"Userbot: не удалось удалить {f}: {e}")
        return True

    async def send_code_request(self, phone: str) -> Tuple[bool, str]:
        """Отправляем код. ИСПРАВЛЕНО (v3):
        - возвращает (ok, ошибка) — репетитор видит реальную причину,
          а не просто «Ошибка отправки кода»;
        - если привязан другой аккаунт (другой номер) — автоматически
          сбрасывает старую сессию, иначе Telegram не даст код на
          новый номер (API думает, что вы уже в другом аккаунте)."""
        phone = normalize_phone(phone)
        if not phone:
            return False, "Не распознан номер. Формат: +79991234567 или +15551234567"
        try:
            old_phone = await self.current_account_phone()
            if old_phone and old_phone != phone:
                logger.info(
                    f"Userbot: смена аккаунта {old_phone} → {phone}, "
                    "сбрасываю старую сессию"
                )
                await self.reset_session()
        except Exception as e:
            logger.warning(f"Userbot: не удалось проверить старый аккаунт: {e}")
        if not self.client:
            try:
                self.client = self._fresh_client()
                await self.client.connect()
            except Exception as e:
                return False, f"Не удалось создать клиент: {e}"
        try:
            # v3.2: ОБЯЗАТЕЛЬНО сохраняем phone_code_hash для входа.
            # ИСПРАВЛЕНО: Telethon (актуальные версии) возвращает из
            # send_code_request СТРОКУ — сам хэш. Прежний код делал
            # getattr(sent, "phone_code_hash", None) и всегда получал None,
            # из-за чего sign_in уходил без хэша и Telegram отклонял даже
            # верный код. Поддерживаем и старый формат (объект SentCode).
            sent = await self.client.send_code_request(phone)
            if isinstance(sent, str):
                self.phone_code_hash = sent or None
            else:
                code_hash = getattr(sent, "phone_code_hash", None)
                if not code_hash:
                    inner = getattr(sent, "sent_code", None) or getattr(sent, "phone", None)
                    code_hash = getattr(inner, "phone_code_hash", None)
                self.phone_code_hash = code_hash
            logger.info(
                f"Userbot: код отправлен на {phone} "
                f"(phone_code_hash={'есть' if self.phone_code_hash else 'НЕТ'})"
            )
            return True, ""
        except FloodWaitError as e:
            return False, f"Слишком много попыток — Telegram просит подождать {e.seconds} с."
        except RPCError as e:
            # v3.1: PhoneBannedError в Telethon 1.36 нет; ловим все RPC-ошибки
            # и достаём вменяемое «PHONE_NUMBER_BANNED» из строки ошибки
            txt = str(e)
            if "BANNED" in txt.upper():
                return False, "Этот номер забанен в Telegram."
            err = f"{type(e).__name__}: {txt}"
            logger.error(f"Userbot: ошибка отправки кода на {phone}: {err}")
            return False, err
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            logger.error(f"Userbot: ошибка отправки кода на {phone}: {err}")
            return False, err
    async def sign_in(self, phone: str, code: str,
                      phone_code_hash: Optional[str] = None) -> Tuple[bool, str]:
        """Входим по коду. ИСПРАВЛЕНО (v3): возвращает (ok, ошибка).
        v3.2: используем phone_code_hash из send_code_request — иначе
        Telegram чаще всего отвечает PhoneCodeExpiredError даже на
        корректный свежий код."""
        if not self.client:
            return False, "Клиент не инициализирован"
        code_hash = phone_code_hash or self.phone_code_hash
        if not code_hash:
            # Без хэша Telethon запросит НОВЫЙ код, и введённый станет
            # недействительным — лучше явно попросить начать заново.
            return False, (
                "Сессия ввода кода потеряна (возможно, бот перезапускался).\n"
                "Нажмите «🔑 Авторизоваться» ещё раз — придёт новый код."
            )
        try:
            if code_hash:
                await self.client.sign_in(
                    phone, code, phone_code_hash=code_hash
                )
            else:
                await self.client.sign_in(phone, code)
            self.is_connected = True
            me = await self.client.get_me()
            logger.info(f"✅ Userbot авторизован: {me.first_name} ({me.phone})")
            return True, ""
        except SessionPasswordNeededError:
            logger.info("Userbot: у аккаунта включён двухступенчатый пароль")
            return False, "PASSWORD"
        except PhoneCodeInvalidError:
            return False, (
                "Код не подошёл. Проверьте:\n"
                "— не перепутан ли порядок (Telegram шлёт 5 цифр);\n"
                "— не истёк ли (живёт ~5 минут, затем просите новый);\n"
                "— не осталась ли активна старая сессия (нажмите «🔌 Отключить» и начните заново).\n"
                "Введите код ещё раз:"
            )
        except PhoneCodeExpiredError:
            return False, (
                "⌛ Код истёк (живёт ~5 минут).\n"
                "Нажмите «🔑 Авторизоваться» ещё раз — придёт новый код."
            )
        except FloodWaitError as e:
            return False, f"Слишком много попыток — подождите {e.seconds} с."
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            logger.error(f"Userbot: ошибка входа: {err}")
            return False, err
    async def finish_2fa(self, password: str) -> Tuple[bool, str]:
        """В3: завершение входа двухступенчатым паролем Telegram."""
        if not self.client:
            return False, "Клиент не инициализирован"
        try:
            await self.client.sign_in(password=password)
            self.is_connected = True
            me = await self.client.get_me()
            logger.info(f"✅ Userbot авторизован (2FA): {me.first_name} ({me.phone})")
            return True, ""
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            logger.error(f"Userbot: ошибка 2FA: {err}")
            return False, err
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
