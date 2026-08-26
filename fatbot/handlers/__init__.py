from . import (admin, card, casino, collection, daily, market, misc, pay, profile,
               ref, sellall, shop, start, trade, upgrade, upgradeshop, workshop)
from aiogram import Router


def build_router() -> Router:
    root = Router()
    for mod in (
        start,
        card,
        collection,
        pay,
        trade,
        upgrade,
        sellall,
        market,
        casino,
        shop,
        upgradeshop,
        workshop,
        profile,
        daily,
        ref,
        admin,
        misc,
    ):
        root.include_router(mod.router)
    return root
