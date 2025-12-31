import sqlite3
import pandas as pd
import os

# Configuration
DB_NAME = 'tgsrtc.db'
DATA_FOLDER = 'Telangana' # Put your .txt files here

def init_db():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print("🚀 Creating Tables...")
    
    # 1. Stops
    cursor.execute('''
        CREATE TABLE stops (
            stop_id TEXT PRIMARY KEY,
            stop_name TEXT,
            stop_lat REAL,
            stop_lon REAL
        )
    ''')

    # 2. Routes
    cursor.execute('''
        CREATE TABLE routes (
            route_id TEXT PRIMARY KEY,
            route_short_name TEXT,
            route_long_name TEXT
        )
    ''')

    # 3. Trips
    cursor.execute('''
        CREATE TABLE trips (
            route_id TEXT,
            trip_id TEXT PRIMARY KEY,
            service_id TEXT,
            trip_headsign TEXT,
            trip_short_name TEXT,
            bus_class TEXT
        )
    ''')

    # 4. Stop Times (The big one)
    cursor.execute('''
        CREATE TABLE stop_times (
            trip_id TEXT,
            stop_id TEXT,
            arrival_time TEXT,
            departure_time TEXT,
            stop_sequence INTEGER
        )
    ''')

    conn.commit()
    return conn

def load_data(conn):
    print("📥 Loading Routes...")
    routes_df = pd.read_csv(f'{DATA_FOLDER}/routes.txt', dtype=str)
    routes_df[['route_id', 'route_short_name', 'route_long_name']].to_sql('routes', conn, if_exists='append', index=False)

    print("📥 Loading Stops...")
    stops_df = pd.read_csv(f'{DATA_FOLDER}/stops.txt', dtype={'stop_id': str})
    stops_df = stops_df[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
    stops_df.to_sql('stops', conn, if_exists='append', index=False)

    print("📥 Loading Trips...")
    trips_df = pd.read_csv(f'{DATA_FOLDER}/trips.txt', dtype=str)
    # Map CSV columns to DB columns if names differ slightly
    trips_df[['route_id', 'trip_id', 'service_id', 'trip_headsign', 'trip_short_name', 'bus_class']].to_sql('trips', conn, if_exists='append', index=False)

    print("📥 Loading Stop Times (This might take a minute)...")
    # Read in chunks because this file is huge
    chunksize = 100000
    for chunk in pd.read_csv(f'{DATA_FOLDER}/stop_times.txt', dtype=str, chunksize=chunksize):
        chunk[['trip_id', 'stop_id', 'arrival_time', 'departure_time', 'stop_sequence']].to_sql('stop_times', conn, if_exists='append', index=False)
        print(f"   Processed {len(chunk)} rows...")

    print("🔨 Creating Indexes for Speed...")
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX idx_stop_name ON stops(stop_name)")
    cursor.execute("CREATE INDEX idx_st_trip_id ON stop_times(trip_id)")
    cursor.execute("CREATE INDEX idx_st_stop_id ON stop_times(stop_id)")
    cursor.execute("CREATE INDEX idx_trips_route_id ON trips(route_id)")
    conn.commit()

    print("✅ TGSRTC Database Built Successfully!")
    conn.close()

if __name__ == "__main__":
    conn = init_db()
    load_data(conn)