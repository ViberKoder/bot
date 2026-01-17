"""
API endpoints для Eggchain Explorer
Добавьте эти роуты в ваш основной bot.py файл
"""

from aiohttp import web
import json
from datetime import datetime
import sqlite3
import os

# Путь к базе данных (адаптируйте под вашу структуру)
DB_PATH = os.getenv('DB_PATH', 'eggs.db')

def get_db_connection():
    """Создает соединение с базой данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    """
    # Обработка OPTIONS запроса для CORS
    if request.method == 'OPTIONS':
        response = web.Response()
        return add_cors_headers(response)
    
    egg_id = request.match_info.get('egg_id')
    
    if not egg_id:
        response = web.json_response({'error': 'Egg ID is required'}, status=400)
        return add_cors_headers(response)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Получаем информацию о яйце
        # Адаптируйте SQL запрос под вашу структуру таблиц
        cursor.execute('''
            SELECT 
                egg_id,
                sender_id,
                recipient_id,
                hatched_by,
                timestamp_sent,
                timestamp_hatched,
                status
            FROM eggs
            WHERE egg_id = ?
        ''', (egg_id,))
        
        egg = cursor.fetchone()
        
        if not egg:
            return web.json_response({'error': 'Egg not found'}, status=404)
        
        # Получаем username отправителя
        sender_username = None
        if egg['sender_id']:
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (egg['sender_id'],))
            sender_user = cursor.fetchone()
            if sender_user:
                sender_username = sender_user['username']
        
        # Получаем username того, кто вылупил
        hatched_by_username = None
        if egg['hatched_by']:
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (egg['hatched_by'],))
            hatched_user = cursor.fetchone()
            if hatched_user:
                hatched_by_username = hatched_user['username']
        
        result = {
            'egg_id': egg['egg_id'],
            'sender_id': egg['sender_id'],
            'sender_username': sender_username,
            'recipient_id': egg['recipient_id'],
            'hatched_by': egg['hatched_by'],
            'hatched_by_username': hatched_by_username,
            'timestamp_sent': egg['timestamp_sent'],
            'timestamp_hatched': egg['timestamp_hatched'],
            'status': egg['status'] or ('hatched' if egg['hatched_by'] else 'pending')
        }
        
        response = web.json_response(result)
        return add_cors_headers(response)
        
    except sqlite3.Error as e:
        response = web.json_response({'error': f'Database error: {str(e)}'}, status=500)
        return add_cors_headers(response)
    except Exception as e:
        response = web.json_response({'error': str(e)}, status=500)
        return add_cors_headers(response)
    finally:
        conn.close()

async def get_user_eggs(request):
    """
    GET /api/user/{user_id}/eggs
    Возвращает список всех яиц, отправленных пользователем
    """
    # Обработка OPTIONS запроса для CORS
    if request.method == 'OPTIONS':
        response = web.Response()
        return add_cors_headers(response)
    
    user_id = request.match_info.get('user_id')
    
    if not user_id:
        response = web.json_response({'error': 'User ID is required'}, status=400)
        return add_cors_headers(response)
    
    try:
        user_id = int(user_id)
    except ValueError:
        response = web.json_response({'error': 'Invalid user ID'}, status=400)
        return add_cors_headers(response)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Получаем все яйца, отправленные пользователем
        # Адаптируйте SQL запрос под вашу структуру таблиц
        cursor.execute('''
            SELECT 
                egg_id,
                sender_id,
                recipient_id,
                hatched_by,
                timestamp_sent,
                timestamp_hatched,
                status
            FROM eggs
            WHERE sender_id = ?
            ORDER BY timestamp_sent DESC
        ''', (user_id,))
        
        eggs = cursor.fetchall()
        
        result_eggs = []
        for egg in eggs:
            # Получаем username того, кто вылупил
            hatched_by_username = None
            if egg['hatched_by']:
                cursor.execute('SELECT username FROM users WHERE user_id = ?', (egg['hatched_by'],))
                hatched_user = cursor.fetchone()
                if hatched_user:
                    hatched_by_username = hatched_user['username']
            
            result_eggs.append({
                'egg_id': egg['egg_id'],
                'sender_id': egg['sender_id'],
                'recipient_id': egg['recipient_id'],
                'hatched_by': egg['hatched_by'],
                'hatched_by_username': hatched_by_username,
                'timestamp_sent': egg['timestamp_sent'],
                'timestamp_hatched': egg['timestamp_hatched'],
                'status': egg['status'] or ('hatched' if egg['hatched_by'] else 'pending')
            })
        
        response = web.json_response({'eggs': result_eggs})
        return add_cors_headers(response)
        
    except sqlite3.Error as e:
        response = web.json_response({'error': f'Database error: {str(e)}'}, status=500)
        return add_cors_headers(response)
    except Exception as e:
        response = web.json_response({'error': str(e)}, status=500)
        return add_cors_headers(response)
    finally:
        conn.close()

def setup_eggchain_routes(app):
    """
    Добавляет роуты для Eggchain Explorer в aiohttp приложение
    Использование: setup_eggchain_routes(app) в вашем bot.py
    """
    app.router.add_get('/api/egg/{egg_id}', get_egg_by_id)
    app.router.add_options('/api/egg/{egg_id}', get_egg_by_id)
    app.router.add_get('/api/user/{user_id}/eggs', get_user_eggs)
    app.router.add_options('/api/user/{user_id}/eggs', get_user_eggs)
