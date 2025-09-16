Working script: scraper_v2.py

It requires a Bright Data API key to be set in the .env file.

It processes 20 pages of jobs (20 requests) and saves them to a CSV file.

$1.5 per 1000 requests.

- With 1 request you can scrape around +10 jobs initial info or 1 request for detail job info (includes full job description).

1 request = 10 job initial info

1 request = 1 job detail info / 1 job update status

Average time per request (per page): 3.36 seconds
Total time for 20 pages: 67.11 seconds (Can be parallelized)