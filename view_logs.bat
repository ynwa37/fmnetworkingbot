@echo off
echo ========================================
echo        ПРОСМОТР ЛОГОВ БОТА
echo ========================================
echo.
echo Выберите действие:
echo 1. Логи в реальном времени (tail -f)
echo 2. Последние 50 строк
echo 3. Поиск ошибок
echo 4. Статус бота
echo 5. Все логи
echo.
set /p choice="Введите номер (1-5): "

if "%choice%"=="1" (
    echo 📊 Показываем логи в реальном времени...
    echo Нажмите Ctrl+C для выхода
    ssh root@62.113.37.231 "tail -f /root/fmnetworkingbot/bot.log"
) else if "%choice%"=="2" (
    echo 📊 Последние 50 строк логов:
    ssh root@62.113.37.231 "tail -50 /root/fmnetworkingbot/bot.log"
) else if "%choice%"=="3" (
    echo 🔍 Поиск ошибок в логах:
    ssh root@62.113.37.231 "grep -i error /root/fmnetworkingbot/bot.log"
) else if "%choice%"=="4" (
    echo 📊 Статус бота:
    ssh root@62.113.37.231 "cd /root/fmnetworkingbot && ./manage_bot.sh status"
) else if "%choice%"=="5" (
    echo 📊 Все логи:
    ssh root@62.113.37.231 "cat /root/fmnetworkingbot/bot.log"
) else (
    echo ❌ Неверный выбор
)

echo.
pause
