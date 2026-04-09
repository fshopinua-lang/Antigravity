#!/bin/bash
# Установщик приложения "Финансовый отчёт" для Fedora
set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$APP_DIR/.venv"
PYTHON="$VENV/bin/python"

echo "════════════════════════════════════════"
echo "  📊 Установка: Финансовый отчёт"
echo "════════════════════════════════════════"

# 1. Создаём виртуальное окружение если нет
if [ ! -f "$PYTHON" ]; then
  echo "→ Создаю виртуальное окружение..."
  python3 -m venv "$VENV" || ~/.local/bin/uv venv "$VENV"
fi

# 2. Устанавливаем зависимости
echo "→ Устанавливаю зависимости..."
if command -v ~/.local/bin/uv &>/dev/null; then
  ~/.local/bin/uv pip install flask pandas openpyxl --python "$PYTHON" -q
else
  "$PYTHON" -m pip install flask pandas openpyxl -q
fi

# 3. Создаём скрипт запуска
LAUNCHER="$HOME/.local/bin/finance-report"
mkdir -p "$HOME/.local/bin"
cat > "$LAUNCHER" << EOF
#!/bin/bash
cd "$APP_DIR"
"$PYTHON" finance_web/app.py
EOF
chmod +x "$LAUNCHER"

# 4. Создаём .desktop файл (иконка в меню GNOME)
DESKTOP="$HOME/.local/share/applications/finance-report.desktop"
mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Финансовый отчёт
Name[ru]=Финансовый отчёт
Comment=Производство и расходы предприятия
Exec=$LAUNCHER
Icon=utilities-system-monitor
Terminal=false
Categories=Office;Finance;
Keywords=финансы;отчёт;производство;расходы;
StartupNotify=true
EOF

# 5. Обновляем базу приложений
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "✅ Установка завершена!"
echo ""
echo "  Запуск из терминала:  finance-report"
echo "  Или найдите 'Финансовый отчёт' в меню приложений GNOME"
echo ""
