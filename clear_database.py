#!/usr/bin/env python3
"""
Скрипт для очистки базы данных
"""
import sqlite3
import os

def clear_database():
    """Очистка базы данных"""
    db_path = 'bot_database.db'
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Очищаем таблицы
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM likes")
        
        # Сбрасываем автоинкремент
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='users'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='likes'")
        
        conn.commit()
        conn.close()
        
        print("✅ База данных очищена!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при очистке базы: {e}")
        return False

if __name__ == "__main__":
    clear_database()
