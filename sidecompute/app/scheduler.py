import requests
from litellm import completion
from .prompts import TIME_ANALYSIS_SYS_PROMPT
import os
from django.conf import settings

os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
NREL_API_KEY = settings.NREL_API_KEY

def get_lat_lon(zip_code):
   url = "https://nominatim.openstreetmap.org/search"
   params = {
       "postalcode": zip_code,
       "country": "USA",
       "format": "json",
       "limit": 1
   }
   headers = {
       "User-Agent": "zip-to-coords-script"
   }


   r = requests.get(url, params=params, headers=headers)
   r.raise_for_status()
   data = r.json()


   if not data:
       raise ValueError("No results found for that ZIP code.")

   lat = float(data[0]["lat"])
   lon = float(data[0]["lon"])
   return lat, lon


def fetch_rate(zip):
    lat, lon = get_lat_lon(zip)
    url = f"https://developer.nrel.gov/api/utility_rates/v3.json?api_key={API_KEY}&lat={lat}&lon={lon}"

    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data

def calculate_cost(run_time_hours, cost_per_kwh, power_consumption_watts):
    """
    Calculate the cost of running a device based on runtime, cost per kWh, and power consumption.

    Parameters:
    - run_time_hours (float): The number of hours the device runs.
    - cost_per_kwh (float): The cost per kilowatt-hour (in dollars).
    - power_consumption_watts (float): The power consumption of the device in watts.

    Returns:
    - float: The total cost of running the device.
    """
    # Convert watts to kilowatts
    power_consumption_kw = power_consumption_watts / 1000.0

    # Calculate the energy consumed in kWh
    energy_consumed_kwh = power_consumption_kw * run_time_hours

    # Calculate the total cost
    total_cost = energy_consumed_kwh * cost_per_kwh

    return total_cost

def get_run_time(file_cont, flops, power):
    prompt = f"{file_cont}\n\nGPU FLOPS:{flops}\nGPU max power consumption: {power}"

    messages = [
        {"role": "system",  "content": TIME_ANALYSIS_SYS_PROMPT},
        {"role": "user",    "content": prompt}
    ]

    # Call the LLM to generate the improved prompt
    llm_response = completion(
        model="gemini/gemini-2.0-flash",
        messages=messages
    )

    # Extract and return the improved prompt text
    return float(llm_response["choices"][0]["message"]["content"])
