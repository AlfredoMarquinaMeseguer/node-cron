import asyncio
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from classes.dao import Offer, Source, Petition
from offer_scraper.scrapers.utils import common


async def scrap(petition: Petition):
    # '/home/alfredo/Downloads/geckodriver-v0.33.0-linux64'
    driver: webdriver.Firefox = common.headless_webdriver()

    driver.get('https://developer.infojobs.net/test-console/execute.xhtml')
    driver.implicitly_wait(1)

    textfield_xpath = '//*[@id="apiuri"]'
    text_field = driver.find_element(by=By.XPATH, value=textfield_xpath)

    button_xpath = '//*[@id="send-button"]'
    button = driver.find_element(by=By.XPATH, value=button_xpath)

    # json_xpath='//*[@id="formattedBody"]'
    # json = driver.find_element(by=By.XPATH, value=json_xpath)

    query = "https://api.infojobs.net/api/7/offer?p=" + petition.query.replace(" ", "+") + ""

    text_field.send_keys(query)
    button.click()

    await asyncio.sleep(4)

    request_xpath = '//*[@id="formattedBody"]'
    request = driver.find_element(by=By.XPATH, value=request_xpath)
    items = json.loads(request.text.replace("\n", ""))['items']
    driver.close()
    [Offer.from_scrapped(item, Source.INFO_JOBS, petition.mongo_id).save() for item in items]

    # answer: [dict] = [Offer.from_infojobs(item).to_mongo() for item in items]
    # return answer


def sync_scrap(petition: Petition) -> [Offer]:
    return asyncio.run(scrap(petition))
