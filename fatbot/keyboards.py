from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from . import data


def main_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🐷 ФКарточка"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="🎒 Коллекция"), KeyboardButton(text="💼 Инвентарь")],
        [KeyboardButton(text="🎰 Казино"), KeyboardButton(text="📢 Авито")],
        [KeyboardButton(text="🛒 ФШоп"), KeyboardButton(text="⬆️ Улучшения")],
        [KeyboardButton(text="🏪 Мастерская"), KeyboardButton(text="🎁 Бонус")],
        [KeyboardButton(text="🤝 Рефералы"), KeyboardButton(text="📦 Контейнеры")],
        [KeyboardButton(text="🏭 Ферма"), KeyboardButton(text="📜 Квесты")],
        [KeyboardButton(text="🛒 Магазин жиров"), KeyboardButton(text="⚙️ Настройки")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def ikb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows]
    )


def rarities_kb(prefix: str, counts: dict[str, int], back_cb: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for key in data.ORDER:
        cnt = counts.get(key, 0)
        if cnt <= 0:
            continue
        d = data.RARITIES[key]
        chance = f" ({int(data.UPGRADE_CHANCE[key] * 100)}%)" if prefix == "upr" else ""
        label = f"{d['emoji']} {d['name']}{chance} [{cnt}]"
        row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if back_cb:
        rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cards_page_kb(
    select_prefix: str, page_prefix: str, cards: list, page: int, pages: int, back_cb: str
) -> InlineKeyboardMarkup:
    rows = []
    for c in cards:
        mark = " 🔖" if c.listed else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{data.RARITIES[c.rarity]['emoji']} {c.name} · {c.weight} кг{mark}",
                    callback_data=f"{select_prefix}:{c.id}",
                )
            ]
        )
    nav = []
    if pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"{page_prefix}:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"{page_prefix}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_manage_kb(card_id: int, listed: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="💸 Продать", callback_data=f"sellone:{card_id}")]]
    rows.append([InlineKeyboardButton(text="⬆️ Апгрейд", callback_data=f"upone:{card_id}")])
    if not listed:
        rows.append([InlineKeyboardButton(text="📢 На Авито", callback_data=f"avsel:{card_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="coll_root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(yes_cb: str, no_cb: str | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="✅ Да", callback_data=yes_cb)]]
    if no_cb:
        rows[0].append(InlineKeyboardButton(text="❌ Нет", callback_data=no_cb))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def market_nav_kb(page: int, pages: int, listing_ids: list[int]) -> InlineKeyboardMarkup:
    rows = []
    for lid in listing_ids:
        rows.append([InlineKeyboardButton(text=f"💰 Купить №{lid}", callback_data=f"avbuy:{lid}")])
    nav = []
    if pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"avp:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"avp:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(text="📤 Выставить жир", callback_data="avsell_menu"),
            InlineKeyboardButton(text="📦 Мои объявления", callback_data="avimy"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def casino_kb() -> InlineKeyboardMarkup:
    return ikb(
        [
            [("🪙 Монетка", "cas_cf"), ("🎰 Слоты", "cas_sl")],
            [("◀️ В меню", "noop")],
        ]
    )


def bets_kb(prefix: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for b in data.BET_PRESETS:
        label = f"{b // 1000}к" if b < 1_000_000 else "1кк"
        row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}:{b}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🍀 All-in", callback_data=f"{prefix}:all")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="casino_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_kb(owned: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for a in data.ACCESSORIES:
        label = f"{a['emoji']} {a['name']} — {a['price']} FC" + (" ✅" if a["key"] in owned else "")
        cb = "noop" if a["key"] in owned else f"accbuy:{a['key']}"
        rows.append([InlineKeyboardButton(text=label, callback_data=cb)])
    rows.append([InlineKeyboardButton(text="🔁 Обменять 1,000,000 ФОчек → 1 FC", callback_data="accex")])
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="noop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def upgrades_kb(user) -> InlineKeyboardMarkup:
    rows = []
    for u in data.UPGRADES:
        lvl = getattr(user, f"{u['key']}_lvl")
        if lvl >= data.UPGRADE_MAX_LVL:
            label = f"{u['emoji']} {u['name']} [{lvl}] — MAX"
            cb = "noop"
        else:
            label = f"{u['emoji']} {u['name']} [{lvl}] — {data.UPGRADE_COST(lvl):,}"
            cb = f"ubuy:{u['key']}"
        rows.append([InlineKeyboardButton(text=label, callback_data=cb)])
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="noop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def workshop_kb(has_workshop: bool) -> InlineKeyboardMarkup:
    if not has_workshop:
        return confirm_kb("wsnew_go")
    return ikb(
        [
            [("💰 Собрать доход", "wscol")],
            [("⬆️ Улучшить мастерскую", "wsupg")],
        ]
    )


def trade_accept_kb(initiator_id: int) -> InlineKeyboardMarkup:
    return ikb([[("✅ Принять", f"tracc:{initiator_id}"), ("❌ Отказаться", f"trdec:{initiator_id}")]])


def trade_confirm_kb() -> InlineKeyboardMarkup:
    return ikb([[("✅ Согласиться на обмен", "tryes"), ("❌ Отменить", "trno")]])
