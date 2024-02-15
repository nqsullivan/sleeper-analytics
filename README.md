# Sleeper Analytics

## Description

Sleeper Analytics is a Python application designed to analyze and visualize data from the Sleeper fantasy football
platform. It uses various libraries such as numpy, pandas, requests, and matplotlib to fetch, process, and visualize the
data.

The application fetches player, roster, and matchup data from the Sleeper API and calculates various statistics such as
total points for and against, average points for and against, points difference, and efficiency. These statistics are
then saved to a CSV file for further analysis.

In addition to calculating statistics, the application also generates a plot of the 3-week moving average of points for
each team, excluding the last week. This plot is saved as a PNG file.

## How to Use
1. Clone the repository
2. Install the required packages using `pip install -r requirements.txt`
3. Run the application using `python main.py <league_id>`