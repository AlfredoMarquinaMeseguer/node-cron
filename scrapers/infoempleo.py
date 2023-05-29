"""
Scraps from InfoEmpleo.com and obtains a Offer convertible dictionary.

I know the spaghetti is obvious but have no time.
Now I regretti making another scraper.

:Author: Alfredo Marquina Meseguer
"""

import asyncio
import datetime
import logging

import httpx as httpx
import lxml
import selenium.webdriver.firefox.webdriver
from bs4 import BeautifulSoup
from lxml import etree
from selenium import webdriver
from selenium.webdriver.common.by import By
from classes import offer_consts
from classes.dao import Petition, Offer, Source
from offer_scraper.scrapers.utils import common, wait

ROOT_URL = "https://www.infoempleo.com"
MAIN_URL = ROOT_URL + "/trabajo/"

# TODO: eventually replace this
TITLE_K = 'title'
COMPANY_K = 'company'
CITY_K = 'city'
PROVINCE_K = 'province'
ID_K = 'id'
LINK_JOB_K = 'link_job'
LINK_LOGO_K = 'link_logo'
DESCRIPTION_K = 'description'
POST_DATE_K = 'post_date'
ADD_DATE_K = 'add_date'

HACE_NORMAL_LEN = 3


async def scrap(petition: Petition) -> [dict[str, any]]:
    # driver: webdriver.firefox.webdriver.WebDriver = webdriver.Firefox()
    driver: webdriver.firefox.webdriver.WebDriver = common.headless_webdriver()
    driver.get(MAIN_URL)

    # Get rid of pop-ups
    wait.loading()
    driver.find_element(By.CSS_SELECTOR, "#onetrust-pc-btn-handler").click()  # Personalize cookies
    wait.limit()
    driver.find_element(By.CSS_SELECTOR, ".save-preference-btn-handler").click()  # Only accept necesary
    wait.limit()
    driver.find_element(By.CSS_SELECTOR, "span.close:nth-child(1)").click()  # Get rid of other pop-up

    driver.find_element(By.ID, "search").send_keys(petition.query)
    if petition.location is not None:
        driver.find_element(By.ID, "region").send_keys(petition.location)

    driver.find_element(By.CSS_SELECTOR, ".btn-line > span").click()

    # Get rid of new pop-up
    wait.loading()
    driver.find_element(By.CSS_SELECTOR, "span.close:nth-child(1)").click()

    soup = BeautifulSoup(driver.page_source, "html.parser")
    tags = soup.find_all("li", attrs={"class": "offerblock"})
    results = [asyncio.create_task(scrap_page(absolute_url(tag("a")[0].get("href", None)), petition)) for tag in tags]
    try:
        next_arrow = driver.find_element(By.CSS_SELECTOR, ".next > button:nth-child(1)")
    except Exception:
        # Si salta error es porque no existe, que es porque hay menos de 20 ofertas disponibles
        next_arrow = None

    while next_arrow:
        next_arrow.click()
        soup = BeautifulSoup(driver.page_source, "lxml")
        tags = soup.find_all("li", attrs={"class": "offerblock"})
        results.extend(  # Create list of jobs of scrap page to wait in the end. They don't return data.
            [asyncio.create_task(scrap_page(ROOT_URL + tag("a")[0].get("href", None), petition)) for tag in tags])
        if not soup.find("li", attrs={"class": "next disabled"}):
            next_arrow = driver.find_element(By.CSS_SELECTOR, ".next > button:nth-child(1)")
        else:
            next_arrow = False
    # print(driver.page_source)
    # results = []
    # for tag in tags:
    #     # print(tag("a")[0].get("href", None))
    #     results.append(scrap_page(MAIN_URL + tag("a")[0].get("href", None)))
    # V2 is 1.0694151828816918 x faster

    driver.quit()
    return await asyncio.gather(*results)


async def scrap_page(url: str, petition: Petition) -> None:
    # 0:02:34.392560
    # driver: webdriver.firefox.webdriver.WebDriver = webdriver.Firefox()
    #
    # # driver: webdriver.firefox.webdriver.WebDriver = headless_webdriver()
    # driver.get(url)
    # soup = BeautifulSoup(driver.page_source, "html.parser")
    # driver.quit()

    # 0: 00:03.770957
    # TODO: limit petitions I don't know how in async
    try:
        wait.limit()
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    dom: lxml.etree.Element = etree.HTML(str(soup))
    # print(r.text)
    # try:
    #     # Get rid of pop-ups
    #     time.sleep(2)  # Wait for pop-ups to load
    #     driver.find_element(By.CSS_SELECTOR, "#onetrust-pc-btn-handler").click()  # Personalize cookies
    #     time.sleep(1)  # Wait for cookies page to load
    #     driver.find_element(By.CSS_SELECTOR, ".save-preference-btn-handler").click()  # Only accept necesary
    #
    #     driver.find_element(By.CSS_SELECTOR, "span.close:nth-child(1)").click()  # Get rid of other pop-up
    #     pass
    # except Exception as e:
    #     pass
    # finally:
    #     soup = BeautifulSoup(driver.page_source, "html.parser")
    #     driver.quit()

    # if type(prueba) == list:
    #     algo = prueba[0].text
    # else:
    #     algo = prueba.text
    # province = province_and_time[0].strip().replace("\xa0", "")
    # time_ = province_and_time[1].split()
    # print()
    company = soup.find("li", attrs={"class": "companyname"})
    dictionary = {TITLE_K: soup.find("h1", attrs={"class": "h1 regular"}).get_text(),
                  COMPANY_K: company.get_text(),
                  ID_K: soup.find("li", attrs={"class": "ref"}).get_text().removeprefix("Ref: "),
                  'link_job': url
                  }
    link_company = company.find("a").attrs.get("href")
    dictionary['link_company'] = absolute_url(link_company)  # TODO: preguntar si

    logo = soup.find("li", attrs={"style": "margin-right:1rem"})
    if logo is not None:
        link_logo = logo("img")[0].get("src")
        dictionary['link_logo'] = absolute_url(link_logo)

    location = soup.find("li", attrs={"class": "block"}).get_text()
    if (sep := location.find("(")) != -1:
        dictionary['city'] = location[:sep].strip()
        dictionary['province'] = location[sep + 1: location.rfind(")")]
    else:
        dictionary['province'] = location.strip()
    # offer_data: [str] = []
    # # company_link = offer_data.find_all("ul")
    # for ul in soup.find("div", attrs={"class": "offer-excerpt"}).find_all("ul"):
    #     for li in ul.find_all("li"): <li style="margin-right:1rem"><a href="/colaboradoras/adecco/presentacion/"><img src="https://cdnazure.infoempleo.com/infoempleo.empresas/images/logos/LOGO ADECCO.gif" alt="Adecco" width="115" height="54"></a></li><li class="companyname"><a href="/colaboradoras/adecco/presentacion/">Adecco</a></li><li class="ref">Ref: 2940055</li>
    #         offer_data.append(li.find("p").get_text())

    offer_data: [str] = [li.find("p").get_text() for ul in
                         soup.find("div", attrs={"class": "offer-excerpt"}).find_all("ul") for li in ul.find_all("li")]
    # El primero es la experiencia

    dictionary['experience_min'] = dom.xpath('/html/body/div[1]/div[4]/div/section/div[5]/div/div/ul/li[1]')[0].text
    # El segundo es el salario
    # El único que he encontrado: Entre 10.000 y 15.000€ Brutos/anuales
    try:
        salario = dom.xpath('/html/body/div[1]/div[4]/div/section/div[1]/ul[1]/li[2]/p')[0].text
        if salario != "Retribución sin especificar":
            # foo = salario.split()  # TODO: cambiar nombre variable company_link algo util
            dictionary[offer_consts.SALARY_MIN] = common.salary_to_int(salario)
            dictionary[offer_consts.SALARY_MAX] = common.salary_to_int(salario)
            dictionary[offer_consts.SALARY_PERIOD] = salario

    except Exception as e:
        logging.error(f"Algo petó obteniendo el salario de Infoempleo. Mensaje: {e}")
    # El tercero es Área-Puesto se mapea company_link category
    area_puesto: [str] = offer_data[2].split("-")
    dictionary[offer_consts.CATEGORY] = area_puesto[0]

    position = area_puesto[1].find("'")
    dictionary[offer_consts.SUBCATEGORY]: str = \
        area_puesto[1][:position if position != -1 else len(area_puesto[1])].split("Categoría")[0].strip()

    # El cuarto es Categoría o nivel

    hace: [str] = soup.find("li", attrs={"class": "mt10"}).get_text().split()

    if len(hace) >= HACE_NORMAL_LEN:
        match hace[2]:
            case "horas" | "hora":
                subtract_time = datetime.timedelta(hours=int(hace[1]))
            case "días":
                subtract_time = datetime.timedelta(days=int(hace[1]))
            case _:
                subtract_time = datetime.timedelta(minutes=0)
    else:
        subtract_time = datetime.timedelta(minutes=0)

    dictionary['post_date'] = (datetime.datetime.now() - subtract_time).date()
    dictionary['add_date'] = datetime.date.today()

    description = soup.find("div", attrs={"class": "offer"})
    dictionary[DESCRIPTION_K] = description.get_text().replace("Descripción de la oferta", "")

    dictionary['requirement_min'] = description.find_all("pre")[1].get_text()

    # return dictionary
    # TODO: cambiar para recibir petición de api clases como Parametro

    Offer.from_scrapped(dictionary, Source.INFO_EMPLEO, petition.mongo_id).save()
    # return Job.from_scrapped(dictionary, Source.INFO_EMPLEO, petition.mongo_id).to_mongo()
    # return dictionary


# TODO: put in utilities
def absolute_url(url):
    """Return the absolute url of the infoempleo page.

    :param url:
    :return:
    """
    if url[:4] == "http":
        return url
    else:
        return ROOT_URL + url


if __name__ == "__main__":
    # # Previous profiling to see what solution is faster
    # time_v1 = timeit.timeit(v1, number=1000)
    # time_v2 = timeit.timeit(v2, number=1000)
    # print("Time of version 1:", time_v1)
    # print("Time of version 2:", time_v2)
    #
    # if time_v1 > time_v2:
    #     print("V2 is", time_v1 / time_v2, "x faster")
    # else:
    #     print("V1 is", time_v2 / time_v1, "x faster")
    #
    # # V2 is 1.0694201828816918 x faster

    # Test para scrap page
    lista_jobs = ['https://www.infoempleo.com/ofertasdetrabajo/formadora-de-java/madrid/2913816/',
                  'https://www.infoempleo.com/ofertasdetrabajo/programadora-java/alcobendas/2941256/',
                  'https://www.infoempleo.com/ofertasdetrabajo/full-stack-java/madrid/2944178/',
                  'https://www.infoempleo.com/ofertasdetrabajo/analista-programador-java/madrid/2900314/',
                  'https://www.infoempleo.com/ofertasdetrabajo/desarrollador-backend-java/alcobendas/2944120/',
                  'https://www.infoempleo.com/ofertasdetrabajo/big-data-analyst/san-sebastian-de-los-reyes/2945990/',
                  'https://www.infoempleo.com/ofertasdetrabajo/web-project-manager-information-technology/madrid/2818' +
                  '725/',
                  'https://www.infoempleo.com/ofertasdetrabajo/desarrolladora-fullstack-madrid/madrid/2946974/',
                  'https://www.infoempleo.com/ofertasdetrabajo/it-analyst/madrid/2924412/',
                  'https://www.infoempleo.com/ofertasdetrabajo/integradora-de-soluciones-tecnologicas/madrid/2945043/',
                  'https://www.infoempleo.com/ofertasdetrabajo/desarrolladora-web-hibrido-03408372/madrid/2940055/']
    start = datetime.datetime.now()
    # results = asyncio.run(test_speed_page())
    # print(len(results))
    # print(results)
    # for j in results:
    #     for i in j:
    #         if i is not None:
    #             print(json.dumps(i, indent=4))
    #
    # print(datetime.datetime.now() - start)
    data = {
        "user": "johndoe",
        "creation_datetime": datetime.datetime.now(),
        "query": "Python",
        "location": "Madrid",
        "disabled": False
    }
    for i in asyncio.run(scrap(Petition(**data))):
        print(i)
        # resultados = asyncio.run(scrap("", ""))
    # for i in lista_jobs:
    #     a = asyncio.run(scrap_page(i))
    #     print(a.get('post_date'), a.get('add_date'))
