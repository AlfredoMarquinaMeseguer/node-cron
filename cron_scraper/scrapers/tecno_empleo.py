import asyncio
import datetime
from typing import Any
import bs4
import httpx as httpx
from bs4 import BeautifulSoup
from classes.dao import Petition, Offer, Source
from classes import offer_consts
from offer_scraper.scrapers.utils.common import round_up, salary_to_int
from offer_scraper.scrapers.utils.wait import limit

URL = "https://www.tecnoempleo.com/ofertas-trabajo/?te={}&pagina={}"
OFFERS_PER_PAGE = 30
ANNOYING_LABELS = ["actualizada", "nueva"]

DIV = "div"
NUMBER_OFFERS_ATTRS = {
    "class": [
        "text-center bg-gray-800 pt-3 pb-2 my-3",
        "text-center bg-gray-200 pt-3 pb-2 my-3"
    ]
}
OFFERS_ATTRS = {
    "class": [
        "p-2 border-bottom py-3 bg-white",
        "p-2 border-bottom py-3 bg-warning-soft",
    ]
}
OFFER_URL_ATTR = "onclick"


async def scrap(petition: Petition) -> list[dict[str, Any]]:
    """
    Scraps tecnoEmpleo.com and saves the results in the mongo database
    :param petition: Request for scraping being followed
    :return:
    """
    offers = []
    source = httpx.get(URL.format(petition.query.replace(" ", "+"), str(1))).text
    soup = BeautifulSoup(source, "html.parser")
    results = int(
        soup.find(DIV, attrs=NUMBER_OFFERS_ATTRS)
        .get_text()
        .split()[0]
        .replace(".", "")
    )

    for page_num in range(round_up(results / OFFERS_PER_PAGE)):
        # Coger todas las urls de ofertas en la página

        page_offers: bs4.ResultSet = soup.find_all(
            DIV,
            attrs=OFFERS_ATTRS,
        )

        for x in page_offers:
            offer_url = x.get(OFFER_URL_ATTR).split("=")[1].replace("'", "").strip()
            task = asyncio.create_task(scrap_page(offer_url, petition.mongo_id))
            offers.append(task)

        limit()
        source = httpx.get(
            URL.format(petition.query.replace(" ", "+"), str(page_num + 2))
        ).text
        soup = BeautifulSoup(source, "html.parser")
    return await asyncio.gather(*offers)


async def scrap_page(url: str, petition_id) -> None:
    await asyncio.sleep(0.5)
    page = httpx.get(url).text
    soup = BeautifulSoup(page, "lxml")

    return_dictionary = {offer_consts.LINK_JOB: url}

    offer_header = soup.find("div", attrs={"class": "col-12 col-md-12 col-lg-8"})

    return_dictionary[offer_consts.TITLE] = offer_header.find("h1", attrs={"itemprop": "title"}).get_text().strip()

    return_dictionary[offer_consts.LINK_LOGO] = (
        soup.find("div", attrs={"class": "col-12 col-md-12 col-lg-4"})
        .find_next("a")
        .get("href")
    )
    empresa = offer_header.find_next("a")
    return_dictionary[offer_consts.COMPANY] = empresa.get_text().strip()
    return_dictionary[offer_consts.LINK_COMPANY] = empresa.get("href")

    post_date_string = offer_header.find("span", attrs={"class": "ml-4"}).get_text().strip()
    post_date = post_date_string.lower()

    for p in ANNOYING_LABELS:
        post_date = post_date.replace(p, "")

    return_dictionary[offer_consts.POST_DATE] = datetime.datetime.strptime(post_date, "%d/%m/%Y").date()

    main_info = soup.find("div", attrs={"class": "col-12 col-md-5 col-lg-4 mb-5"})
    lista = main_info.find("ul", attrs={"class": "list-unstyled mb-0 fs--15"})
    elementos = lista.find_all("span", attrs={"class": "float-end"})

    ubicacion: str = elementos[0].get_text()
    if ubicacion.lower().find("remoto") == -1:
        ubi_info = ubicacion.split("-")
        if len(ubi_info) == 1:
            return_dictionary[offer_consts.PROVINCE] = ubi_info[0].strip().removesuffix(' (Híbrido)')
        else:
            return_dictionary[offer_consts.CITY] = ubi_info[0].strip()
            if ubi_info[1].lower().find("españa") == -1:
                return_dictionary[offer_consts.PROVINCE] = ubi_info[1].strip()
        del ubi_info

    return_dictionary[offer_consts.WORKDAY] = elementos[2].get_text().strip()
    return_dictionary[offer_consts.EXPERIENCE] = elementos[3].get_text().strip()
    return_dictionary[offer_consts.CONTRACT_TYPE] = elementos[4].get_text().strip()

    if len(elementos) == 7:  # Si el
        obtain_salary(elementos, return_dictionary)

    return_dictionary[offer_consts.DESCRIPTION] = soup.find("div", attrs={"itemprop": "description"}).get_text().strip()
    return_dictionary[offer_consts.ID] = return_dictionary.get(offer_consts.LINK_JOB).split("/")[-1]

    return Offer.from_scrapped(return_dictionary, Source.TECNO_EMPLEO, petition_id).save()


def obtain_salary(elementos, return_dictionary):
    salario = elementos[5].get_text().split("€")
    if len(salario) == 0:  # Por si te sale en dolares en vez de euros
        salario = elementos[5].get_text().split("$")
    if salario[0] == "Indefinido":
        return_dictionary[offer_consts.SALARY_MIN] = salary_to_int(salario[0].strip())
        if len(salario) == 3:
            return_dictionary[offer_consts.SALARY_MAX] = salary_to_int(salario[1].strip().replace("-", ""))
            return_dictionary[offer_consts.SALARY_PERIOD] = salario[2].strip()
        else:
            return_dictionary[offer_consts.SALARY_PERIOD] = salario[1].strip()
    del salario


if __name__ == "__main__":
    a = asyncio.run(scrap(Petition(query="backend", creation_datetime=datetime.datetime.now())))
    print(len(a))

    print("*" * 20)
    for i in a:
        print(i)
    # print(scrap_page(
    #     "https://www.tecnoempleo.com/analista-ciberseguridad-cloud-iot-remoto/ciberseguridad-azure-aws/rf-92f2192522c2734f2b41"
    # ))
