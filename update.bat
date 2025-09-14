@echo off
title Обновление бота
color 0A

echo.
echo  ██╗   ██╗██████╗ ██████╗  █████╗ ████████╗███████╗
echo ██║   ██║██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔════╝
echo ██║   ██║██████╔╝██║  ██║███████║   ██║   █████╗  
echo ╚██╗ ██╔╝██╔══██╗██║  ██║██╔══██║   ██║   ██╔══╝  
echo  ╚████╔╝ ██║  ██║██████╔╝██║  ██║   ██║   ███████╗
echo   ╚═══╝  ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝
echo.
echo                    🚀 ОБНОВЛЕНИЕ БОТА 🚀
echo.

echo [1/3] 📝 Сохраняем изменения...
git add .
git commit -m "Обновление %date% %time%" 2>nul || echo "Нет изменений"

echo.
echo [2/3] 📤 Отправляем на GitHub...
git push origin main

echo.
echo [3/3] 🔄 Обновляем сервер...
ssh root@62.113.37.231 "cd /root/fmnetworkingbot && git pull origin main && pkill -f 'python bot.py' 2>/dev/null; source venv/bin/activate && nohup python bot.py > bot.log 2>&1 &"

echo.
echo ✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО!
echo.
echo 📋 Проверьте бота:
echo    • Отправьте /start боту
echo    • Логи: ssh root@62.113.37.231 "tail -f /root/fmnetworkingbot/bot.log"
echo.
pause
