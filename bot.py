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
    ReplyKeyboardRemove,
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
    await state.set_state(WeatherState.start_city)
    await message.answer(
        "Введите начальную точку маршрута",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(WeatherState.start_city)
async def process_start_city(message: Message, state: FSMContext):
    await state.update_data(start_city=[message.text])
    await state.set_state(WeatherState.end_city)
    await message.answer(
        "Введите конечную точку",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(WeatherState.end_city)
async def process_end_city(message: Message, state: FSMContext):
    await state.update_data(end_city=[message.text])
    await state.set_state(WeatherState.intermediate_cities)
    await message.answer(
        "Введите промежуточные точки (через запятую) или пропустите этот шаг, используя команду /skip"
    )


@dp.message(Command("skip"), WeatherState.intermediate_cities)
async def skip_intermediate_cities(message: Message, state: FSMContext):
    await state.update_data(intermediate_cities=[])
    await state.set_state(WeatherState.days)
    await message.answer(
        "Выберите период для прогноза погоды", reply_markup=create_days_keyboard()
    )


@dp.message(WeatherState.intermediate_cities)
async def process_intermediate_cities(message: Message, state: FSMContext):
    await state.update_data(intermediate_cities=message.text.split(","))
    await state.set_state(WeatherState.days)
    await message.answer(
        "Выберите период для прогноза погоды", reply_markup=create_days_keyboard()
    )


def create_days_keyboard():
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


@dp.callback_query(WeatherState.days)
async def process_days(callback: CallbackQuery, state: FSMContext):
    await state.update_data(days=callback.data)
    data = await state.get_data()
    await state.clear()

    start_city = data["start_city"]
    end_city = data["end_city"]
    intermediate_cities = data["intermediate_cities"]
    days = int(data["days"])
    print(days, type(days))

    cities = start_city + intermediate_cities + end_city
    params = {
        "cities": ",".join(cities),
    }
    response = requests.get(f"http://127.0.0.1:8050/get_data", params=params)
    print(response.url)
    if response.status_code == 200:
        cities_data = response.json()
        for city in cities_data:
            forecast_data = city.get("forecast")
            msg = f"Прогноз погоды в городе {html.bold(city.get('name'))}\n"
            for day in forecast_data[:days]:
                msg += f"\nДата: {day.get('Date')}\nТемпература (°C): {day.get('Temperature')}\nСкорость ветра (м/c): {day.get('Wind Speed')}\
                    \nВероятность осадков (%): {day.get('Precipitation Probability')}\n"
            await callback.message.answer(msg)

        await callback.message.answer(
            f"Вы можете ознакомиться с графиками по данной ссылке http://127.0.0.1:8050?start-city={start_city[0]}&end-city={end_city[0]}"
        )
    else:
        error_data = response.json()
        print(error_data)
        await callback.message.answer(error_data.get("error"))


@dp.message()
async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
