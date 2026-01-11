# 🚏 Bus Route Optimizer
A comprehensive bus journey planner built from scratch for South Indian interstate travel - because finding the right bus shouldn't feel like archaeological research.

### What this does
You know that frustration when planning a bus journey across South India? Checking APSRTC, then KSRTC, then TNSTC websites separately, trying to figure out connections, comparing timings, wondering if you'll be roasted by the sun through the window for 6 hours straight?
This isn't another aggregator showing you the same RedBus listings. This is a built-from-ground-up journey planner that directly integrates with state transport systems.

Type in your start and destination:

- Finds buses across multiple state transport corporations directly from their sources along with the stops of a particular bus along the way 🐼
- Maps the actual route with real road geometry (not a 'lame' straight line)
- Calculates which side to sit based on sun position and route bearing throughout the journey
- Shows accurate timings and fares by hitting official APIs and cross-verifying through web scraping 🧘‍♀️
- Visualizes your entire journey on an interactive map from OpenStreetmaps

🌐 [Try it out Live here](https://hemann-bus-tracker.hf.space/)

### Currently Supporting
#### States & Coverage: (only supports state run not private ones)
- Andhra Pradesh (APSRTC) - Full statewide coverage via official API
- Kerala (KSRTC) - Comprehensive coverage through KBuses integration
- Tamil Nadu (TNSTC) - Direct TNSTC system integration
- Karnataka (KSRTC-KA) - Karnataka state transport network
- Telangana (TGSRTC) - Hyderabad metropolitan region (GTFS-based)
#### Bus Categories:
- Express, Ordinary,AC,  Non-AC , Sleeper,  Semi-Sleeper,  Deluxe , Super Deluxe , Ultra Deluxe, Plus whatever creative names the RTCs dream up
---
## What Makes This Different

Most bus booking sites just throw a list of buses at you. Here's what we do differently:

1. **Physics-Based Shade Calculation** ☀️

This is unnecessarily over-engineered (because have you ever sat on the wrong side of the bus and (being introvert) regretted it for 8 hours?) and I'm proud of it. The system:
- Calculates sun azimuth and altitude for your journey time
- Computes route bearing for each road segment
- Determines relative angle between sun and bus direction
- Tells you whether left or right side gets more shade
- Shows percentage of journey time you'll have shade
Try getting that from a booking aggregator.

2. **Smart Caching System**

Built a SQLite-based cache that:
- Stores search results for 2 hours
- Tracks cache hit counts to identify popular routes
- Auto-cleans entries older than 100 days
- Dramatically speeds up repeated searche

3. **Real Route Geometry and visualization**

Using OpenRouteService's HGV routing, we calculate the actual path buses take. You see the real route on the map, with actual distance and estimated duration. Not guesswork.

4. **Intelligent Multi-Source Verification**

For different RTCs, we hit both their mobile API and scrape their website. Why? Because sometimes the API returns incomplete fare data. We cross-reference to give you the most accurate information possible.

5. **State-Smart Detection**

Drop a city name and it figures out which state transport corporation to query. No dropdowns, no confusion.

6. **Direct Source Integration**

We're not scraping booking platforms. We go straight to APSRTC APIs, TNSTC servers, official KSRTC data. When you search, you're seeing what the state transport corporations actually have, not what third-party sites decided to show you.

---

## Tech Stack (The Real Stack, Not Marketing Speak)
### Backend:

- Flask - Python web framework
- SQLite - For caching and GTFS data storage
- BeautifulSoup4 - HTML parsing when APIs don't exist
- Requests + Sessions - HTTP handling with proper session management

### Frontend:

- Vanilla JavaScript - clean DOM manipulation
- Leaflet.js - Interactive map rendering with custom markers
- CSS3 - Responsive design that works on mobile

### External Services:

- OpenRouteService - HGV routing, geocoding, directions
- APSRTC Mobile API - Real-time bus data
- KSRTC Karnataka API - Live service search
- TNSTC Web Portal - Tamil Nadu bus schedules
- KBuses - Kerala bus information
- GTFS Data - Telangana transport (Hyderabad region)

### The Work arounds:

- Custom session manager for TNSTC (cause their sessions expire faster than milk)
- Solar position calculation using spherical trigonometry
- Multi-pattern fuzzy matching for stop names
- Automatic state detection from geocoding results
- Dynamic route bearing calculation

--- 

### Running Locally

```
# Clone the repo
git clone https://github.com/Hemanthpulicharla/Bus_route_optimiser.git
cd Bus_route_optimiser

# Install dependencies in requirements.txt
pip install flask flask-cors requests beautifulsoup4

# Get your OpenRouteService API key
# Sign up at https://openrouteservice.org/ (free tier works fine)
# Replace ORS_API_KEY in app.py

# Run it up
python app.py
```

Navigate to `http://localhost:5000`

## Project Structure
```
├── app.py                          # Main Flask application
├── bus_cache.db                    # SQLite cache database
├── tgsrtc.db                       # Telangana GTFS database
├── place_id.json                   # APSRTC depot mappings
├── placeid_kerela.json             # Kerala KSRTC stops
├── placeid_tnstc_template.json     # Tamil Nadu locations
├── place_id_kr.json                # Karnataka city IDs
├── SETC_tn.csv                     # Tamil Nadu route codes
└── templates/
    └── index.html                  # Frontend

```
--- 

## The Roadmap
### Multi-Hop Routing
  - Currently: You search A→B, you get direct buses.
  - Coming: A→C→B routing when direct isn't available or when connections are faster/cheaper.
Calculate transfer times between buses
  - Optimize for least time vs least cost
  - Show connection feasibility scores
### True Price Intelligence 
  Not just showing prices - understanding them:

### Compare official site vs RedBus vs AbhiBus vs other platforms
  - Track price history and patterns
  - Flag "book now" opportunities when prices are low
  - Detect dynamic pricing shenanigans
### ML-Driven Smart Recommendations
  - Using Google Maps data + historical travel patterns:

### Predict actual journey times (not scheduled times)
  - Route reliability scoring based on real delays
  - Operator punctuality ratings
  - Traffic-aware departure time suggestions
  - Alternative route recommendations during peak hours
### Layover Intelligence
Got 90 minutes between buses in Vijayawada?
  - Nearby places to eat, rest (within actual walking distance)
  - Tourist spots you can hit in your layover window
  - Safety ratings for bus stands at different times
  - Luggage storage locations
### Multimodal Transport Integration
  - Because sometimes bus+metro+auto is the answer:
  - Local metro integration (Hyderabad, Bangalore, Chennai)
  - Last-mile auto/cab suggestions
  - Time and cost optimization across modes

## Known Issues:

  - Kerala timings are web-scraped, not from official API - accuracy depends on KBuses updates
  - TNSTC session management is temperamental, may need retry on first attempt
  - Night journeys skip shade analysis (because duh)
  - Some APSRTC fares show "N/A" when their web service has a moment
  - Karnataka API sometimes switches between "Bangalore" and "Bengaluru" randomly
  - Telangana coverage is Hyderabad metro region only, not full state
  - GTFS data for TGSRTC is static - updates require manual refresh
---
### Contributing
Found a bug? Route not working? State you want added?
Open an issue or send a PR. The code is messy in places (especially the scraping bits) but it works.

Particularly interested in:

  - Additional state transport integrations
  - Better stop name matching algorithms
  - Fare accuracy improvements
  - GTFS data for more regions

Live Demo: [https://hemann-bus-tracker.hf.space/](https://hemann-bus-tracker.hf.space/)

