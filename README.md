Working script: scraper_v2.py
It requires a Bright Data API key to be set in the .env file.
It processes 10 pages of jobs and saves them to a CSV file.

$1.5 per 1000 requests (each page is 10 jobs initial info, then 1 request for detail job info)

1 request = 10 job initial info
1 request = 1 job detail info / 1 job update status