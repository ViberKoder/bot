"""
Пример интеграции Eggchain API в существующий bot.py

Замените существующие части вашего кода на этот пример
"""

# ============================================
# 1. ИМПОРТЫ (добавьте в начало bot.py)
# ============================================
from eggchain_api import setup_eggchain_routes
from aiohttp import web
import sqlite3
from datetime import datetime
import uuid

# ============================================
# 2. ФУНКЦИЯ СОЗДАНИЯ ЯЙЦА (обновите вашу функцию)
# ============================================
def create_egg(sender_id, recipient_id=None):
    """
    Создает новое яйцо с уникальным ID
    Адаптируйте под вашу структуру базы данных
    """
    # Генерируем уникальный ID для яйца
    egg_id = str(uuid.uuid4())
    
    # Подключаемся к базе данных
    conn = sqlite3.connect('eggs.db')  # или ваш путь к БД
    cursor = conn.cursor()
    
    # Создаем запись о яйце
    cursor.execute('''
        INSERT INTO eggs (
            egg_id, 
            sender_id, 
            recipient_id, 
            timestamp_sent, 
            status
        ) VALUES (?, ?, ?, ?, ?)
    ''', (
        egg_id,
        sender_id,
        recipient_id,
        datetime.now().isoformat(),
        'pending'
    ))
    
    conn.commit()
    conn.close()
    
    return egg_id

# ============================================
# 3. ФУНКЦИЯ ВЫЛУПЛЕНИЯ ЯЙЦА (обновите вашу функцию)
# ============================================
def hatch_egg(egg_id, hatched_by_user_id):
    """
    Обновляет информацию о вылуплении яйца
    Адаптируйте под вашу структуру базы данных
    """
    conn = sqlite3.connect('eggs.db')  # или ваш путь к БД
    cursor = conn.cursor()
    
    # Обновляем запись о яйце
    cursor.execute('''
        UPDATE eggs 
        SET 
            hatched_by = ?, 
            timestamp_hatched = ?, 
            status = ?
        WHERE egg_id = ?
    ''', (
        hatched_by_user_id,
        datetime.now().isoformat(),
        'hatched',
        egg_id
    ))
    
    conn.commit()
    conn.close()

# ============================================
# 4. ИНИЦИАЛИЗАЦИЯ API СЕРВЕРА (в функции main или startup)
# ============================================
async def main():
    # ... ваш существующий код для бота ...
    
    # Создаем aiohttp приложение для API
    app = web.Application()
    
    # Добавьте ваши существующие API роуты
    # Например:
    # app.router.add_get('/api/stats', get_stats_handler)
    
    # Добавляем роуты для Eggchain Explorer
    setup_eggchain_routes(app)
    
    # Запускаем API сервер
    port = int(os.getenv('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"API server started on port {port}")
    
    # ... ваш код для запуска бота ...

# ============================================
# 5. ПРИМЕР ИСПОЛЬЗОВАНИЯ В ОБРАБОТЧИКЕ БОТА
# ============================================
async def handle_inline_query(update, context):
    """
    Пример обработчика inline query для отправки яйца
    """
    query = update.inline_query.query
    user = update.inline_query.from_user
    
    # Создаем яйцо с уникальным ID
    egg_id = create_egg(sender_id=user.id)
    
    # Создаем inline результат
    results = [InlineQueryResultArticle(
        id=egg_id,
        title="🥚 Send Egg",
        input_message_content=InputTextMessageContent(
            message_text=f"🥚 Egg #{egg_id[:8]}..."
        ),
        # Добавляем кнопку для открытия explorer
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔍 View in Explorer",
                web_app=WebAppInfo(url=f"https://hatchapp-xi.vercel.app/eggchain?egg_id={egg_id}")
            )
        ]])
    )]
    
    await update.inline_query.answer(results)

# ============================================
# 6. СТРУКТУРА БАЗЫ ДАННЫХ (SQL для создания таблиц)
# ============================================
"""
CREATE TABLE IF NOT EXISTS eggs (
    egg_id TEXT PRIMARY KEY,
    sender_id INTEGER NOT NULL,
    recipient_id INTEGER,
    hatched_by INTEGER,
    timestamp_sent TEXT NOT NULL,
    timestamp_hatched TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_eggs_sender ON eggs(sender_id);
CREATE INDEX IF NOT EXISTS idx_eggs_hatched_by ON eggs(hatched_by);
"""
