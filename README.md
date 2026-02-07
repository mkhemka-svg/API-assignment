# Earthquake Explorer (USGS Public API)
This is a small Python app that fetches recent earthquakes from the USGS 
Earthquake Catalog API and displays a ranked list of earthquakes. 
It can also generate a simple plot of magnitude over time. Essentially, it calls 
the USGS Earthquake Catalog API using Python’s requests module to make an HTTP 
GET request to a public endpoint that returns data in GeoJSON (JSON) format. 
(Endpoint:"https://earthquake.usgs.gov/fdsnws/event/1/query")
The request includes query parameters such as a time window (how many hours back), 
minimum magnitude and a result limit, which allow the user to control what 
earthquake data is retrieved. The API response contains a list of earthquake 
"features" where each feature provides the magnitude of the event, the time it 
occurred (returned as epoch milliseconds and converted into a readable UTC 
datetime), the depth of the earthquake in kilometers, and a descriptive location 
string relative to a nearby city or region. These fields are formatted into 
readable entries. The application displays this information in the terminal and 
can also visualize earthquake magnitudes over time using matplotlib. This API 
does not require an API key, so there are no secrets to manage.
