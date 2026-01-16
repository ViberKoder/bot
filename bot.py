import logging
from telegram import (
    InlineQueryResultArticle, 
    InputTextMessageContent, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    Update
)
from telegram.ext import Application, CommandHandler, InlineQueryHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
import uuid
from aiohttp import web
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "8439367607:AAGcK4tBrXKkqm5DDG7Sp3YSKEQTX09XqXE"

# Хранилище для отслеживания вылупленных яиц (в продакшене лучше использовать БД)
hatched_eggs = set()

# Статистика: сколько яиц вылупил каждый пользователь
# Формат: {user_id: count}
eggs_hatched_by_user = {}

# Статистика: сколько яиц пользователя вылупили другие
# Формат: {user_id: count}
user_eggs_hatched_by_others = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    from telegram import WebAppInfo
    
    user_id = update.message.from_user.id
    
    # Получаем статистику пользователя
    hatched_count = eggs_hatched_by_user.get(user_id, 0)
    my_eggs_hatched = user_eggs_hatched_by_others.get(user_id, 0)
    
    # Создаем кнопку для открытия mini app
    # Передаем user_id в URL для получения статистики
    web_app_url = f"https://hatch-app.vercel.app/?user_id={user_id}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📊 View Stats",
            web_app=WebAppInfo(url=web_app_url)
        )]
    ])
    
    await update.message.reply_text(
        "Hi! I'm the egg hatching bot 🥚\n\n"
        "Use me in inline mode:\n"
        "1. In any chat, start typing @tohatchbot egg\n"
        "2. Select an egg from the results\n"
        "3. Click 'Hatch' to hatch it! 🐣\n\n"
        f"📊 Your stats:\n"
        f"🥚 Hatched: {hatched_count}\n"
        f"🐣 Your eggs hatched: {my_eggs_hatched}",
        reply_markup=keyboard
    )


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline запросов"""
    query = update.inline_query.query.lower().strip()
    
    logger.info(f"Inline query received: '{query}' (original: '{update.inline_query.query}')")
    
    # Показываем результат если запрос пустой или содержит "egg"
    if query and "egg" not in query:
        logger.info(f"Query '{query}' doesn't contain 'egg', returning empty results")
        await update.inline_query.answer([], cache_time=1)
        return
    
    # Получаем ID отправителя
    sender_id = update.inline_query.from_user.id
    
    # Создаем уникальный ID для этого яйца (используем короткий формат без дефисов)
    egg_id = str(uuid.uuid4()).replace("-", "")
    
    # Сохраняем информацию об отправителе яйца
    # Формат callback_data: hatch_{sender_id}|{egg_id}
    # Используем | как разделитель, чтобы избежать проблем с UUID
    callback_data = f"hatch_{sender_id}|{egg_id}"
    
    # Создаем кнопку "Hatch"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚 Hatch", callback_data=callback_data)]
    ])
    
    # Создаем результат с эмодзи яйца
    results = [
        InlineQueryResultArticle(
            id=egg_id,
            title="🥚 Send Egg",
            description="Click to send an egg to the chat",
            input_message_content=InputTextMessageContent(
                message_text="🥚",
                parse_mode=ParseMode.HTML
            ),
            reply_markup=keyboard
        )
    ]
    
    await update.inline_query.answer(results, cache_time=1)
    logger.info(f"Results sent: {len(results)} result(s)")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    
    logger.info(f"Button callback received: {query.data}")
    
    # Получаем ID пользователя, который нажал на кнопку
    clicker_id = query.from_user.id
    
    # Извлекаем данные из callback_data
    # Поддерживаем два формата для обратной совместимости:
    # Новый: hatch_{sender_id}|{egg_id}
    # Старый: hatch_{egg_id}_{sender_id} (может быть с дефисами в UUID)
    
    sender_id = None
    egg_id = None
    
    if not query.data.startswith("hatch_"):
        await query.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        logger.error(f"Invalid callback_data format: {query.data}")
        return
    
    # Убираем префикс "hatch_"
    data_part = query.data[6:]  # 6 = len("hatch_")
    
    # Пробуем новый формат: sender_id|egg_id
    if "|" in data_part:
        parts = data_part.split("|")
        if len(parts) == 2:
            try:
                sender_id = int(parts[0])
                egg_id = parts[1]
                logger.info(f"Parsed new format: sender_id={sender_id}, egg_id={egg_id}")
            except ValueError:
                await query.answer("❌ Ошибка: неверный формат данных", show_alert=True)
                logger.error(f"Invalid sender_id in new format: {query.data}")
                return
    
    # Если новый формат не сработал, пробуем старый формат
    if sender_id is None or egg_id is None:
        # Старый формат: egg_id может содержать дефисы, sender_id - последний элемент после последнего подчеркивания
        parts = data_part.split("_")
        if len(parts) >= 2:
            try:
                # Последний элемент - sender_id
                sender_id = int(parts[-1])
                # Все остальное - egg_id (может содержать дефисы)
                egg_id = "_".join(parts[:-1])
                logger.info(f"Parsed old format: sender_id={sender_id}, egg_id={egg_id}")
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка: неверный формат данных", show_alert=True)
                logger.error(f"Invalid format in old format: {query.data}")
                return
    
    # Если оба формата не сработали
    if sender_id is None or egg_id is None or not egg_id:
        await query.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        logger.error(f"Could not parse callback_data: {query.data}")
        return
    
    logger.info(f"Egg ID: {egg_id}, Sender ID: {sender_id}, Clicker ID: {clicker_id}")
    
    # Проверяем, не было ли уже вылуплено это яйцо
    if egg_id in hatched_eggs:
        await query.answer("🐣 This egg has already hatched!", show_alert=True)
        logger.info(f"Egg {egg_id} already hatched")
        return
    
    # ВАЖНО: Проверяем, не пытается ли отправитель вылупить свое яйцо
    # Это должно быть ПЕРЕД любым изменением сообщения
    if clicker_id == sender_id:
        await query.answer("❌ You can't hatch your own egg! Only the recipient can do it.", show_alert=True)
        logger.info(f"BLOCKED: Sender {sender_id} tried to hatch their own egg {egg_id}")
        return
    
    # Если все проверки пройдены, вылупляем яйцо
    # Помечаем яйцо как вылупленное СРАЗУ, чтобы предотвратить двойное вылупление
    hatched_eggs.add(egg_id)
    
    # Обновляем статистику
    # Увеличиваем счетчик для того, кто вылупил
    eggs_hatched_by_user[clicker_id] = eggs_hatched_by_user.get(clicker_id, 0) + 1
    # Увеличиваем счетчик для отправителя (его яйцо вылупили)
    user_eggs_hatched_by_others[sender_id] = user_eggs_hatched_by_others.get(sender_id, 0) + 1
    
    await query.answer("🐣 Hatching egg...")
    
    logger.info(f"Egg {egg_id} hatched by {clicker_id} (sent by {sender_id})")
    logger.info(f"Stats updated: {clicker_id} hatched {eggs_hatched_by_user[clicker_id]} eggs, "
                f"{sender_id} has {user_eggs_hatched_by_others[sender_id]} eggs hatched")
    
    # Создаем кнопку для открытия mini app
    from telegram import WebAppInfo
    web_app_url = f"https://hatch-app.vercel.app/?user_id={clicker_id}"
    
    # Меняем 🥚 на 🐣 и добавляем кнопку "Hatch App"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📊 Hatch App",
            web_app=WebAppInfo(url=web_app_url)
        )]
    ])
    
    await query.edit_message_text(
        "🐣",
        reply_markup=keyboard
    )


async def stats_api(request):
    """API endpoint для получения статистики"""
    # Добавляем CORS headers
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response(
            {'error': 'user_id required'}, 
            status=400,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    try:
        user_id = int(user_id)
    except ValueError:
        return web.json_response(
            {'error': 'invalid user_id'}, 
            status=400,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    hatched_count = eggs_hatched_by_user.get(user_id, 0)
    my_eggs_hatched = user_eggs_hatched_by_others.get(user_id, 0)
    
    return web.json_response(
        {
            'hatched_by_me': hatched_count,
            'my_eggs_hatched': my_eggs_hatched
        },
        headers={'Access-Control-Allow-Origin': '*'}
    )


def main():
    """Запуск бота"""
    import threading
    import asyncio
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем веб-сервер для API в отдельном потоке
    def run_api_server():
        async def start_server():
            import os
            # Используем PORT из окружения (для Railway, Render и т.д.) или 8080 по умолчанию
            port = int(os.environ.get('PORT', 8080))
            
            app = web.Application()
            app.router.add_get('/api/stats', stats_api)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', port)
            await site.start()
            logger.info(f"API server started on http://0.0.0.0:{port}/api/stats")
            # Держим сервер запущенным
            await asyncio.Event().wait()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_server())
    
    # Запускаем API сервер в отдельном потоке
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    # Запускаем бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
