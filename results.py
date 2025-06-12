import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from config_reader import config
from datetime import datetime
from sqlalchemy import DateTime, Integer, Text, ForeignKey
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session
from sqlalchemy.orm import mapped_column, relationship
from typing import List, Optional


# Адрес БД
sqlite_database = config.database_address.get_secret_value()
# Cоздаем движок SqlAlchemy
engine = create_engine(sqlite_database, echo=False)


class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = 'users'

    tg_id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[int]] = mapped_column(Text)
    store: Mapped[Optional[int]] = mapped_column(Text)

    reports: Mapped[List['Reports']] = relationship('Reports', back_populates='users')


class Reports(Base):
    __tablename__ = 'reports'

    reports_id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True)
    sales: Mapped[Optional[int]] = mapped_column(Integer)
    remainings: Mapped[Optional[int]] = mapped_column(Integer)
    user: Mapped[Optional[int]] = mapped_column(ForeignKey('users.tg_id'))
    username: Mapped[Optional[int]] = mapped_column(Integer)
    store: Mapped[Optional[str]] = mapped_column(Text)
    date: Mapped[Optional[str]] = mapped_column(DateTime)

    users: Mapped[Optional['Users']] = relationship('Users', back_populates='reports')


# Cоздаем таблицы
Base.metadata.create_all(bind=engine)

#
# Диапазон времени на основании текущего и трех значений
#
class TimeRange:


    def __init__(self, start, end, range):

        self.start = start
        self.end = end
        self.range = range
    
    def calculate_range(date):

        year    = date.year
        month   = date.month
        day     = date.day
        hour    = date.hour
        range   = ""

        if hour < 12:

            start   = datetime(year, month, day, 0, 0, 0)
            end     = datetime(year, month, day, 11, 59, 59, 999999) 
            range   = "1. С 00:00 до 12:00"

        elif hour < 18:

            start   = datetime(year, month, day, 12, 0, 0)
            end     = datetime(year, month, day, 17, 59, 59, 999999) 
            range   =  "2. С 12:00 до 18:00"

        else:
            
            start   = datetime(year, month, day, 18, 0, 0)
            end     = datetime(year, month, day, 23, 59, 59, 999999) 
            range   = "3. С 18:00 до 00:00"
        
        return TimeRange(start, end, range)


def reports_in_range(db, current_date = None):

    if current_date is None:
        # Текущее время
        now = datetime.now()

    else:
        
        now = current_date

    time_range = TimeRange.calculate_range(now)

    # Запрос на записи за определенный промежуток времени 
    query = select(Reports).where(Reports.date.between(time_range.start, time_range.end))

    # Выполнение запроса
    reports = db.execute(query).scalars().all()

    # Сумма по продажам
    sales_sum = 0

    # Сумма по остаткам
    remainings_sum = 0

    reports_str = ""        

    # Вывод результатов
    for report in reports:
        report_store         = str(report.store)
        report_date          = str(report.date.strftime("%d.%m.%Y %H:%M"))
        report_sales         = str(report.sales)
        report_remainings    = str(report.remainings)  
        reports_str +=   "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"              
        reports_str += (f"Магазин: {report_store}\n")
        reports_str += (f"Дата: {report_date}\n")
        reports_str += (f"Продажи: {report_sales}, Остатки: {report_remainings}\n")
        sales_sum       += report.sales
        remainings_sum  += report.remainings        


    reports_str     +=   "─────────────────────────────\n"              
    if current_date is not None:
        reports_str +=   "  <b>Дата: " + str(current_date) + "</b>\n"
    reports_str     +=   "  <b>Временной диапазон №"    + str(time_range.range) + "</b>\n"
    reports_str     +=  "─────────────────────────────\n" 
    reports_str     +=  "  <b>Итого продаж:     "       + str(sales_sum)        + "</b>\n"
    reports_str     +=  "  <b>Итого остатков:  "        + str(remainings_sum)   + "</b>\n"
    reports_str     +=  "─────────────────────────────"

    return reports_str


def validate_date_time(input_str):
    try:
        datetime.strptime(input_str, "%d.%m.%Y %H:%M")
        return True
    except ValueError:
        return False

# Telegram id администратора
admin_id = config.admin_id.get_secret_value()

# # Включаем логирование
logging.basicConfig(level=logging.INFO)

# Создаем объект бота
bot = Bot(token=config.results_bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Создаем диспетчер бота
dp = Dispatcher()

# 
# Создаём клавиатуры
#
 
# Клавиатура в главном меню
def main_keyboard():
    buttons = [
        [types.KeyboardButton(text="Суммы сейчас")],
        [types.KeyboardButton(text="Другая дата")]       
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard 

# Клавиатура "вернуться назад"
def go_back_keyboard():
    buttons = [[types.KeyboardButton(text="⏪ Вернуться назад")]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

# Создаем машину состояний
class Form(StatesGroup):
    time_change = State()  
    main_menu   = State()
    default = State()


@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext) -> None:    
    await message.answer("Добро пожаловать, "  
                            + message.from_user.username 
                            + "!\n", 
                            reply_markup=main_keyboard()
                            )
    await state.set_state(Form.default)
    

@dp.message(F.text == 'Суммы сейчас')
async def set_balance(message: types.Message, state: FSMContext) -> None:    
    await state.update_data(summary = message.text)  
    with Session(autoflush=False, bind=engine) as db: 
        await message.answer(reports_in_range(db), reply_markup=go_back_keyboard())


@dp.message(F.text == 'Другая дата')
async def set_balance(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Form.time_change)    
    await message.answer("Укажите дату в формате: день.месяц.год час:минута", 
                         reply_markup=go_back_keyboard()
                         )
    

@dp.message(F.text == "⏪ Вернуться назад")
async def reply_message(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Form.default)
    await message.answer(" Возвращаемся назад . . .",
                         reply_markup=main_keyboard()
                         )


@dp.message(Form.time_change)
async def time_change(message: Message, state: FSMContext) -> None:

    
    if validate_date_time(message.text):
        current_date = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        print(current_date.year)
        with Session(autoflush=False, bind=engine) as db: 
            await message.answer(reports_in_range(db, current_date = current_date), reply_markup=go_back_keyboard())
    else:
        await message.answer("Введите корректную дату в формате: день.месяц.год час:минута (01.01.2025 13:37)!", 
                             reply_markup=go_back_keyboard()
                             ) 

# Обрабатываем состояние "По умолчанию"
@dp.message(Form.default)
async def main_menu(message: Message, state: FSMContext) -> None:
    pass  


# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)


# Стартуем!
if __name__ == "__main__":
    asyncio.run(main())