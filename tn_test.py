import json
import time
import random
import itertools
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
# Major Cities in Tamil Nadu to scan
CITIES = [
    "Trichy", "Chennai", "Madurai", "Coimbatore", "Salem", 
    "Tirunelveli", "Thanjavur", "Nagercoil", "Kumbakonam", 
    "Erode", "Vellore", "Kanyakumari", "Bengaluru", "Puducherry",
    "Tuticorin", "Rameswaram", "Ooty", "Kodaikanal"
]

# Output file
OUTPUT_FILE = "tnstc_full_dump.json"

def get_driver():
    """Setup Headless Chrome Driver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Mask automation to avoid immediate detection
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

def scrape_current_page(driver, from_city, to_city):
    """Parses the current visible buses on the page"""
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Wix Repeaters usually use role="listitem"
    items = soup.find_all("div", {"role": "listitem"})
    
    page_buses = []
    
    for item in items:
        try:
            text_content = item.get_text(separator="|", strip=True).split("|")
            
            # The text usually comes out like: ['TNSTC', '3 X 2', 'TRICHY', 'CHENNAI', '12:10 am']
            # The order might vary slightly, but usually: Corp, Type, From, To, Time
            
            # Simple heuristic mapping based on common values
            bus_obj = {
                "from": from_city,
                "to": to_city,
                "journeyDate": "Daily",
                "source": "TamilVandi",
                "depotName": "TNSTC", # Default
                "serviceType": "Bus",
                "dep": "N/A"
            }
            
            for txt in text_content:
                u_txt = txt.upper()
                if "TNSTC" in u_txt or "SETC" in u_txt:
                    bus_obj["depotName"] = txt
                elif "DELUXE" in u_txt or "AC" in u_txt or "SLEEPER" in u_txt or "3 X 2" in u_txt:
                    bus_obj["serviceType"] = txt
                elif ":" in txt and ("AM" in u_txt or "PM" in u_txt):
                    bus_obj["dep"] = txt.replace("🕒", "").strip()
            
            # Create a unique ID for deduplication
            bus_id = f"{bus_obj['depotName']}_{bus_obj['dep']}_{from_city}_{to_city}"
            bus_obj["_id"] = bus_id
            
            if bus_obj["dep"] != "N/A":
                page_buses.append(bus_obj)
                
        except Exception:
            continue
            
    return page_buses

def harvest_route(driver, from_city, to_city):
    """Navigates through pagination for a specific route"""
    url = f"https://www.tamilvandi.com/timings?from={from_city}&to={to_city}"
    print(f"🚌 Visiting: {from_city} -> {to_city}")
    
    driver.get(url)
    time.sleep(random.uniform(3, 5)) # Wait for initial load
    
    all_buses_for_route = []
    seen_ids = set()
    page_num = 1
    
    while True:
        # 1. Scrape current view
        current_buses = scrape_current_page(driver, from_city, to_city)
        new_items = 0
        
        for bus in current_buses:
            if bus["_id"] not in seen_ids:
                all_buses_for_route.append(bus)
                seen_ids.add(bus["_id"])
                new_items += 1
        
        print(f"   Pg {page_num}: Found {len(current_buses)} buses ({new_items} new)")
        
        if len(current_buses) == 0:
            print("   No buses found on this route.")
            break

        # 2. Try to find NEXT button
        try:
            # Wix Next buttons usually have an aria-label="Next" or contain specific SVG
            # Based on your HTML dump, the Next button ID is often 'comp-mh5z4g62' or similar
            # Best way is to find by aria-label or text
            next_btn = None
            buttons = driver.find_elements(By.TAG_NAME, "button")
            
            for btn in buttons:
                aria = btn.get_attribute("aria-label")
                if aria and "Next" in aria:
                    next_btn = btn
                    break
            
            # If valid next button found
            if next_btn and next_btn.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView();", next_btn)
                time.sleep(1)
                
                # Check if disabled (Wix buttons often have 'disabled' attribute or class)
                if "disabled" in next_btn.get_attribute("class") or next_btn.get_attribute("disabled"):
                    print("   End of list (Button disabled).")
                    break
                    
                next_btn.click()
                page_num += 1
                
                # Wait for data to change (simple wait is safer than complex conditions here)
                time.sleep(random.uniform(4, 6)) 
            else:
                print("   End of list (No Next button).")
                break
                
        except Exception as e:
            print(f"   Pagination stopped: {e}")
            break
            
    return all_buses_for_route

def main():
    driver = get_driver()
    master_data = []
    
    # Generate route pairs
    routes = list(itertools.permutations(CITIES, 2))
    
    # Load existing if available to resume (Optional)
    try:
        with open(OUTPUT_FILE, 'r') as f:
            master_data = json.load(f)
            print(f"Loaded {len(master_data)} existing records.")
    except:
        pass

    try:
        for i, (origin, dest) in enumerate(routes):
            # Optional: Skip if we already have data for this route (requires logic adjustment)
            
            buses = harvest_route(driver, origin, dest)
            master_data.extend(buses)
            
            # Save every 3 routes just in case script crashes
            if i % 3 == 0:
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(master_data, f, indent=4, ensure_ascii=False)
                print(f"💾 Saved progress. Total buses: {len(master_data)}")
            
            # Anti-ban wait between routes
            time.sleep(random.uniform(2, 5))
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping harvest...")
    finally:
        # Final Save
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(master_data, f, indent=4, ensure_ascii=False)
        print(f"✅ FINAL SAVE. Total buses: {len(master_data)}")
        driver.quit()

if __name__ == "__main__":
    main()