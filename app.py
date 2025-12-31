from flask import Flask, request, jsonify,render_template
from flask_cors import CORS
import requests
import json
from datetime import datetime , timedelta
import math
import time
import sqlite3
from bs4 import BeautifulSoup


ORS_API_KEY="eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjUzNmEzNWQxODNhMjQ4ZGZiZDRlZmJiZTMxZDkwMDU3IiwiaCI6Im11cm11cjY0In0="
Base_url="https://api.openrouteservice.org"


app=Flask(__name__)

APSRTC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Authorization": "Bearer abhibus",
    "Content-Type": "application/json",
    "Origin": "https://apsrtclivetrack.com",
    "Referer": "https://apsrtclivetrack.com/",
    "x-api-key": "53693855434468454E714A596D44457A586975414F573833334833596A584D3333735938444A69357131303D"}
try:
    with open('place_id.json', 'r') as f:
        APSRTC_DATA = json.load(f)
        print(f"Loaded {len(APSRTC_DATA)} stops.")
except Exception as e:
    print(f"Error loading JSON: {e}")
    APSRTC_DATA = []
try:
    with open('placeid_kerela.json', 'r') as f:
        KSRTC_DATA = json.load(f)
        print(f"Loaded {len(KSRTC_DATA)} KSRTC stops.")
except Exception as e:
    print(f"Error loading KSRTC JSON: {e}")
    KSRTC_DATA = []
try:
    with open('placeid_tnstc_template.json', 'r') as f:
        TNSTC_DATA = json.load(f)
        print(f"Loaded {len(TNSTC_DATA)} TNSTC stops.")
except Exception as e:
    print(f"Error loading TNSTC JSON: {e}")
    TNSTC_DATA = []

try:
    with open('place_id_kr.json', 'r', encoding='utf-8') as f:
        raw_kr_data = json.load(f)
        KSRTC_KARNATAKA_MAP = {}
        if raw_kr_data.get('success') and 'data' in raw_kr_data:
            for k, v in raw_kr_data['data'].items():
                city_name = v['Name'].strip().upper()
                KSRTC_KARNATAKA_MAP[city_name] = v['ID']
        print(f"Loaded {len(KSRTC_KARNATAKA_MAP)} KSRTC Karnataka stops.")
except Exception as e:
    print(f"Error loading KSRTC Karnataka JSON: {e}")
    KSRTC_KARNATAKA_MAP = {}

class TNSTCSessionManager:
    def __init__(self):
        self.session = requests.Session()
        self.last_refresh_time = 0
        self.refresh_interval = 15 * 60 
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.tnstc.in",
            "Referer": "https://www.tnstc.in/OTRSOnline/jqreq.do?hiddenAction=SearchService",
            "X-Requested-With": "XMLHttpRequest"
        }
        self.session.headers.update(self.headers)

    def refresh_session(self):
        try:
            self.session.get("https://www.tnstc.in/home.do", timeout=10)
            
            self.session.get("https://www.tnstc.in/OTRSOnline/jqreq.do?hiddenAction=SearchService", timeout=10)
            
            self.last_refresh_time = datetime.now().timestamp()
        except Exception as e:
            print(f"Failed to refresh session: {e}")

    def get_valid_session(self):
        current_time = datetime.now().timestamp()
        if (current_time - self.last_refresh_time) > self.refresh_interval:
            self.refresh_session()    
        return self.session


class BusCache:
    def __init__(self, db_path='bus_cache.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self): 
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bus_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                from_place TEXT NOT NULL,
                to_place TEXT NOT NULL,
                search_date TEXT NOT NULL,
                buses_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hit_count INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_search 
            ON bus_searches(state, from_place, to_place, search_date)
        ''')
        
        conn.commit()
        conn.close()
        print("Bus cache database started")
    
    def get_cached_buses(self, state, from_place, to_place, max_age_hours=2):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        cursor.execute('''
            SELECT buses_data, created_at, hit_count, id
            FROM bus_searches
            WHERE state = ? 
            AND from_place = ? 
            AND to_place = ?
            AND search_date = ?
            AND created_at > ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (state, from_place.upper(), to_place.upper(), today, cutoff_time.isoformat()))
        
        row = cursor.fetchone()
        
        if row:
            buses_data, created_at, hit_count, cache_id = row
            
            cursor.execute('''
                UPDATE bus_searches 
                SET hit_count = hit_count + 1 
                WHERE id = ?
            ''', (cache_id,))
            conn.commit()
            
            conn.close()
            
            print(f"CACHE HIT: {state} {from_place}→{to_place} (hits: {hit_count + 1}, age: {created_at})")
            
            return {
                'cached': True,
                'data': json.loads(buses_data),
                'cached_at': created_at,
                'hit_count': hit_count + 1
            }
        
        conn.close()
        print(f"CACHE MISS: {state} {from_place}→{to_place}")
        return None
    
    def save_buses(self, state, from_place, to_place, buses_data):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute('''
            SELECT id FROM bus_searches
            WHERE state = ? 
            AND from_place = ? 
            AND to_place = ?
            AND search_date = ?
        ''', (state, from_place.upper(), to_place.upper(), today))
        
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE bus_searches
                SET buses_data = ?,
                    created_at = CURRENT_TIMESTAMP,
                    hit_count = 1
                WHERE id = ?
            ''', (json.dumps(buses_data), existing[0]))
            print(f"CACHE UPDATED: {state} {from_place}→{to_place}")
        else:
            cursor.execute('''
                INSERT INTO bus_searches 
                (state, from_place, to_place, search_date, buses_data)
                VALUES (?, ?, ?, ?, ?)
            ''', (state, from_place.upper(), to_place.upper(), today, json.dumps(buses_data)))
            print(f"CACHE SAVED: {state} {from_place}→{to_place}")
        
        conn.commit()
        conn.close()
    
    def cleanup_old_cache(self, days_old=7):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime("%Y-%m-%d")
        
        cursor.execute('''
            DELETE FROM bus_searches
            WHERE search_date < ?
        ''', (cutoff_date,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            print(f"Cleaned up {deleted} old cache entries")
        return deleted
bus_cache = BusCache()
bus_cache.cleanup_old_cache(days_old=100)

tnstc_manager = TNSTCSessionManager()
TNSTC_PLACE_CODES = {}
TNSTC_JSON_MAP = {}

try:
    import csv
    with open('SETC_tn.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_c = row.get('From', '').strip().upper()
            to_c = row.get('To', '').strip().upper()
            if from_c: TNSTC_PLACE_CODES[from_c] = from_c[:3]
            if to_c: TNSTC_PLACE_CODES[to_c] = to_c[:3]
    print(f"Loaded {len(TNSTC_PLACE_CODES)} TNSTC CSV codes.")
except Exception as e:
    print(f"Error loading SETC_tn.csv: {e}")

try:
    with open('placeid_tnstc_template.json', 'r') as f:
        tnstc_places = json.load(f)
        for place in tnstc_places:
            p_name = place.get('value', '').strip().upper()
            p_id = place.get('id', '')
            if p_name and p_id:
                TNSTC_JSON_MAP[p_name] = p_id
    print(f"Loaded {len(TNSTC_JSON_MAP)} TNSTC JSON IDs.")
except Exception as e:
    print(f"Error loading TNSTC JSON map: {e}")

def sunposition(lat,lon,timestamp):

	lat_rad=math.radians(lat)
	long_rad=math.radians(lon)
	day_of_year=timestamp.timetuple().tm_yday
	hour=timestamp.hour+timestamp.minute/60.0
	declination=23.45 *math.sin(math.radians(360 * (day_of_year)/365)) # yes that is 23.45 since day is not like 24 hours rather 1/4 less 24
	dec_rad=math.radians(declination)
	hour_angle=15*(hour-12) # 15 degree per hour 

	ha_rad=math.radians(hour_angle)

	sun_altitude=(math.sin(lat_rad)*math.sin(dec_rad)+ math.cos(lat_rad)*math.cos(dec_rad)*math.cos(ha_rad))
	altitude = math.degrees(math.asin(sun_altitude))

	cos_azimuth=((math.sin(dec_rad)-math.sin(lat_rad)*sun_altitude)/(math.cos(lat_rad)*math.cos(math.asin(sun_altitude))))
	cos_azimuth = max(-1,min(1,cos_azimuth))
	azimuth=math.degrees(math.acos(cos_azimuth))

	if hour >12:
		azimuth=360-azimuth

	return azimuth,altitude

def bearing_calculation(lat1,long1,lat2,long2):

	lat1,long1,lat2,long2=map(math.radians,[lat1,long1,lat2,long2])

	dlong=long2-long1

	x=math.sin(dlong) * math.cos(lat2)
	y=(math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlong))

	bearing= math.atan2(x,y)
	bearing=math.degrees(bearing)
	bearing = (bearing + 360) % 360


	return bearing


def shade_finder(coordinates,start_time_str,duration_min):

	hour,minute=map(int,start_time_str.split(':'))

	start_time=datetime.now().replace(hour=hour,minute=minute,second=0,microsecond=0)

	shade_data=[]

	total_segments=len(coordinates)-1

	left_side_time=0
	right_side_time=0
	print(hour)
	if hour >= 18 or hour <6:
		return{
		'preferred_side': 'N/A',
            'preferred_window': 'Night journey - shade analysis not applicable',
            'left_shade_minutes': 0,
            'right_shade_minutes': 0,
            'shade_percentage': 0,
            'total_duration': duration_min,
            'is_night': True,
            'segments': []
		}

	for i in range(total_segments):

		lat1,long1=coordinates[i][1],coordinates[i][0]
		lat2,long2=coordinates[i+1][1],coordinates[i+1][0]

		segment_time=start_time.timestamp() + (duration_min * 60 * i/total_segments)
		current_time=datetime.fromtimestamp(segment_time)

		bearing= bearing_calculation(lat1,long1,lat2,long2)

		sun_azimuth,sun_altitude=sunposition(lat1,long1,current_time)

		if sun_altitude <0:
			continue
		relative_angle=(sun_azimuth - bearing + 360) % 360

		if 90 <= relative_angle <=270:
			shade_side="LEFT"
			left_side_time +=(duration_min/total_segments)
		else:
			shade_side="Right"
			right_side_time+=(duration_min/total_segments)
		shade_data.append({
			'segment':i,
			'bearing':round(bearing,2),
			'sun_azimuth': round(sun_azimuth,2),
			'sun_altitude':round(sun_altitude,2),
			'shade_side':shade_side,
			'time':current_time.strftime('%H:%M')

			})	
	if left_side_time > right_side_time:
		preferred_side="LEFT"
		preferred_window="Windows on the left side"
		shade_percentage=round((left_side_time/duration_min)*100,1)
	else:
		preferred_side="Right"
		preferred_window="Windows on the Right"
		shade_percentage=round((right_side_time/duration_min)*100,1)
	return {
        'preferred_side': preferred_side,
        'preferred_window': preferred_window,
        'left_shade_minutes': round(left_side_time, 1),
        'right_shade_minutes': round(right_side_time, 1),
        'shade_percentage': shade_percentage,
        'total_duration': duration_min,
        'segments': shade_data[:5]
    }

def scrape_fare_only(from_id, to_id):
    
    today_str = datetime.now().strftime("%d/%m/%Y")
    web_url = "https://www.apsrtconline.in/oprs-web/forward/booking/avail/services.do"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.apsrtconline.in/oprs-web/",
    }
    
    params = {
        "txtJourneyDate": today_str,
        "startPlaceId": from_id,
        "endPlaceId": to_id,
        "txtLinkJourneyDate": today_str,
        "ajaxAction": "fw",
        "qryType": "0"
    }
    
    try:
        response = requests.get(web_url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            fare_map = {}
            
            # Find all bus services
            services = soup.find_all('div', class_='rSetForward')
            
            for service in services:
                try:
                    # Get bus number
                    bus_no_tag = service.find('div', class_='srvceNO')
                    bus_no = bus_no_tag.get_text(strip=True) if bus_no_tag else None
                    
                    # Get fare (THIS IS THE KEY PART)
                    fare_tag = service.find('span', class_='TickRate')
                    fare = fare_tag.get_text(strip=True) if fare_tag else "N/A"
                    
                    if bus_no:
                        fare_map[bus_no] = fare
                        
                except Exception as e:
                    continue
            
            return fare_map
        else:
            return {}
            
    except Exception as e:
        print(f"Fare scraping error: {e}")
        return {}

def detect_state_from_label(label):
    label_upper = label.upper()
    parts = [part.strip() for part in label.split(',')]
    if len(parts) >= 2:
        state_code = parts[1].upper()
        kerala_codes = ['KL', 'KERALA']
        andhra_codes = ['AP', 'ANDHRA PRADESH']
        if state_code in kerala_codes:
            return 'KSRTC'
        elif state_code in andhra_codes:
            return 'APSRTC'
    city = parts[0].upper() if parts else label.upper()
    
    kerala_keywords = ['KERALA', 'KANNUR', 'KOCHI', 'THIRUVANANTHAPURAM', 
                       'KOZHIKODE', 'THRISSUR', 'PALAKKAD', 'MALAPPURAM',
                       'KOLLAM', 'ALAPPUZHA', 'KOTTAYAM', 'IDUKKI', 
                       'ERNAKULAM', 'KASARAGOD', 'WAYANAD', 'PATHANAMTHITTA']
    andhra_keywords = ['ANDHRA PRADESH', 'VIJAYAWADA', 'VISAKHAPATNAM', 
                       'TIRUPATI', 'GUNTUR', 'NELLORE', 'KAKINADA',
                       'RAJAHMUNDRY', 'KADAPA', 'ANANTAPUR', 'KURNOOL',
                       'VIZIANAGARAM', 'ELURU', 'ONGOLE', 'NANDYAL',
                       'MACHILIPATNAM', 'TENALI', 'CHITTOOR', 'HINDUPUR',
                       'PRODDATUR', 'BHIMAVARAM', 'MADANAPALLE', 'GUNTAKAL',
                       'DHARMAVARAM', 'GUDIVADA', 'SRIKAKULAM', 'NARASARAOPET',
                       'TADIPATRI', 'TADEPALLIGUDEM', 'CHILAKALURIPET']

    tamil_keywords = ['TAMIL NADU', 'CHENNAI', 'COIMBATORE', 'MADURAI', 
                      'TRICHY', 'TIRUCHIRAPPALLI', 'SALEM', 'TIRUNELVELI',
                      'ERODE', 'VELLORE', 'THOOTHUKUDI', 'THANJAVUR',
                      'DINDIGUL', 'CUDDALORE', 'KANCHIPURAM', 'TIRUPPUR',
                      'KARUR', 'RAJAPALAYAM', 'SIVAKASI', 'NAGERCOIL',
                      'KUMBAKONAM', 'PUDUKKOTTAI', 'HOSUR','TN']

    karnataka_keywords = ['KARNATAKA', 'BENGALURU', 'BANGALORE', 'MANGALORE', 'MYSURU', 'MYSORE', 'HUBLI', 'BELGAUM', 'SHIVAMOGGA', 'HASSAN', 'UDUPI','KR','KA']
    tg_cities = ['HYDERABAD', 'WARANGAL', 'NIZAMABAD', 'KARIMNAGAR', 'KHAMMAM', 'SECUNDERABAD', 'KUKATPALLY', 'DILSUKHNAGAR', 'MIYAPUR', 'GACHIBOWLI','TG','TS']
    
    label_upper = label.upper()
    
    for city in tg_cities:
        if city in label_upper:
            return 'TGSRTC' 
    for ka_city in karnataka_keywords:
        if ka_city in city:
            return 'KSRTC-KA'
    for tcity in tamil_keywords:
        if tcity in city:
            return 'TNSTC'    

    for kcity in kerala_keywords:
        if kcity in city:
            return 'KSRTC'
    
    # Check Andhra Pradesh
    for acity in andhra_keywords:
        if acity in city:
            return 'APSRTC'

    return 'APSRTC'
@app.route('/get_route', methods=['POST'])
def get_route():
    req_data = request.get_json()
    if not req_data:
        return jsonify({"error": "No data received"}), 400

    start_coords = req_data.get('start', [77.2090, 28.6139])
    end_coords = req_data.get('end', [78.0081, 27.1767]) 

    url = f"{Base_url}/v2/directions/driving-hgv/geojson"
    params = {
        "coordinates": [start_coords, end_coords]
    }
    
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": 'application/json'
    }
    response = requests.post(url, json=params, headers=headers)

    if response.status_code != 200:
        print("API Error:", response.text)
        return jsonify({"error": "ERROR HAI BHAI!! ERROS"}), 400

    data = response.json()

    try:
        r_coordinate = data['features'][0]['geometry']['coordinates']
        summary = data['features'][0]['properties']['summary']
        dist_km=round(summary['distance']/1000,1)
        duration_sec=summary['duration']
        duration_minutes = int(duration_sec / 60)
        hours=int(duration_sec//3600)
        current_time_str = datetime.now().strftime("%H:%M")
        shade_info = shade_finder(r_coordinate, current_time_str, duration_minutes)
        print('here')
        minutes=int((duration_sec %3600)//60)
        duration_str=f"{hours}h {minutes}min" if hours>0 else f"{minutes}min"
        
        leafly = [[coord[1], coord[0]] for coord in r_coordinate]
        print(duration_str)

        return jsonify({
            'path': leafly,
            'start_point': [start_coords[1], start_coords[0]],
            'end_point': [end_coords[1], end_coords[0]],
            'distance': f"{dist_km} km",
            'duration': duration_str,
            'shade_analysis': shade_info
        })
    except (KeyError, IndexError) as e:
        return jsonify({"error": "Could not parse route data"}), 500
@app.route('/api/search',methods=['GET'])
def api_search():
    query=request.args.get('q','')
    if len(query)<3:
        return jsonify([])
    url=f'{Base_url}/geocode/search'
    param={
	"api_key":ORS_API_KEY,
	"text":query,
	"size":5,
	"boundary.country":"IN"
	}
    try:
        response=requests.get(url,params=param)
        if response.status_code ==200:
            data=response.json()
            suggestions=[]
            for feature in data.get('features',[]):
                label=feature['properties']['label']
                state=detect_state_from_label(label)
                print(state)
                suggestions.append({
					"label":feature['properties']['label'],
					"coords":feature['geometry']['coordinates'],
                    "state":state
					})
            return jsonify(suggestions)
    except Exception as e:
        print(f"Geocode error:{e}")
    return jsonify([])

@app.route('/api/resolve-apsrtc-id',methods=['POST'])
def get_place_id():
    req_data=request.get_json()
    if not req_data or 'address' not in req_data:
        return jsonify({"error":"YEH SAHI BHAT NAHI HAI.. I got not place to give ID for"}),400

    search_string = req_data.get('address','').upper()
    state=req_data.get('state','APSRTC')
    if state == 'KSRTC':
        data_source = KSRTC_DATA
    elif state == 'TNSTC':
        data_source = TNSTC_DATA
    else:
        data_source = APSRTC_DATA
    for depot in data_source:
        stop_name = depot.get('value','').upper()
        if stop_name and stop_name in search_string:
            return jsonify({
				"id":depot['id'],
				 "code": depot.get('code', ''),
				"match":depot['value']
				})
    return jsonify({ "id":None})

@app.route('/api/find-buses',methods=['POST'])
def findbus():
	req_data = request.get_json()
	from_id = req_data.get('fromId')
	from_name = req_data.get('fromName', 'Unknown')
	to_name = req_data.get('toName', 'Unknown')
	to_id = req_data.get('toId')
	if not from_id or not to_id:
		return jsonify({"error": "Missing Start or End IDs"}), 400
	url = "https://utsappapicached01.apsrtconline.in/uts-vts-api/services/all"
	try:
		payload = {
            "sourceLinkId": int(from_id),
            "destinationLinkId": int(to_id),
            "sourcePlaceId": int(from_id),
            "destinationPlaceId": int(to_id),
            "userId": "1363789069449", 
            "versionCode": "2020254",
            "apiVersion": 1
        }
	except ValueError:
		return jsonify({"error": "IDs must be numeric"}), 400
	try:
		response = requests.post(url, headers=APSRTC_HEADERS, json=payload)
		if response.status_code == 200:
			data = response.json()
			fare_data=scrape_fare_only(from_id,to_id)
			fare_map=fare_data
			fare_value=[]
			for fare in fare_map.values():
				try:
					fare_value.append(int(fare))
				except:
					pass
			avg_fare = round(sum(fare_value) / len(fare_value)) if fare_value else None
			if data.get('data') and isinstance(data['data'],list):
				for bus in data['data']:
					bus_no=bus.get('oprsNo','').strip()
					bus['fare']=fare_map.get(bus_no,'N/A')
					print(bus['fare'])
				data['averageFare'] = avg_fare

			bus_cache.save_buses('APSRTC', from_name, to_name, data)
			return jsonify(data)
		else:
			print(f"APSRTC Error: {response.status_code} - {response.text}")
			return jsonify({"error": "External API Failed", "details": response.text}), 500

	except Exception as e:
		print(f"Request Error: {e}")
		return jsonify({"error": str(e)}), 500

@app.route('/api/find-buses2', methods=['POST'])
def findbus2():
    req_data = request.get_json()
    from_id = req_data.get('fromId')
    to_id = req_data.get('toId')

    if not from_id or not to_id:
        return jsonify({"error": "Missing Start or End IDs"}), 400

    today_str = datetime.now().strftime("%d/%m/%Y")
    
    web_url = "https://www.apsrtconline.in/oprs-web/forward/booking/avail/services.do"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.apsrtconline.in/oprs-web/",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = {
        "txtJourneyDate": today_str,
        "startPlaceId": from_id,
        "endPlaceId": to_id,
        "txtLinkJourneyDate": today_str,
        "ajaxAction": "fw",
        "covidBkgEnable": "",
        "qryType": "0"
    }

    try:
        response = requests.get(web_url, headers=headers, params=params)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            bus_list = []
            services = soup.find_all('div', class_='result-grid-box')
            if not services:
                services = soup.select('.srvceNO') 
            results = soup.find_all('div', class_='search-result-item') 
            if not results:
                 results = soup.find_all('div', class_='rSet')

            for service in results:
                try:

                    type_tag = service.find('h3') or service.find('div', class_='srvceName')
                    srv_type = type_tag.get_text(strip=True) if type_tag else "BUS"


                    no_tag = service.find('div', class_='srvceNO')
                    oprs_no = no_tag.get_text(strip=True) if no_tag else "N/A"

                    start_tag = service.find('span', class_='startTime')
                    end_tag = service.find('span', class_='endTime')
                    
                    start_time = start_tag.get_text(strip=True) if start_tag else "00:00"
                    end_time = end_tag.get_text(strip=True) if end_tag else "00:00"
                    bus_obj = {
                        "oprsNo": oprs_no,
                        "serviceType": srv_type,
                        "serviceStartTime": start_time,
                        "serviceEndTime": end_time,
                        "depotName": "APSRTC", # Web results often hide depot name
                        "journeyDate": today_str
                    }
                    bus_list.append(bus_obj)
                except Exception as p_err:
                    print(f"Skipped a row due to error: {p_err}")
                    continue

            print(f"Parsed {len(bus_list)} buses from HTML.")
            return jsonify(bus_list)
            
        else:
            print(f"Web Error: {response.status_code}")
            return jsonify({"error": "Web Failed"}), 500

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-bus-stops', methods=['POST'])
def get_bus_stops():
    req_data = request.get_json()
    doc_id = req_data.get('docId')
    
    if not doc_id:
        return jsonify({"error": "Missing docId"}), 400

    url = "https://utsappapicached01.apsrtconline.in/uts-vts-api/servicewaypointdetails/bydocid"
    
    # Using the headers you provided
    payload = {"docId": doc_id}
    
    try:
        response = requests.post(url, headers=APSRTC_HEADERS, json=payload)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Failed to fetch stops", "details": response.text}), response.status_code
    except Exception as e:
        print(f"Stops API Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/find-buses-kerala', methods=['POST'])
def find_buses_kerala():
    req_data = request.get_json()
    
    from_name = req_data.get('fromName', '').split(',')[0].strip().upper()
    to_name = req_data.get('toName', '').split(',')[0].strip().upper()
    
    if not from_name or not to_name:
        return jsonify({"error": "Missing Locations"}), 400
    
    src_slug = from_name.replace(" ", "-")
    dst_slug = to_name.replace(" ", "-")
    
    base_url = f"https://www.kbuses.in/v3/Find/source/{src_slug}/destination/{dst_slug}/type/all/timing/all"
    
    print(f"🔍 Fetching Kerala buses from: {base_url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.kbuses.in/"
    }

    all_buses = []
    current_page = 1
    max_pages = 10
    
    try:
        while current_page <= max_pages:
            if current_page == 1:
                page_url = base_url
            else:
                page_url = f"{base_url}?page={current_page}"
            
            response = requests.get(page_url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                print(f"{current_page} returned status: {response.status_code}")
                break
            
            soup = BeautifulSoup(response.text, 'html.parser')
            bus_containers = soup.find_all('div', class_='indibus')
            
            if len(bus_containers) == 0:
                print(f"No more buses found: {current_page}.")
                break
            
            print(f"Found {len(bus_containers)} buses: {current_page}")
            
            for container in bus_containers:
                try:
                   
                    bus_name_elem = container.find('span', class_='busname')
                    if bus_name_elem:
                        for icon in bus_name_elem.find_all('svg'):
                            icon.decompose()
                        bus_name = bus_name_elem.get_text(strip=True)
                    else:
                        bus_name = "KSRTC"

                   
                    bus_type_elem = container.find('div', class_='bustype')
                    bus_type = bus_type_elem.get_text(strip=True) if bus_type_elem else "Ordinary"

                    
                    time_elem = container.find('span', class_='large_bold')
                    start_time = time_elem.get_text(strip=True) if time_elem else "N/A"

                   
                    small_txts = container.find_all('span', class_='smalltxt')
                    end_time = None
                    duration = None
                    
                    for span in small_txts:
                        txt = span.get_text(strip=True)
                        
                        if "@" in txt:
                            parts = txt.split('@')
                            if len(parts) > 1:
                                end_time = parts[1].strip()
                        
                        elif "hour" in txt.lower() or "minute" in txt.lower():
                            duration = txt
                    route_info = ""
                    details_elem = container.find('details')
                    if details_elem:
                        route_p = details_elem.find('p')
                        if route_p:
                            route_info = route_p.get_text(strip=True)
                    fare = None
                    bus_info_divs = container.find_all('div', class_='bus-info')
                    for div in bus_info_divs:
                        fare_text = div.get_text()
                        if 'Fare:' in fare_text or '₹' in fare_text:
                            import re
                            fare_match = re.search(r'₹\s*(\d+)', fare_text)
                            if fare_match:
                                fare = fare_match.group(1)
                                break

                    detail_url = None
                    detail_link = container.find('a', class_='btn-outline-success')
                    
                    if detail_link and detail_link.has_attr('href'):
                        href = detail_link.get('href')
                        if href.startswith('/'):
                            detail_url = f"https://www.kbuses.in{href}"
                        elif href.startswith('http'):
                            detail_url = href
                        else:
                            detail_url = f"https://www.kbuses.in/{href}"

                    bus_obj = {
                        "oprsNo": bus_name,
                        "serviceType": bus_type,
                        "serviceStartTime": start_time,
                        "serviceEndTime": end_time if end_time else "N/A",
                        "duration": duration if duration else "N/A",
                        "fare": fare if fare else "N/A",
                        "depotName": "KERALA",
                        "serviceDocId": detail_url,  # This is the critical field for stops
                        "route": route_info,
                        "journeyDate": datetime.now().strftime("%d/%m/%Y"),
                        "page": current_page
                    }
                    
                    all_buses.append(bus_obj)

                except Exception as parse_err:
                    print(f"Error parsing bus: {parse_err}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            pagination = soup.find('nav', {'aria-label': 'Page navigation'})
            if not pagination:
                break
            
            next_link = None
            for link in pagination.find_all('a'):
                if 'Next' in link.get_text():
                    next_link = link.get('href')
                    break
            
            if not next_link:
                print(f"No more pages. Stopping: {current_page}.")
                break
            
            current_page += 1
        
        print(f"Total buses scraped: {len(all_buses)} from {current_page} pages")
        
        return jsonify({
            "data": all_buses, 
            "source": "KBuses", 
            "totalPages": current_page,
            "totalBuses": len(all_buses)
        })

    except requests.Timeout:
        print("Request timeout")
        return jsonify({"error": "Request timeout"}), 504
    except Exception as e:
        print(f"Scraper Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/get-kerala-bus-stops', methods=['POST'])
def get_kerala_bus_stops():
    req_data = request.get_json()
    detail_url = req_data.get('detailUrl')
    
    if not detail_url:
        return jsonify({"error": "Missing detail URL"}), 400
    
    if detail_url.startswith('/'):
        detail_url = f"https://www.kbuses.in{detail_url}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.kbuses.in/"
    }
    
    try:
        response = requests.get(detail_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return jsonify({"error": f"Failed to fetch bus details: {response.status_code}"}), 500
        
        soup = BeautifulSoup(response.text, 'html.parser')
        stops = []
  
        table = soup.find('table', class_='table-hover')
        
        if table:
           
            rows = table.find_all('tr')
            
            current_stop_name = ""
            
            for row in rows:
                
                header_th = row.find('th', class_='cell1')
                if header_th:
                    current_stop_name = header_th.get_text(strip=True)
                    continue
                
                
                cols = row.find_all('td')
                if cols and len(cols) >= 2 and current_stop_name:
                    stop_time = cols[1].get_text(strip=True)
                    
                    
                    detail_name = cols[0].get_text(strip=True)
                    
                    stops.append({
                        "placeName": current_stop_name,
                        "detailName": detail_name,      
                        "scheduleArrTime": stop_time,
                        "seqNo": len(stops) + 1
                    })
                    
                   
                    current_stop_name = ""
        
      
        if not stops:
            indibus_div = soup.find('div', class_='card indibus smalltxt')
            if indibus_div:
                via_div = indibus_div.find('div', style="padding: 5px;")
                if via_div:
                    text = via_div.get_text(strip=True)
                    if "Via" in text:
                        
                        clean_text = text.replace("Via ➥", "").replace("Via", "")
                        parts = clean_text.split('⤳')
                        for i, part in enumerate(parts):
                            stops.append({
                                "placeName": part.strip(),
                                "scheduleArrTime": "--:--", 
                                "seqNo": i + 1
                            })

        print(f"Extracted {len(stops)} stops for K bus")
        return jsonify({"data": stops})
        
    except Exception as e:
        print(f"Error fetching Kerala bus stops: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/find-buses-tnstc', methods=['POST'])
def find_buses_tnstc():
    req_data = request.get_json()
    
    # 1. Input Handling
    from_name = req_data.get('fromName', '')
    to_name = req_data.get('toName', '')
    
    if not from_name or not to_name:
        return jsonify({"error": "Missing location names"}), 400
    
    from_place = from_name.split(',')[0].strip().upper()
    to_place = to_name.split(',')[0].strip().upper()
    
    print(f"\nTNSTC Request: {from_place} -> {to_place}")

    from_code = TNSTC_PLACE_CODES.get(from_place, from_place[:3])
    to_code = TNSTC_PLACE_CODES.get(to_place, to_place[:3])
    
    if from_place not in TNSTC_PLACE_CODES:
        for k, v in TNSTC_PLACE_CODES.items():
            if from_place in k: from_code = v; break
    if to_place not in TNSTC_PLACE_CODES:
        for k, v in TNSTC_PLACE_CODES.items():
            if to_place in k: to_code = v; break

    from_id = TNSTC_JSON_MAP.get(from_place)
    to_id = TNSTC_JSON_MAP.get(to_place)

    if not from_id:
        for k, v in TNSTC_JSON_MAP.items():
            if from_place in k: from_id = v; break
    if not to_id:
        for k, v in TNSTC_JSON_MAP.items():
            if to_place in k: to_id = v; break
    PLACE_ID_MAP = {
        'TRICHY': '74', 'TIRUCHIRAPPALLI': '74', 'COIMBATORE': '114',
        'CHENNAI': '1358', 'MADURAI': '190', 'SALEM': '533',
        'KUMBAKONAM': '80', 'THANJAVUR': '190', 'TIRUNELVELI': '190',
        'ERODE': '190', 'KARUR': '190'
    }
    if not from_id: from_id = PLACE_ID_MAP.get(from_place)
    if not to_id: to_id = PLACE_ID_MAP.get(to_place)

    if not from_id or not to_id:
        return jsonify({"error": f"Place ID not found for {from_place} or {to_place}"}), 400

    today_str = datetime.now().strftime("%d/%m/%Y")
    url = "https://www.tnstc.in/OTRSOnline/jqreq.do"
    
    payload = {
        "hiddenStartPlaceID": from_id,
        "hiddenEndPlaceID": to_id,
        "txtStartPlaceCode": from_code,
        "txtEndPlaceCode": to_code,
        "hiddenStartPlaceName": from_place,
        "hiddenEndPlaceName": to_place,
        "matchStartPlace": from_place,
        "matchEndPlace": to_place,
        "hiddenCurrentDate": today_str,
        "hiddenOnwardJourneyDate": today_str,
        "hiddenAction": "SearchService",
        "languageType": "E",
        "checkSingleLady": "N",
        "txtJourneyDate": "DD/MM/YYYY",
        "txtReturnDate": "DD/MM/YYYY",
        "hiddenMaxNoOfPassengers": "16",
        "selectStartPlace": from_code,
        "selectEndPlace": to_code,
    }

    try:

        session = tnstc_manager.get_valid_session()
        
        response = session.post(url, data=payload, timeout=20)
        
        # Check if session expired during request (Specific TNSTC error check)
        if "Session Expired" in response.text or response.status_code != 200:
            print("⚠️ Session expired during request. Retrying...")
            tnstc_manager.refresh_session() # Force refresh
            session = tnstc_manager.get_valid_session()
            response = session.post(url, data=payload, timeout=20)

        soup = BeautifulSoup(response.text, 'html.parser')
        bus_items = soup.find_all('div', class_='bus-item')
        
        buses = []
        for item in bus_items:
            try:
                operator_elem = item.find('span', class_='operator-name')
                operator = operator_elem.get_text(strip=True) if operator_elem else "TNSTC"
                
                type_spans = item.find_all('span', class_='text-muted')
                bus_type = type_spans[0].get_text(strip=True) if type_spans else "Unknown"
                
                trip_link = item.find('a', href=True)
                trip_code = trip_link.get_text(strip=True) if trip_link else "N/A"
                
                time_divs = item.find_all('div', class_='time-info')
                start_time = "N/A"
                end_time = "N/A"
                
                if len(time_divs) >= 2:
                    start_span = time_divs[0].find('span', class_='text-dark')
                    start_time = start_span.get_text(strip=True) if start_span else "N/A"
                    end_span = time_divs[-1].find('span', class_='text-dark')
                    end_time = end_span.get_text(strip=True) if end_span else "N/A"
                
                duration_elem = item.find('span', class_='duration')
                duration = duration_elem.get_text(strip=True) if duration_elem else "N/A"
                
                via_elem = item.find('small', style=lambda x: x and 'blue' in x)
                via = via_elem.get_text(strip=True).replace('Via-', '') if via_elem else ""
                
                price_elem = item.find('div', class_='price')
                fare = price_elem.get_text(strip=True).replace('Rs', '').strip() if price_elem else "N/A"
                
                seats_elem = item.find('span', class_='text-1')
                seats = seats_elem.get_text(strip=True).replace('Seats Available', '').strip() if seats_elem else "N/A"
                
                buses.append({
                    "oprsNo": trip_code,
                    "serviceType": bus_type,
                    "serviceStartTime": start_time,
                    "serviceEndTime": end_time,
                    "depotName": operator,
                    "duration": duration,
                    "via": via,
                    "fare": fare,
                    "availableSeats": seats,
                    "journeyDate": today_str,
                    "source": "TNSTC"
                })
            except Exception:
                continue

        print(f"Found {len(buses)} buses")
        result={
        	"data":buses,
        	"source":"TNSTC",
        	"totalBuses":"len(buses)"
        }
        bus_cache.save_buses('TNSTC', from_place, to_place, result)
        return jsonify({
            "data": buses,
            "source": "TNSTC",
            "totalBuses": len(buses)
        })

    except Exception as e:
        print(f"Connection Error: {e}")
        return jsonify({"error": "TNSTC Connection Failed", "details": str(e)}), 500



@app.route('/api/find-buses-ksrtc-karnataka', methods=['POST'])
def find_buses_ksrtc_karnataka():
    req_data = request.get_json()
    from_name_raw = req_data.get('fromName', '').split(',')[0].strip()
    to_name_raw = req_data.get('toName', '').split(',')[0].strip()
    journey_date_iso = req_data.get('journeyDate')
    
    if not journey_date_iso:
        journey_date_iso = datetime.now().strftime("%Y-%m-%d")
    
    from_id = (KSRTC_KARNATAKA_MAP.get(from_name_raw.lower()) or 
               KSRTC_KARNATAKA_MAP.get(from_name_raw.upper()) or
               KSRTC_KARNATAKA_MAP.get(from_name_raw.title()))
    
    to_id = (KSRTC_KARNATAKA_MAP.get(to_name_raw.lower()) or 
             KSRTC_KARNATAKA_MAP.get(to_name_raw.upper()) or
             KSRTC_KARNATAKA_MAP.get(to_name_raw.title()))
    
    if not from_id or not to_id:
        print(f"City ID not found: {from_name_raw} or {to_name_raw}")
        return jsonify({"error": "City not found in database"}), 400
    
    from_name = from_name_raw.title()
    to_name = to_name_raw.title()
    
    try:
        date_obj = datetime.strptime(journey_date_iso, "%Y-%m-%d")
        indian_date = date_obj.strftime("%d-%m-%Y")
    except:
        indian_date = journey_date_iso
    
    session = requests.Session()
    
    base_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        session.get('https://ksrtc.in/oprs-web/', headers=base_headers, timeout=10)
        
        time.sleep(0.2)
        search_url = f"https://ksrtc.in/search?mode=oneway&fromCity={from_id}|{from_name}&toCity={to_id}|{to_name}&departDate={indian_date}&stationInFromCity=&stationInToCity=&IsSingleLady=0"
        
        search_headers = base_headers.copy()
        search_headers['Referer'] = 'https://ksrtc.in/oprs-web/'
        
        session.get(search_url, headers=search_headers, timeout=10)
        
        time.sleep(0.3)  
        api_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': search_url,
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        
        session.get('https://ksrtc.in/api/resource/getStaticCityList', 
                   headers=api_headers, timeout=10)
        
        api_url = "https://ksrtc.in/api/resource/searchRoutesV4"
        
        to_name_api = to_name
        if to_name.lower() == "bengaluru":
            to_name_api = "Bangalore"
        
        params = {
            'fromCityID': str(from_id),
            'toCityID': str(to_id),
            'fromCityName': from_name,
            'toCityName': to_name_api, 
            'journeyDate': journey_date_iso,  
            'mode': 'oneway'
        }
        
        response = session.get(api_url, params=params, headers=api_headers, timeout=15)
        
        
        if response.status_code != 200:

            return jsonify({"error": f"API returned {response.status_code}"}), 500
        
        if len(response.content) < 10:
            return jsonify({"error": "Empty response", "data": [], "totalBuses": 0})
        
        # Parse JSON
        try:
            raw_data = response.json()
        except json.JSONDecodeError as e:
            print(f"JSON Error: {e}")
            print(f"Response preview: {response.text[:300]}")
            return jsonify({"error": "Invalid JSON"}), 500
        
        # Validate data type
        if not isinstance(raw_data, list):

            return jsonify({
                "error": "No buses found",
                "data": [],
                "totalBuses": 0,
                "source": "KSRTC-KA"
            })
        
        
        formatted_buses = []
        
        for bus in raw_data:
            try:
                dep_str = bus.get('DepartureTime', '')
                arr_str = bus.get('ArrivalTime', '')
                
                start_time = "N/A"
                end_time = "N/A"
                duration_str = "N/A"
                arrival_date = ""
                
                if dep_str and arr_str:
                    dep_dt = datetime.strptime(dep_str, "%Y-%m-%dT%H:%M:%S")
                    arr_dt = datetime.strptime(arr_str, "%Y-%m-%dT%H:%M:%S")
                    
                    
                    duration = arr_dt - dep_dt
                    hours = duration.seconds // 3600
                    minutes = (duration.seconds % 3600) // 60
                    duration_str = f"{hours}h {minutes}m"
                    
                    start_time = dep_dt.strftime("%H:%M")
                    end_time = arr_dt.strftime("%H:%M")
                    arrival_date = arr_dt.strftime("%d %b")
                
                bus_obj = {
                    "oprsNo": bus.get('TripCode', 'N/A'),
                    "serviceType": bus.get('ServiceType', 'KSRTC'),
                    "serviceStartTime": start_time,
                    "serviceEndTime": end_time,
                    "arrivalDate": arrival_date,
                    "duration": duration_str,
                    "fare": str(bus.get('Fare', 0)),
                    "availableSeats": str(bus.get('AvailableSeats', 0)),
                    "depotName": bus.get('CompanyName', 'KSRTC Karnataka'),
                    "via": bus.get('ViaPlaces', ''),
                    "amenities": bus.get('AmenitiesType', ''),
                    "journeyDate": journey_date_iso,
                    "source": "KSRTC-KA",
                    "arrangement": bus.get('Arrangement', ''),
                    "hasAC": bool(bus.get('HasAC', 0)),
                    "hasSleeper": bool(bus.get('HasSleeper', 0)),
                    "routeName": bus.get('RouteName', ''),
                    "serviceId": bus.get('ServiceID', ''),
                    "tripId": bus.get('TripID', ''),
                    "serviceDocId": bus.get('RouteScheduleId') 
                }
                
                formatted_buses.append(bus_obj)
                
            except Exception as parse_err:
                print(f"  ⚠️ Parse error: {parse_err}")
                continue
        
        return jsonify({
            "success": True,
            "data": formatted_buses,
            "source": "KSRTC-KA",
            "totalBuses": len(formatted_buses),
            "route": f"{from_name} to {to_name}",
            "date": journey_date_iso
        })
        
    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timeout"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Connection failed"}), 503
    except Exception as e:
        print(f" Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-ksrtc-ka-stops', methods=['POST'])
def get_ksrtc_ka_stops():
    req_data = request.get_json()
    route_code = req_data.get('routeCode')
    
    if not route_code:
        return jsonify({"error": "Missing Route Code"}), 400

    print(f"Fetching KSRTC-KA Stops for: {route_code}")

    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://ksrtc.in/oprs-web/',
        'Origin': 'https://ksrtc.in'
    }
    session.headers.update(headers)

    try:
        session.get('https://ksrtc.in/oprs-web/', timeout=5)
        
        url = f"https://ksrtc.in/api/resource/ActiveMiddleCities"
        params = {"RouteCode": route_code}
        
        response = session.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            stops_list = []
            raw_list = []

            if isinstance(data, list):
                raw_list = data
            elif isinstance(data, dict):
                raw_list = data.get("APIGetActiveMiddleCitiesListResult", [])
                if not raw_list:
                    raw_list = data.get("data", [])

            for i, stop in enumerate(raw_list):
                stops_list.append({
                    "placeName": stop.get("CityName", "Unknown"),
                    "scheduleArrTime": "--:--", 
                    "seqNo": stop.get("Position", i+1)
                })
            stops_list.sort(key=lambda x: int(x['seqNo']))

            return jsonify({"data": stops_list})
        else:
            print(f"KSRTC Stops API Error: {response.status_code}")
            return jsonify({"error": "Failed to fetch stops"}), 500

    except Exception as e:
        print(f"KSRTC Stops Exception: {e}")
        return jsonify({"error": str(e)}), 500



def get_tgsrtc_db():
    try:
        conn = sqlite3.connect('tgsrtc.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

@app.route('/api/tgsrtc/resolve-id', methods=['POST'])
def resolve_tgsrtc_id():
    req_data = request.get_json()
    place_name = req_data.get('address', '').split(',')[0].strip() # Extract "Suryapet"
    
    if not place_name:
        return jsonify({"error": "No place name provided"}), 400

    conn = get_tgsrtc_db()
    if not conn:
        return jsonify({"error": "Database missing"}), 500
        
    cursor = conn.cursor()
    
    print(f"🟣 Searching TGSRTC DB for: {place_name}")

    cursor.execute("SELECT stop_id, stop_name FROM stops WHERE stop_name LIKE ? LIMIT 1", (place_name,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("SELECT stop_id, stop_name FROM stops WHERE stop_name LIKE ? LIMIT 1", (f"{place_name}%",))
        row = cursor.fetchone()
    
    if not row:
        cursor.execute("SELECT stop_id, stop_name FROM stops WHERE stop_name LIKE ? LIMIT 1", (f"%{place_name}%",))
        row = cursor.fetchone()

    conn.close()

    if row:
        print(f"Found TGSRTC ID: {row['stop_id']} for {row['stop_name']}")
        return jsonify({
            "id": row['stop_id'], 
            "match": row['stop_name'],
            "state": "TGSRTC"
        })
    else:
        print(f"No ID found in stops.txt for {place_name}")
        return jsonify({"id": None})
@app.route('/api/find-buses-tgsrtc', methods=['POST'])
def find_buses_tgsrtc():
    req_data = request.get_json()
    from_id = req_data.get('fromId')
    to_id = req_data.get('toId')

    if not from_id or not to_id:
        return jsonify({"error": "Missing valid GTFS Stop IDs"}), 400

    conn = get_tgsrtc_db()
    cursor = conn.cursor()

    print(f"🟣 Finding TGSRTC Buses: {from_id} -> {to_id}")

    query = '''
        SELECT 
            r.route_short_name,
            r.route_long_name,
            t.trip_id,
            t.bus_class,
            st1.departure_time as start_time,
            st2.arrival_time as end_time
        FROM stop_times st1
        JOIN stop_times st2 ON st1.trip_id = st2.trip_id
        JOIN trips t ON st1.trip_id = t.trip_id
        JOIN routes r ON t.route_id = r.route_id
        WHERE st1.stop_id = ? 
          AND st2.stop_id = ?
          AND CAST(st1.stop_sequence AS INTEGER) < CAST(st2.stop_sequence AS INTEGER)
        ORDER BY st1.departure_time
        LIMIT 50
    '''

    try:
        cursor.execute(query, (from_id, to_id))
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            # Calculate Duration
            try:
                t1 = datetime.strptime(row['start_time'], "%H:%M:%S")
                t2 = datetime.strptime(row['end_time'], "%H:%M:%S")
                duration = t2 - t1
                hours, remainder = divmod(duration.seconds, 3600)
                minutes = remainder // 60
                dur_str = f"{hours}h {minutes}m"
            except:
                dur_str = "N/A"

            results.append({
                "oprsNo": row['route_short_name'], # e.g. 107VR
                "serviceType": row['bus_class'] or "TGSRTC",
                "serviceStartTime": row['start_time'][:5], # HH:MM
                "serviceEndTime": row['end_time'][:5],
                "duration": dur_str,
                "fare": "N/A", # GTFS usually doesn't have fare
                "depotName": "TGSRTC",
                "journeyDate": datetime.now().strftime("%d-%m-%Y"),
                "via": row['route_long_name'],
                "source": "TGSRTC"
            })
            
        conn.close()
        print(f"Found {len(results)} TGSRTC buses")
        return jsonify({"data": results, "source": "TGSRTC", "totalBuses": len(results)})

    except Exception as e:
        print(f"TG SQL Error: {e}")
        return jsonify({"error": str(e)}), 500





@app.route('/')
def index():
    return render_template('index.html')


if __name__ =="__main__":

    app.run(debug=True)
