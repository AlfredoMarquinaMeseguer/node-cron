"""
Common functions shared by function.
Some were in a bigger utils file and were refactored.
"""
import re

from selenium import webdriver
from selenium.webdriver.firefox.webdriver import WebDriver, Options


# *************  Convert salary string to int ************* #
def salary_to_int(salary: str) -> int:
    return int(re.sub('[.€$, ]', '', salary)) if len(salary) else None


def round_up(num: float) -> int:
    """Rounds up a real number into an integer
    :param num: real number
    :return:
    """
    return int(num // 1 + ((num % 1) ** 0))


def headless_webdriver() -> WebDriver:
    """
    This
    :return:
    """
    options = Options()
    options.add_argument('--headless')
    return webdriver.Firefox(options=options)
