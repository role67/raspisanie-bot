from datetime import datetime, time

# Расписание для понедельника
MONDAY_SCHEDULE = {
    "классный час 1": {"start": "08:30", "end": "09:15", "name": "Классный час - разговоры о важном / Россия - мои горизонты"},
    "классный час 2": {"start": "09:15", "end": "10:00", "name": "Общий классный час в группе"},
    "1 пара 1": {"start": "10:20", "end": "11:05", "name": "1 пара (первая часть)"},
    "1 пара 2": {"start": "11:20", "end": "12:05", "name": "1 пара (вторая часть)"},
    "2 пара 1": {"start": "12:30", "end": "13:15", "name": "2 пара (первая часть)"},
    "2 пара 2": {"start": "13:30", "end": "14:15", "name": "2 пара (вторая часть)"},
    "3 пара": {"start": "14:30", "end": "16:00", "name": "3 пара"}
}

# Расписание со вторника по пятницу
WEEKDAY_SCHEDULE = {
    "1 пара": {"start": "08:30", "end": "10:00", "name": "1 пара"},
    "2 пара 1": {"start": "10:20", "end": "11:05", "name": "2 пара (первая часть)"},
    "2 пара 2": {"start": "11:20", "end": "12:05", "name": "2 пара (вторая часть)"},
    "3 пара 1": {"start": "12:30", "end": "13:15", "name": "3 пара (первая часть)"},
    "3 пара 2": {"start": "13:30", "end": "14:15", "name": "3 пара (вторая часть)"},
    "4 пара": {"start": "14:30", "end": "16:00", "name": "4 пара"}
}

# Расписание для субботы
SATURDAY_SCHEDULE = {
    "1 пара": {"start": "08:30", "end": "10:00", "name": "1 пара"},
    "2 пара": {"start": "10:20", "end": "11:50", "name": "2 пара"},
    "3 пара": {"start": "12:10", "end": "13:40", "name": "3 пара"}
}

def get_current_lesson_info():
    """Возвращает информацию о текущей паре и времени до следующей"""
    now = datetime.now()
    current_time = now.time()
    weekday = now.weekday()  # 0 = понедельник, 6 = воскресенье

    # Выбираем расписание в зависимости от дня недели
    if weekday == 0:  # Понедельник
        schedule = MONDAY_SCHEDULE
    elif weekday == 5:  # Суббота
        schedule = SATURDAY_SCHEDULE
    elif weekday < 5:  # Вторник-пятница
        schedule = WEEKDAY_SCHEDULE
    else:  # Воскресенье
        return "🎉 Сегодня выходной! Занятия начнутся завтра в 08:30"

    # Проверяем текущую пару
    for lesson, times in schedule.items():
        start_time = datetime.strptime(times['start'], "%H:%M").time()
        end_time = datetime.strptime(times['end'], "%H:%M").time()
        
        if start_time <= current_time <= end_time:
            minutes_left = (datetime.combine(now.date(), end_time) - 
                          datetime.combine(now.date(), current_time)).seconds // 60
            return (f"📚 Сейчас идет: {times['name']}\n"
                   f"⏰ Начало: {times['start']}\n"
                   f"🔄 Конец: {times['end']}\n"
                   f"⌛️ До конца пары: {minutes_left} мин.")

    # Ищем следующую пару
    next_lesson = None
    for lesson, times in schedule.items():
        start_time = datetime.strptime(times['start'], "%H:%M").time()
        if current_time < start_time:
            next_lesson = (times, start_time)
            break

    if next_lesson:
        times, start_time = next_lesson
        minutes_until = (datetime.combine(now.date(), start_time) - 
                        datetime.combine(now.date(), current_time)).seconds // 60
        return (f"💤 Сейчас перерыв\n"
               f"📚 Следующая пара: {times['name']}\n"
               f"⏰ Начало через: {minutes_until} мин. ({times['start']})")

    return "✅ Занятия на сегодня закончились!"

def get_schedule_string(day_of_week=None):
    """Возвращает расписание звонков для указанного дня недели"""
    if day_of_week == 0:  # Понедельник
        return ("📅 Понедельник:\n\n"
                "I курс:\n"
                "8:30 - 9:15 классный час - разговоры о важном\n"
                "9:15 - 10:00 общий классный час в группе\n\n"
                "II-III-IV курсы:\n"
                "8:30 - 9:15 классный час - Россия - мои горизонты\n"
                "9:15 - 10:00 общий классный час в группе\n\n"
                "1 пара:\n10:20 - 11:05\n11:20 - 12:05\n"
                "2 пара:\n12:30 - 13:15\n13:30 - 14:15\n"
                "3 пара: 14:30 - 16:00")
    elif day_of_week == 5:  # Суббота
        return ("📅 Суббота:\n\n"
                "1 пара: 8:30 - 10:00\n"
                "2 пара: 10:20 - 11:50\n"
                "3 пара: 12:10 - 13:40")
    elif day_of_week is None or 1 <= day_of_week <= 4:  # Вторник-пятница
        return ("📅 Вторник-Пятница:\n\n"
                "1 пара: 8:30 - 10:00\n"
                "2 пара:\n10:20 - 11:05\n11:20 - 12:05\n"
                "3 пара:\n12:30 - 13:15\n13:30 - 14:15\n"
                "4 пара: 14:30 - 16:00")