# 🚀 Готово к деплою на Railway!

## ✅ Код готов и закоммичен локально

Все файлы подготовлены:
- ✅ `bot.py` - основной код бота
- ✅ `requirements.txt` - зависимости
- ✅ `railway.json` - конфигурация для Railway
- ✅ `Procfile` - для Render
- ✅ Все готово к деплою

## 📤 Шаг 1: Создайте репозиторий на GitHub

1. Зайдите на https://github.com/new
2. Repository name: `tohatchbot` (или `hatch-bot`)
3. Owner: `ViberKoder`
4. Выберите **Public**
5. **НЕ** добавляйте README, .gitignore или license
6. Нажмите "Create repository"

## 📤 Шаг 2: Загрузите код

После создания репозитория выполните:

```powershell
cd C:\Users\leviv\telegram_egg_bot
git remote set-url origin https://github.com/ViberKoder/tohatchbot.git
git push -u origin main --force
```

Или если репозиторий называется по-другому, замените URL.

## 🚂 Шаг 3: Деплой на Railway

1. Зайдите на https://railway.app
2. Sign up with GitHub
3. Нажмите "New Project"
4. Выберите "Deploy from GitHub repo"
5. Выберите репозиторий `ViberKoder/tohatchbot`
6. Railway автоматически определит Python и запустит бота

## ⚙️ Шаг 4: Настройте переменные

В Railway:
1. Откройте ваш проект
2. Settings → Variables
3. Добавьте:
   - **Name**: `BOT_TOKEN`
   - **Value**: `8439367607:AAGcK4tBrXKkqm5DDG7Sp3YSKEQTX09XqXE`

## 🌐 Шаг 5: Получите публичный URL

1. В Railway откройте ваш сервис
2. Settings → Networking
3. Нажмите "Generate Domain"
4. Скопируйте URL (например: `https://tohatchbot.railway.app`)

## 🔗 Шаг 6: Обновите mini app

В Vercel:
1. Settings → Environment Variables
2. Добавьте/обновите:
   - **Name**: `API_URL`
   - **Value**: `https://tohatchbot.railway.app/api/stats`

## ✅ Готово!

Теперь:
- ✅ Бот работает 24/7 на Railway
- ✅ API доступен публично
- ✅ Mini app получает статистику
- ✅ Не нужно держать компьютер включенным

## 🔍 Проверка

Откройте в браузере:
```
https://tohatchbot.railway.app/api/stats?user_id=123456
```

Должен вернуться JSON:
```json
{"hatched_by_me": 0, "my_eggs_hatched": 0}
```
