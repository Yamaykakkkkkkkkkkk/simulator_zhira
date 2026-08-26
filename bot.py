import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramUnauthorizedError

from fatbot.config import BOT_TOKEN, DATABASE_URL
from fatbot.db import DbSessionMiddleware, init_db, make_engine, make_sessionmaker
from fatbot.handlers import build_router
from fatbot.web import start_web


async def check():
    engine = make_engine(DATABASE_URL)
    try:
        await init_db(engine)
        print("✅ База данных инициализирована:", DATABASE_URL.split("@")[-1])
        if not BOT_TOKEN:
            print("⚠️ BOT_TOKEN не задан (для запуска укажите его в .env)")
        else:
            print("✅ BOT_TOKEN задан")
    finally:
        await engine.dispose()


async def run():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан. Создайте .env (см. .env.example) и укажите токен от @BotFather.")
        sys.exit(1)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    engine = make_engine(DATABASE_URL)
    await init_db(engine)
    sm = make_sessionmaker(engine)
    dp = Dispatcher()
    dp.update.outer_middleware(DbSessionMiddleware(sm))
    dp.include_router(build_router())
    port = int(os.getenv("PORT", "8080"))
    start_web(port)
    logging.info(f"HTTP-сервер запущен на 0.0.0.0:{port}")
    bot = Bot(BOT_TOKEN)
    try:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        except TelegramUnauthorizedError:
            print("❌ Неверный BOT_TOKEN. Проверьте токен у @BotFather.")
            sys.exit(1)
        finally:
            await bot.session.close()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if "--check" in sys.argv:
        asyncio.run(check())
    else:
        asyncio.run(run())
