@echo off
title Восстановление рабочей версии
color 0A

echo.
echo                    🔄 ВОССТАНОВЛЕНИЕ РАБОЧЕЙ ВЕРСИИ 🔄
echo.

echo [1/3] 📥 Получение рабочей версии...
git fetch origin
git reset --hard working-version

echo.
echo [2/3] 📤 Отправка на сервер...
git push origin main --force

echo.
echo [3/3] 🚀 Перезапуск бота на сервере...
ssh root@62.113.37.231 "cd /root/fmnetworkingbot && git reset --hard origin/main && pkill -f 'python bot.py' && nohup python bot.py > bot.log 2>&1 &"

echo.
echo ✅ ГОТОВО! Рабочая версия восстановлена
echo.
echo 📋 Полезные команды:
echo    • Логи: ssh root@62.113.37.231 "tail -f /root/fmnetworkingbot/bot.log"
echo    • Остановка: ssh root@62.113.37.231 "pkill -f 'python bot.py'"
echo.
pause
