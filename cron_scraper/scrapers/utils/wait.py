"""
Waiting functions for the scraper.

:author: Alfredo Marquina Meseguer
"""
import asyncio
from random import randint, random


def loading(min_w: int = 5, max_w: int = 7) -> None:
    """
    Wait a random amount for the page to load.
    Time waited between `max_w` and `min_w` - 7 and 5 by default - seconds. Some pages detect bots if they wait
    the same amount of seconds between inputs, so the time has to be different every time.
    :param min_w: Maximum amount of time waited.
    :param max_w: Minimum amount of time waited.
    """
    asyncio.run(asyncio.sleep(randint(min_w, max_w)))


def limit(min_w: int | float = 0.5, max_w: int | float = 1.5) -> None:
    """
    Wait to limit the amount of inputs made.
    Wait between `max_w` and `min_w` - 1.5 and 0.5 by default - seconds. Some pages detect bots if they wait
    the same amount of seconds between inputs, so the time has to be different every time.
    :param min_w: Minimum amount of time waited.
    :param max_w: Maximum amount of time waited.
    """
    asyncio.run(asyncio.sleep(random() / (max_w - min_w + 1) + min_w))
