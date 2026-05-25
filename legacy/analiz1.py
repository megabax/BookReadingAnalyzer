import pandas as pd

try:
    df = pd.read_csv("reclan.csv", encoding="utf-8")
    print("Файл успешно прочитан с кодировкой UTF-8")
except UnicodeDecodeError:
    print("UTF-8 не подходит. Пробуем CP1251...")
    try:
        df = pd.read_csv("reclan.csv", encoding="cp1251")
        print("Файл успешно прочитан с кодировкой CP1251")
    except UnicodeDecodeError:
        print("CP1251 тоже не подходит. Пробуем Latin1...")
        try:
            df = pd.read_csv("reclan.csv", encoding="latin1")
            print("Файл успешно прочитан с кодировкой Latin1")
        except UnicodeDecodeError:
            print("Не удалось прочитать файл с известными кодировками. Возможно, нужна другая кодировка.")
            # Если вы знаете, какая именно кодировка используется, замените "latin1" на нее.
            # Например, pd.read_csv("reclan.csv", encoding="koi8-r")
except FileNotFoundError:
    print("Ошибка: Файл 'reclan.csv' не найден. Убедитесь, что он находится в той же директории, что и скрипт, или укажите полный путь.")

if 'df' in locals(): # Проверяем, был ли DataFrame успешно создан
    print("\nПервые 5 строк DataFrame:")
    print(df.head())
