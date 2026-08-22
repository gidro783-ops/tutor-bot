# -*- coding: utf-8 -*-
"""Тесты ИИ-ассистента: сборка системного промпта из анкеты и FAQ."""
from services import ai_assistant as ai


class TestBuildSystemPrompt:
    def test_includes_knowledge_base(self):
        prompt = ai.build_system_prompt(
            {
                ai.KB_NAME: "Мария, репетитор по математике",
                ai.KB_SUBJECTS: "Математика — 1200 ₽/час\nОГЭ — 1500 ₽/час",
                ai.KB_ABOUT: "8 лет опыта, онлайн, пробное бесплатно",
            },
            faq=[],
        )
        assert "Мария" in prompt
        assert "1200 ₽/час" in prompt
        assert "8 лет опыта" in prompt
        assert "от имени репетитора" in prompt.lower() or "от лица репетитора" in prompt

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
