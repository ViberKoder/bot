#!/usr/bin/env python3
"""
Скрипт для полного сброса всех счетчиков и бесплатных яиц
"""
import json
import os

DATA_FILE = "bot_data.json"

def reset_all_counters():
    """Полностью сбрасывает все счетчики и бесплатные яйца"""
    if not os.path.exists(DATA_FILE):
        print(f"Файл {DATA_FILE} не найден! Создаю новый файл с пустыми данными.")
        # Создаем файл с пустыми данными
        data = {
            'hatched_eggs': [],
            'eggs_hatched_by_user': {},
            'user_eggs_hatched_by_others': {},
            'eggs_sent_by_user': {},
            'daily_eggs_sent': {},
            'egg_points': {},
            'completed_tasks': {},
            'referrers': {},
            'referral_earnings': {},
            'ton_payments': {}
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("OK: Created new file with empty data!")
        return
    
    try:
        # Загружаем данные
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Полностью обнуляем все счетчики
        data['eggs_hatched_by_user'] = {}  # Сколько яиц вылупил каждый пользователь
        data['user_eggs_hatched_by_others'] = {}  # Сколько яиц пользователя вылупили другие
        data['eggs_sent_by_user'] = {}  # Сколько яиц отправил каждый пользователь
        data['daily_eggs_sent'] = {}  # Ежедневные счетчики (сбрасывает бесплатные яйца)
        data['egg_points'] = {}  # Все поинты
        data['hatched_eggs'] = []  # Список вылупленных яиц
        data['completed_tasks'] = {}  # Выполненные задания
        data['referral_earnings'] = {}  # Реферальные заработки
        
        # Сохраняем обратно
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print("OK: All counters and free eggs have been reset!")
        print("\nReset:")
        print("- All hatched eggs counters (hatched_by_me)")
        print("- All my eggs hatched by others counters (my_eggs_hatched)")
        print("- All sent eggs counters")
        print("- All daily counters (free eggs reset)")
        print("- All points")
        print("- All hatched eggs list")
        print("- All completed tasks")
        print("- All referral earnings")
        print("\nPreserved:")
        print("- Referral system (who referred whom - referrers)")
        print("- TON payment history (ton_payments)")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("Starting reset of all counters and free eggs...")
    reset_all_counters()
    print("\nDone!")
