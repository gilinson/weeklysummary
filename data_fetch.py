from functools import lru_cache
import urllib.request
import time
import csv
import urllib.request
import codecs
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from math import radians, cos, sin, asin, sqrt
from plane_config import planes

#@lru_cache(maxsize=32)
def get_airport_info(code, airports):
    """
    Get metadata for an airport given its code
    """
    return list(filter(lambda x: x['ident'] == code, airports))[0]


def get_flights(icoa24, end):
    """
    Fetch flight data from opensky for 30 days from an end data for a specific plane
    """
    api_url = "https://opensky-network.org/api/flights/aircraft"
    begin = end - 24 * 3600 * 30  # 30 days in seconds

    response = requests.get(
        api_url,
        params={
            'icao24': icoa24,
            'begin': begin,
            'end': end
        }
    )

    return response.json()

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees)
    From https://stackoverflow.com/questions/4913349/haversine-formula-in-python-bearing-and-distance-between-two-gps-points
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return c * r


def get_distance_between_airports(arrival_code, departure_code, airports):
    """
    Given two airport codes, find distance
    """
    if arrival_code is None or departure_code is None:
        return None

    arrival_info = get_airport_info(arrival_code, airports)
    departure_info = get_airport_info(departure_code, airports)
    distance = haversine(
        float(departure_info['longitude_deg']),
        float(departure_info['latitude_deg']),
        float(arrival_info['longitude_deg']),
        float(arrival_info['latitude_deg'])
    )
    return distance


def download_data():
    # Download airport data
    url = 'https://ourairports.com/data/airports.csv'
    ftpstream = urllib.request.urlopen(url)
    airport_csv_reader = csv.DictReader(codecs.iterdecode(ftpstream, 'utf-8'))
    airports = []
    for row in airport_csv_reader:
        airports.append(row)

    # Fetch flight data from opensky REST API
    # https://openskynetwork.github.io/opensky-api/rest.html

    end = int(time.time())
    flights = []
    n_months = 1  # 61 months so we get 5 full years because data is slightly delayed

    for i in range(n_months):
        print('Fetching month ' + str(i + 1) + ': ', end=' ')
        end += -(24 * 30 * 3600 + 1)  # TODO is this correct?
        for plane in planes:
            print(plane['name'] + '...', end='')
            f = get_flights(plane['icao24'], end)
            print(len(f))
            flights.append(f)
        print('')

    # Flatten the returned data
    flat_list = [x for xs in flights for x in xs]

    resolved_flights = []
    last_icao24 = None
    flat_list = sorted(flat_list, key=lambda d: (d['icao24'], d['firstSeen']))
    for i in range(len(flat_list)):

        flight = flat_list[i]

        departure = flight['estDepartureAirport']
        arrival = flight['estArrivalAirport']
        est_departure_time = int(flight['firstSeen'])
        est_arrival_time = int(flight['lastSeen'])
        duration = est_arrival_time - est_departure_time

        # For first occurrence of a plane
        if last_icao24 != flight['icao24']:
            airport_seq = []
            resolved_flights.append({
                'departure': departure,
                'arrival': arrival,
                'depature_time': est_departure_time,
                'duration': duration,
                'icao24': flight['icao24']

            })
            airport_seq.append(arrival)
            last_icao24 = flight['icao24']
            continue

        # Is the plane at an airport that we don't have a record of it flying to?
        if departure != airport_seq[-1] and departure is not None and airport_seq[-1] is not None:
            resolved_flights.append({
                'departure': airport_seq[-1],
                'arrival': departure,
                # We don't have this info, so make assumption
                'depature_time': est_departure_time,
                'duration': None,
                'icao24': flight['icao24']
            })

        # Append the current flight record
        resolved_flights.append({
            'departure': departure or airport_seq[-1],
            'arrival': arrival,
            'depature_time': est_departure_time,
            'duration': duration,
            'icao24': flight['icao24']

        })
        airport_seq.append(arrival)
        last_icao24 = flight['icao24']

    df_flights = pd.DataFrame.from_dict(resolved_flights)
    # Calculate distance between airports
    df_flights['distance'] = df_flights.apply(
        lambda x: get_distance_between_airports(
            x['arrival'],
            x['departure'],
            airports),
        axis=1)

    # Calculate average speed of each plane
    speed = df_flights[['icao24', 'distance', 'duration']].dropna().groupby('icao24').apply(
        lambda x: sum(x['distance']) / sum(x['duration'])
    )

    # Where we don't have a duration, calculate one based on distance
    speed = pd.DataFrame(speed)
    speed.columns = ['speed']
    df_flights = df_flights.join(speed, on='icao24')
    df_flights.loc[df_flights['duration'].isnull(), 'duration'] = df_flights['distance'] / df_flights['speed']

    # More mundging
    df_flights['name'] = df_flights['icao24'].apply(
        lambda x: list(filter(lambda y: y['icao24'] == x, planes))[0]['name'])
    df_flights['departure_ts'] = df_flights['depature_time'].apply(datetime.utcfromtimestamp)
    df_flights['quarter'] = df_flights['departure_ts'].dt.to_period('Y').dt.to_timestamp()

    galph = 466
    df_flights['fuel_used_gal'] = round(galph * (df_flights['duration'] / (60 * 60)), 2)
    df_flights['fuel_used_kg'] = df_flights['fuel_used_gal'] * 3.04
    # df_flights['c02_tons'] = (df_flights['fuel_used_kg'] * 3.15 ) / 907.185 # short tons?
    df_flights['c02_tons'] = (df_flights['fuel_used_kg'] * 3.15) / 1000
    df_flights['duration_hours'] = df_flights['duration'] / (3600)


    return df_flights