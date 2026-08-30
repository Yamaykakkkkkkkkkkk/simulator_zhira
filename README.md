# 🐷 Симулятор Жира — Telegram-бот

Телеграм-бот на Python (aiogram 3 + SQLAlchemy): собирайте карточки жира, улучшайте их,
продавайте на «ЖироАвито», играйте в казино и качайте мастерскую.

## Возможности

- `/start` — приветствие, реферальная ссылка (`?start=<id>`)
- `/fcard` или «ФКарточка» — выбить случайный жир (5 редкостей, дефекты, кулдаун ~3 ч)
- `/profile [@юзернейм]` / `/faccount` — профиль, статус по общему весу, счётчик просмотров
- `/myfats` — коллекция по редкостям, продажа/апгрейд/выставление конкретного жира
- `/pay`, `/paycoin` — переводы ФОчек и F-Coins (суммы с `к`/`кк`)
- `/trade @user` — обмен жиром между игроками
- `/upgrade`, `/upgradeall` — апгрейд редкости (карта сгорает при неудаче)
- `/sellall` — массовая продажа по редкости
- `/avito`, `/avisell`, `/avimy` — рынок игроков (комиссия 5%)
- `/casino` — монетка и слоты
- `/fshop` — аксессуары за F-Coins (+ обмен 1 000 000 ФОчек → 1 FC)
- `/upgradeshop` — прокачка удачи, метаболизма, торговца, агронома
- `/newworkshop`, `/myworkshop` — мастерская: пассивный доход, сбор и улучшение
- `/daily` — 7-дневный цикл наград, `/ref` — реферальная программа
- `/give` (админ) — выдача валюты для тестов
- `/fcooldown` (только владелец, `OWNER_ID`) — глобально включает/выключает задержку карточек для всех игроков

## База данных

Сервер (runxbuild) не имеет постоянного хранилища, поэтому данные нельзя хранить локально.
Бот использует SQLAlchemy:

- **Прод:** любой внешний PostgreSQL. Бесплатные варианты: [Neon](https://neon.tech) или [Supabase](https://supabase.com).
  В `.env`: `DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname`
- **Локально/тесты:** SQLite (по умолчанию), ничего настраивать не нужно.

## Веб-порт для хостинга

Бот поднимает Flask-сервер на порту из переменной `PORT` (по умолчанию `8080`):
`GET /` возвращает **Hello World**, `GET /health` — `ok`. Это нужно для платформ,
которые требуют открытый HTTP-порт (runxbuild и подобные).

## Запуск

```bash
pip install -r requirements.txt
cp .env.example .env      # впишите BOT_TOKEN от @BotFather и DATABASE_URL
python bot.py             # запуск polling
python bot.py --check     # проверка конфига и БД без запуска
```

## Тесты

```bash
pip install -r requirements.txt
pytest -q
```

## License

Copyright (C) 2026 Linuin

This project is licensed under the GNU General Public License v3.0.
See the [LICENSE](LICENSE) file for details.
