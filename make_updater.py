# -*- coding: utf-8 -*-
"""Генератор apply_update.py: упаковывает все изменения vs origin/main."""
import base64
import gzip
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
WORKSPACE = Path(r"C:\Users\рс\.zcode\workspace\default")

diff = subprocess.run(
    ["git", "diff", "--name-status", "origin/main", "HEAD"],
    cwd=ROOT, capture_output=True, text=True, check=True,
).stdout.strip().splitlines()

new_or_changed, obsolete = [], []
for line in diff:
    parts = [p.strip() for p in line.split("\t") if p.strip()]
    if not parts:
        continue
    status, paths = parts[0], parts[1:]
    if status.startswith("R"):
        obsolete.append(paths[0])
        new_or_changed.append(paths[1])
    elif status.startswith("D"):
        obsolete.append(paths[0])
    else:
        new_or_changed.append(paths[0])

payloads = {}
for rel in new_or_changed:
    data = (ROOT / rel).read_bytes()
    payloads[rel] = base64.b64encode(gzip.compress(data, 9)).decode("ascii")

files_repr = "\n".join(
    f'    "{rel}":\n        "{packed}",' for rel, packed in payloads.items()
)
obsolete_repr = ",\n".join(f'    "{p}"' for p in obsolete)

script = f'''# -*- coding: utf-8 -*-
"""Обновление tutor-bot v3: тарифы (Free: рассылки 10/день + ДЗ 5/мес,
PRO 990 P/мес), фикс входа userbot по коду, кнопки отмены, тесты.

Запуск (из папки бота или её родителя):
    python apply_update.py            # обновить ботов в текущей папке
    python apply_update.py D:/tutor   # или указать путь явно

Что делает:
  1. Находит папку бота (где лежит main.py).
  2. Сохраняет заменяемые файлы в backup_update_<дата>/.
  3. Пишет новые файлы, удаляет устаревшие, чистит __pycache__.
  4. Проверяет, что все .py компилируются, и гоняет смоук-тест.
     (смоук-тесту нужны библиотеки: если их нет — поставьте
      pip install -r requirements.txt и запустите ещё раз)

Обновление кумулятивное: применяется и поверх оригинала, и поверх
любого из прошлых обновлений. Откат — файлы из backup_update_<дата>/.
Только stdlib — ничего устанавливать не нужно.
"""
import base64
import gzip
import py_compile
import shutil
import subprocess
import sys
import time
from pathlib import Path

FILES = {{
{files_repr}
}}

OBSOLETE = [
{obsolete_repr}
]


def find_root(base: Path) -> Path | None:
    if (base / "main.py").exists() and (base / "config.py").exists():
        return base
    if base.exists():
        for cand in sorted(base.iterdir()):
            if cand.is_dir() and (cand / "main.py").exists() and (cand / "config.py").exists():
                return cand
    return None


def unpack(packed: str) -> bytes:
    return gzip.decompress(base64.b64decode(packed))


def main() -> int:
    arg = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    root = find_root(arg)
    if root is None:
        print("X Папка бота не найдена: нужен каталог с main.py и config.py.")
        print("  Запустите из папки бота или передайте путь аргументом.")
        return 1

    print(f"Цель: {{root}}")
    backup = root / f"backup_update_{{time.strftime('%Y%m%d_%H%M%S')}}"
    saved = 0
    for rel in list(FILES) + OBSOLETE:
        src = root / rel
        if src.exists():
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            saved += 1
    print(f"Бэкап: {{saved}} файл(ов) -> {{backup.name}}/")

    written = 0
    for rel, packed in FILES.items():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(unpack(packed))
        written += 1
    print(f"Записано: {{written}} файл(ов)")

    removed = 0
    for rel in OBSOLETE:
        target = root / rel
        if target.exists():
            target.unlink()
            removed += 1
    scripts_dir = root / "scripts"
    if scripts_dir.exists() and not any(p.is_file() for p in scripts_dir.rglob("*")):
        shutil.rmtree(scripts_dir, ignore_errors=True)
    print(f"Удалено устаревших: {{removed}}")

    for cache in root.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    errors = []
    for rel in FILES:
        if rel.endswith(".py"):
            try:
                py_compile.compile(str(root / rel), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"{{rel}}: {{e}}")
    if errors:
        print("X Ошибка компиляции (откатите бэкап!):")
        for e in errors:
            print("  ", e)
        return 2
    print("Синтаксис всех .py: OK")

    smoke = root / "tests" / "smoke_test.py"
    if smoke.exists():
        result = subprocess.run(
            [sys.executable, str(smoke)], capture_output=True, text=True
        )
        combined = ((result.stdout or "") + (result.stderr or "")).strip()
        print("Смоук-тест, последние строки:")
        for line in combined.splitlines()[-6:]:
            print("   ", line)
        if result.returncode != 0:
            print("!! смоук-тест не прошёл. Частая причина — не хватает библиотек")
            print("   в том Python, которым запускаете. Лечится:")
            print("   python -m pip install -r requirements.txt")
            print("   Файлы обновления уже применены — это не блокер.")

    print()
    print("OK! Обновление применено. Дальше:")
    print("   1. python -m pip install -r requirements.txt")
    print("   2. перезапустите бота")
    print("   3. тарифы: /subscription; оплата — PAYMENT_PROVIDER_TOKEN в .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

target = WORKSPACE / "apply_update.py"
target.write_text(script, encoding="utf-8", newline="\n")
print(f"OK: {target} ({target.stat().st_size // 1024} KB)")
print("Изменено/новых:", len(new_or_changed), "| удалено:", len(obsolete))
