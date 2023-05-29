import crontab
from crontab import CronTab


def scraper_cron_job():
    cron = CronTab(user="root")
    # job = cron.new(command='/usr/bin/python3 /app/master_of_scrapers.py')
    job = cron.new(command='/usr/bin/python3 /app/imprime.py')

    job.minute.every(1)

    cron.write()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    scraper_cron_job()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
