import requests
import pandas as pd

url = "https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/FeatureServer/0/query"


params = {
    "geometry": "-123.2620,44.5646",   # Corvallis example
    "geometryType": "esriGeometryPoint",
    "spatialRel": "esriSpatialRelIntersects",
    "distance": 50,
    "units": "esriSRUnit_Mile",
    "outFields": "*",
    "f": "json"
}

r = requests.get(url, params=params)
r.raise_for_status()

data = r.json()

records = [feature["attributes"] for feature in data["features"]]
df = pd.DataFrame(records)

print(df.head())
print(df.columns)

