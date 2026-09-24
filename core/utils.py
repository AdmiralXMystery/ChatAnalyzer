import re
from datetime import datetime
from bs4 import BeautifulSoup

MONTHS = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'мая': 5, 'июн': 6,
    'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
}

def clean_folder_name(name: str) -> str:
    if not name: return "Без названия"
    name = re.sub(r'[\\/*?:"<>|]', " ", name)
    name = re.sub(r"[^\w\s\d\(\)\-\._]", " ", name)
    return re.sub(r"\s+", " ", name).strip() or "Без названия"


def parse_date(date_str):
    if not date_str:
        return None
    try:
        parts = date_str.split()
        day = int(parts[0])
        month = MONTHS[parts[1]]
        year = int(parts[2])
        time_parts = parts[4].split(':')
        return datetime(year, month, day, int(time_parts[0]), int(time_parts[1]), int(time_parts[2]))
    except:
        return None




def parse_message(msg_div):
    result = {
        'id': msg_div.get('data-id'),
        'sender': '',
        'date': None,
        'text': '',
        'attachments': [],
    }

    header = msg_div.find('div', class_='message__header')
    if header:
        name_link = header.find('a')
        if name_link:
            result['sender'] = name_link.text.strip()
            date_str = header.text.split(',', 1)[1].strip() if ',' in header.text else ''
        else:
            result['sender'] = header.text.split(',')[0].strip() if ',' in header.text else header.text
            date_str = header.text.split(',', 1)[1].strip() if ',' in header.text else ''
        result['date'] = parse_date(date_str)

    # Текст
    text_div = header.find_next_sibling('div') if header else None
    if text_div:
        text_clone = BeautifulSoup(str(text_div), 'html.parser')
        for kludge in text_clone.find_all('div', class_='kludges'):
            kludge.decompose()
        result['text'] = text_clone.get_text(strip=True)

    for attach in msg_div.find_all('div', class_='attachment'):
        attachment = {}
        desc = attach.find('div', class_='attachment__description')
        if desc:
            attachment['description'] = desc.get_text(strip=True)
        link = attach.find('a', class_='attachment__link')
        if link:
            attachment['url'] = link.get('href')
        if attachment:
            result['attachments'].append(attachment)


    return result