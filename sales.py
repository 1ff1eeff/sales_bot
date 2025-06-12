import asyncio
import logging


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
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session
from sqlalchemy.orm import mapped_column, relationship
from typing import List, Optional


#
# Модель БД
#

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


# Адрес БД
sqlite_database = config.database_address.get_secret_value()
# Cоздаем движок 
engine = create_engine(sqlite_database, echo=False)
# Cоздаем таблицы
Base.metadata.create_all(bind=engine)


# Добавляем пользователя в БД если отуствует
def add_user(db, tg_id, name):

    # Проверяем наличие записи пользователя в БД
    query = db.query(Users).filter(Users.tg_id==tg_id).first()

    # Создаем объект пользователя
    user = Users(tg_id=tg_id, name=name) 

    if query is None:   
        # Добавляем пользователя в БД
        db.add(user)
        db.commit()
        db.refresh(user) 
        #print(f"Пользователь [{user.tg_id}] - {user.name} ({user.store}) добавлен в БД!") 

    else: 
        user = db.query(Users).filter(Users.tg_id==tg_id).first()
        #print(f"Пользователь [{user.tg_id}] - {user.name} ({user.store}) найден в БД!") 
    
    return user


# 
# Создаём клавиатуры
#
 
# Клавиатура в главном меню
def main_keyboard():
    buttons = [
        [types.KeyboardButton(text="Ввести остатки и продажи")],
        [types.KeyboardButton(text="Передать данные")]       
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
    sales = State()
    remainings = State()    
    default = State()

# Telegram id администратора
admin_id = config.admin_id.get_secret_value()

# Текущие продажи
current_sales = 0
# Текущие остатки
current_remainings = 0


# # Включаем логирование
logging.basicConfig(level=logging.INFO)

# Создаем объект бота
bot = Bot(token=config.sales_bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Создаем диспетчер бота
dp = Dispatcher()


# Обрабатываем команду "/start"
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext) -> None:

    # Устанавливаем состояние по умолчанию
    await state.set_state(Form.default)

    # Cоздаем сессию подключения к бд
    with Session(autoflush=False, bind=engine) as db:  

        # Получаем id пользователя в telegram 
        user_tg_id = message.from_user.id   

        # Получаем имя пользователя в telegram 
        user_tg_name = message.from_user.username 

        # Добавляем пользователя в БД если отуствует       
        user = add_user(db, 
                        tg_id = user_tg_id, 
                        name = user_tg_name
                        )

        await message.answer("Добро пожаловать, "  
                            + user.name 
                            + "!\n", 
                            reply_markup=main_keyboard()
                            )


# Обрабатываем сообщение "Ввести остатки и продажи"
@dp.message(F.text == 'Ввести остатки и продажи')
async def set_balance(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Form.remainings)
    await message.answer("Укажите текущие остатки:", 
                         reply_markup=go_back_keyboard()
                         )


# Обрабатываем сообщение "Продажи"
@dp.message(F.text == 'Продажи')
async def set_balance(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Form.sales)
    await message.answer("Укажите текущие продажи:", 
                         reply_markup=go_back_keyboard()
                         )


@dp.message(F.text == 'Передать данные')
async def send_data(message: types.Message):

    #data = "Остатки:\t" + str(current_remainings) + "\nПродажи:\t" + str(current_sales)
    #await bot.send_message(admin_id, data)


    with Session(autoflush=False, bind=engine) as db:

        # Получаем id пользователя в telegram 
        user_tg_id = message.from_user.id   
         
        # Получаем имя пользователя в telegram 
        user_tg_name = message.from_user.username 

        # Получаем объект пользователя
        # Добавляем если пользователь отуствует в БД        
        user = add_user(db, 
                        tg_id = user_tg_id, 
                        name = user_tg_name
                        )

        # Получаем текущую дату и время
        current_datetime = datetime.now() 

        # Создаем объект таблицы отчета
        report = Reports(sales      =   current_sales, 
                         remainings =   current_remainings, 
                         user       =   user.tg_id,
                         username   =   user.name,
                         store      =   user.store,
                         date       =   current_datetime,
                         )

        # Добавляем созданный отчет в БД
        db.add(report)
        db.commit()

        
        print("Получен отчёт:" 
              + "\nМагазин: " 
              + str(user.store)
              + "\nДата: " 
              + str(current_datetime.strftime("%d.%m.%Y %H:%M"))
              + "\nОстатки: " 
              + str(current_remainings)
              + "\nПродажи: " 
              + str(current_sales)
            )

        await message.answer("Данные переданы!\n"
                             + "➖➖➖➖➖➖\n"
                             + "Остатки: " 
                             + str(current_remainings) + " \n" 
                             + "Продажи: " 
                             + str(current_sales),
                             reply_markup=main_keyboard()
                             )        
        

# Обрабатываем сообщение "⏪ Вернуться назад"
@dp.message(F.text == "⏪ Вернуться назад")
async def reply_message(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Form.default)
    await message.answer("Остатки: " 
                         + str(current_remainings)                         
                         + "\nПродажи: " 
                         + str(current_sales),
                         reply_markup=main_keyboard()
                         )
    
    
# Обрабатываем состояние "По умолчанию"
@dp.message(Form.default)
async def main_menu(message: Message, state: FSMContext) -> None:
    pass  


# Обрабатываем состояние "Остатки"
@dp.message(Form.remainings)
async def set_balance(message: Message, state: FSMContext) -> None:
    remainings_value = message.text    
    if remainings_value.isdigit():
        await state.update_data(remainings = message.text)   
        global current_remainings
        current_remainings = int(remainings_value)  
        await message.answer("Укажите текущие продажи:", 
                             reply_markup=go_back_keyboard()
                             )                   
        await state.set_state(Form.sales)
    else:
        await message.answer("Введите корректную сумму (только число)!", 
                             reply_markup=go_back_keyboard()
                             )    


# Обрабатываем состояние "Продажи"
@dp.message(Form.sales)
async def set_balance(message: Message, state: FSMContext) -> None:
    sales_value = message.text    
    if sales_value.isdigit():
        await state.update_data(sales = message.text)  
        global current_sales
        current_sales = int(sales_value)  
        await message.answer("Остатки: " + str(current_remainings)                              
                             + "\nПродажи: " 
                             + str(current_sales), 
                             reply_markup=main_keyboard()
                             )      
        await state.set_state(Form.default)
    else:
        await message.answer("Введите корректную сумму (только число)!", 
                             reply_markup=go_back_keyboard()
                             ) 


# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)

# Стартуем!
if __name__ == "__main__":
    asyncio.run(main())