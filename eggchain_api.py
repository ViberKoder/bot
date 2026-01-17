"""
API endpoints для Eggchain Explorer
Работает с JSON файлом bot_data.json
"""

from aiohttp import web
import json
import os
from datetime import datetime

# Путь к файлу данных (должен совпадать с bot.py)
DATA_FILE = os.getenv('DATA_FILE', 'bot_data.json')

def load_data():
    """Загружает данные из JSON файла"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {}
    return {}

def add_cors_headers(response):
    """Добавляет CORS заголовки к ответу"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

async def get_egg_by_id(request):
    """
    GET /api/egg/{egg_id}
    Возвращает информацию о конкретном яйце
    Формат egg_id: {sender_id}_{egg_id} или просто {egg_id}
    """
    # Обработка OPTIONS запроса для CORS
    if request.method == 'OPTIONS':
        response = web.Response()
        return add_cors_headers(response)
    
    egg_id_param = request.match_info.get('egg_id')
    
    if not egg_id_param:
        response = web.json_response({'error': 'Egg ID is required'}, status=400)
        return add_cors_headers(response)
    
    try:
        data = load_data()
        
        # Получаем детальную информацию о яйцах
        eggs_detail = data.get('eggs_detail', {})  # {egg_key: {sender_id, egg_id, hatched_by, timestamp_sent, timestamp_hatched}}
        hatched_eggs = set(data.get('hatched_eggs', []))
        
        # Ищем яйцо в eggs_detail
        egg_info = None
        egg_key = None
        
        # Сначала пробуем найти по полному ключу (sender_id_egg_id)
        if egg_id_param in eggs_detail:
            egg_key = egg_id_param
            egg_info = eggs_detail[egg_key]
        else:
            # Ищем по частичному совпадению (только egg_id)
            for key, info in eggs_detail.items():
                if info.get('egg_id') == egg_id_param:
                    egg_key = key
                    egg_info = info
                    break
        
        # Если не нашли в детальной информации, пробуем восстановить из hatched_eggs
        if not egg_info:
            # Ищем в hatched_eggs по формату sender_id_egg_id
            if egg_id_param in hatched_eggs:
                parts = egg_id_param.split('_', 1)
                if len(parts) == 2:
                    sender_id = int(parts[0])
                    egg_id = parts[1]
                    egg_info = {
                        'sender_id': sender_id,
                        'egg_id': egg_id,
                        'hatched_by': None,  # Не знаем, кто вылупил
                        'timestamp_sent': None,
                        'timestamp_hatched': None
                    }
                    egg_key = egg_id_param
            else:
                # Пробуем найти по egg_id в hatched_eggs
                for egg_key_candidate in hatched_eggs:
                    if egg_key_candidate.endswith(f'_{egg_id_param}'):
                        parts = egg_key_candidate.split('_', 1)
                        if len(parts) == 2:
                            sender_id = int(parts[0])
                            egg_id = parts[1]
                            egg_info = {
                                'sender_id': sender_id,
                                'egg_id': egg_id,
                                'hatched_by': None,
                                'timestamp_sent': None,
                                'timestamp_hatched': None
                            }
                            egg_key = egg_key_candidate
                            break
        
        if not egg_info:
            response = web.json_response({'error': 'Egg not found'}, status=404)
            return add_cors_headers(response)
        
        sender_id = egg_info.get('sender_id')
        egg_id = egg_info.get('egg_id', egg_id_param)
        hatched_by = egg_info.get('hatched_by')
        timestamp_sent = egg_info.get('timestamp_sent')
        timestamp_hatched = egg_info.get('timestamp_hatched')
        
        # Проверяем, вылуплено ли яйцо
        is_hatched = egg_key in hatched_eggs if egg_key else False
        
        # Если вылуплено, но hatched_by не указан, пытаемся найти из других источников
        if is_hatched and not hatched_by:
            # Можно попробовать найти из других данных, но для простоты оставляем None
            pass
        
        result = {
            'egg_id': egg_id,
            'sender_id': sender_id,
            'sender_username': None,  # Username нужно получать из Telegram API
            'recipient_id': None,
            'hatched_by': hatched_by,
            'hatched_by_username': None,
            'timestamp_sent': timestamp_sent,
            'timestamp_hatched': timestamp_hatched,
            'status': 'hatched' if is_hatched else 'pending'
        }
        
        response = web.json_response(result)
        return add_cors_headers(response)
        
    except Exception as e:
        response = web.json_response({'error': str(e)}, status=500)
        return add_cors_headers(response)

async def get_user_eggs(request):
    """
    GET /api/user/{user_id}/eggs
    Возвращает список всех яиц, отправленных пользователем
    """
    # Обработка OPTIONS запроса для CORS
    if request.method == 'OPTIONS':
        response = web.Response()
        return add_cors_headers(response)
    
    user_id_param = request.match_info.get('user_id')
    
    if not user_id_param:
        response = web.json_response({'error': 'User ID is required'}, status=400)
        return add_cors_headers(response)
    
    try:
        user_id = int(user_id_param)
    except ValueError:
        response = web.json_response({'error': 'Invalid user ID'}, status=400)
        return add_cors_headers(response)
    
    try:
        data = load_data()
        
        # Получаем детальную информацию о яйцах
        eggs_detail = data.get('eggs_detail', {})
        hatched_eggs = set(data.get('hatched_eggs', []))
        
        # Находим все яйца, отправленные этим пользователем
        user_eggs = []
        for egg_key, egg_info in eggs_detail.items():
            if egg_info.get('sender_id') == user_id:
                egg_id = egg_info.get('egg_id', egg_key.split('_', 1)[1] if '_' in egg_key else egg_key)
                is_hatched = egg_key in hatched_eggs
                
                user_eggs.append({
                    'egg_id': egg_id,
                    'sender_id': user_id,
                    'recipient_id': None,
                    'hatched_by': egg_info.get('hatched_by'),
                    'hatched_by_username': None,
                    'timestamp_sent': egg_info.get('timestamp_sent'),
                    'timestamp_hatched': egg_info.get('timestamp_hatched'),
                    'status': 'hatched' if is_hatched else 'pending'
                })
        
        # Также проверяем hatched_eggs для яиц, которых нет в eggs_detail
        for egg_key in hatched_eggs:
            if egg_key.startswith(f'{user_id}_'):
                # Проверяем, нет ли уже этого яйца в списке
                egg_id = egg_key.split('_', 1)[1] if '_' in egg_key else egg_key
                if not any(e['egg_id'] == egg_id for e in user_eggs):
                    user_eggs.append({
                        'egg_id': egg_id,
                        'sender_id': user_id,
                        'recipient_id': None,
                        'hatched_by': None,
                        'hatched_by_username': None,
                        'timestamp_sent': None,
                        'timestamp_hatched': None,
                        'status': 'hatched'
                    })
        
        # Сортируем по timestamp_sent (новые сначала)
        user_eggs.sort(key=lambda x: x.get('timestamp_sent') or '', reverse=True)
        
        response = web.json_response({'eggs': user_eggs})
        return add_cors_headers(response)
        
    except Exception as e:
        response = web.json_response({'error': str(e)}, status=500)
        return add_cors_headers(response)

def setup_eggchain_routes(app):
    """
    Добавляет роуты для Eggchain Explorer в aiohttp приложение
    Использование: setup_eggchain_routes(app) в вашем bot.py
    """
    app.router.add_get('/api/egg/{egg_id}', get_egg_by_id)
    app.router.add_options('/api/egg/{egg_id}', get_egg_by_id)
    app.router.add_get('/api/user/{user_id}/eggs', get_user_eggs)
    app.router.add_options('/api/user/{user_id}/eggs', get_user_eggs)
