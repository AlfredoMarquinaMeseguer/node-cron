import asyncio
import datetime
import time
import bs4
import httpx
import requests
from bs4 import BeautifulSoup
import logging
import classes.offer_consts as offer
from classes.dao import Source, Offer, Petition
from offer_scraper.scrapers.utils import wait

TOO_MANY_RETRIES = "Talent page scrap: Too many retries"

COUNTRIES = ("España", "Spain")
PARSER = "html.parser"

# HTML Tag Names
CLASS = "class"
DIV = "div"
IMG = "img"
SECTION = "section"
# **** Attributes searched in talent ****
# From the search page
NUMBER_PAGE_SELECTED = "page-number page-selected"
CURRENT_PAGE_NUMBER_ATTR = {"name": "span", 'attrs': {CLASS: NUMBER_PAGE_SELECTED}}
JOB_ATTR = "card card__job"
JOB_TITLE_ATTR = "card__job-title card__job-link gojob"
COMPANY_NAME_ATTR = "card__job-empname-label"
JOB_LOCATION_ATTR = "card__job-location"
ID_ATTR = "data-id"
# From the specific job page
LINK_LOGO_ATTR = "job__header__logo"
IMAGE_SRC_URL = "src"
JOB_DESCRIPTION_ATTR = "job__description"
DAYS_POSTED_ATTR = "card__jobDatePosted"


# Scrapeo completo de talent.com
def scrap_job(job: bs4.element.Tag) -> dict:
    """ Receives the Tag objects of a job offer and returns a dictionary of its important information.

    :param job: the tag where the information of the offer is stored
    :return: information of the job offer as a dictionary
    """
    dictionary: dict = {
        offer.TITLE: job.find("h2", attrs={CLASS: JOB_TITLE_ATTR}).get_text(),
        offer.COMPANY: job.find(DIV, attrs={CLASS: COMPANY_NAME_ATTR}).get_text()}

    location = job.find(DIV, attrs={CLASS: JOB_LOCATION_ATTR}).get_text().split(", ")
    if len(location) > 1 and location[0] not in COUNTRIES:
        dictionary[offer.CITY] = location[0]
        dictionary[offer.PROVINCE] = location[1]

    # Tengo varias soluciones
    # En una línea con regex
    # job_id = re.findall(r"(?<=\')[a-z0-9]+(?=\')", onclick.attrs.get('onclick'))[0]

    # En varias líneas con métodos de clase str
    # id_no_formateada = onclick.attrs.get(ON_CLICK)
    # inicio = id_no_formateada.find(COMILLA) + 1
    # final = id_no_formateada.rfind(COMILLA)
    # dictionary[ID_DICT] = id_no_formateada[inicio:final]

    # Como todos los ids parecen tener la misma longitud se puede hacer.
    # Lo malo es que es la más frágil a los cambios de las página web
    # dictionary[ID_K] = onclick.attrs.get(ONCLICK)[28:40]  # TODO: weird

    dictionary[offer.ID] = job.attrs.get(ID_ATTR)
    dictionary[offer.LINK_JOB] = "https://es.talent.com/view?id=" + dictionary.get(offer.ID)

    # Obtener info del trabajo
    wait_response = 10
    job_page = httpx.get(dictionary.get(offer.LINK_JOB))

    job_page_soup = BeautifulSoup(job_page.content, PARSER)

    # Conseguir el link de la imagen
    link_logo_tag = job_page_soup.find(DIV, attrs={CLASS: LINK_LOGO_ATTR})
    description_tag = job_page_soup.find(DIV, attrs={CLASS: JOB_DESCRIPTION_ATTR})
    days_posted_tag = job_page_soup.find(DIV, attrs={CLASS: DAYS_POSTED_ATTR})

    # If is null is maybe because the page hasn't loaded yet
    while wait_response < 25 and None in (link_logo_tag, description_tag, days_posted_tag):
        wait_response += 1
        wait.limit()
        job_page = httpx.get(dictionary.get(offer.LINK_JOB))

        job_page_soup = BeautifulSoup(job_page.content, PARSER)
        link_logo_tag = job_page_soup.find(DIV, attrs={CLASS: LINK_LOGO_ATTR})
        description_tag = job_page_soup.find(DIV, attrs={CLASS: JOB_DESCRIPTION_ATTR})
        days_posted_tag = job_page_soup.find(DIV, attrs={CLASS: DAYS_POSTED_ATTR})

    # if wait_response == 25:
    #     print("Too many retries of link_logo")  # TODO: cambiar a logging
    # else:
    if link_logo_tag:
        dictionary[offer.LINK_LOGO] = link_logo_tag.find(IMG).attrs.get(IMAGE_SRC_URL)

    if description_tag:
        dictionary[offer.DESCRIPTION]: str = description_tag.get_text().strip()

    if days_posted_tag:
        days_posted_sep = days_posted_tag.getText().split()

        if days_posted_sep[1] == "más":
            days_to_subtract = 30
        elif days_posted_sep[1] == "menos" or days_posted_sep[2] == "horas":
            days_to_subtract = 0
        else:
            days_to_subtract = int(days_posted_sep[1])

        dictionary[offer.POST_DATE] = (datetime.date.today() - datetime.timedelta(days=days_to_subtract))

    dictionary[offer.UPDATE_DATE] = datetime.date.today()

    return dictionary
    # print(dictionary)


def scrap_page(soup: bs4.BeautifulSoup = None, url: str = None) -> list[dict] | None:
    """Obtains all the job offers of a whole page of talent.com job search thingy as a dictionary.
    The function takes either the BeautifulSoup object or takes the url of the page and makes it a BeautifulSoup object.
    If url is not None soup is ignored.

    :param soup: beautiful soup object of the scrapped page. Defaults to None
    :param url: link to the scrapped page if not None soup value is ignored. Defaults to None
    :return: list of job offers in the page each as a dictionary
    """
    if url:
        page = requests.get(url)
        time.sleep(5)  # Wait for page to load
        soup = BeautifulSoup(page.content, PARSER)  # The Spanish Inquisition
    elif not soup:
        print("No Soup")
        return None

    page_jobs: list[dict] = []
    number_of_retries = 0  # tracks the number of retries to limit them

    results: bs4.ResultSet = soup.find_all(SECTION, attrs={CLASS: JOB_ATTR})

    for job in results:
        try:
            page_jobs.append(scrap_job(job))
        except AttributeError as e:
            logging.error("Exception: {}".format(e))
        results.append(job)  # It goes back to the pile to be processed again
        number_of_retries += 1
        if number_of_retries > 25:
            logging.error(TOO_MANY_RETRIES)
            break

    return page_jobs


def scrap_talent(query: str = "", query_location: str = "Spain", radius: str = 100) -> list[dict]:
    """Makes a query to the talent.com job post website and returns a list of the offers found, in dictionary form.
    Each dictionary can be converted a Job object by using the Job.from_talent class method.

    :param query: Query used to search the job offers. Defaults to ""
    :param query_location: Location to be searched. Defaults to "Spain"
    :param radius: Maximus distance to the location. Defaults to 100
    :return: List of all the job offers found
    """
    url = "https://es.talent.com/jobs?k=" + query + "&l=" + query_location + "&radius=" + str(radius)

    # NOTE: The idea for the loop is the following:
    # Is a bit strange but if it where just one it would be the following:
    #
    # obtain_condition_data()
    # if condition: scrape()
    #
    # If it is a loop it takes the following shape
    #
    # obtain condition data
    # while condition
    #   scrape
    #   obtain next cicle condition data

    lista_de_jobs: list[dict] = []
    page_number = 1  # Force both vars to be equal so that they enter the while loop

    page = requests.get(url + "&p=" + str(page_number))
    time.sleep(5)  # Wait for page to load
    soup = BeautifulSoup(page.content, PARSER)  # The Spanish Inquisition
    current_page_number = int(soup.find("span", attrs={CLASS: NUMBER_PAGE_SELECTED}).get_text())

    while page_number == current_page_number:
        lista_de_jobs.extend(scrap_page(soup))

        page = requests.get(url + "&p=" + str(page_number))
        time.sleep(5)  # Wait for the page to load
        soup = BeautifulSoup(page.content, PARSER)
        current_page_number = int(soup.find("span", attrs={CLASS: NUMBER_PAGE_SELECTED}).get_text())
        page_number += 1
        # Scrap _ page
    return lista_de_jobs


SEARCH = "https://es.talent.com/jobs?k={}&l={}&radius={}"


async def scrap(petition: Petition, radius: str = 100) -> list[dict]:
    """Makes a query to the talent.com job post website and returns a list of the offers found, in dictionary form.
        Each dictionary can be converted a Job object by using the Job.from_talent class method.

        :param petition: Petition to scrap for.
        :param radius: Maximus distance to the location. Defaults to 100.
        :return: List of all the job offers found.
    """
    url = SEARCH.format(petition.query, petition if petition.location is not None else "Spain", str(radius))
    tasks = []
    page_number = current_page_number = 1
    soup = None

    try:
        current_page_number, soup = await get_search_page(page_number, url)
        scraped = True
    except Exception:
        scraped = False

    # Should have been a do while loop
    while page_number == current_page_number:
        if scraped:  # TODO: Dudas
            # tasks.append(asyncio.create_task(async_scraping_page(soup)))
            tasks.extend(await async_scraping_page(soup, petition))
            page_number += 1
            wait.loading()

            try:  # TODO: pensar en algo que lo haga mejor
                current_page_number, soup = await get_search_page(page_number, url)
                scraped = True
            except Exception:
                scraped = False
                # print("no cargado")

            current_page_number = int(soup.find(**CURRENT_PAGE_NUMBER_ATTR).get_text())
            await asyncio.sleep(1)  # Limit to not collapse the server
        else:

            try:
                current_page_number, soup = await get_search_page(page_number, url)
                scraped = True
            except Exception:
                scraped = False

    return tasks


async def get_search_page(page_number, url):
    new_url = url + "&p=" + str(page_number)
    page = await get_http(new_url)
    soup = BeautifulSoup(page.text, PARSER)  # The Spanish Inquisition
    current_page_number = int(soup.find(**CURRENT_PAGE_NUMBER_ATTR).get_text())
    return current_page_number, soup


async def get_http(new_url):
    async with httpx.AsyncClient() as client:
        page: httpx.Response = await client.get(new_url, timeout=10)
    return page


async def async_scraping_page(soup: bs4.BeautifulSoup, petition: Petition) -> list[dict]:
    jobs_set: bs4.ResultSet = soup.find_all("section", attrs={CLASS: "card card__job"})
    num_sub_lists = 3

    # calculate the length of each sublist
    sublist_length = len(jobs_set) // num_sub_lists + (0 if len(jobs_set) % num_sub_lists == 0 else 1)

    # create the smaller sub_lists
    sub_lists = [jobs_set[i:i + sublist_length] for i in range(0, len(jobs_set), sublist_length)]

    tasks = []
    for i in sub_lists:
        task = asyncio.create_task(async_scrap_jobs(i, petition))
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    end = []
    for i in results:
        end.extend(i)

    return end

    # Con compresión de listas, Tras la prueba esto parece incluso más lento
    # return [item for sublist in results for item in sublist]

    # Resultado de las pruebas con números:
    # Time using list comprehension: 1.142787099999623
    # Time using extend() with for loop: 0.16656979999970645


async def async_scrap_jobs(job_list: list[bs4.element.Tag], petition: Petition) -> None:
    number_of_retries = 0
    for job in job_list:
        try:
            dictionary: dict = {
                offer.TITLE: job.find("h2", attrs={CLASS: JOB_TITLE_ATTR}).get_text(),
                offer.COMPANY: job.find(DIV, attrs={CLASS: COMPANY_NAME_ATTR}).get_text()}

            location = job.find(DIV, attrs={CLASS: JOB_LOCATION_ATTR}).get_text().split(", ")
            if len(location) > 1 and location[0] not in ("España", "Spain"):
                dictionary[offer.CITY] = location[0]
                dictionary[offer.PROVINCE] = location[1]

            # onclick: bs4.element.Tag = job.find(DIV_ATTR, attrs={CLASS_ATTR: "link-printable-wrap"})
            #
            # if not onclick:
            #     onclick: bs4.element.Tag = job.find(DIV_ATTR, attrs={CLASS_ATTR: "link-job-wrap"})
            # # Tengo varias soluciones
            # # En una línea con regex
            # # job_id = re.findall(r"(?<=\')[a-z0-9]+(?=\')", onclick.attrs.get('onclick'))[0]
            #
            # En varias líneas con métodos de clase str
            # id_no_formateada = onclick.attrs.get('onclick')
            # inicio = id_no_formateada.find("'")+1
            # final = id_no_formateada.rfind("'")
            # dictionary[ID_DICT] = id_no_formateada[inicio:final]

            # Como todos los ids parecen tener la misma longitud se puede hacer.
            # Lo malo es que es la más frágil a los cambios de las páginas web
            # dictionary[ID_DICT] = onclick.attrs.get('onclick')[28:40]

            dictionary[offer.ID] = job.attrs.get(ID_ATTR)
            dictionary[offer.LINK_JOB] = "https://es.talent.com/view?id=" + dictionary.get(offer.ID)

            # Obtener info del trabajo
            wait.limit()
            job_page = await get_http(dictionary.get(offer.LINK_JOB))
            wait.limit()
            job_page_soup = BeautifulSoup(job_page.content, PARSER)

            # # If is null is maybe because the page hasn't loaded yet
            # while wait_response < 25 and None in (link_logo_tag, description_tag, days_posted_tag):
            #     wait_response += 1
            #     job_page = requests.get(dictionary.get(LINK_JOB_K))
            #     await asyncio.sleep(wait_response)
            #     # time.sleep(wait_response)  # Wait for the page to load
            #
            #     job_page_soup = BeautifulSoup(job_page.content, PARSER)
            #     link_logo_tag = job_page_soup.find(DIV, attrs={CLASS: LINK_LOGO_ATTR})
            #     description_tag = job_page_soup.find(DIV, attrs={CLASS: JOB_DESCRIPTION_ATTR})
            #     days_posted_tag = job_page_soup.find(DIV, attrs={CLASS: DAYS_POSTED_ATTR})

            # Conseguir el link de la imagen
            # link_logo_tag = job_page_soup.find(DIV, attrs={CLASS: LINK_LOGO_ATTR})
            # description_tag = job_page_soup.find(DIV, attrs={CLASS: JOB_DESCRIPTION_ATTR})
            # days_posted_tag = job_page_soup.find(DIV, attrs={CLASS: DAYS_POSTED_ATTR})

            # if wait_response == 25:
            #     print("Too many retries of link_logo")  # TODO: cambiar a logging
            # else:
            # if link_logo_tag:
            dictionary[offer.LINK_LOGO] = job_page_soup.find(DIV, attrs={CLASS: LINK_LOGO_ATTR}).find(IMG).attrs.get(
                IMAGE_SRC_URL)

            dictionary[offer.DESCRIPTION]: str = job_page_soup.find(
                DIV,
                attrs={CLASS: JOB_DESCRIPTION_ATTR}
            ).get_text().strip()

            days_posted_sep = job_page_soup.find(DIV, attrs={CLASS: DAYS_POSTED_ATTR}).getText().split()

            # Spaghetti Time
            if days_posted_sep[1] == "más":  # Check if senetence is "Hace más de x dias"
                days_to_subtract = 30
            elif days_posted_sep[1] == "menos" or days_posted_sep[2] == "horas":
                # Check if sentence structure is: "Hace menos de 1 hora" or "Hace x horas"
                days_to_subtract = 0
            else:
                # The remaining possible structure is: "Hace x días"
                days_to_subtract = int(days_posted_sep[1])

            dictionary[offer.POST_DATE] = (datetime.date.today() - datetime.timedelta(days=days_to_subtract))

            logging.info(f"Job scrapped from talent.com {dictionary[offer.LINK_JOB]}")
            Offer.from_scrapped(dictionary, Source.TALENT, petition.mongo_id).save()
        except AttributeError:
            # Caused because the page hasn't loaded yet, the website server is down or the internet connection
            # doesn't work
            job_list.append(job)
            number_of_retries += 1
            if number_of_retries > 25:
                logging.error(TOO_MANY_RETRIES)
                break
