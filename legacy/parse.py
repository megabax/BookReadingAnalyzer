from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options  # Import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import numpy as np

from lib import load_table_item, load_table_column


def parse_chapter_reads_selenium(driver, url):
    """
    Парсит страницу author.today с использованием Selenium для извлечения информации о прочтениях книги по главам.

    Args:
        url (str): URL страницы со статистикой книги.

    Returns:
        dict: Словарь, где ключи - названия глав, а значения - количество прочтений.
              Возвращает None в случае ошибки.
    """

    dates=[]
    chapters=[]

    try:
        # Find the table
        grid = driver.find_element(By.ID, "grid")
        load_table_item(grid, dates, "div.k-grid-header-wrap.k-auto-scrollable","th")

        load_table_column(grid, chapters, "div.k-grid-content-locked", "td")

        table = np.zeros((len(chapters),len(dates)))
        Xpath='//*[@id="grid"]/div[3]/table'
        #table_items = grid.find_elements(By.CSS_SELECTOR, "div.k-grid-content k-auto-scrollable")
        table_items = grid.find_elements(By.XPATH, Xpath)
        if table_items:
            #table_items = elements.find_elements(By.TAG_NAME, "table")
            tr_items = table_items[0].find_elements(By.TAG_NAME, "tr")
            row=0
            for tr_item in tr_items:
                col=0
                td_items = tr_item.find_elements(By.TAG_NAME, "td")
                for td_item in td_items:
                    if td_item.text.strip()=='':
                        table[row,col]=0
                    else:
                        table[row,col]=int(td_item.text)
                    col+=1
                row+=1

    except Exception as e:
        print(f"Ошибка при работе с Selenium: {e}")
        return None
    finally:
        try:
            driver.quit()  # Ensure the browser is closed in all cases
        except:
            pass # If driver wasn't initialized, ignore the exception


    return dates, chapters, table


chrome_options = Options()
#chrome_options.add_argument("--headless")  # Run Chrome in headless mode (no GUI)
chrome_options.add_argument("--no-sandbox")  # Required for running in some environments (e.g., Docker)
chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
# Set a user-agent to mimic a real browser
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
driver = webdriver.Chrome(options=chrome_options)

url = "https://author.today/report/work/stats?startDate=2025-07-01T20%3A00%3A00.000Z&endDate=2025-07-31T19%3A59%3A59.000Z&workId=323389&valueType=hit"

driver.get(url)

# Wait for the table to load (adjust timeout as needed)
try:
    print("Просто введите что-нибудь, когда будете готовы")
    a = input("Ввод:")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "grid"))  # id="grid"
    )
except TimeoutException:
    print("Превышено время ожидания загрузки страницы.")
    exit(1)

chapter_reads = parse_chapter_reads_selenium(driver, url)

if chapter_reads:
    for chapter, reads in chapter_reads.items():
        print(f"Глава: {chapter}, Прочтений: {reads}")
else:
    print("Не удалось получить данные о прочтениях.")
