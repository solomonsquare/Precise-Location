# Precise Location Search

Precise Location Search is a web application that empowers users to find points of interest with pinpoint accuracy. Whether you're searching for restaurants, shops, skate parks, playgrounds, or any other amenity, the app dynamically retrieves results within precise boundaries defined by postal codes or specified areas.

## Features

- **Dynamic Search**: Enter queries in the format "[place type] in [location]" to search for specific locations.
- **Exact Boundary Matching**: Utilizes Nominatim and the Overpass API to fetch location data and restrict results to exact areas or postal boundaries.
- **Interactive Map**: An intuitive map displays markers for each location, updating dynamically based on your search.
- **Comprehensive Filtering**: Supports a variety of categories through standard OSM tags, including:
  - Food courts, train and bus stations, BBQ areas, gardens, and marketplaces
  - Skate parks (with enhanced filtering for `leisure=skate_park`, `sport=skateboard`, and `sport=skating`)
  - Playgrounds and sports centers
- **Responsive UI**: Built with a modern React frontend and a Flask backend for a seamless user experience.
- **No Hardcoded Locations**: All locations and boundaries are dynamically determined via user input and external APIs, with no static defaults.

## Technologies Used

- **Frontend**: ReactJS with Mapbox for map rendering
- **Backend**: Python Flask
- **Location Services**: OpenStreetMap Overpass API for location data, Nominatim for geocoding
- **Utilities**: Custom JavaScript functions for boundary calculations and coordinate validation

## Setup

### Prerequisites

- Python 3.x
- Node.js (for frontend development, if needed)
- A valid Mapbox Access Token

### Installation

1. **Clone the Repository**

   ```bash
   git clone <repository-url>
   cd Precise-Search-V0
   ```

2. **Install Backend Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**

   Create a `.env` file in the root directory with the following content:

   ```
   MAPBOX_ACCESS_TOKEN=your_access_token_here
   ```

4. **Run the Application**

   ```bash
   python app.py (or python3 app.py)
   ```

5. **Access the Application**

   Open your browser and navigate to:
   
   ```
   http://localhost:5000
   ```

## Usage

- **Search Queries**: Type your query in the format "[place type] in [location]". Examples include:
  - "restaurants in SW12BB"
  - "coffee shops in Westgate road"
  - "skatepark in downtown"

- **Map Interaction**: 
  - Markers represent the search results on the map.
  - Click on a marker to view additional details about that location.
  - Each location includes a link to search for more details on Google.

- **Filtering**: 
  - The app dynamically filters results so that only locations within the defined search area are displayed.

## Notes

- The application relies on live data from OpenStreetMap via the Overpass API. Ensure your network permits connections to these endpoints.
- There are no hardcoded default locations or boundaries; all data is fetched dynamically based on user input and external API responses.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for improvements or bug fixes.

## License

[MIT License](LICENSE) 