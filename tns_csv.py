import csv
import json

def csv_to_place_json():
    """Convert SETC_tn.csv to place ID JSON format"""
    
    places = {}  # Use dict to avoid duplicates
    
    with open('SETC_tn.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            from_place = row['From'].strip().upper()
            to_place = row['To'].strip().upper()
            
            # Add both places
            if from_place and from_place not in places:
                places[from_place] = {
                    "value": from_place,
                    "id": "",  # Will need to fill manually or scrape
                    "code": from_place[:3]  # First 3 letters as code
                }
            
            if to_place and to_place not in places:
                places[to_place] = {
                    "value": to_place,
                    "id": "",
                    "code": to_place[:3]
                }
    
    # Convert to list and sort
    places_list = sorted(places.values(), key=lambda x: x['value'])
    
    # Save as JSON
    with open('placeid_tnstc_template.json', 'w', encoding='utf-8') as f:
        json.dump(places_list, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Extracted {len(places_list)} unique places")
    print("💾 Saved to 'placeid_tnstc_template.json'")
    print("\n📋 First 10 places:")
    for place in places_list[:10]:
        print(f"  - {place['value']}")
    
    return places_list

if __name__ == "__main__":
    csv_to_place_json()