import requests
import json

# The exact URL you found
url = "https://utsappapicached01.apsrtconline.in/uts-vts-api/servicewaypointdetails/bydocid"

# The headers are CRITICAL. We must look exactly like the browser.
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

# --- IMPORTANT: PASTE THE PAYLOAD FROM YOUR NETWORK TAB HERE ---
# This is an example guess. You must replace this with the real data you see in Chrome.
payload =   {"docId":"25112025_9146_4_TIRUVURU"}
try:
    response = requests.post(url, headers=APSRTC_HEADERS, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        print("Success! Data Received:")
        print(json.dumps(data, indent=2)) # Pretty print the JSON
    else:
        print(f"Failed with Status Code: {response.status_code}")
        print("Response:", response.text)

except Exception as e:
    print(f"Error: {e}")