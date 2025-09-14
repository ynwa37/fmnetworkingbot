#!/bin/bash

# Скрипт для управления ботом
# Использование: ./manage_bot.sh [start|stop|restart|status]

BOT_DIR="/root/fmnetworkingbot"
BOT_SCRIPT="python bot.py"
LOG_FILE="$BOT_DIR/bot.log"

case "$1" in
    start)
        echo "🔄 Остановка всех экземпляров бота..."
        pkill -f "$BOT_SCRIPT" 2>/dev/null || true
        sleep 2
        
        echo "🚀 Запуск бота..."
        cd "$BOT_DIR"
        source venv/bin/activate
        nohup $BOT_SCRIPT > "$LOG_FILE" 2>&1 &
        sleep 2
        
        if pgrep -f "$BOT_SCRIPT" > /dev/null; then
            echo "✅ Бот успешно запущен!"
            echo "📊 PID: $(pgrep -f "$BOT_SCRIPT")"
        else
            echo "❌ Ошибка запуска бота!"
            exit 1
        fi
        ;;
        
    stop)
        echo "🛑 Остановка бота..."
        pkill -f "$BOT_SCRIPT" 2>/dev/null || true
        sleep 2
        
        if pgrep -f "$BOT_SCRIPT" > /dev/null; then
            echo "⚠️  Принудительная остановка..."
            pkill -9 -f "$BOT_SCRIPT" 2>/dev/null || true
            sleep 1
        fi
        
        if ! pgrep -f "$BOT_SCRIPT" > /dev/null; then
            echo "✅ Бот остановлен!"
        else
            echo "❌ Не удалось остановить бота!"
            exit 1
        fi
        ;;
        
    restart)
        echo "🔄 Перезапуск бота..."
        $0 stop
        sleep 1
        $0 start
        ;;
        
    status)
        if pgrep -f "$BOT_SCRIPT" > /dev/null; then
            echo "✅ Бот работает"
            echo "📊 PID: $(pgrep -f "$BOT_SCRIPT")"
            echo "📝 Логи: tail -f $LOG_FILE"
        else
            echo "❌ Бот не работает"
        fi
        ;;
        
    *)
        echo "Использование: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
