from typing import Any
from geocoding import get_location
from weather_service import get_hourly_rainfall, get_weather_alert
from usgs_service import get_usgs_streamflow, get_all_usgs_stations, USGSStationIndex
from mock_data_service import get_mock_location


def get_environmental_data(lat: float, lng: float, usgs_site_id: str) -> dict[str, Any]:
    rain = get_hourly_rainfall(lat, lng)
    alert = get_weather_alert(lat, lng)
    stream = get_usgs_streamflow(usgs_site_id)

    return {
        "rain_forecast_inches": rain,
        "water_level_status": "high" if stream["streamflow_cfs"] > 1000 else "normal",
        "streamflow_status": "above_normal" if stream["trend"] == "rising" else "normal",
        "weather_alert": alert,
        "nearest_gauge_distance_miles": 8.2,  # later replace with spatial query
        "water_level_trend": stream["trend"],
    }



def main():
    print("\n🌊 FLOOD RISK SYSTEM START\n")

    # -------------------------------------------------
    # Step 1: Load real USGS station network
    # -------------------------------------------------
    print("📡 Loading USGS station network...")
    stations = get_all_usgs_stations()

    print(f"✅ Loaded {len(stations)} stations")

    # -------------------------------------------------
    # Step 2: Build spatial index
    # -------------------------------------------------
    print("🧭 Building spatial index...")
    index = USGSStationIndex(stations)

    # -------------------------------------------------
    # Step 3: Define user location (replace mock_location)
    # -------------------------------------------------
    lat = 44.5646
    lng = -123.2620

    print("\n📍 User location:")
    print(lat, lng)

    # -------------------------------------------------
    # Step 4: Find nearest USGS gauge
    # -------------------------------------------------
    nearest = index.nearest(lat, lng)

    print("\n🌊 Nearest USGS gauge:")
    print(nearest)

    usgs_site_id = nearest[0]["site_id"]


    # -----------------------------
    # 3. Call your REAL environmental pipeline function
    # -----------------------------
    env = get_environmental_data(lat, lng, usgs_site_id)

    print("\n🌦️ Environmental Data Output:")
    for k, v in env.items():
        print(f"{k}: {v}")

    # -----------------------------
    # 4. Basic sanity check logic
    # -----------------------------
    print("\n🧠 Quick Interpretation:")

    if env["weather_alert"] != "none":
        print("⚠️ Active weather alert detected:", env["weather_alert"])

    if env["water_level_trend"] == "rising":
        print("📈 River levels are rising")

    if env["rain_forecast_inches"] > 2:
        print("🌧️ Heavy rainfall expected")

    print("\n✅ Pipeline test complete\n")


if __name__ == "__main__":
    main()


