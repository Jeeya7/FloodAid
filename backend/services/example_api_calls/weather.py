
import requests

# get hourly rain data

headers = {
    "User-Agent": "your-app (you@email.com)"
}

lat, lon = 44.5646, -123.2620

url = f"https://api.weather.gov/points/{lat},{lon}"

r = requests.get(url, headers=headers)
r.raise_for_status()

data = r.json()

forecast_hourly_url = data["properties"]["forecastHourly"]

print(forecast_hourly_url)


r = requests.get(forecast_hourly_url, headers=headers)
r.raise_for_status()

forecast = r.json()

periods = forecast["properties"]["periods"]

for hour in periods[:24]:
    print(
        hour["startTime"],
        "Rain chance:", hour["probabilityOfPrecipitation"]["value"],
        "%",
        "Forecast:", hour["shortForecast"]
    )



### get active weather alerts

print ("_________ weather alert __________")
url = "https://api.weather.gov/alerts/active"

params = {
    "area": "OR"
}

r = requests.get(url, headers=headers, params=params)
r.raise_for_status()

alerts = r.json()["features"]

for alert in alerts:
    props = alert["properties"]
    print(props["event"])
    print(props["headline"])
    print()