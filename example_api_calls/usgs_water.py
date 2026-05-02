import requests

site = "01646500"  # Example gauge station
url = "https://waterservices.usgs.gov/nwis/iv/"

params = {
    "format": "json",
    "sites": site,
    "parameterCd": "00065",  # gage height
    "period": "P1D"          # last 1 day
}

response = requests.get(url, params=params)
response.raise_for_status()

data = response.json()

# Extract time series values
series = data["value"]["timeSeries"]

for ts in series:
    variable = ts["variable"]["variableName"]
    values = ts["values"][0]["value"]

    print(variable)
    for point in values[:5]:
        print(point["dateTime"], point["value"])


def get_water_level(site, days=1):
    url = "https://waterservices.usgs.gov/nwis/iv/"
    params = {
        "format": "json",
        "sites": site,
        "parameterCd": "00065",
        "period": f"P{days}D"
    }

    r = requests.get(url, params=params)
    r.raise_for_status()

    return r.json()["value"]["timeSeries"][0]["values"][0]["value"]

levels = get_water_level("14191000")
