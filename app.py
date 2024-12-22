from dash import (
    Dash,
    dcc,
    html,
    Input,
    Output,
    State,
    MATCH,
    ALL,
    ctx,
)
import plotly.graph_objects as go
import requests
import pandas as pd
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
from flask import Flask, request, jsonify

# Настройка шаблонов Bootstrap
load_figure_template(["minty", "minty_dark"])

API_KEY = "gqfTGXi6zHBN50BhfeaHupSotfgEoI4Q"

server = Flask(__name__)

app = Dash(__name__, server=server, external_stylesheets=[dbc.themes.MINTY])

df = pd.DataFrame()


# Функция для получения location key
def get_location_key(city_name):
    url = f"http://dataservice.accuweather.com/locations/v1/cities/search?apikey={API_KEY}&q={city_name}&language=ru-RU"
    response = requests.get(url)
    if response.status_code == 200 and response.json():
        return response.json()[0]["Key"]
    return None


# Функция для получения координат города
def get_city_coordinates(city_name):
    location_key = get_location_key(city_name)
    if location_key:
        url = f"http://dataservice.accuweather.com/locations/v1/{location_key}?apikey={API_KEY}"
        response = requests.get(url)
        if response.status_code == 200 and response.json():
            coords = response.json().get("GeoPosition", {})
            return coords.get("Latitude"), coords.get("Longitude")
    return None, None


# Функция для получения данных прогноза погоды на 5 дней
def get_forecast_data(location_key):
    url = f"http://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}?apikey={API_KEY}&metric=true&details=true"
    response = requests.get(url)
    if response.status_code == 200 and response.json():
        return response.json()["DailyForecasts"]
    return None


# Создание графика
def create_graph(data, param, days=3):
    fig = go.Figure(
        data=go.Scatter(
            x=data.head(days)["Date"],
            y=data.head(days)[param],
            mode="lines+markers",
            name=param,
        )
    )
    fig.update_layout(
        title="Прогноз погоды",
        template="minty_dark",
        xaxis_title="Дата",
        yaxis_title=param,
    )
    return fig


# Создание DataFrame
def create_df(data):
    forecast_data = []
    for day in data:
        forecast = {
            "Date": day["Date"],
            "Temperature": day["Temperature"]["Maximum"]["Value"],
            "Wind Speed": day["Day"]["Wind"]["Speed"]["Value"],
            "Precipitation Probability": day["Day"]["PrecipitationProbability"],
        }
        forecast_data.append(forecast)
    return pd.DataFrame(forecast_data)


@server.route("/get_data", methods=["GET"])
def get_data():
    city_names = request.args.get("cities")
    if not city_names:
        return jsonify({"error": 'Необходим параметр "cities"'}), 400

    cities = city_names.split(",")
    cities_data = []

    for city in cities:
        location_key = get_location_key(city)
        if not location_key:
            return (
                jsonify({"error": f"Не удалось найти данные для города {city}."}),
                400,
            )
        forecast = get_forecast_data(location_key)
        if forecast:
            cities_data.append({"name": city, "forecast": forecast})
        else:
            return jsonify({"error": f"Weather data not found for city: {city}"}), 404


# Функция для создания карты
def create_map(cities):
    locations = []
    city_names = []

    for city in cities:
        lat, lon = get_city_coordinates(city)
        if lat is not None and lon is not None:
            locations.append([lat, lon])
            city_names.append(city)

    if not locations:
        return go.Figure()

    # Центрируем карту по среднему положению городов
    center_lat = sum([loc[0] for loc in locations]) / len(locations)
    center_lon = sum([loc[1] for loc in locations]) / len(locations)

    # Создание карты с маркерами и маршрутом
    fig = go.Figure(
        go.Scattermapbox(
            lat=[loc[0] for loc in locations],
            lon=[loc[1] for loc in locations],
            mode="markers+text+lines",
            marker={"size": 10, "color": "blue", "symbol": "circle"},
            text=city_names,
            textposition="top right",
            line={"width": 2, "color": "blue"},
        )
    )

    fig.update_layout(
        mapbox={
            "style": "open-street-map",
            "center": {"lat": center_lat, "lon": center_lon},
            "zoom": 5,
        },
        showlegend=False,
        title="Маршрут между городами",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )

    return fig


app.layout = dbc.Container(
    [
        dcc.Location(id="url", refresh=False),
        html.H1(
            "Прогноз погоды", className="text-center my-4 display-4 text-primary"
        ),  # Большой заголовок
        dbc.Row(
            [
                dbc.Col(
                    dbc.Input(
                        id="start-city",
                        placeholder="Начальный город",
                        className="dbc form-control-lg",
                    ),
                    md=6,
                    lg=4,
                    className="mx-auto",
                ),
            ],
            className="mb-3 justify-content-center",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Input(
                        id="end-city",
                        placeholder="Конечный город",
                        className="dbc form-control-lg",
                    ),
                    md=6,
                    lg=4,
                    className="mx-auto",
                ),
            ],
            className="mb-3 justify-content-center",
        ),
        html.Div(id="intermediate-cities-container", children=[]),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        "Добавить промежуточный город",
                        id="add-intermediate-city",
                        color="primary",
                        className="w-100 btn-lg",
                    ),
                    md=4,
                    lg=4,
                    className="mx-auto",
                ),
            ],
            className="mb-4 justify-content-center",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        "Получить прогноз",
                        id="submit-btn",
                        color="secondary",
                        className="w-100 btn-lg",
                    ),
                    md=2,
                    lg=4,
                    className="mx-auto",
                ),
            ],
            className="mb-4 justify-content-center",
        ),
        dbc.Row(
            dbc.Col(
                dbc.Alert(
                    id="error-alert",
                    is_open=False,
                    dismissable=True,
                    color="danger",
                    className="text-center mb-4 d-flex align-items-center justify-content-center",
                    duration=4000,
                ),
                md=6,
                className="mx-auto",
            ),
        ),
        dcc.Loading(
            children=html.Div(id="weather-graphs"),
            id="loading-component",
            overlay_style={"visibility": "visible", "filter": "blur(5px)"},
        ),
    ],
    fluid=True,
)


@app.callback(
    Output("intermediate-cities-container", "children"),
    Input("add-intermediate-city", "n_clicks"),
    Input({"type": "remove-button", "index": ALL}, "n_clicks"),
    State("intermediate-cities-container", "children"),
    prevent_initial_call=True,
)
def update_intermediate_city(add_clicks, remove_clicks, children):
    triggered_id = ctx.triggered_id

    if triggered_id == "add-intermediate-city":
        new_input = dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            dbc.Input(
                                placeholder="Промежуточный город",
                                className="form-control form-control-lg flex-grow-1",
                                id={
                                    "type": "intermediate-city",
                                    "index": len(children),
                                },
                            ),
                            dbc.Button(
                                "Удалить",
                                color="danger",
                                className="btn-lg",
                                id={
                                    "type": "remove-button",
                                    "index": len(children),
                                },
                                style={"margin-left": "10px"},
                            ),
                        ],
                        style={"display": "flex", "align-items": "center"},
                        className="w-100",
                    ),
                    md=6,
                    lg=4,
                    className="mx-auto",
                )
            ],
            className="mb-3 justify-content-center",
        )
        children.append(new_input)

    else:
        for idx, val in enumerate(remove_clicks):
            if val is not None:
                del children[idx]
    return children


@app.callback(
    Output("weather-graphs", "children"),
    Output("error-alert", "is_open"),
    Output("error-alert", "children"),
    Input("submit-btn", "n_clicks"),
    State("start-city", "value"),
    State("end-city", "value"),
    State({"type": "intermediate-city", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def get_weather(n_clicks, start_city, end_city, intermediate_cities):
    global df

    if not start_city or not end_city:
        return "", True, "Укажите начальный и конечный города."

    cities = [start_city] + (intermediate_cities or []) + [end_city]
    cities = [x for x in cities if x is not None]

    all_data = []
    graphs = []

    for city in cities:
        location_key = get_location_key(city)
        if not location_key:
            return "", True, f"Не удалось найти данные для города {city}."

        forecast = get_forecast_data(location_key)
        if forecast:
            city_df = create_df(forecast)
            city_df["City"] = city
            all_data.append(city_df)

            graph_controls = html.Div(
                [
                    dcc.RadioItems(
                        id={"type": "forecast-type-radio", "index": city},
                        options=[
                            {"label": "Температура", "value": "Temperature"},
                            {"label": "Скорость ветра", "value": "Wind Speed"},
                            {
                                "label": "Вероятность осадков",
                                "value": "Precipitation Probability",
                            },
                        ],
                        value="Temperature",
                        inline=True,
                        style={"display": "flex", "gap": "20px"},
                    ),
                    dcc.Slider(
                        1,
                        5,
                        2,
                        value=3,
                        id={"type": "forecast-days-slider", "index": city},
                    ),
                ]
            )

            graph = dcc.Graph(
                id={"type": "forecast-graph", "index": city},
                figure=create_graph(city_df, "Temperature", 3),
            )

            graphs.append(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H4(f"Город: {city}", className="text-center"),
                            graph_controls,
                            graph,
                        ]
                    ),
                    className="mb-4",
                )
            )
        else:
            return "", True, f"Не удалось загрузить прогноз для города {city}."

    df = pd.concat(all_data, ignore_index=True)
    graphs.append(
        dbc.Card(
            dbc.CardBody(
                [
                    html.H4(f"Маршрут между городами", className="text-center"),
                    dcc.Graph(figure=create_map(cities)),
                ]
            ),
            className="mb-4",
        )
    )

    return graphs, False, ""


@app.callback(
    Output({"type": "forecast-graph", "index": MATCH}, "figure"),
    [
        Input({"type": "forecast-type-radio", "index": MATCH}, "value"),
        Input({"type": "forecast-days-slider", "index": MATCH}, "value"),
    ],
    prevent_initial_call=True,
)
def update_graph(params, days):
    city = ctx.triggered_id["index"]
    city_df = df[df["City"] == city]
    return create_graph(city_df, params, days)


if __name__ == "__main__":
    app.run_server(debug=True)
