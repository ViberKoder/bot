import logging
from telegram import (
    InlineQueryResultArticle, 
    InputTextMessageContent, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    Update,
    LabeledPrice
)
from telegram.ext import Application, CommandHandler, InlineQueryHandler, CallbackQueryHandler, ContextTypes, ChatMemberHandler, PreCheckoutQueryHandler, MessageHandler, filters
from telegram.constants import ChatMemberStatus
from telegram.constants import ParseMode
import uuid
from aiohttp import web
import json
import os
from datetime import datetime, date

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "8439367607:AAGcK4tBrXKkqm5DDG7Sp3YSKEQTX09XqXE"

# Файл для сохранения данных
DATA_FILE = "bot_data.json"

# ID канала Cocoin
COCOIN_CHANNEL = "@cocoin"

# Лимиты
FREE_EGGS_PER_DAY = 10
EGG_PRICE_STARS = 1  # 1 яйцо = 1 Star

# Функция для загрузки данных из файла
def load_data():
    """Загружает данные из файла"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'hatched_eggs': set(data.get('hatched_eggs', [])),
                    'eggs_hatched_by_user': data.get('eggs_hatched_by_user', {}),
                    'user_eggs_hatched_by_others': data.get('user_eggs_hatched_by_others', {}),
                    'eggs_sent_by_user': data.get('eggs_sent_by_user', {}),
                    'daily_eggs_sent': data.get('daily_eggs_sent', {}),  # {user_id: {'date': '2024-01-01', 'count': 5}}
                    'egg_points': data.get('egg_points', {}),
                    'completed_tasks': data.get('completed_tasks', {})
                }
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return get_default_data()
    return get_default_data()

# Функция для получения данных по умолчанию
def get_default_data():
    """Возвращает данные по умолчанию"""
    return {
        'hatched_eggs': set(),
        'eggs_hatched_by_user': {},
        'user_eggs_hatched_by_others': {},
        'eggs_sent_by_user': {},
        'daily_eggs_sent': {},
        'egg_points': {},
        'completed_tasks': {}
    }

# Функция для сохранения данных в файл
def save_data():
    """Сохраняет данные в файл"""
    try:
        data = {
            'hatched_eggs': list(hatched_eggs),
            'eggs_hatched_by_user': eggs_hatched_by_user,
            'user_eggs_hatched_by_others': user_eggs_hatched_by_others,
            'eggs_sent_by_user': eggs_sent_by_user,
            'daily_eggs_sent': daily_eggs_sent,
            'egg_points': egg_points,
            'completed_tasks': completed_tasks
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Data saved successfully")
    except Exception as e:
        logger.error(f"Error saving data: {e}")

# Загружаем данные при старте
data = load_data()
hatched_eggs = data['hatched_eggs']
eggs_hatched_by_user = data['eggs_hatched_by_user']
user_eggs_hatched_by_others = data['user_eggs_hatched_by_others']
eggs_sent_by_user = data.get('eggs_sent_by_user', {})
daily_eggs_sent = data.get('daily_eggs_sent', {})
egg_points = data['egg_points']
completed_tasks = data['completed_tasks']

# Функция для проверки и обновления ежедневного лимита
def check_daily_limit(user_id):
    """Проверяет и обновляет ежедневный лимит отправленных яиц. Возвращает (can_send, daily_count)"""
    today = date.today().isoformat()
    
    # Получаем данные пользователя
    user_data = daily_eggs_sent.get(user_id, {})
    
    # Если это новый день или первый раз, сбрасываем счетчик
    if user_data.get('date') != today:
        daily_eggs_sent[user_id] = {'date': today, 'count': 0}
        user_data = daily_eggs_sent[user_id]
    
    daily_count = user_data.get('count', 0)
    
    # Проверяем лимит
    if daily_count < FREE_EGGS_PER_DAY:
        return (True, daily_count)
    else:
        return (False, daily_count)

def increment_daily_count(user_id):
    """Увеличивает счетчик отправленных яиц за сегодня"""
    today = date.today().isoformat()
    
    user_data = daily_eggs_sent.get(user_id, {})
    if user_data.get('date') != today:
        daily_eggs_sent[user_id] = {'date': today, 'count': 1}
    else:
        daily_eggs_sent[user_id]['count'] = user_data.get('count', 0) + 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.message.from_user.id
    
    # Получаем статистику пользователя
    hatched_count = eggs_hatched_by_user.get(user_id, 0)
    my_eggs_hatched = user_eggs_hatched_by_others.get(user_id, 0)
    
    # Создаем кнопку для открытия mini app
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📊 View Stats",
            url="https://t.me/ToHatchBot/app"
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
    
    # Создаем уникальный ID для этого яйца
    # Используем короткий формат: первые 16 символов UUID без дефисов
    # Это достаточно для уникальности и помещается в лимит Telegram (64 байта)
    egg_id = str(uuid.uuid4()).replace("-", "")[:16]
    
    # Сохраняем информацию об отправителе яйца
    # Формат callback_data: hatch_{sender_id}|{egg_id}
    # Используем | как разделитель, чтобы избежать проблем с UUID
    callback_data = f"hatch_{sender_id}|{egg_id}"
    
    # Проверяем длину callback_data (максимум 64 байта для Telegram)
    callback_data_bytes = len(callback_data.encode('utf-8'))
    if callback_data_bytes > 64:
        # Если все еще слишком длинный, укорачиваем еще больше
        # sender_id обычно 8-10 цифр, оставляем место для префикса "hatch_" и разделителя "|"
        max_egg_id_len = 64 - len(f"hatch_{sender_id}|".encode('utf-8'))
        if max_egg_id_len > 0:
            egg_id = egg_id[:max_egg_id_len]
            callback_data = f"hatch_{sender_id}|{egg_id}"
            logger.warning(f"Callback data too long, shortened egg_id to {egg_id} (length: {len(egg_id)})")
        else:
            # Если даже с минимальным egg_id не помещается, используем только sender_id и timestamp
            import time
            egg_id = str(int(time.time()))[-8:]  # Последние 8 цифр timestamp
            callback_data = f"hatch_{sender_id}|{egg_id}"
            logger.warning(f"Callback data still too long, using timestamp-based egg_id: {egg_id}")
    
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
    logger.info(f"Results sent: {len(results)} result(s), callback_data length: {len(callback_data.encode('utf-8'))}")
    
    # Примечание: В Telegram Bot API нет события, которое срабатывает когда пользователь выбирает результат из inline query.
    # Поэтому мы увеличиваем счетчик при каждом inline query с "egg".
    # Это не идеально, но это лучшее что можно сделать без дополнительных событий.
    # В реальности пользователь может сделать inline query, но не выбрать результат, что приведет к неточному подсчету.
    # Но для большинства случаев это работает достаточно хорошо.
    
    # Увеличиваем счетчик отправленных яиц только если запрос содержит "egg"
    if "egg" in query or query == "":
        eggs_sent_by_user[sender_id] = eggs_sent_by_user.get(sender_id, 0) + 1
        
        # Проверяем задание "Send 100 egg"
        if eggs_sent_by_user[sender_id] >= 100 and not completed_tasks.get(sender_id, {}).get('send_100_eggs', False):
            # Начисляем 500 Egg
            egg_points[sender_id] = egg_points.get(sender_id, 0) + 500
            
            # Отмечаем задание как выполненное
            if sender_id not in completed_tasks:
                completed_tasks[sender_id] = {}
            completed_tasks[sender_id]['send_100_eggs'] = True
            
            # Сохраняем данные
            save_data()
            
            logger.info(f"User {sender_id} completed 'Send 100 egg' task, earned 500 Egg points")
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=sender_id,
                    text="🎉 Congratulations! You earned 500 Egg points for sending 100 eggs!"
                )
            except Exception as e:
                logger.error(f"Failed to send notification to user {sender_id}: {e}")


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик предварительной проверки платежа"""
    query = update.pre_checkout_query
    logger.info(f"Pre-checkout query received: {query.invoice_payload}")
    
    # Всегда подтверждаем платеж
    await query.answer(ok=True)
    logger.info(f"Pre-checkout approved for payload: {query.invoice_payload}")

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик успешного платежа"""
    payment = update.message.successful_payment
    user_id = update.message.from_user.id
    
    logger.info(f"Successful payment received: {payment.invoice_payload}, amount: {payment.total_amount} {payment.currency}")
    
    # Парсим payload: egg_payment_{sender_id}|{egg_id}
    if payment.invoice_payload.startswith("egg_payment_"):
        payload_part = payment.invoice_payload[12:]  # Убираем "egg_payment_"
        parts = payload_part.split("|")
        
        if len(parts) >= 2:
            try:
                sender_id = int(parts[0])
                egg_id = parts[1]
                
                # Проверяем, что платеж от правильного пользователя
                if user_id != sender_id:
                    logger.error(f"Payment user mismatch: {user_id} != {sender_id}")
                    await update.message.reply_text("❌ Error: Payment user mismatch")
                    return
                
                # Создаем яйцо с кнопкой Hatch
                callback_data = f"hatch_{sender_id}|{egg_id}"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🥚 Hatch", callback_data=callback_data)]
                ])
                
                # Отправляем яйцо в тот же чат, где был платеж
                try:
                    await update.message.reply_text("🥚", reply_markup=keyboard)
                    logger.info(f"Egg sent after payment for user {user_id}, egg_id: {egg_id}")
                    
                    # Увеличиваем счетчики
                    eggs_sent_by_user[sender_id] = eggs_sent_by_user.get(sender_id, 0) + 1
                    increment_daily_count(sender_id)
                    
                    # Проверяем задание "Send 100 egg"
                    if eggs_sent_by_user[sender_id] >= 100 and not completed_tasks.get(sender_id, {}).get('send_100_eggs', False):
                        egg_points[sender_id] = egg_points.get(sender_id, 0) + 500
                        if sender_id not in completed_tasks:
                            completed_tasks[sender_id] = {}
                        completed_tasks[sender_id]['send_100_eggs'] = True
                        await update.message.reply_text("🎉 Congratulations! You earned 500 Egg points for sending 100 eggs!")
                    
                    save_data()
                    
                except Exception as e:
                    logger.error(f"Error sending egg after payment: {e}")
                    await update.message.reply_text("❌ Error sending egg. Please contact support.")
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing payment payload: {e}")
                await update.message.reply_text("❌ Error processing payment. Please contact support.")
        else:
            logger.error(f"Invalid payment payload format: {payment.invoice_payload}")
            await update.message.reply_text("❌ Error: Invalid payment payload")
    else:
        logger.warning(f"Unknown payment payload: {payment.invoice_payload}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    
    logger.info(f"Button callback received: {query.data}")
    
    # Обработка оплаты яйца
    if query.data.startswith("pay_egg_"):
        user_id = query.from_user.id
        data_part = query.data[8:]  # Убираем "pay_egg_"
        parts = data_part.split("|")
        
        if len(parts) >= 2:
            try:
                sender_id = int(parts[0])
                egg_id = parts[1]
                
                # Проверяем, что пользователь оплачивает свое яйцо
                if user_id != sender_id:
                    await query.answer("❌ Error: Invalid payment request", show_alert=True)
                    return
                
                # Создаем invoice для оплаты
                try:
                    await context.bot.send_invoice(
                        chat_id=user_id,
                        title="🥚 Send Egg",
                        description=f"Pay {EGG_PRICE_STARS} Telegram Star to send one egg",
                        payload=f"egg_payment_{sender_id}|{egg_id}",
                        provider_token=None,  # Для Telegram Stars provider_token не нужен
                        currency="XTR",  # XTR - это валюта Telegram Stars
                        prices=[LabeledPrice(label="1 Egg", amount=EGG_PRICE_STARS)],
                        start_parameter=f"egg_{egg_id}"
                    )
                    await query.answer("💳 Opening payment...")
                    logger.info(f"Sent invoice to user {user_id} for egg payment")
                except Exception as e:
                    logger.error(f"Error sending invoice: {e}")
                    await query.answer(f"❌ Error: {str(e)}", show_alert=True)
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing payment callback: {e}")
                await query.answer("❌ Error: Invalid payment request", show_alert=True)
        return
    
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
    
    # Создаем уникальный ключ для яйца (комбинация sender_id и egg_id)
    # Это предотвращает коллизии при укорачивании UUID
    egg_key = f"{sender_id}_{egg_id}"
    
    # Проверяем, не было ли уже вылуплено это яйцо
    if egg_key in hatched_eggs:
        await query.answer("🐣 This egg has already hatched!", show_alert=True)
        logger.info(f"Egg {egg_key} already hatched")
        return
    
    # ВАЖНО: Проверяем, не пытается ли отправитель вылупить свое яйцо
    # Это должно быть ПЕРЕД любым изменением сообщения
    if clicker_id == sender_id:
        await query.answer("❌ You can't hatch your own egg! Only the recipient can do it.", show_alert=True)
        logger.info(f"BLOCKED: Sender {sender_id} tried to hatch their own egg {egg_id}")
        return
    
    # Если все проверки пройдены, вылупляем яйцо
    # Помечаем яйцо как вылупленное СРАЗУ, чтобы предотвратить двойное вылупление
    # Используем egg_key (комбинация sender_id и egg_id) для уникальности
    hatched_eggs.add(egg_key)
    
    # Обновляем статистику
    # Увеличиваем счетчик для того, кто вылупил
    eggs_hatched_by_user[clicker_id] = eggs_hatched_by_user.get(clicker_id, 0) + 1
    # Увеличиваем счетчик для отправителя (его яйцо вылупили)
    user_eggs_hatched_by_others[sender_id] = user_eggs_hatched_by_others.get(sender_id, 0) + 1
    
    # Начисляем поинты Egg
    # +1 очко тому, кто вылупил чужое яйцо
    egg_points[clicker_id] = egg_points.get(clicker_id, 0) + 1
    # +2 очка отправителю, чье яйцо вылупили
    egg_points[sender_id] = egg_points.get(sender_id, 0) + 2
    
    # Проверяем задание "Hatch 100 egg"
    hatched_count = eggs_hatched_by_user.get(clicker_id, 0)
    if hatched_count >= 100 and not completed_tasks.get(clicker_id, {}).get('hatch_100_eggs', False):
        # Начисляем 500 Egg
        egg_points[clicker_id] = egg_points.get(clicker_id, 0) + 500
        
        # Отмечаем задание как выполненное
        if clicker_id not in completed_tasks:
            completed_tasks[clicker_id] = {}
        completed_tasks[clicker_id]['hatch_100_eggs'] = True
        
        logger.info(f"User {clicker_id} completed 'Hatch 100 egg' task, earned 500 Egg points")
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=clicker_id,
                text="🎉 Congratulations! You earned 500 Egg points for hatching 100 eggs!"
            )
        except Exception as e:
            logger.error(f"Failed to send notification to user {clicker_id}: {e}")
    
    # Сохраняем данные после обновления
    save_data()
    
    await query.answer("🐣 Hatching egg...")
    
    logger.info(f"Egg {egg_id} hatched by {clicker_id} (sent by {sender_id})")
    
    # Создаем кнопки для открытия mini app и отправки еще одного яйца
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📱 Hatch App",
                url="https://t.me/ToHatchBot/app"
            ),
            InlineKeyboardButton(
                "Send 🥚",
                switch_inline_query_current_chat="egg"
            )
        ]
    ])
    
    # Меняем 🥚 на 🐣 и добавляем кнопки
    try:
        await query.edit_message_text(
            "🐣",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        # Если не удалось отредактировать, пробуем без кнопок
        try:
            await query.edit_message_text("🐣")
        except Exception as e2:
            logger.error(f"Error editing message without buttons: {e2}")
            # Если и это не работает, просто отвечаем
            await query.answer("🐣 Egg hatched!", show_alert=False)


async def chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик изменений статуса участников канала"""
    if update.chat_member is None:
        return
    
    chat = update.chat_member.chat
    user = update.chat_member.from_user
    new_status = update.chat_member.new_chat_member.status
    
    # Проверяем, что это канал Cocoin
    if chat.username and chat.username.lower() == "cocoin":
        user_id = user.id
        
        # Если пользователь подписался (стал MEMBER или не LEFT/KICKED)
        if new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            # Проверяем, не получал ли уже награду
            if not completed_tasks.get(user_id, {}).get('subscribed_to_cocoin', False):
                # Начисляем 333 Egg
                egg_points[user_id] = egg_points.get(user_id, 0) + 333
                
                # Отмечаем задание как выполненное
                if user_id not in completed_tasks:
                    completed_tasks[user_id] = {}
                completed_tasks[user_id]['subscribed_to_cocoin'] = True
                
                # Сохраняем данные после обновления
                save_data()
                
                logger.info(f"User {user_id} subscribed to Cocoin, earned 333 Egg points")
                
                # Уведомляем пользователя
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="🎉 Congratulations! You earned 333 Egg points for subscribing to @cocoin!"
                    )
                except Exception as e:
                    logger.error(f"Failed to send notification to user {user_id}: {e}")


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
    sent_count = eggs_sent_by_user.get(user_id, 0)
    points = egg_points.get(user_id, 0)
    tasks = completed_tasks.get(user_id, {})
    
    return web.json_response(
        {
            'hatched_by_me': hatched_count,
            'my_eggs_hatched': my_eggs_hatched,
            'eggs_sent': sent_count,
            'egg_points': points,
            'tasks': tasks
        },
        headers={'Access-Control-Allow-Origin': '*'}
    )


# Глобальная переменная для хранения application (для проверки подписок)
bot_application = None

async def check_subscription_api(request):
    """API endpoint для проверки подписки"""
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
    
    # Проверяем подписку через Telegram API
    try:
        subscribed = completed_tasks.get(user_id, {}).get('subscribed_to_cocoin', False)
        
        # Если еще не отмечено как выполненное, проверяем через API
        if not subscribed and bot_application:
            try:
                chat_member = await bot_application.bot.get_chat_member(
                    chat_id=COCOIN_CHANNEL,
                    user_id=user_id
                )
                
                # Проверяем, что пользователь подписан
                if chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    # Начисляем 333 Egg
                    egg_points[user_id] = egg_points.get(user_id, 0) + 333
                    
                    # Отмечаем задание как выполненное
                    if user_id not in completed_tasks:
                        completed_tasks[user_id] = {}
                    completed_tasks[user_id]['subscribed_to_cocoin'] = True
                    
                    # Сохраняем данные после обновления
                    save_data()
                    
                    subscribed = True
                    logger.info(f"User {user_id} is subscribed to Cocoin, earned 333 Egg points")
            except Exception as e:
                logger.error(f"Error checking chat member: {e}")
                # Если пользователь не найден или не подписан, subscribed остается False
        
        return web.json_response(
            {
                'subscribed': subscribed
            },
            headers={'Access-Control-Allow-Origin': '*'}
        )
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        return web.json_response(
            {'error': 'failed to check subscription'}, 
            status=500,
            headers={'Access-Control-Allow-Origin': '*'}
        )


def main():
    """Запуск бота"""
    import threading
    import asyncio
    global bot_application
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    bot_application = application
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(ChatMemberHandler(chat_member_handler, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    
    # Запускаем веб-сервер для API в отдельном потоке
    def run_api_server():
        async def start_server():
            import os
            # Используем PORT из окружения (для Railway, Render и т.д.) или 8080 по умолчанию
            port = int(os.environ.get('PORT', 8080))
            
            app = web.Application()
            app.router.add_get('/api/stats', stats_api)
            app.router.add_post('/api/stats/check_subscription', check_subscription_api)
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
