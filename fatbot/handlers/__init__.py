from . import (admin, achievements, auction, card, casino, collection, config, containers,
               daily, duel, exchange, fatshop, farm, level, market, misc, pay, prestige, profile, quests,
               ref, roulette, season, sellall, shop, start, story, trade, upgrade, upgradeshop, workshop,
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
        story,
        level,
        season,
        achievements,
        containers,
        workshoplist,
        farm,
        auction,
        exchange,
        roulette,
        duel,
        prestige,
        misc,
    ):
        root.include_router(mod.router)
    return root
