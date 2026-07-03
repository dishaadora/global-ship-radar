import csv
import random
import time
from datetime import datetime, timedelta

def generate_mock_data(filename="raw_ais_data.csv", num_records=1000):
    # Standard AIS ship types:
    # 30: Fishing
    # 70-79: Cargo
    # 80-89: Tanker
    # Other: 60 (Passenger), 36 (Sailing), 52 (Tug), etc.
    ship_pool = [
        {"mmsi": 311000123, "name": "Al-Batha", "type_code": 81},      # Tanker
        {"mmsi": 311000456, "name": "Ocean Voyager", "type_code": 70}, # Cargo
        {"mmsi": 477000789, "name": "Blue Marlin", "type_code": 30},   # Fishing
        {"mmsi": 235000111, "name": "Desert Star", "type_code": 82},   # Tanker
        {"mmsi": 419000222, "name": "Indus Prince", "type_code": 74},  # Cargo
        {"mmsi": 477123456, "name": "Sindbad", "type_code": 30},       # Fishing
        {"mmsi": 538000333, "name": "Pacific Explorer", "type_code": 60}, # Passenger (Other)
        {"mmsi": 636000444, "name": "Gulf Breeze", "type_code": 79},   # Cargo
        {"mmsi": 355000555, "name": "Sea Pearl", "type_code": 36},     # Sailing (Other)
        {"mmsi": 413000666, "name": "Red Sea Pearl", "type_code": 85}, # Tanker
    ]
    
    # Boundaries: Lat 12 to 28, Lon 50 to 65
    lat_min, lat_max = 12.0, 28.0
    lon_min, lon_max = 50.0, 65.0
    
    start_time = datetime(2026, 7, 2, 12, 0, 0)
    
    # Different timestamp formats to mock non-uniformity:
    # 1. ISO 8601: "YYYY-MM-DDTHH:MM:SSZ"
    # 2. Custom date-time: "DD/MM/YYYY HH:MM:SS"
    # 3. Slanted format: "YYYY/MM/DD HH:MM:SS"
    # 4. Unix Epoch: string representation of timestamp float
    formats = [
        lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        lambda dt: dt.strftime("%d/%m/%Y %H:%M:%S"),
        lambda dt: dt.strftime("%Y/%m/%d %H:%M:%S"),
        lambda dt: str(int(dt.timestamp()))
    ]

    records = []
    
    for i in range(num_records):
        ship = random.choice(ship_pool)
        
        # Decide if this record should be out-of-bounds (5% chance)
        if random.random() < 0.05:
            # Out of bounds coordinates
            if random.random() < 0.5:
                lat = random.uniform(30.0, 45.0)  # Too far north
            else:
                lat = random.uniform(0.0, 10.0)   # Too far south
            
            if random.random() < 0.5:
                lon = random.uniform(35.0, 48.0)  # Too far west
            else:
                lon = random.uniform(67.0, 80.0)  # Too far east
        else:
            # In bounds coordinates
            lat = random.uniform(lat_min, lat_max)
            lon = random.uniform(lon_min, lon_max)
            
        sog = round(random.uniform(0.0, 25.0), 1)
        cog = round(random.uniform(0.0, 360.0), 1)
        heading = int(random.uniform(0, 359)) if random.random() > 0.1 else 511  # 511 = unavailable
        
        # Time increment
        dt = start_time + timedelta(seconds=i * 10 + random.randint(-5, 5))
        
        # Choose a random timestamp format
        ts_formatter = random.choice(formats)
        timestamp_str = ts_formatter(dt)
        
        records.append({
            "mmsi": ship["mmsi"],
            "ship_name": ship["name"],
            "ship_type_code": ship["type_code"],
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "sog": sog,
            "cog": cog,
            "heading": heading,
            "timestamp": timestamp_str
        })
        
        # Inject duplicates
        # 1. Exact row duplicate (2% chance)
        if random.random() < 0.02:
            records.append(records[-1])
            
        # 2. Semi-duplicate with slightly different position/time (1% chance)
        if random.random() < 0.01:
            dupe = records[-1].copy()
            # same mmsi and timestamp, but maybe slightly different lat/lon
            dupe["latitude"] = round(dupe["latitude"] + 0.001, 5)
            records.append(dupe)

    # Let's shuffle records to mix duplicates and out-of-order timings
    random.shuffle(records)
    
    # Save to CSV
    keys = records[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(records)
        
    print(f"Generated {len(records)} mock AIS records (including duplicates/anomalies) in '{filename}'")

if __name__ == "__main__":
    generate_mock_data()
