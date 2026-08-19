import random
from database import db


class ABTestingService:
    """Сервис A/B тестирования рекламных текстов."""

    @staticmethod
    async def get_variant(test_id: int) -> tuple[str, str]:
        """
        Возвращает (текст варианта, название варианта 'A' или 'B').
        Равномерное распределение.
        """
        tests = await db.get_active_ab_tests()
        test = next((t for t in tests if t["id"] == test_id), None)
        if not test:
            return "", ""

        # Выбираем вариант с меньшим количеством отправок
        if test["variant_a_sends"] <= test["variant_b_sends"]:
            variant = "A"
            text = test["variant_a_text"]
        else:
            variant = "B"
            text = test["variant_b_text"]

        # Инкрементируем счётчик
        await db.increment_ab_stat(test_id, variant, "sends")

        return text, variant

    @staticmethod
    async def record_click(test_id: int, variant: str):
        """Записать клик (переход) для варианта."""
        await db.increment_ab_stat(test_id, variant, "clicks")