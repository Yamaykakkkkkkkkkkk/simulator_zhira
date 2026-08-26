from . import (admin, achievements, auction, card, casino, collection, config, containers,
               daily, duel, exchange, fatshop, farm, market, misc, pay, profile, quests,
               ref, roulette, sellall, shop, start, trade, upgrade, upgradeshop, workshop,
               workshoplist)
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
        config,
        fatshop,
        quests,
        achievements,
        containers,
        workshoplist,
        farm,
        auction,
        exchange,
        roulette,
        duel,
        misc,
    ):
        root.include_router(mod.router)
    return root
