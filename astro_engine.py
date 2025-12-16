import pandas as pd
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib import const
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
import datetime
import math

# --- Constants ---
# Mapping Names to Symbols
ZODIAC_SYMBOLS = {
    'Aries': '♈', 'Taurus': '♉', 'Gemini': '♊', 'Cancer': '♋', 
    'Leo': '♌', 'Virgo': '♍', 'Libra': '♎', 'Scorpio': '♏', 
    'Sagittarius': '♐', 'Capricorn': '♑', 'Aquarius': '♒', 'Pisces': '♓'
}

PLANET_MAPPING = {
    const.SUN: 'Sun', const.MOON: 'Moon', const.MERCURY: 'Mercury',
    const.VENUS: 'Venus', const.MARS: 'Mars', const.JUPITER: 'Jupiter',
    const.SATURN: 'Saturn', const.URANUS: 'Uranus', const.NEPTUNE: 'Neptune',
    const.PLUTO: 'Pluto'
}

def format_rounded_up(float_degrees):
    return math.ceil(float_degrees)

def get_house_of_planet(planet_lon, houses_list):
    house_ids = [const.HOUSE1, const.HOUSE2, const.HOUSE3, const.HOUSE4,
                 const.HOUSE5, const.HOUSE6, const.HOUSE7, const.HOUSE8,
                 const.HOUSE9, const.HOUSE10, const.HOUSE11, const.HOUSE12]
    for i in range(12):
        cusp_start = houses_list.get(house_ids[i]).lon
        next_idx = (i + 1) % 12
        cusp_end = houses_list.get(house_ids[next_idx]).lon
        if cusp_end < cusp_start: 
            if planet_lon >= cusp_start or planet_lon < cusp_end: return i + 1
        else:
            if cusp_start <= planet_lon < cusp_end: return i + 1
    return 1

def calculate_chart_data(name, city, birth_date, birth_time):
    try:
        # 1. Geolocation
        geolocator = Nominatim(user_agent="astro_soul_app_v2")
        location = geolocator.geocode(city)
        if not location: return None, "City not found"
        
        # 2. Timezone
        tf = TimezoneFinder()
        tz_str = tf.timezone_at(lng=location.longitude, lat=location.latitude)
        local_tz = pytz.timezone(tz_str)
        
        full_time_str = f"{birth_date} {birth_time}"
        try:
            dt_naive = datetime.datetime.strptime(full_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt_naive = datetime.datetime.strptime(full_time_str, "%Y-%m-%d %H:%M")
            
        dt_aware = local_tz.localize(dt_naive)
        offset_seconds = dt_aware.utcoffset().total_seconds()
        flatlib_offset = f"{'+' if offset_seconds>=0 else '-'}{abs(int(offset_seconds/3600)):02d}:{int((abs(offset_seconds/3600)%1)*60):02d}"
        
        # 3. Calculation
        geo_pos = GeoPos(location.latitude, location.longitude)
        date = Datetime(dt_naive.strftime('%Y/%m/%d'), dt_naive.strftime('%H:%M'), flatlib_offset)
        planet_ids = [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS, 
                      const.JUPITER, const.SATURN, const.URANUS, const.NEPTUNE, const.PLUTO]
        
        chart = Chart(date, geo_pos, IDs=planet_ids)
        houses_list = chart.houses

        result_data = []
        
        # Add Ascendant
        asc = houses_list.get(const.HOUSE1)
        result_data.append({
            'planet': 'Ascendant',
            'sign': asc.sign,
            'sign_symbol': ZODIAC_SYMBOLS.get(asc.sign, ''), # Add Symbol
            'degree_int': format_rounded_up(asc.signlon),
            'house': 1,
            'is_retrograde': False
        })

        # Add Planets
        for pid in planet_ids:
            obj = chart.get(pid)
            house_num = get_house_of_planet(obj.lon, houses_list)
            
            result_data.append({
                'planet': PLANET_MAPPING.get(pid, pid),
                'sign': obj.sign,
                'sign_symbol': ZODIAC_SYMBOLS.get(obj.sign, ''), # Add Symbol
                'degree_int': format_rounded_up(obj.signlon),
                'house': house_num,
                'is_retrograde': False 
            })

        return result_data, None

    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        return None, str(e)