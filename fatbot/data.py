ORDER = ["common", "rare", "epic", "legendary", "mythic"]

RARITIES = {
    "common": {"name": "Ширпотреб", "emoji": "🥴", "min": 5, "max": 29, "ppk": 60, "chance": 55},
    "rare": {"name": "Домашний", "emoji": "🏠", "min": 30, "max": 89, "ppk": 600, "chance": 25},
    "epic": {"name": "Элитный", "emoji": "💎", "min": 90, "max": 199, "ppk": 6000, "chance": 13},
    "legendary": {"name": "Ресторанный", "emoji": "👑", "min": 220, "max": 480, "ppk": 60000, "chance": 6},
    "mythic": {"name": "Легендарный", "emoji": "🔥", "min": 500, "max": 1500, "ppk": 600000, "chance": 1},
}

NAMES = {
    "common": [
        "Пивной животик",
        "Офисный жирок",
        "Пельменный бугорок",
        "Новогодний запас",
        "Любовная ручка",
        "Диванный холмик",
        "Чипсовый слой",
        "Шашлычный бочок",
        "Майонезный карман",
        "Батонный валик",
    ],
    "rare": [
        "Борщевой каркас",
        "Зимний подкожник",
        "Свадебный откат",
        "Отпускное пузо",
        "Дачный занос",
        "Мамин гостевой жир",
        "Пивной животик PRO",
        "Гриль-массив",
        "Праздничный нанос",
    ],
    "epic": [
        "Висцеральный бегемот",
        "Абдоминальный титан",
        "Сальное море",
        "Пузо-комод",
        "Трёхэтажный живот",
        "Мраморное сало",
    ],
    "legendary": [
        "Левиафан борща",
        "Сало Столетия",
        "Чрево Великолепное",
        "Гравитационный центр",
        "Древний холм предков",
    ],
    "mythic": [
        "Жир Ктулху",
        "Абсолютный Холм",
        "Чёрная дыра желудка",
        "Вечный Задок",
    ],
}

DEFECTS = [
    "растяжки",
    "дряблость третьей степени",
    "целлюлитная сетка",
    "неровный обхват",
    "запах старого сала",
    "провисшая складка",
]

FLAVORS_BAD = [
    "По дороге курьер споткнулся, и жир примялся.",
    "Жир перевозили в жару — немного подтёк.",
    "Курьер несколько раз уронил коробку с жиром.",
]
FLAVORS_GOOD = [
    "Жир доставлен в идеальном состоянии!",
    "Курьер аккуратно донёс пузо двумя руками.",
]

UPGRADE_CHANCE = {"common": 0.45, "rare": 0.30, "epic": 0.18, "legendary": 0.10}
UPGRADE_FEE = {"common": 5_000, "rare": 50_000, "epic": 500_000, "legendary": 5_000_000}

DAILY_REWARDS = [10_000, 20_000, 30_000, 50_000, 80_000, 120_000, 200_000]

ACCESSORIES = [
    {"key": "clip", "name": "Зажим для похудения", "emoji": "📎", "price": 5, "desc": "Перезарядка карточки −5%"},
    {"key": "fork", "name": "Вилка фуа-гра", "emoji": "🥂", "price": 10, "desc": "+2% к удаче"},
    {"key": "scale", "name": "Инерционные весы", "emoji": "⚖️", "price": 15, "desc": "+3% к продаже жира"},
    {"key": "clover", "name": "Клевер удачи", "emoji": "🍀", "price": 20, "desc": "+1% к шансу победы в казино"},
]
ACCESSORY_BY_KEY = {a["key"]: a for a in ACCESSORIES}

UPGRADES = [
    {"key": "luck", "name": "Удача", "emoji": "🍀", "desc": "+1% к шансу редкого жира и апгрейда"},
    {"key": "speed", "name": "Метаболизм", "emoji": "⚡", "desc": "−3 мин к перезарядке карточки"},
    {"key": "trader", "name": "Торговец", "emoji": "💰", "desc": "+1% к цене продажи жира"},
    {"key": "farmer", "name": "Агроном", "emoji": "🏭", "desc": "+5% к доходу мастерской"},
]
UPGRADE_MAX_LVL = 10
UPGRADE_COST = lambda lvl: 50_000 * (2 ** lvl)

WORKSHOP_CREATE_COST = 2_500_000
WORKSHOP_MAX_LVL = 5
WORKSHOP_BASE_HOUR = 8_000
WORKSHOP_UPG_COST = lambda lvl: 1_000_000 * (2 ** (lvl - 1))

MARKET_FEE = 0.05

STATUS_TIERS = [
    (10_000, "Абсолютный чемпион"),
    (2_000, "Гуру сала"),
    (500, "Уважаемый толстяк"),
    (100, "Толстяк"),
    (0, "Обычный"),
]

ACHIEVEMENTS = [
    ("first_card", "🐷 Первая карточка"),
    ("ten_cards", "🃏 Десяток жиров"),
    ("centner", "⚖️ Центнер веса"),
    ("millionaire", "💎 Миллионер"),
    ("upgrader", "⬆️ Апгрейдер"),
    ("seller", "🤝 Торговец"),
    ("gambler", "🎰 Игроман"),
    ("star", "👁 Звезда"),
]

CASINO_MIN_BET = 100
CASINO_MAX_BET = 1_000_000
SLOTS_SYMBOLS = ["🐷", "🍔", "🍟", "🍺", "🍩", "🥓"]
BET_PRESETS = [1_000, 10_000, 100_000, 1_000_000]

DAILY_QUESTS = [
    {"key": "buy2", "desc": "Купить 2 жира в магазине", "target": 2, "reward": 7_000, "category": "fatshop"},
    {"key": "casino1", "desc": "Сыграть в казино 1 раз", "target": 1, "reward": 7_500, "category": "casino"},
    {"key": "open5", "desc": "Открыть 5 карточек", "target": 5, "reward": 8_000, "category": "fcard"},
]

WEEKLY_QUESTS = [
    {"key": "workshop_collect", "desc": "Собрать 500,000 ФОчек с мастерской", "target": 500_000, "reward": 150_000, "category": "workshop"},
    {"key": "buy20", "desc": "Купить 20 жиров в магазине", "target": 20, "reward": 120_000, "category": "fatshop"},
    {"key": "avito_sell", "desc": "Продать жиров на Авито на 1,000,000 ФОчек", "target": 1_000_000, "reward": 200_000, "category": "market"},
]

CONTAINER_TYPES = [
    {"key": "wooden", "name": "Деревянный ящик", "emoji": "📦", "capacity": 5, "price": 50_000, "desc": "Вмещает 5 жиров"},
    {"key": "metal", "name": "Металлический контейнер", "emoji": "📦", "capacity": 10, "price": 150_000, "desc": "Вмещает 10 жиров"},
    {"key": "golden", "name": "Золотой контейнер", "emoji": "📦", "capacity": 15, "price": 500_000, "desc": "Вмещает 15 жиров"},
]
CONTAINER_BY_KEY = {c["key"]: c for c in CONTAINER_TYPES}

MAX_CONTAINERS = 5

FATSHOP_PRICES = {
    "common": 1_500,
    "rare": 15_000,
    "epic": 150_000,
    "legendary": 1_500_000,
    "mythic": 15_000_000,
}

FARM_POWER = {1: 50, 2: 100, 3: 200}
FARM_COOLING = {1: 45, 2: 90, 3: 180}
FARM_SLOTS = {1: 2, 2: 3, 3: 4}
FARM_UPGRADE_COST = {1: 100_000, 2: 500_000}
FARM_FCOIN_PER_HOUR = {1: 5, 2: 10, 3: 20}
