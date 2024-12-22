import asyncio
import logging
import sys
import requests
from os import getenv

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)

BOT_TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()

user_data = {}


class WeatherState(StatesGroup):
    start_city = State()
    end_city = State()
    intermediate_cities = State()
    days = State()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"Привет, {html.bold(message.from_user.full_name)}! Я бот для прогноза погоды. Используйте /help для получения списка команд"
    )


@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    await message.reply(
        "Доступные команды:\n/start - приветствие\n/help - справка\n/weather - запрос погоды"
    )


@dp.message(Command("weather"))
async def command_weather_handler(message: Message, state: FSMContext):
    await message.answer("Введите начальную точку маршрута:")
    await state.set_state(WeatherState.start_city)


@dp.message(WeatherState.start_city)
async def process_start_city(message: Message, state: FSMContext):
    await state.update_data(start_city=message.text)
    await message.answer("Введите конечную точку:")
    await state.set_state(WeatherState.end_city)


@dp.message(WeatherState.end_city)
async def process_end_city(message: Message, state: FSMContext):
    await state.update_data(end_city=message.text)
    await message.answer(
        "Введите промежуточные точки (через запятую) или пропустите этот шаг, используя команду /skip:"
    )
    await state.set_state(WeatherState.intermediate_cities)


@dp.message(Command("skip"), WeatherState.intermediate_cities)
async def skip_intermediate_cities(message: Message, state: FSMContext):
    await state.update_data(intermediate_cities=[])
    await message.answer(
        "Выберите период для прогноза погоды", reply_markup=days_keyboard()
    )
    await state.set_state(WeatherState.days)


@dp.message(WeatherState.intermediate_cities)
async def process_intermediate_cities(message: Message, state: FSMContext):
    await state.update_data(intermediate_cities=message.text.split(","))
    await message.answer(
        "Выберите период для прогноза погоды", reply_markup=days_keyboard()
    )
    await state.set_state(WeatherState.days)


def days_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 день", callback_data="1"),
                InlineKeyboardButton(text="3 дня", callback_data="3"),
                InlineKeyboardButton(text="5 дней", callback_data="5"),
            ]
        ],
        resize_keyboard=True,
    )

    return keyboard


@dp.callback_query(WeatherState.days, F.data.in_(["1", "3", "5"]))
async def process_days(callback: CallbackQuery, state: FSMContext):
    await state.update_data(days=callback.data)
    data = await state.get_data()

    start_city = data["start_city"]
    end_city = data["end_city"]
    intermediate_cities = data["intermediate_cities"]
    days = data["days"]

    params = {
        "start_city": start_city,
        "end_city": end_city,
        "intermediate_cities": intermediate_cities,
        "days": days,
    }
    response = requests.get(f"http://127.0.0.1:8050/get_data", params=params)
    if response.status_code == 200:
        cities_data = response.json()
        for city in cities_data:
            msg = f"Название города: {city.name}"
            await callback.message.answer(msg)
    else:
        msg = str(response)
        await callback.message.answer(msg)
    await state.set_state(None)


@dp.message()
async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
