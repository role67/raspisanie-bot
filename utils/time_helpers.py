import datetime
import pytz
from core.config import TIMEZONE

# Расписание звонков (время начала и конца в минутах от полуночи)
# Формат: [(start, end, is_split), ...]. is_split - флаг для разделенных пар
BELLS_SCHEDULE = {
    "monday": [ # Понедельник
        (620, 725, True),  # 1 пара 10:20 - 12:05 (с перерывом внутри)
        (750, 855, True),  # 2 пара 12:30 - 14:15 (с перерывом внутри)
        (870, 960, False), # 3 пара 14:30 - 16:00
    ],
    "tue-fri": [ # Вторник - Пятница
        (510, 600, False), # 1 пара 8:30 - 10:00
        (620, 725, True),  # 2 пара 10:20 - 12:05 (с перерывом внутри)
        (750, 855, True),  # 3 пара 12:30 - 14:15 (с перерывом внутри)
        (870, 960, False), # 4 пара 14:30 - 16:00
    ],
    "saturday": [ # Суббота
        (510, 600, False), # 1 пара 8:30 - 10:00
        (620, 710, False), # 2 пара 10:20 - 11:50
        (730, 820, False), # 3 пара 12:10 - 13:40
    ]
}

# Текстовое представление звонков
BELLS_TEXT = """
🔔 **Расписание звонков**

**Понедельник:**
Классные часы: 8:30 - 10:00
1 пара: 10:20 - 12:05
2 пара: 12:30 - 14:15
3 пара: 14:30 - 16:00

**Вторник - Пятница:**
1 пара: 8:30 - 10:00
2 пара: 10:20 - 12:05
3 пара: 12:30 - 14:15
4 пара: 14:30 - 16:00

**Суббота:**
1 пара: 8:30 - 10:00
2 пара: 10:20 - 11:50
3 пара: 12:10 - 13:40
"""

def get_current_moscow_time():
    """Возвращает текущее время по Москве."""
    return datetime.datetime.now(pytz.timezone(TIMEZONE))

def get_current_week_type():
    """Определяет тип недели (четная/нечетная)."""
    now = get_current_moscow_time()
    iso_week = now.isocalendar()[1]
    return "четная" if iso_week % 2 == 0 else "нечетная"

def get_time_status():
    """Возвращает статус текущего времени относительно пар."""
    now = get_current_moscow_time()
    weekday = now.weekday()
    time_in_minutes = now.hour * 60 + now.minute

    schedule = []
    if weekday == 0: # Понедельник
        schedule = BELLS_SCHEDULE["monday"]
    elif 1 <= weekday <= 4: # Вторник - Пятница
        schedule = BELLS_SCHEDULE["tue-fri"]
    elif weekday == 5: # Суббота
        schedule = BELLS_SCHEDULE["saturday"]
    
    if not schedule:
        return "🎉 Сегодня выходной!"

    # Обработка классных часов в понедельник
    if weekday == 0:
        if 510 <= time_in_minutes < 600: # 8:30 - 10:00
            return f"ℹ️ Идет классный час\n⌛️ До конца: {600 - time_in_minutes} мин."
        if time_in_minutes < 510:
             return f"ℹ️ Пары еще не начались\n⌛️ До начала классного часа: {510 - time_in_minutes} мин."

    for i, (start, end, is_split) in enumerate(schedule):
        pair_number = i + 1
        
        # Если идет пара
        if start <= time_in_minutes < end:
            # Обработка внутреннего перерыва в разделенных парах
            if is_split:
                first_half_end = start + 45
                second_half_start = end - 45
                if first_half_end <= time_in_minutes < second_half_start:
                    return f"ℹ️ Перерыв внутри {pair_number}-й пары\n⌛️ До второй половины: {second_half_start - time_in_minutes} мин."

            return f"ℹ️ Идет {pair_number}-я пара\n⌛️ До конца: {end - time_in_minutes} мин."
        
        # Если перемена между парами
        if i > 0:
            prev_end = schedule[i-1][1]
            if prev_end <= time_in_minutes < start:
                return f"ℹ️ Перемена после {i}-й пары\n⌛️ До начала {pair_number}-й пары: {start - time_in_minutes} мин."

    # Если до начала первой пары
    first_pair_start = schedule[0][0]
    if time_in_minutes < first_pair_start:
        return f"ℹ️ Пары еще не начались\n⌛️ До начала 1-й пары: {first_pair_start - time_in_minutes} мин."

    # Если все пары закончились
    return "🎉 УРА, ПАРЫ ЗАКОНЧИЛИСЬ! 🥳👍"
