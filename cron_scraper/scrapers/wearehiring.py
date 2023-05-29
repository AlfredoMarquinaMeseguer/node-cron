"""
Scrap from the page WeAreHiring.

"""
import asyncio
import logging
import httpx as httpx
import selenium.webdriver.firefox.webdriver
from bs4 import BeautifulSoup
import lxml
from lxml import html
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.remote.webelement import WebElement
import classes.offer_consts as job
from classes.dao import Offer, Source, Petition
from offer_scraper.scrapers.utils.common import headless_webdriver, salary_to_int
from offer_scraper.scrapers.utils.wait import limit

ROOT_PAGE = "https://www.wearehiring.io"
SEARCH = "https://www.wearehiring.io/ofertas-empleo-digital?search_for={}"
# ****************** HTML TAGS ******************
A = "a"
P = "p"
SRC = "src"
IMG = "img"
FIGURE = "figure"
DIV = "div"
SPAN = "span"
HREF = "href"
# ****************** SCRAP CONSTANTS ******************
XPATH_NUM_OFFERS = '/html/body/div[1]/section[2]/div/div[1]/div[1]/span/b'
ATTRS_OFFERS = {'id': 'pagination-list', 'class': 'boxes-wrapper'}

# ****************** SCRAP PAGE CONSTANTS ******************
XPATH_CITY = '/html/body/div/section[1]/div/div[4]/div[2]/div[1]/div[1]/p[2]/span[2]'
XPATH_COMPANY = "/html/body/div/section[1]/div/div[4]/div[2]/div[1]/div[1]/p[2]/span[1]"
XPATH_TITLE = "/html/body/div/section[1]/div/div[4]/div[2]/div[1]/div[1]/p[1]/strong"

ATTRS_CATEGORY = {'class': "job-tag category-tag bg-white mr2"}
ATTRS_EXPERIENCE = {'class': "job-tag level-tag bg-white mr2"}
ATTRS_BIG_BOX = {'class': "column is-7 has-text-right-desktop"}
ATTRS_CONTENT = {'class': "content"}
ATTRS_LOGO = {"class": 'image rounded-image size-120'}
ATTRS_DESCRIPTION = {'class': 'job-description'}

NO_SALARY = "A consultar"
SEP_SALARY = "-"
LXML_PARSER = "lxml"

SALARY_PERIOD_ALWAYS = 'Bruto/año'
# ****************** SCRIPTS ******************
SCROLL_SCRIPT = "window.scrollBy(0, arguments[0]);"
NOT_AT_THE_BOTTOM_SCRIPT = "return window.pageYOffset + arguments[0] < arguments[1]"
SCROLL_HEIGHT_SCRIPT = "return document.body.scrollHeight"
WINDOW_HEIGHT_SCRIPT = "return window.innerHeight"


async def scrap_page(url: str, petition: Petition) -> None:
    limit()
    page: str = httpx.get(url).text

    soup: BeautifulSoup = BeautifulSoup(page, "lxml")
    doc: lxml.html = html.fromstring(page)

    # Obtain the
    def xpath_text(xpath: str) -> str:
        return doc.xpath(xpath)[0].text.strip()

    job_dict: dict[str, any] = {
        job.TITLE: xpath_text(XPATH_TITLE),
        job.COMPANY: xpath_text(XPATH_COMPANY),
        job.CITY: xpath_text(XPATH_CITY),
        job.CATEGORY: soup.find(SPAN, attrs=ATTRS_CATEGORY).get_text().strip(),
        job.EXPERIENCE: soup.find(SPAN, attrs=ATTRS_EXPERIENCE).get_text().strip()
    }

    content = soup.find(DIV, attrs=ATTRS_BIG_BOX).find(DIV, attrs=ATTRS_CONTENT)
    workday_info = [x.get_text().strip() for x in content.find_all(SPAN)]
    if len(workday_info) == 3:
        job_dict[job.SUBCATEGORY] = workday_info[1]
        job_dict[job.WORKDAY] = workday_info[2]
    else:
        salary = content.find_next(P).get_text().strip()
        if salary != NO_SALARY:
            job_dict[job.SALARY_PERIOD] = SALARY_PERIOD_ALWAYS
            aux = salary.split(SEP_SALARY)
            job_dict[job.SALARY_MIN] = salary_to_int(aux[0])
            if len(aux) == 2:
                job_dict[job.SALARY_MAX] = salary_to_int(aux[1])
        job_dict[job.SUBCATEGORY] = workday_info[0]
        job_dict[job.WORKDAY] = workday_info[1]
    job_dict[job.DESCRIPTION] = soup.find(DIV, attrs=ATTRS_DESCRIPTION).get_text()

    job_dict[job.LINK_LOGO] = ROOT_PAGE + soup.find(FIGURE, attrs=ATTRS_LOGO).find(
        IMG).get(SRC)

    job_dict[job.LINK_JOB] = url
    job_dict[job.ID] = url.split(SEP_SALARY)[-1]

    logging.info(f"Offer from We are hiring {job_dict[job.ID]} scraped url: {job_dict[job.LINK_JOB]}")
    Offer.from_scrapped(job_dict, Source.WE_HIRING, petition.mongo_id).save()


async def scrap(petition: Petition):
    driver: webdriver.firefox.webdriver.WebDriver = headless_webdriver()
    driver.get(SEARCH.format(petition.query))

    # get the height of the viewport
    viewport_height = driver.execute_script(WINDOW_HEIGHT_SCRIPT)

    # get the height of the entire page
    page_height = driver.execute_script(SCROLL_HEIGHT_SCRIPT)
    num_offers: WebElement = driver.find_element(By.XPATH,
                                                 XPATH_NUM_OFFERS)

    # Scroll down the page to load all the offers
    for _ in range(int(num_offers.text.split()[0]) // 10):
        # get the height of the entire page
        while driver.execute_script(NOT_AT_THE_BOTTOM_SCRIPT, viewport_height,
                                    page_height):
            driver.execute_script(SCROLL_SCRIPT, page_height)
        time.sleep(5)

        page_height = driver.execute_script(SCROLL_HEIGHT_SCRIPT)

    page_source = driver.page_source
    driver.quit()

    soup = BeautifulSoup(page_source, LXML_PARSER)

    tasks = [asyncio.create_task(scrap_page(ROOT_PAGE + offer.get(HREF, None), petition))
             for offer in soup.find(DIV, attrs=ATTRS_OFFERS)(A)]
    return await asyncio.gather(*tasks)
