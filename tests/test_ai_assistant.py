# -*- coding: utf-8 -*-
"""Тесты ИИ-ассистента: сборка системного промпта из анкеты и FAQ."""
from services import ai_assistant as ai


class TestBuildSystemPrompt:
    def test_includes_knowledge_base(self):
        prompt = ai.build_system_prompt(
            {
                ai.KB_NAME: "Мария, репетитор по математике",
                ai.KB_SUBJECTS: "Математика — 1200 ₽/час\nОГЭ-подготовка — 1500 ₽/час",
                ai.KB_ABOUT: "8 лет опыта, онлайн, пробное бесплатно",
            },
            faq=[],
        )
        assert "Мария" in prompt
        assert "1200 ₽/час" in prompt
        assert "8 лет опыта" in prompt

    def test_human_persona_rules(self):
        """Живой человек: без смайлов, без приветствий в каждом ответе."""
        prompt = ai.build_system_prompt({ai.KB_NAME: "Мария"}, faq=[])
        low = prompt.lower()
        assert "не ассистент и не бот" in low
        assert "без эмодзи" in low
        assert "не здоровайся при каждом" in low

    def test_custom_style_appended_with_priority(self):
        prompt = ai.build_system_prompt(
            {ai.KB_STYLE: "Обращайся на ты и шути."}, faq=[]
        )
        assert "Обращайся на ты и шути." in prompt
        assert "приоритетнее всего" in prompt.lower() or "главнее" in prompt.lower()

    def test_no_style_no_extra_block(self):
        prompt = ai.build_system_prompt({}, faq=[])
        assert "Особый стиль" not in prompt

    def test_includes_faq(self):
        prompt = ai.build_system_prompt(
            {ai.KB_NAME: "", ai.KB_SUBJECTS: "", ai.KB_ABOUT: ""},
            faq=[{"question": "Где проходят занятия?", "answer": "В Zoom онлайн."}],
        )
        assert "Где проходят занятия?" in prompt
        assert "В Zoom онлайн." in prompt

    def test_empty_kb_still_works(self):
        prompt = ai.build_system_prompt({}, faq=[])
        assert "Анкета пока не заполнена" in prompt

    def test_no_invented_promise_words(self):
        """Промпт обязан запрещать выдумывать — это ключевое требование."""
        prompt = ai.build_system_prompt(
            {ai.KB_SUBJECTS: "Математика"}, faq=[]
        )
        assert "не выдумывай" in prompt.lower() or "ничего не выдумывай" in prompt.lower()


class TestCustomPrompt:
    def test_override_replaces_default(self):
        prompt = ai.build_system_prompt(
            {ai.KB_PROMPT: "Ты — Мария. Отвечай коротко и на ты.",
             ai.KB_SUBJECTS: "Математика — 1000 ₽/час"},
            faq=[],
        )
        assert "Ты — Мария" in prompt
        assert "Ты — репетитор" not in prompt      # стандартный шаблон не участвует
        assert "1000 ₽/час" in prompt              # факты приложены

    def test_no_override_keeps_default(self):
        prompt = ai.build_system_prompt({ai.KB_SUBJECTS: "Физика"}, faq=[])
        assert "Ты — репетитор" in prompt
