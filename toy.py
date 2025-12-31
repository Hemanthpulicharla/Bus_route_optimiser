import requests
import json
from datetime import datetime

class KSRTCBusTracker:
    def __init__(self, city_file="place_id_kr.json"):
        self.session = requests.Session()
        self.city_map = {}
        self.load_cities(city_file)
        self.init_session()

    def load_cities(self, file_path):
        """Loads the city JSON file to map 'Mangalore' -> '30'"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
                # The file structure is {"success":true, "data": {"0":{...}, "1":{...}}}
                if raw.get('success'):
                    for k, v in raw['data'].items():
                        # Map lowercase name to ID
                        self.city_map[v['Name'].lower().strip()] = v['ID']
                    print(f"✅ Loaded {len(self.city_map)} cities.")
                else:
                    print("❌ Invalid JSON format in place_id_kr.json")
        except FileNotFoundError:
            print(f"❌ File {file_path} not found.")

    def init_session(self):
        """Sets up headers to look like a real browser"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://ksrtc.in/oprs-web/',
            'Content-Type': 'application/json'
        })
        # Visit home to get cookies
        try:
            self.session.get('https://ksrtc.in/oprs-web/')
        except:
            pass

    def get_city_id(self, name):
        return self.city_map.get(name.lower().strip())

    def parse_and_display(self, bus_list):
        """
        THIS IS THE PART YOU NEEDED:
        Extracts Time, Price, and Duration from the JSON response.
        """
        print(f"\nFound {len(bus_list)} Buses:\n")
        
        for bus in bus_list:
            # 1. GET RAW DATA
            # The JSON keys based on your provided log
            svc_type = bus.get('ServiceType', 'Bus')
            fare = bus.get('Fare', 0)
            seats = bus.get('AvailableSeats', 0)
            trip_code = bus.get('TripCode', 'N/A')
            
            # 2. PARSE TIMINGS (ISO Format: 2025-12-15T22:15:00)
            dep_str = bus.get('DepartureTime')
            arr_str = bus.get('ArrivalTime')
            
            # Convert string to Python datetime objects
            dep_dt = datetime.strptime(dep_str, "%Y-%m-%dT%H:%M:%S")
            arr_dt = datetime.strptime(arr_str, "%Y-%m-%dT%H:%M:%S")
            
            # Calculate Duration
            duration = arr_dt - dep_dt
            
            # Format for display (e.g., "22:15")
            dep_display = dep_dt.strftime("%H:%M") 
            arr_display = arr_dt.strftime("%H:%M")
            # Format Date (e.g. "16 Dec")
            arr_date_display = arr_dt.strftime("%d %b")

            # 3. PRINT RESULT
            print("-" * 60)
            print(f"🚌 {svc_type} ({trip_code})")
            print(f"🕒 {dep_display} ➝ {arr_display} ({arr_date_display})")
            print(f"⏱️  Duration: {duration}")
            print(f"💰 Price: ₹{fare}")
            print(f"💺 Seats Available: {seats}")
            print("-" * 60)

    def search(self, from_city, to_city, date_str):
        # 1. Get IDs
        fid = self.get_city_id(from_city)
        tid = self.get_city_id(to_city)

        if not fid or not tid:
            print("❌ City not found in local DB")
            return

        # 2. Prepare API URL
        url = "https://ksrtc.in/api/resource/searchRoutesV4"
        params = {
            'fromCityID': fid,
            'toCityID': tid,
            'fromCityName': from_city,
            'toCityName': to_city,
            'journeyDate': date_str, # YYYY-MM-DD
            'mode': 'oneway'
        }

        # 3. Fetch
        print(f"🔎 Searching {from_city} -> {to_city} on {date_str}...")
        resp = self.session.get(url, params=params)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                self.parse_and_display(data)
            else:
                print("⚠️ No buses found or unexpected format.")
        else:
            print(f"❌ Error: {resp.status_code}")

# --- EXECUTION ---
if __name__ == "__main__":
    tracker = KSRTCBusTracker()
    
    # Change the date to a valid future date!
    tracker.search("Mangalore", "Bengaluru", "2025-12-15")