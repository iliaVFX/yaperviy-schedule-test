"""Build a static GitHub Pages site and the iOS broadcast feed."""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
MONTHS = 'января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split()
WEEKDAYS = 'понедельник вторник среда четверг пятница суббота воскресенье'.split()
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def read_week(path):
    years = set(re.findall(r'(?<!\d)20\d{2}(?!\d)', path.stem))
    if len(years) != 1:
        raise ValueError('Укажите год выпуска в имени файла.')
    year = int(years.pop())
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo('word/document.xml')
        if info.file_size > 12_000_000:
            raise ValueError('Слишком большой документ.')
        document = ET.fromstring(archive.read(info))
    days = []
    previous = None
    for row in document.findall('.//w:tbl/w:tr', NS):
        cells = [' '.join(' '.join(''.join(p.itertext()) for p in c.findall('w:p', NS)).split())
                 for c in row.findall('w:tc', NS)]
        if not any(cells):
            continue
        if len(cells) == 1:
            match = re.fullmatch(r'(\d{1,2})\s+(\w+),?\s+(\w+)', cells[0].lower())
            if not match or match[2] not in MONTHS:
                raise ValueError(f'Не удалось прочитать дату: {cells[0]}')
            month = MONTHS.index(match[2]) + 1
            if previous and previous.month == 12 and month == 1:
                year += 1
            day = dt.date(year, month, int(match[1]))
            if (previous and day != previous + dt.timedelta(days=1)) or WEEKDAYS[day.weekday()] != match[3]:
                raise ValueError(f'Проверьте дату и день недели: {cells[0]}')
            previous = day
            days.append({'date': day.isoformat(), 'programmes': []})
            continue
        if not days or len(cells) != 4 or not cells[1]:
            raise ValueError(f'Не удалось прочитать строку: {cells}')
        time, title, details, age = cells
        if time and not re.fullmatch(r'(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?', time):
            raise ValueError(f'Проверьте время передачи «{title}»: {time}')
        days[-1]['programmes'].append(dict(time=time or None, title=title, details=details, ageRating=age))
    if len(days) != 7 or previous.weekday() != 6 or any(not 1 <= len(d['programmes']) <= 300 for d in days):
        raise ValueError('Ожидается программа с понедельника по воскресенье.')
    return days


def build(output, repo='', branch='main'):
    days = {d['date']: d for d in json.loads((ROOT/'seed.json').read_text())['days']}
    imported = set()
    for path in sorted((ROOT/'inbox').glob('*')):
        if path.suffix.lower() != '.docx':
            continue
        week = read_week(path)
        if week[0]['date'] in imported:
            raise ValueError(f'Две версии недели {week[0]["date"]} в inbox. Оставьте одну.')
        imported.add(week[0]['date'])
        days.update((d['date'], d) for d in week)
    ordered = sorted(days)
    today = (dt.datetime.now(dt.timezone(dt.timedelta(hours=3))) - dt.timedelta(hours=6)).date()
    monday = today - dt.timedelta(days=today.weekday())
    relevant = [key for key in ordered if key >= monday.isoformat()]
    feed = {'days': [days[key] for key in (relevant[:28] or ordered[-7:])]}
    output.mkdir(parents=True, exist_ok=True)
    (output/'schedule.json').write_text(json.dumps(feed, ensure_ascii=False))
    template = (ROOT/'index.html').read_text()
    upload = 'https://github.com/' + repo + '/upload/' + branch + '/inbox' if repo else ''
    link = f'<a class="button" href="{html.escape(upload, quote=True)}">Загрузить Word-файл ↗</a>' if repo else '<p>После подключения GitHub здесь появится кнопка загрузки.</p>'
    (output/'index.html').write_text(template.replace('<!--UPLOAD-->', link))
    shutil.copy(ROOT/'app.js', output)
    shutil.copy(ROOT/'style.css', output)


if __name__ == '__main__':
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/'dist',
          os.getenv('GITHUB_REPOSITORY', ''), os.getenv('GITHUB_REF_NAME', 'main'))
