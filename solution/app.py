import os
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for
from urllib.parse import unquote
import plotly.graph_objs as go
from dash import Dash, dcc, html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

app = Flask(__name__)

dash_app = Dash(
    __name__,
    server=app,
    url_base_pathname='/dashboard/',
    external_stylesheets=[
        dbc.themes.DARKLY,
        {
            "href": "https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap",
            "rel": "stylesheet"
        }
    ]
)

load_dotenv()
API_KEY = os.getenv("ACCUWEATHER_TOKEN")
WEATHER_API_TOKEN = os.getenv("WEATHER_API_TOKEN")

dash_app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='graphs', children="Загрузка графиков...")
])


def get_weather(city):
    try:
        location_url = f"http://dataservice.accuweather.com/locations/v1/cities/search?apikey={API_KEY}&q={city}&language=ru-ru"
        location_data = requests.get(location_url).json()

        if location_data:
            location_key = location_data[0]['Key']
            weather_url = f"http://dataservice.accuweather.com/currentconditions/v1/{location_key}?apikey={API_KEY}&language=ru-ru&details=true"
            weather_data = requests.get(weather_url).json()

            if weather_data:
                return {
                    "city": city,
                    "temperature": weather_data[0]['Temperature']['Metric']['Value'],
                    "humidity": weather_data[0]['RelativeHumidity'],
                    "wind_speed": weather_data[0]['Wind']['Speed']['Metric']['Value'],
                    "precipitation": weather_data[0]['HasPrecipitation'],
                    "weather_text": weather_data[0]['WeatherText']
                }
    except:
        return render_template('error.html')
    return None


def prepare_forecast_data(forecast_data):
    dates, temperatures, precipitation, wind_speeds = [], [], [], []

    for day in forecast_data["forecast"]["forecastday"]:
        dates.append(day["date"])
        temperatures.append(day["day"]["maxtemp_c"])
        precipitation.append(day["day"]["daily_chance_of_rain"])
        wind_speeds.append(day["day"]["maxwind_kph"])

    return dates, temperatures, precipitation, wind_speeds


def check_bad_weather(weather, preference):
    conditions = []
    if preference == 'southern':
        if weather['temperature'] < 15 or weather['temperature'] > 30:
            conditions.append('температура')
        if weather['humidity'] > 80:
            conditions.append('влажность')
    elif preference == 'northern':
        if weather['temperature'] < -10 or weather['temperature'] > 20:
            conditions.append('температура')
        if weather['humidity'] > 60:
            conditions.append('влажность')

    return conditions if conditions else None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dashboard/<city>/<int:days>')
def dashboard(city, days):
    dash_app.layout = html.Div(children=[html.Div(id='graphs')])
    return dash_app.index()


@dash_app.callback(
    [Output('graphs', 'children')],
    [Input('url', 'search')]
)
def update_layout(search):
    params_str = search.lstrip('?')
    params_parts = params_str.split('&')
    params = {k: v for k, v in [p.split('=') for p in params_parts]}

    city = params.get('city')
    if city:
        city = unquote(city)
    days = params.get('days', '1')

    if not city or not days.isdigit():
        return ["Ошибка: проверьте параметры URL."]

    days = int(days)
    data = get_weather_data(city, days)
    if not data:
        return ["Данные о погоде не найдены."]

    return [create_graphs(data, days)]


def get_weather_data(city, days):
    url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_TOKEN}&q={city}&days={days}"
    response = requests.get(url)
    data = response.json()
    return data.get('forecast', {}).get('forecastday', [])


def create_graphs(data, days):
    if days == 1:
        hours = data[0]['hour']
        times = [hour['time'][-5:] for hour in hours]
        temperatures = [hour['temp_c'] for hour in hours]
        precipitation = [hour['precip_mm'] for hour in hours]
        wind_speed = [hour['wind_kph'] for hour in hours]
        humidity = [hour['humidity'] for hour in hours]
        pressure = [hour['pressure_mb'] for hour in hours]

        traces = [
            {'data': go.Scatter(x=times, y=temperatures, mode='lines+markers', name='Температура (°C)')},
            {'data': go.Bar(x=times, y=precipitation, name='Осадки (мм)')},
            {'data': go.Scatter(x=times, y=wind_speed, mode='lines+markers', name='Скорость ветра (км/ч)')},
            {'data': go.Scatter(x=times, y=humidity, mode='lines+markers', name='Влажность (%)')},
            {'data': go.Scatter(x=times, y=pressure, mode='lines+markers', name='Давление (мБар)')}
        ]
    else:
        dates = [day['date'] for day in data]
        temperatures = [day['day']['avgtemp_c'] for day in data]
        precipitation = [day['day']['totalprecip_mm'] for day in data]
        wind_speed = [day['day']['maxwind_kph'] for day in data]
        humidity = [day['day']['avghumidity'] for day in data]
        pressure = [day['hour'][12]['pressure_mb'] for day in data]

        traces = [
            {'data': go.Scatter(x=dates, y=temperatures, mode='lines+markers', name='Температура (°C)')},
            {'data': go.Bar(x=dates, y=precipitation, name='Осадки (мм)')},
            {'data': go.Scatter(x=dates, y=wind_speed, mode='lines+markers', name='Скорость ветра (км/ч)')},
            {'data': go.Scatter(x=dates, y=humidity, mode='lines+markers', name='Влажность (%)')},
            {'data': go.Scatter(x=dates, y=pressure, mode='lines+markers', name='Давление (мБар)')}
        ]

    titles = ['Температура', 'Осадки', 'Скорость ветра', 'Влажность', 'Давление']
    graphs = []

    for trace, title in zip(traces, titles):
        layout = go.Layout(
            title=title,
            xaxis=dict(title='Время' if days == 1 else 'Дата'),
            yaxis=dict(title=title),
            paper_bgcolor="#2e2e4d",
            plot_bgcolor="#1e1e2f",
            font=dict(color="#ffffff")
        )
        fig = {'data': [trace['data']], 'layout': layout}
        graphs.append(dcc.Graph(figure=fig))

    return graphs


@app.route('/check_weather', methods=['POST'])
def check_weather():
    start_city = request.form['start_city']
    additional_cities = request.form.getlist('additional_cities')
    preference = request.form['preference']

    start_weather = get_weather(start_city)
    weathers = [get_weather(city) for city in additional_cities]

    if not start_weather:
        return redirect(url_for('index'))

    start_conditions = check_bad_weather(start_weather, preference)
    conditions = [check_bad_weather(w, preference) for w in weathers]

    return render_template(
        'result.html',
        start_weather=start_weather,
        weathers=weathers,
        conditions=conditions,
        start_conditions=start_conditions
    )


if __name__ == '__main__':
    app.run(debug=True)
