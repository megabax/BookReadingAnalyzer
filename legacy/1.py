import requests
from bs4 import BeautifulSoup

def parse_chapter_reads(url):
    """
    Парсит страницу author.today для извлечения информации о прочтениях книги по главам.

    Args:
        url (str): URL страницы со статистикой книги.

    Returns:
        dict: Словарь, где ключи - названия глав, а значения - количество прочтений.
              Возвращает None в случае ошибки.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Поднимает HTTPError для плохих запросов (4XX, 5XX)
        print(response.content)

        soup = BeautifulSoup(response.content, 'html.parser')

        # Находим таблицу с данными о прочтениях
        table = soup.find('table', class_='table')

        if not table:
            print("Таблица с данными не найдена.")
            return None

        # Извлекаем строки таблицы (исключая заголовок)
        rows = table.find_all('tr')[1:]

        chapter_reads = {}
        for row in rows:
            # Извлекаем ячейки строки
            cells = row.find_all('td')

            if len(cells) >= 2:  # Убеждаемся, что есть хотя бы название главы и количество прочтений
                chapter_name = cells[0].text.strip()
                reads = int(cells[1].text.strip())  # Преобразуем в целое число

                chapter_reads[chapter_name] = reads

        return chapter_reads

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к странице: {e}")
        return None
    except Exception as e:
        print(f"Ошибка при парсинге страницы: {e}")
        return None


# Пример использования
url = "https://author.today/report/work/stats?startDate=2025-07-01T20%3A00%3A00.000Z&endDate=2025-07-31T19%3A59%3A59.000Z&workId=323389&valueType=hit"
chapter_reads = parse_chapter_reads(url)

if chapter_reads:
    for chapter, reads in chapter_reads.items():
        print(f"Глава: {chapter}, Прочтений: {reads}")
else:
    print("Не удалось получить данные о прочтениях.")
