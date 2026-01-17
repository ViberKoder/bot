import logging
from telegram import (
    InlineQueryResultArticle, 
    InputTextMessageContent, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    Update,
    WebAppInfo
)
from telegram.ext import Application, CommandHandler, InlineQueryHandler, CallbackQueryHandler, ContextTypes, ChatMemberHandler, MessageHandler, filters
from telegram.constants import ChatMemberStatus
from telegram.constants import ParseMode
import uuid
from aiohttp import web
import json
import os
from datetime import datetime, date
import aiohttp
from eggchain_api import setup_eggchain_routes, set_bot_instance

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота - получаем из переменной окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable is not set!")
    raise ValueError("BOT_TOKEN environment variable is required!")

# Файл для сохранения данных
DATA_FILE = "bot_data.json"

# ID канала Hatch Egg
HATCH_EGG_CHANNEL = "@hatch_egg"

# Лимиты
FREE_EGGS_PER_DAY = 10
EGG_PACK_SIZE = 10  # Количество яиц в пакете
TON_PRICE_PER_PACK = 0.15  # 0.15 TON за 10 яиц
TON_WALLET = "UQCHdlQ2TLpa6Kpu5Pu8HeJd1xe3EL1Kx2wFekeuOnSpFcP0"  # TON кошелек для оплаты
MINI_APP_URL = "https://hatchapp-xi.vercel.app"  # URL mini app
REFERRAL_PERCENTAGE = 0.25  # 25% от поинтов реферала

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
                    'completed_tasks': data.get('completed_tasks', {}),
                    'referrers': data.get('referrers', {}),  # {user_id: referrer_id} - кто привел пользователя
                    'referral_earnings': data.get('referral_earnings', {}),  # {referrer_id: total_earned} - сколько заработал рефовод
                    'ton_payments': data.get('ton_payments', {}),  # {user_id: [{'date': '2024-01-01', 'amount': 0.1, 'tx_hash': '...'}]}
                    'eggs_detail': data.get('eggs_detail', {})  # {egg_key: {sender_id, egg_id, hatched_by, timestamp_sent, timestamp_hatched}}
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
        'completed_tasks': {},
        'referrers': {},
        'referral_earnings': {},
        'ton_payments': {},
        'eggs_detail': {}
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
            'completed_tasks': completed_tasks,
            'referrers': referrers,
            'referral_earnings': referral_earnings,
            'ton_payments': ton_payments,
            'eggs_detail': eggs_detail
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
referrers = data.get('referrers', {})  # {user_id: referrer_id}
referral_earnings = data.get('referral_earnings', {})  # {referrer_id: total_earned}
ton_payments = data.get('ton_payments', {})  # {user_id: [{'date': '2024-01-01', 'amount': 0.1, 'tx_hash': '...'}]}
eggs_detail = data.get('eggs_detail', {})  # {egg_key: {sender_id, egg_id, hatched_by, timestamp_sent, timestamp_hatched}}

# Функция для проверки и обновления ежедневного лимита
def check_daily_limit(user_id):
    """Проверяет и обновляет ежедневный лимит отправленных яиц. Возвращает (can_send, daily_count, total_limit)"""
    today = date.today().isoformat()
    
    # Получаем данные пользователя
    user_data = daily_eggs_sent.get(user_id, {})
    
    # Если это новый день или первый раз, сбрасываем счетчик (но сохраняем оплаченные яйца для нового дня)
    if user_data.get('date') != today:
        # Сохраняем paid_eggs при инициализации нового дня
        old_paid_eggs = daily_eggs_sent.get(user_id, {}).get('paid_eggs', 0)
        daily_eggs_sent[user_id] = {'date': today, 'count': 0, 'paid_eggs': old_paid_eggs}
        user_data = daily_eggs_sent[user_id]
    
    daily_count = user_data.get('count', 0)
    paid_eggs = user_data.get('paid_eggs', 0)
    total_limit = FREE_EGGS_PER_DAY + paid_eggs
    
    # Проверяем лимит
    if daily_count < total_limit:
        return (True, daily_count, total_limit)
    else:
        return (False, daily_count, total_limit)

def increment_daily_count(user_id):
    """Увеличивает счетчик отправленных яиц за сегодня"""
    today = date.today().isoformat()
    
    user_data = daily_eggs_sent.get(user_id, {})
    if user_data.get('date') != today:
        # Сохраняем paid_eggs при инициализации нового дня
        old_paid_eggs = daily_eggs_sent.get(user_id, {}).get('paid_eggs', 0)
        daily_eggs_sent[user_id] = {'date': today, 'count': 0, 'paid_eggs': old_paid_eggs}
    else:
        daily_eggs_sent[user_id]['count'] = user_data.get('count', 0) + 1

def add_paid_eggs(user_id, amount):
    """Добавляет оплаченные яйца к лимиту пользователя"""
    today = date.today().isoformat()
    
    user_data = daily_eggs_sent.get(user_id, {})
    if user_data.get('date') != today:
        old_paid_eggs = user_data.get('paid_eggs', 0)
        daily_eggs_sent[user_id] = {'date': today, 'count': 0, 'paid_eggs': old_paid_eggs + amount}
    else:
        daily_eggs_sent[user_id]['paid_eggs'] = user_data.get('paid_eggs', 0) + amount


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


async def reset_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /reset_all - полностью обнуляет все счетчики и бесплатные яйца"""
    user_id = update.message.from_user.id
    
    # Полностью обнуляем все счетчики
    egg_points.clear()  # Все поинты
    eggs_sent_by_user.clear()  # Счетчики отправленных яиц
    daily_eggs_sent.clear()  # Ежедневные счетчики (сбрасывает бесплатные яйца)
    eggs_hatched_by_user.clear()  # Сколько яиц вылупил каждый пользователь (hatched_by_me)
    user_eggs_hatched_by_others.clear()  # Сколько яиц пользователя вылупили другие (my_eggs_hatched)
    hatched_eggs.clear()  # Список всех вылупленных яиц
    referral_earnings.clear()  # Реферальные заработки
    completed_tasks.clear()  # Выполненные задания
    
    # Сохраняем изменения
    save_data()
    
    logger.info(f"User {user_id} reset ALL counters and free eggs")
    
    await update.message.reply_text(
        "✅ Все счетчики и бесплатные яйца полностью сброшены!\n\n"
        "Сброшено:\n"
        "• Все счетчики вылупленных яиц (hatched_by_me)\n"
        "• Все счетчики своих яиц, вылупленных другими (my_eggs_hatched)\n"
        "• Все счетчики отправленных яиц\n"
        "• Все ежедневные счетчики (бесплатные яйца сброшены)\n"
        "• Все поинты\n"
        "• Все вылупленные яйца\n"
        "• Все выполненные задания\n"
        "• Все реферальные заработки\n\n"
        "Сохранено:\n"
        "• Реферальная система (кто кого привел)\n"
        "• История TON платежей"
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
    
    # Сохраняем детальную информацию о яйце для Eggchain Explorer
    egg_key = f"{sender_id}_{egg_id}"
    eggs_detail[egg_key] = {
        'sender_id': sender_id,
        'egg_id': egg_id,
        'hatched_by': None,
        'timestamp_sent': datetime.now().isoformat(),
        'timestamp_hatched': None
    }
    
    # Сохраняем информацию об отправителе яйца
    # Формат callback_data: hatch_{sender_id}|{egg_id}
    # Реферал устанавливается когда кто-то открывает яйцо (открывающий становится рефералом отправителя)
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
    
    # Проверяем ежедневный лимит
    can_send_free, daily_count, total_limit = check_daily_limit(sender_id)
    
    if not can_send_free:
        # Лимит превышен, отправляем крестик (❌) вместо яйца
        # Крестик нельзя вылупить, поэтому не добавляем кнопку Hatch
        locked_results = [
            InlineQueryResultArticle(
                id=f"locked_{egg_id}",
                title="❌ Locked Egg",
                description=f"You've used all {total_limit} eggs today. Buy more eggs in Mini App!",
                input_message_content=InputTextMessageContent(
                    message_text="❌",
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "📊 Open Mini App",
                        url="https://t.me/ToHatchBot/app"
                    )]
                ])
            )
        ]
        await update.inline_query.answer(locked_results, cache_time=1)
        logger.info(f"User {sender_id} exceeded daily limit ({daily_count}/{total_limit}), sending locked egg (❌)")
        return
    
    # Лимит не превышен, создаем результат с эмодзи яйца
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
    
    # Увеличиваем счетчики только если запрос содержит "egg" или пустой
    if "egg" in query or query == "":
        # Увеличиваем общий счетчик
        eggs_sent_by_user[sender_id] = eggs_sent_by_user.get(sender_id, 0) + 1
        
        # Увеличиваем ежедневный счетчик
        increment_daily_count(sender_id)
        
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
        
        save_data()


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    
    logger.info(f"Button callback received: {query.data}")
    
    # Получаем ID пользователя, который нажал на кнопку
    clicker_id = query.from_user.id
    
    # Извлекаем данные из callback_data
    # Формат: hatch_{sender_id}|{egg_id}
    # Поддерживаем старые форматы для обратной совместимости
    
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
        if len(parts) >= 2:
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
    
    # Обновляем детальную информацию о яйце для Eggchain Explorer
    if egg_key not in eggs_detail:
        eggs_detail[egg_key] = {
            'sender_id': sender_id,
            'egg_id': egg_id,
            'hatched_by': clicker_id,
            'timestamp_sent': datetime.now().isoformat(),
            'timestamp_hatched': datetime.now().isoformat()
        }
    else:
        eggs_detail[egg_key]['hatched_by'] = clicker_id
        eggs_detail[egg_key]['timestamp_hatched'] = datetime.now().isoformat()
    
    # РЕФЕРАЛЬНАЯ СИСТЕМА: Если clicker_id еще не имеет реферала, устанавливаем sender_id как его реферала
    # Когда кто-то открывает яйцо, он становится рефералом того, кто отправил яйцо
    if clicker_id not in referrers and sender_id != clicker_id:
        referrers[clicker_id] = sender_id
        logger.info(f"User {clicker_id} became referral of {sender_id}")
    
    # Обновляем статистику
    # Увеличиваем счетчик для того, кто вылупил
    eggs_hatched_by_user[clicker_id] = eggs_hatched_by_user.get(clicker_id, 0) + 1
    # Увеличиваем счетчик для отправителя (его яйцо вылупили)
    user_eggs_hatched_by_others[sender_id] = user_eggs_hatched_by_others.get(sender_id, 0) + 1
    
    # Начисляем поинты Egg
    # +1 очко тому, кто вылупил чужое яйцо
    clicker_points = 1
    egg_points[clicker_id] = egg_points.get(clicker_id, 0) + clicker_points
    
    # +2 очка отправителю, чье яйцо вылупили
    sender_points = 2
    egg_points[sender_id] = egg_points.get(sender_id, 0) + sender_points
    
    # РЕФЕРАЛЬНАЯ СИСТЕМА: Рефовод получает 25% от поинтов реферала
    # Когда реферал зарабатывает поинты, его рефовод получает 25% от этих поинтов
    
    # Проверяем, есть ли у clicker_id реферал (может быть установлен выше или уже был)
    clicker_referrer = referrers.get(clicker_id)
    if clicker_referrer and clicker_referrer != clicker_id:
        # Реферал clicker_id получает 25% от поинтов clicker_id
        referral_bonus = int(clicker_points * REFERRAL_PERCENTAGE)
        if referral_bonus > 0:
            referral_earnings[clicker_referrer] = referral_earnings.get(clicker_referrer, 0) + referral_bonus
            egg_points[clicker_referrer] = egg_points.get(clicker_referrer, 0) + referral_bonus
            logger.info(f"Referrer {clicker_referrer} earned {referral_bonus} points (25% of {clicker_points}) from referral {clicker_id}")
    
    # Проверяем, есть ли у sender_id реферал
    sender_referrer = referrers.get(sender_id)
    if sender_referrer and sender_referrer != sender_id:
        # Реферал sender_id получает 25% от поинтов sender_id
        referral_bonus = int(sender_points * REFERRAL_PERCENTAGE)
        if referral_bonus > 0:
            referral_earnings[sender_referrer] = referral_earnings.get(sender_referrer, 0) + referral_bonus
            egg_points[sender_referrer] = egg_points.get(sender_referrer, 0) + referral_bonus
            logger.info(f"Referrer {sender_referrer} earned {referral_bonus} points (25% of {sender_points}) from referral {sender_id}")
    
    # Проверяем задание "Hatch 100 egg"
    hatched_count = eggs_hatched_by_user.get(clicker_id, 0)
    if hatched_count >= 333 and not completed_tasks.get(clicker_id, {}).get('hatch_333_eggs', False):
        # Начисляем 100 Egg
        egg_points[clicker_id] = egg_points.get(clicker_id, 0) + 100
        
        # Отмечаем задание как выполненное
        if clicker_id not in completed_tasks:
            completed_tasks[clicker_id] = {}
        completed_tasks[clicker_id]['hatch_333_eggs'] = True
        
        logger.info(f"User {clicker_id} completed 'Hatch 333 egg' task, earned 100 Egg points")
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=clicker_id,
                text="🎉 Congratulations! You earned 100 Egg points for hatching 333 eggs!"
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
    
    # Проверяем, что это канал Hatch Egg
    if chat.username and chat.username.lower() == "hatch_egg":
        user_id = user.id
        
        # Если пользователь подписался (стал MEMBER или не LEFT/KICKED)
        if new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            # Проверяем, не получал ли уже награду
            if not completed_tasks.get(user_id, {}).get('subscribed_to_hatch_egg', False):
                # Начисляем 20 Eggs (available eggs to send)
                today = date.today().isoformat()
                user_data = daily_eggs_sent.get(user_id, {})
                if user_data.get('date') != today:
                    # Сохраняем paid_eggs при инициализации нового дня
        old_paid_eggs = daily_eggs_sent.get(user_id, {}).get('paid_eggs', 0)
        daily_eggs_sent[user_id] = {'date': today, 'count': 0, 'paid_eggs': old_paid_eggs}
                    user_data = daily_eggs_sent[user_id]
                user_data['paid_eggs'] = user_data.get('paid_eggs', 0) + 20
                
                # Отмечаем задание как выполненное
                if user_id not in completed_tasks:
                    completed_tasks[user_id] = {}
                completed_tasks[user_id]['subscribed_to_hatch_egg'] = True
                
                # Сохраняем данные после обновления
                save_data()
                
                logger.info(f"User {user_id} subscribed to Hatch Egg, earned 20 Eggs")
                
                # Уведомляем пользователя
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="🎉 Congratulations! You earned 20 Eggs for subscribing to @hatch_egg!"
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
    referral_earned = referral_earnings.get(user_id, 0)
    referrer_id = referrers.get(user_id)
    
    # Count referrals (users who have this user as referrer)
    referrals_count = sum(1 for ref_user_id, ref_referrer_id in referrers.items() if ref_referrer_id == user_id)
    
    # Calculate available eggs (10 free per day + paid eggs - sent today)
    # Paid eggs сохраняются между днями, сбрасывается только daily_sent
    today = date.today().isoformat()
    user_data = daily_eggs_sent.get(user_id, {})
    if user_data.get('date') != today:
        # New day, reset only daily_sent, keep paid_eggs
        daily_sent = 0
        paid_eggs = user_data.get('paid_eggs', 0)  # Сохраняем купленные яйца
    else:
        daily_sent = user_data.get('count', 0)
        paid_eggs = user_data.get('paid_eggs', 0)
    
    available_eggs = FREE_EGGS_PER_DAY + paid_eggs - daily_sent
    if available_eggs < 0:
        available_eggs = 0
    
    return web.json_response(
        {
            'hatched_by_me': hatched_count,
            'my_eggs_hatched': my_eggs_hatched,
            'eggs_sent': sent_count,
            'egg_points': points,
            'hatch_points': hatched_count,  # Hatch points = вылупленные яйца
            'available_eggs': available_eggs,  # Available eggs to send today
            'tasks': tasks,
            'referral_earned': referral_earned,
            'referral_earnings': referral_earned,  # Alias for compatibility
            'referrals_count': referrals_count,
            'has_referrer': referrer_id is not None
        },
        headers={'Access-Control-Allow-Origin': '*'}
    )


# Глобальная переменная для хранения application (для проверки подписок)
bot_application = None

async def check_subscription_api(request):
    """API endpoint для проверки подписки"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return web.Response(
            status=200,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Accept',
                'Access-Control-Max-Age': '3600'
            }
        )
    
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
        subscribed = completed_tasks.get(user_id, {}).get('subscribed_to_hatch_egg', False)
        
        # Если еще не отмечено как выполненное, проверяем через API
        if not subscribed and bot_application:
            try:
                # Используем правильный формат для канала
                channel_id = HATCH_EGG_CHANNEL if HATCH_EGG_CHANNEL.startswith('@') else f'@{HATCH_EGG_CHANNEL}' if not HATCH_EGG_CHANNEL.startswith('-') else HATCH_EGG_CHANNEL
                chat_member = await bot_application.bot.get_chat_member(
                    chat_id=channel_id,
                    user_id=user_id
                )
                
                # Проверяем, что пользователь подписан
                if chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    # Начисляем 20 Eggs (available eggs to send)
                    today = date.today().isoformat()
                    user_data = daily_eggs_sent.get(user_id, {})
                    if user_data.get('date') != today:
                        # Сохраняем paid_eggs при инициализации нового дня
                        old_paid_eggs = daily_eggs_sent.get(user_id, {}).get('paid_eggs', 0)
                        daily_eggs_sent[user_id] = {'date': today, 'count': 0, 'paid_eggs': old_paid_eggs}
                        user_data = daily_eggs_sent[user_id]
                    user_data['paid_eggs'] = user_data.get('paid_eggs', 0) + 20
                    
                    # Отмечаем задание как выполненное
                    if user_id not in completed_tasks:
                        completed_tasks[user_id] = {}
                    completed_tasks[user_id]['subscribed_to_hatch_egg'] = True
                    
                    # Сохраняем данные после обновления
                    save_data()
                    
                    subscribed = True
                    logger.info(f"User {user_id} is subscribed to Hatch Egg, earned 20 Eggs")
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


async def verify_ton_payment_api(request):
    """API endpoint для проверки и подтверждения TON платежа"""
    # Добавляем CORS headers
    if request.method == 'OPTIONS':
        return web.Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )
    
    try:
        data = await request.json()
    except Exception as e:
        return web.json_response(
            {'error': 'invalid json'}, 
            status=400,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    user_id = data.get('user_id')
    tx_hash = data.get('tx_hash')
    amount = data.get('amount')
    
    if not user_id or not tx_hash or not amount:
        return web.json_response(
            {'error': 'user_id, tx_hash, and amount required'}, 
            status=400,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    try:
        user_id = int(user_id)
        amount = float(amount)
    except (ValueError, TypeError):
        return web.json_response(
            {'error': 'invalid user_id or amount'}, 
            status=400,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    # Вычисляем количество яиц на основе суммы (10 яиц = 0.15 TON)
    eggs_to_add = int((amount / TON_PRICE_PER_PACK) * EGG_PACK_SIZE)
    
    # Проверяем, что количество яиц в допустимом диапазоне (10-1000)
    if eggs_to_add < 10:
        return web.json_response(
            {'error': 'insufficient amount', 'required': TON_PRICE_PER_PACK, 'message': f'Minimum purchase is 10 eggs ({TON_PRICE_PER_PACK} TON)'}, 
            status=400,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    if eggs_to_add > 1000:
        return web.json_response(
            {'error': 'too many eggs', 'max': 1000, 'message': 'Maximum purchase is 1000 eggs (15 TON)'}, 
            status=400,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    # Проверяем, не был ли уже обработан этот платеж
    user_payments = ton_payments.get(user_id, [])
    if any(payment.get('tx_hash') == tx_hash for payment in user_payments):
        return web.json_response(
            {'error': 'payment already processed'}, 
            status=400,
            headers={'Access-Control-Allow-Origin': '*'}
        )
    
    # TODO: Здесь должна быть проверка транзакции через TON API
    # Пока что просто добавляем платеж в список (в продакшене нужно проверять через TON API)
    today = date.today().isoformat()
    payment_record = {
        'date': today,
        'amount': amount,
        'tx_hash': tx_hash,
        'eggs': eggs_to_add
    }
    
    if user_id not in ton_payments:
        ton_payments[user_id] = []
    ton_payments[user_id].append(payment_record)
    
    # Добавляем оплаченные яйца к лимиту пользователя
    add_paid_eggs(user_id, eggs_to_add)
    save_data()
    
    logger.info(f"TON payment verified: user_id={user_id}, amount={amount}, eggs={eggs_to_add}, tx_hash={tx_hash}")
    
    return web.json_response(
        {
            'success': True,
            'message': f'Payment verified! You can now send {eggs_to_add} more eggs.',
            'eggs_added': eggs_to_add
        },
        headers={'Access-Control-Allow-Origin': '*'}
    )


async def get_payment_info_api(request):
    """API endpoint для получения информации о платеже"""
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
    
    # Проверяем ежедневный лимит
    can_send, daily_count, total_limit = check_daily_limit(user_id)
    needs_payment = not can_send
    
    return web.json_response(
        {
            'needs_payment': needs_payment,
            'daily_count': daily_count,
            'total_limit': total_limit,
            'free_eggs': FREE_EGGS_PER_DAY,
            'ton_price': TON_PRICE_PER_PACK,
            'ton_wallet': TON_WALLET,
            'eggs_per_pack': EGG_PACK_SIZE
        },
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
    
    # Передаем бота в eggchain_api для получения информации о пользователях
    set_bot_instance(application.bot)
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    # Команда reset_all отключена для защиты данных пользователей
    # application.add_handler(CommandHandler("reset_all", reset_all))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(ChatMemberHandler(chat_member_handler, ChatMemberHandler.CHAT_MEMBER))
    
    # Запускаем веб-сервер для API в отдельном потоке
    def run_api_server():
        async def start_server():
            import os
            # Используем PORT из окружения (для Railway, Render и т.д.) или 8080 по умолчанию
            port = int(os.environ.get('PORT', 8080))
            
            app = web.Application()
            app.router.add_get('/api/stats', stats_api)
            app.router.add_post('/api/stats/check_subscription', check_subscription_api)
            app.router.add_options('/api/stats/check_subscription', check_subscription_api)
            app.router.add_post('/api/ton/verify_payment', verify_ton_payment_api)
            app.router.add_get('/api/ton/payment_info', get_payment_info_api)
            app.router.add_options('/api/ton/verify_payment', verify_ton_payment_api)
            # Добавляем роуты для Eggchain Explorer
            setup_eggchain_routes(app)
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
