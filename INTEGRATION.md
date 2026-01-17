# Интеграция Eggchain API в бота

## Шаги интеграции

### 1. Обновите структуру базы данных

Убедитесь, что в вашей базе данных есть таблица `eggs` со следующими полями:

```sql
CREATE TABLE IF NOT EXISTS eggs (
    egg_id TEXT PRIMARY KEY,
    sender_id INTEGER NOT NULL,
    recipient_id INTEGER,
    hatched_by INTEGER,
    timestamp_sent TEXT,
    timestamp_hatched TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT
);
```

### 2. Добавьте импорт в bot.py

В начале файла `bot.py` добавьте:

```python
from eggchain_api import setup_eggchain_routes
```

### 3. Инициализируйте роуты

В функции, где вы создаете aiohttp приложение (обычно в `main()` или где запускается сервер), добавьте:

```python
# Пример структуры:
async def main():
    # ... ваш существующий код ...
    
    app = web.Application()
    
    # Добавьте существующие роуты
    app.router.add_get('/api/stats', get_stats)  # ваш существующий endpoint
    
    # Добавьте роуты для Eggchain
    setup_eggchain_routes(app)
    
    # Запуск сервера
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
```

### 4. Убедитесь, что при создании яйца сохраняется egg_id

В функции, где создается яйцо, убедитесь, что уникальный `egg_id` сохраняется в базу:

```python
import uuid
from datetime import datetime

def create_egg(sender_id, recipient_id=None):
    egg_id = str(uuid.uuid4())  # или ваш способ генерации уникального ID
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO eggs (egg_id, sender_id, recipient_id, timestamp_sent, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (egg_id, sender_id, recipient_id, datetime.now().isoformat(), 'pending'))
    conn.commit()
    conn.close()
    
    return egg_id
```

### 5. При вылуплении яйца обновляйте hatched_by

В функции вылупления яйца:

```python
def hatch_egg(egg_id, hatched_by_user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE eggs 
        SET hatched_by = ?, timestamp_hatched = ?, status = ?
        WHERE egg_id = ?
    ''', (hatched_by_user_id, datetime.now().isoformat(), 'hatched', egg_id))
    conn.commit()
    conn.close()
```

### 6. Обновите vercel.json для mini app

Добавьте роут для eggchain.html в `vercel.json`:

```json
{
  "routes": [
    {
      "src": "/eggchain",
      "dest": "/eggchain.html"
    },
    {
      "src": "/",
      "dest": "/index.html"
    }
  ]
}
```

### 7. Добавьте кнопку в бота для открытия explorer

В обработчике команд или кнопок добавьте:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# В функции, где показываете статистику или после вылупления:
keyboard = [
    [InlineKeyboardButton("📊 Статистика", web_app=WebAppInfo(url="https://hatchapp-xi.vercel.app/"))],
    [InlineKeyboardButton("🔍 Eggchain Explorer", web_app=WebAppInfo(url="https://hatchapp-xi.vercel.app/eggchain"))]
]
reply_markup = InlineKeyboardMarkup(keyboard)
```

## Проверка работы

1. Убедитесь, что API доступен: `https://your-railway-url.railway.app/api/egg/{egg_id}`
2. Проверьте список яиц: `https://your-railway-url.railway.app/api/user/{user_id}/eggs`
3. Откройте explorer в mini app: `https://hatchapp-xi.vercel.app/eggchain`
