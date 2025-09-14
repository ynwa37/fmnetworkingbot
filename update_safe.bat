@echo off
echo ========================================
echo    ОБНОВЛЕНИЕ БОТА (БЕЗОПАСНОЕ)
echo ========================================

echo [1/4] 📝 Сохранение изменений...
git add .
git commit -m "Обновление бота"
if %errorlevel% neq 0 (
    echo ❌ Ошибка при сохранении изменений
    pause
    exit /b 1
)

echo [2/4] 📤 Отправка на GitHub...
git push origin main
if %errorlevel% neq 0 (
    echo ❌ Ошибка при отправке на GitHub
    pause
    exit /b 1
)

echo [3/4] 🔄 Обновление на сервере...
ssh root@62.113.37.231 "cd /root/fmnetworkingbot && git pull origin main"
if %errorlevel% neq 0 (
    echo ❌ Ошибка при обновлении на сервере
    pause
    exit /b 1
)

echo [4/4] 🔄 Перезапуск бота...
ssh root@62.113.37.231 "cd /root/fmnetworkingbot && ./manage_bot.sh restart"
if %errorlevel% neq 0 (
    echo ❌ Ошибка при перезапуске бота
    pause
    exit /b 1
)

echo.
echo ✅ БОТ УСПЕШНО ОБНОВЛЕН!
echo.
echo 📊 Полезные команды:
echo    • Логи: ssh root@62.113.37.231 "tail -f /root/fmnetworkingbot/bot.log"
echo    • Статус: ssh root@62.113.37.231 "cd /root/fmnetworkingbot && ./manage_bot.sh status"
echo    • Остановка: ssh root@62.113.37.231 "cd /root/fmnetworkingbot && ./manage_bot.sh stop"
echo    • Запуск: ssh root@62.113.37.231 "cd /root/fmnetworkingbot && ./manage_bot.sh start"
echo.
pause
