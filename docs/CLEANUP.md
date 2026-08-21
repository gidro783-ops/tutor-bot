# 🧹 Чистка истории git от бинарного мусора

Скрипт `apply.sh` уже удалил архив и папку драйвера Realtek из рабочего
дерева. Но они остались **в истории коммитов** — репозиторий по-прежнему
тяжёлый, а любой, кто клонирует, скачивает этот бинарник. Файлы из истории
можно вычистить полностью.

## Вариант А: git filter-repo (рекомендуется)

```bash
pip install git-filter-repo

# Сделайте свежий клон на всякий случай:
git clone https://github.com/gidro783-ops/tutor-bot.git tutor-bot-clean
cd tutor-bot-clean

git filter-repo \
  --path "40d1b2d8Realtek_wlan_6101.19.136.0(station-drivers.com)" \
  --path "40d1b2d8Realtek_wlan_6101.19.136.0(station-drivers.com).zip" \
  --invert-paths

# filter-repo удаляет remote — верните его:
git remote add origin https://github.com/gidro783-ops/tutor-bot.git
git push --force origin main
```

## Вариант Б: BFG Repo-Cleaner

```bash
# https://rtyley.github.io/bfg-repo-cleaner/
bfg --delete-folders "40d1b2d8Realtek_wlan_6101.19.136.0(station-drivers.com)" \
    --delete-files "*.zip" tutor-bot.git
cd tutor-bot.git
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

## После force-push

- Heroku: `git push heroku main --force`
- Все, у кого есть старый клон, должны переклонировать репозиторий
  (или `git fetch --all && git reset --hard origin/main`).

## Зачем это важно

1. Архив с драйверами со стороннего сайта — потенциально опасный бинарник,
   ему не место в репозитории Telegram-бота.
2. Клонирование ускоряется в разы.
3. GitHub-поиск индексирует историю — репозиторий выглядит профессионально.
