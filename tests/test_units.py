import random
from datetime import datetime

import pytest

from fatbot import data, services
from fatbot.utils import fmt, remaining_str


def test_fmt():
    assert fmt(129800) == "129,800"
    assert fmt(0) == "0"


def test_remaining_str():
    from datetime import timedelta

    assert remaining_str(timedelta(hours=2, minutes=39, seconds=56)) == "2 ч 39 мин 56 сек"
    assert remaining_str(timedelta(seconds=45)) == "45 сек"
    assert remaining_str(timedelta(minutes=5)) == "5 мин 0 сек"


def test_parse_amount():
    assert services.parse_amount("100") == 100
    assert services.parse_amount("12к") == 12_000
    assert services.parse_amount("12 к") == 12_000
    assert services.parse_amount("1.5кк") == 1_500_000
    assert services.parse_amount("1,5кк") == 1_500_000
    assert services.parse_amount("3kk") == 3_000_000
    assert services.parse_amount("abc") is None
    assert services.parse_amount("-5") is None
    assert services.parse_amount("0") is None


def test_roll_rarity_distribution():
    rng = random.Random(42)
    counts = {k: 0 for k in data.ORDER}
    for _ in range(20000):
        counts[services.roll_rarity(rng, 0)] += 1
    total = sum(counts.values())
    share = counts["common"] / total
    assert 0.50 < share < 0.60
    assert all(counts[k] > 0 for k in data.ORDER)


def test_luck_shifts_distribution():
    rng = random.Random(1)
    common = sum(services.roll_rarity(rng, 30) == "common" for _ in range(20000)) / 20000
    assert common < 0.55


class FakeRng:
    def __init__(self, choices_result):
        self._c = choices_result

    def choices(self, seq, k=1, weights=None):
        return [self._c] * k

    def random(self):
        return 0.5

    def sample(self, seq, n):
        return list(seq)[:n]

    def randint(self, a, b):
        return (a + b) // 2

    def choice(self, seq):
        return seq[0]


def test_make_card_fields_price_with_defects():
    fields, flavor = services.make_card_fields("common", FakeRng("🐷"))
    base = fields["weight"] * data.RARITIES["common"]["ppk"]
    expected = int(base * 0.8 ** len(fields["defects"]))
    assert fields["base_price"] == expected


def test_spin_slots_triple_and_pair():
    reels, mult = services.spin_slots(FakeRng("🐷"))
    assert mult == 12.0 and reels == ("🐷", "🐷", "🐷")

    class PairRng(FakeRng):
        def choices(self, seq, k=1, weights=None):
            return ["🐷", "🍔", "🐷"]

    reels, mult = services.spin_slots(PairRng(None))
    assert mult == 2.0

    class LoseRng(FakeRng):
        def choices(self, seq, k=1, weights=None):
            return ["🐷", "🍔", "🍟"]

    reels, mult = services.spin_slots(LoseRng(None))
    assert mult == 0.0


def test_upgrade_chance_bounds():
    assert services.upgrade_chance("common", 0) == pytest.approx(0.45)
    assert services.upgrade_chance("legendary", 100) <= 0.35
    assert services.upgrade_chance("rare", 1) == pytest.approx(0.30 + 0.02)


def test_status_name():
    assert services.status_name(50) == "Обычный"
    assert services.status_name(150) == "Толстяк"
    assert services.status_name(9999) == "Гуру сала"
    assert services.status_name(99999) == "Абсолютный чемпион"


def test_workshop_pending_and_collect():
    from datetime import timedelta

    from fatbot.models import User
    from fatbot.utils import utcnow

    u = User(id=1, workshop_lvl=2, workshop_at=utcnow() - timedelta(hours=3))
    assert services.workshop_pending(u) == 3 * services.workshop_income_hour(u)
    u.workshop_at = utcnow() - timedelta(days=5)
    assert services.workshop_pending(u) == 24 * services.workshop_income_hour(u)
    amount = services.workshop_collect(u)
    assert amount > 0
    assert services.workshop_pending(u) == 0


async def test_coinflip_win_rate():
    rng = random.Random(7)
    wins = 0
    for _ in range(2000):
        if await services.coinflip_win(rng):
            wins += 1
    assert 0.42 < wins / 2000 < 0.56
