import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
CX = os.getenv("GOOGLE_CX_ID")

app = FastAPI()

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define available categories
QUERY_CATEGORIES = {
    "Full Stack": "Fullstack engineering startups",
    "Machine Learning": "Machine learning AI startups",
    "Cloud Computing": "Cloud-based SaaS startups",
    "Cybersecurity": "Cybersecurity and data protection startups",
    "Blockchain": "Blockchain-based startups",
    "IoT": "Internet of Things (IoT) startups"
}

# Define states and cities
STATES_AND_CITIES = {
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli"],
    "Karnataka": ["Bangalore", "Mysore", "Mangalore", "Hubli-Dharwad"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar"]
}

# Define request model
class SearchRequest(BaseModel):
    category: str
    state: str
    city: str

def google_search(query, start=1):
    """Fetch search results from Google Custom Search API."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CX,
        "q": query,
        "num": 10,
        "start": start,
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        return None

def extract_startup_details(items, city, state):
    """Extract relevant startup details and filter by location."""
    startup_data = []
    for item in items:
        title = item.get("title", "Not Found")
        link = item.get("link", "Not Found")
        snippet = item.get("snippet", "Not Found")
        
        # Check if the location matches - make this more lenient
        location_match = False
        city_lower = city.lower()
        state_lower = state.lower()
        
        # Check for city or state mention (more lenient)
        if city_lower in snippet.lower() or city_lower in title.lower() or state_lower in snippet.lower() or state_lower in title.lower():
            location_match = True
        
        # Only include startups that match location
        if location_match:
            hr = "Not Found"
            linkedin = "Not Found"
            founded = "Unknown"
            
            # Extract location information
            location = f"{city}, {state}, India"
            
            # Try to extract more specific location from snippet
            location_pattern = re.compile(r'(?:located|based|headquartered) (?:in|at) ([^\.]+)', re.IGNORECASE)
            location_match = location_pattern.search(snippet)
            if location_match:
                specific_location = location_match.group(1).strip()
                if specific_location:
                    location = specific_location

            if "linkedin.com/in/" in link:
                linkedin = link
                hr = title  
            elif "crunchbase.com/organization/" in link:
                linkedin = link
                hr = "Visit Crunchbase for HR details"
                
            # More comprehensive founding year extraction
            founding_years = ["2020", "2021", "2022", "2023", "2024"]
            founding_phrases = ["founded in", "established in", "started in", "launched in", "created in"]
            
            # Check for founding year in snippet
            for phrase in founding_phrases:
                for year in founding_years:
                    if f"{phrase} {year}" in snippet.lower():
                        founded = f"Founded in {year}"
                        break
            
            # If still unknown, check for years directly
            if founded == "Unknown":
                for year in founding_years:
                    if year in snippet or year in title:
                        founded = f"Founded in {year}"
                        break

            startup_data.append({
                "Startup Name": title,
                "Snippet": snippet,
                "LinkedIn": linkedin,
                "HR": hr,
                "Founded": founded,
                "Location": location
            })

    return startup_data

@app.post("/api/search")
async def search_startups(request: SearchRequest):
    """Fetch startups based on filters."""
    try:
        if request.category not in QUERY_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        if request.state not in STATES_AND_CITIES or request.city not in STATES_AND_CITIES[request.state]:
            raise HTTPException(status_code=400, detail="Invalid state or city")

        # Create multiple queries to get more diverse results
        queries = [
            f"{QUERY_CATEGORIES[request.category]} in {request.city} {request.state} India founded after 2020 site:linkedin.com OR site:crunchbase.com",
            f"startup {request.category} {request.city} {request.state} India founded 2020 2021 2022 2023 site:linkedin.com OR site:crunchbase.com",
            f"new {QUERY_CATEGORIES[request.category]} company {request.city} {request.state} India established after 2020 site:linkedin.com OR site:crunchbase.com"
        ]

        all_startups = []
        
        # Run multiple searches with different queries
        for query in queries:
            # Fetch more pages (10 pages = up to 100 results per query)
            for page in range(1, 10):
                start = (page - 1) * 10 + 1
                data = google_search(query, start)
                if data and "items" in data:
                    startups = extract_startup_details(data["items"], request.city, request.state)
                    all_startups.extend(startups)
                else:
                    # If no more results, break the loop
                    break
        
        # Remove duplicates based on Startup Name
        unique_startups = []
        seen_names = set()
        for startup in all_startups:
            if startup["Startup Name"] not in seen_names:
                seen_names.add(startup["Startup Name"])
                unique_startups.append(startup)

        return unique_startups

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
async def get_categories():
    return list(QUERY_CATEGORIES.keys())

@app.get("/api/states")
async def get_states():
    return list(STATES_AND_CITIES.keys())

@app.get("/api/cities/{state}")
async def get_cities(state: str):
    if state not in STATES_AND_CITIES:
        raise HTTPException(status_code=400, detail="Invalid state")
    return STATES_AND_CITIES[state]

