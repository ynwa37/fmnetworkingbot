#!/usr/bin/env python3
"""
Тест импортов для проверки зависимостей
"""
import sys
import os

print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Files in directory:", os.listdir('.'))

try:
    print("\nTesting imports...")
    
    # Тест основных импортов
    import asyncio
    print("✓ asyncio")
    
    import logging
    print("✓ logging")
    
    from functools import lru_cache
    print("✓ functools.lru_cache")
    
    from typing import Dict, Any, Optional
    print("✓ typing")
    
    from aiogram import Bot, Dispatcher, types, F
    print("✓ aiogram")
    
    from aiogram.filters import Command, StateFilter
    print("✓ aiogram.filters")
    
    from aiogram.fsm.context import FSMContext
    print("✓ aiogram.fsm.context")
    
    from aiogram.fsm.state import State, StatesGroup
    print("✓ aiogram.fsm.state")
    
    from aiogram.fsm.storage.memory import MemoryStorage
    print("✓ aiogram.fsm.storage.memory")
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
    print("✓ aiogram.types")
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    print("✓ aiogram.utils.keyboard")
    
    import aiosqlite
    print("✓ aiosqlite")
    
    # Тест переменных окружения
    bot_token = os.getenv('BOT_TOKEN')
    if bot_token:
        print("✓ BOT_TOKEN found in environment")
    else:
        print("⚠ BOT_TOKEN not found in environment")
    
    print("\n✅ All imports successful!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
