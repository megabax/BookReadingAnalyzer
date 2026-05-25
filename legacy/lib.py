from selenium.webdriver.common.by import By

def load_table_item(grid, list, selector_name, item_name):
    elements = grid.find_elements(By.CSS_SELECTOR, selector_name)
    if elements:
        table_items = elements[0].find_elements(By.TAG_NAME, "table")
        tr_items = table_items[0].find_elements(By.TAG_NAME, "tr")
        td_items = tr_items[0].find_elements(By.TAG_NAME, item_name)
        for td_item in td_items:
            list.append(td_item.text)
    else:
        print(f"Элемент {selector_name} не найден по CSS_SELECTOR.")

def load_table_column(grid, list, selector_name, item_name):
    elements = grid.find_elements(By.CSS_SELECTOR, selector_name)
    if elements:
        table_items = elements[0].find_elements(By.TAG_NAME, "table")
        tr_items = table_items[0].find_elements(By.TAG_NAME, "tr")
        for tr_item in tr_items:
            td_items = tr_item.find_elements(By.TAG_NAME, item_name)
            for td_item in td_items:
                list.append(td_item.text)
    else:
        print(f"Элемент {selector_name} не найден по CSS_SELECTOR.")