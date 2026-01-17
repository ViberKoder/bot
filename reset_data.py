#!/usr/bin/env python3
"""
Скрипт для обнуления всех поинтов и счетчиков яиц
"""
import json
import os

DATA_FILE = "bot_data.json"

def reset_points_and_eggs():
    """Обнуляет все поинты и счетчики яиц"""
    if not os.path.exists(DATA_FILE):
        print(f"Файл {DATA_FILE} не найден!")
        return
    
    try:
        # Загружаем данные
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Обнуляем поинты и счетчики
        data['egg_points'] = {}
        data['eggs_sent_by_user'] = {}
        data['daily_eggs_sent'] = {}
        data['referral_earnings'] = {}
        
        # Сохраняем обратно
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print("✅ Все поинты и счетчики яиц обнулены!")
        print("\nОбнулено:")
        print("• Все Egg поинты")
        print("• Счетчики отправленных яиц")
        print("• Ежедневные счетчики яиц")
        print("• Реферальные заработки")
        print("\nСохранено:")
        print("• Статистика вылупления")
        print("• Реферальная система (кто кого привел)")
        print("• Выполненные задания")
        print("• TON платежи")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    reset_points_and_eggs()
