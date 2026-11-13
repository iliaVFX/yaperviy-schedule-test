const select = document.querySelector('#day');
const statusText = document.querySelector('#status');
const list = document.querySelector('ol');
async function start() {
  const response = await fetch('schedule.json', { cache: 'no-cache' });
  if (!response.ok) throw new Error();
  const { days } = await response.json();
  const format = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });
  for (const day of days) select.add(new Option(format.format(new Date(day.date)), day.date));
  // Moscow is UTC+3; the broadcast day changes at 06:00 local.
  const today = new Date(Date.now() - 3 * 3600000).toISOString().slice(0, 10);
  select.value = days.find(day => day.date >= today)?.date ?? days[days.length - 1].date;
  function render() {
    const day = days.find(item => item.date === select.value);
    list.replaceChildren();
    for (const slot of day.programmes) {
      const row = document.createElement('li');
      for (const text of [slot.time || 'Уточняется', slot.title, slot.ageRating]) {
        const cell = document.createElement('span');
        cell.textContent = text;
        row.append(cell);
      }
      list.append(row);
    }
    statusText.textContent = 'Передач в программе: ' + day.programmes.length;
  }
  select.onchange = render;
  render();
}
start().catch(() => { statusText.textContent = 'Не удалось открыть расписание. Обновите страницу.'; });
