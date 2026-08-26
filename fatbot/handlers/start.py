from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from .. import services
from ..config import BOT_USERNAME, CHANNEL
from ..keyboards import main_kb
from ..utils import answer_media

router = Router()

WELCOME = (
    "👋 Добро пожаловать, {name}!\n\n"
    "👾 Наш бот предлагает вам погрузиться в мир жира и доказать другим, "
    "что именно вы лучше всех его накапливаете!\n\n"
    '💬 Чтобы открыть вашу первую карточку напишите "ФКарточка".\n\n'
    "Наш телеграм канал: {channel}\n\n"
    "📌 Используйте одну из кнопок ниже для взаимодействия с функциями:"
)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    ref_note = ""
    if command.args and command.args.isdigit():
        if await services.register_referral(session, user, int(command.args)):
            ref_note = "\n\n🤝 Вы присоединились по реферальной ссылке!"
    await answer_media(message, "welcome", WELCOME.format(name="@" + (message.from_user.username or message.from_user.full_name), channel=CHANNEL) + ref_note, main_kb())


@router.message(lambda m: m.text and m.text.strip().lower() in ("/help", "помощь"))
async def cmd_help(message: Message):
    text = (
        "📖 Команды бота:\n\n"
        "/fcard или ФКарточка — выбить жир\n"
        "/profile [@юзернейм] — профиль игрока\n"
        "/myfats — коллекция жиров\n"
        "/finventory — инвентарь аксессуаров и жиров\n"
        "/pay — перевод ФОчек\n"
        "/paycoin — перевод F-Coins\n"
        "/trade @юзернейм — обмен жиром\n"
        "/upgrade и /upgradeall — апгрейд жира\n"
        "/sellall — массовая продажа\n"
        "/avito — рынок жиров\n"
        "/casino — казино\n"
        "/fshop — магазин за F-Coins\n"
        "/upgradeshop — магазин улучшений\n"
        "/fatshop — магазин жиров за ФОчки\n"
        "/fquests — список квестов\n"
        "/fconfig — настройки\n"
        "/achievements — каталог достижений\n"
        "/fcontainershop — магазин контейнеров\n"
        "/mycontainers — ваши контейнеры\n"
        "/newworkshop и /myworkshop — мастерская\n"
        "/workshoplist — список мастерских\n"
        "/ffarm — модульная ферма\n"
        "/fauction — аукцион\n"
        "/fexchange — биржа F-Coin\n"
        "/daily — ежедневный бонус\n"
        "/ref — реферальная программа\n"
        f"\n🔗 t.me/{BOT_USERNAME}"
    )
    await message.answer(text)
