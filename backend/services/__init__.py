# this file is the public interface for the tools folder
# instead of importing directly from each service file,
# other parts of the code can just do:
#   from tools import get_gauges_by_bounds
# instead of:
#   from tools.services.usgs_service import get_gauges_by_bounds

from services.usgs_service import get_gauges_by_bounds, get_usgs_water_data
from services.weather_service import get_weather_context

# __all__ controls what gets exported when someone does "from tools import *"
# it's also useful as documentation — tells you exactly what this package offers
__all__ = [
    # environmental API services
    "get_gauges_by_bounds",   # finds USGS water gauge stations near a location
    "get_usgs_water_data",    # fetches current water level data for a gauge station
    "get_weather_context",    # fetches weather forecast and NWS flood alerts
]