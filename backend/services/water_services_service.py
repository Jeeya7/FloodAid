# water_services_service.py
# Simulates calls to NOAA / NWS streamflow anomaly services.
# In production, replace mock data with real HTTP requests to:
#   https://water.weather.gov/  or  https://api.water.noaa.gov/

from typing import Any

# Mock streamflow context keyed by USGS station_id.
# Each entry mirrors the shape of a real NWS streamflow anomaly response.
_MOCK_STREAMFLOW: dict[str, dict[str, Any]] = {
    # Missouri River — severe above-normal flow
    "06893000": {
        "station_id": "06893000",
        "streamflow_status": "above_normal",
        "percent_difference": 185,
        "anomaly_level": "high",
        "notes": "Sustained heavy rainfall over the upper basin has produced record outflows.",
    },
    # Mississippi River — record flood event
    "07032000": {
        "station_id": "07032000",
        "streamflow_status": "above_normal",
        "percent_difference": 310,
        "anomaly_level": "high",
        "notes": "Confluence of Missouri and Ohio tributaries at peak stage simultaneously.",
    },
    # Sacramento River — moderately elevated, storm approaching
    "11447650": {
        "station_id": "11447650",
        "streamflow_status": "above_normal",
        "percent_difference": 62,
        "anomaly_level": "moderate",
        "notes": "Atmospheric river event expected within 24 hours; flows rising.",
    },
    # Ohio River — above normal, flood watch issued
    "03253500": {
        "station_id": "03253500",
        "streamflow_status": "above_normal",
        "percent_difference": 48,
        "anomaly_level": "moderate",
        "notes": "Spring snowmelt combined with recent rainfall has elevated baseflow.",
    },
    # Colorado River — within normal seasonal range
    "09380000": {
        "station_id": "09380000",
        "streamflow_status": "normal",
        "percent_difference": -5,
        "anomaly_level": "low",
        "notes": "Flow regulated by upstream dam releases; no anomalies detected.",
    },
    "11490000": {
        "station_id": "11490000",
        "streamflow_status": "above_normal",
        "percent_difference": 40,
        "anomaly_level": "moderate",
        "notes": "Coastal runoff and recent storms increasing flow in the Yaquina River near Newport.",
    },
}


def get_streamflow_context(station_id: str) -> dict[str, Any]:
    """
    Return streamflow anomaly context for a given station.

    In production this would call the NWS Advanced Hydrologic Prediction Service:
      GET https://water.weather.gov/ahps2/hydrograph.php?gage=<station_id>
    """
    return _MOCK_STREAMFLOW.get(
        station_id,
        {
            "station_id": station_id,
            "streamflow_status": "normal",
            "percent_difference": 0,
            "anomaly_level": "low",
            "notes": "No streamflow data available for this station.",
        },
    )