import os

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt
import argparse

parser = argparse.ArgumentParser(description="Analyze and visualize data from the Sleeper fantasy football platform")
parser.add_argument('league_id', type=str, help='The league id to analyze')
LEAGUE_ID = parser.parse_args().league_id

global matchup_data, player_data, roster_data
matchup_data = pd.DataFrame()
player_data = pd.DataFrame()
roster_data = pd.DataFrame()


def get_player_data():
    # try and load from local file
    if os.path.exists('player_data.csv'):
        player_data = pd.read_csv('player_data.csv')
        return player_data

    # Make a request to https://api.sleeper.app/v1/players/nfl
    req = requests.get('https://api.sleeper.app/v1/players/nfl')
    player_data = pd.DataFrame(req.json())
    player_data = player_data.T
    player_data = player_data.reset_index()
    player_data.to_csv('player_data.csv', index=False)
    return player_data


def get_roster_data():
    # Make a request to https://api.sleeper.app/v1/league/<league_id>/rosters
    req = requests.get('https://api.sleeper.app/v1/league/' + LEAGUE_ID + '/rosters')
    roster_data = pd.DataFrame(req.json())

    # For each roster, get the name of the owner
    for index, row in roster_data.iterrows():
        # Make a request to https://api.sleeper.app/v1/user/<user_id>
        req = requests.get('https://api.sleeper.app/v1/user/' + row['owner_id'])
        roster_data.loc[index, 'owner_id'] = req.json()['display_name']

    roster_data.to_csv('roster_data.csv', index=False)
    return roster_data


def get_matchup_data():
    # Get the current week https://api.sleeper.app/v1/state/nfl
    req = requests.get('https://api.sleeper.app/v1/state/nfl')
    current_week = req.json()['week']

    matchup_data = pd.DataFrame()

    if current_week == 0:
        r = range(1, 17)
    else:
        r = range(1, current_week + 1)

    for week in r:
        # Make a request to https://api.sleeper.app/v1/league/<league_id>/matchups/<week>
        req = requests.get('https://api.sleeper.app/v1/league/' + LEAGUE_ID + '/matchups/' + str(week))

        # Add the week to the matchup data with a column for the week
        week_data = pd.DataFrame(req.json())
        week_data['week'] = week
        matchup_data = matchup_data.append(week_data)

    matchup_data.to_csv('matchup_data.csv', index=False)
    return matchup_data


def get_total_points_for():
    id_to_pf = {}

    for index, manager in roster_data.iterrows():
        matchup_data_temp = matchup_data.copy()
        matchup_data_temp = matchup_data_temp[matchup_data_temp['roster_id'] == manager['roster_id']]
        id_to_pf[manager['roster_id']] = matchup_data_temp['points'].sum()

    return id_to_pf


def get_total_points_against():
    id_to_pa = {}

    for index, manager in roster_data.iterrows():
        matchup_data_temp = matchup_data.copy()

        # Filter out the matchups entries with the manager's team
        matchup_data_temp = matchup_data_temp[matchup_data_temp['roster_id'] != manager['roster_id']]

        # Filter out the matchup entries where matchup id is not unique for the week
        matchup_data_temp = matchup_data_temp.drop_duplicates(subset=['week', 'matchup_id'], keep=False)

        # Add up the points column to get the total points against
        id_to_pa[manager['roster_id']] = matchup_data_temp['points'].sum()

    return id_to_pa


def get_optimal_roster_from_matchup(matchup_data_temp):
    # Lineups are superflex: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 SUPERFLEX, 1 DST, 1 K
    # Get the top 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 SUPERFLEX, 1 DST, 1 K

    # Use the list of player ids to get the player data
    roster_for_week = pd.DataFrame()
    for index, matchup in matchup_data_temp.iterrows():
        for idx, player_id in enumerate(matchup['players']):
            # Get the player name from the player data and add it to the roster with the points from the points column on the matchup
            player = player_data[player_data['player_id'] == player_id]
            roster_for_week.loc[idx, 'player_name'] = player['full_name'].values[0]
            roster_for_week.loc[idx, 'position'] = player['position'].values[0]
            roster_for_week.loc[idx, 'points'] = matchup['players_points'].get(player_id, 0)

    # Sort the roster by points
    roster_for_week = roster_for_week.sort_values(by=['points'], ascending=False)

    # Get the top 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 SUPERFLEX, 1 DST, 1 K
    # Pop the values from the roster_for_week dataframe as we add them to the optimal_roster dataframe
    optimal_roster = pd.DataFrame()

    # qb
    optimal_roster = optimal_roster.append(roster_for_week[roster_for_week['position'] == 'QB'].head(1))
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'QB'].head(1).index, inplace=True)

    # rb
    optimal_roster = optimal_roster.append(roster_for_week[roster_for_week['position'] == 'RB'].head(2))
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'RB'].head(2).index, inplace=True)

    # wr
    optimal_roster = optimal_roster.append(roster_for_week[roster_for_week['position'] == 'WR'].head(2))
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'WR'].head(2).index, inplace=True)

    # te
    optimal_roster = optimal_roster.append(roster_for_week[roster_for_week['position'] == 'TE'].head(1))
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'TE'].head(1).index, inplace=True)

    # flex
    flex_players = roster_for_week[(roster_for_week['position'] == 'RB') | (roster_for_week['position'] == 'WR') | (roster_for_week['position'] == 'TE')].head(1)
    optimal_roster = optimal_roster.append(flex_players)
    roster_for_week.drop(flex_players.index, inplace=True)

    # superflex
    superflex_players = roster_for_week[(roster_for_week['position'] == 'QB') | (roster_for_week['position'] == 'RB') | (roster_for_week['position'] == 'WR') | (roster_for_week['position'] == 'TE')].head(1)
    optimal_roster = optimal_roster.append(superflex_players)
    roster_for_week.drop(superflex_players.index, inplace=True)

    # dst
    optimal_roster = optimal_roster.append(roster_for_week[roster_for_week['position'] == 'DST'].head(1))
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'DST'].head(1).index, inplace=True)

    # k
    optimal_roster = optimal_roster.append(roster_for_week[roster_for_week['position'] == 'K'].head(1))
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'K'].head(1).index, inplace=True)

    return optimal_roster['points'].sum()


def get_optimal_points_for():
    id_to_opf = {}

    for index, manager in roster_data.iterrows():
        matchup_data_temp = matchup_data.copy()
        matchup_data_temp = matchup_data_temp[matchup_data_temp['roster_id'] == manager['roster_id']]

        running_total = 0

        for week in range(1, matchup_data_temp['week'].max() + 1):
            matchup_data_temp_week = matchup_data_temp[matchup_data_temp['week'] == week]
            running_total += get_optimal_roster_from_matchup(matchup_data_temp_week)

        id_to_opf[manager['roster_id']] = running_total

    return id_to_opf


def get_optimal_points_against():
    id_to_opa = {}

    for index, manager in roster_data.iterrows():
        matchup_data_temp = matchup_data.copy()

        # Filter out the matchups entries with the manager's team
        matchup_data_temp = matchup_data_temp[matchup_data_temp['roster_id'] != manager['roster_id']]

        # Filter out the matchup entries where matchup id is not unique for the week
        matchup_data_temp = matchup_data_temp.drop_duplicates(subset=['week', 'matchup_id'], keep=False)

        running_total = 0

        for week in range(1, matchup_data_temp['week'].max() + 1):
            matchup_data_temp_week = matchup_data_temp[matchup_data_temp['week'] == week]
            running_total += get_optimal_roster_from_matchup(matchup_data_temp_week)

        id_to_opa[manager['roster_id']] = running_total

    return id_to_opa


def get_matchup_data_remaining():
    # Get the current week https://api.sleeper.app/v1/state/nfl
    req = requests.get('https://api.sleeper.app/v1/state/nfl')
    current_week = req.json()['week']

    matchup_data = pd.DataFrame()

    for week in range(current_week + 1, 18):
        # Make a request to https://api.sleeper.app/v1/league/<league_id>/matchups/<week>
        req = requests.get('https://api.sleeper.app/v1/league/' + LEAGUE_ID + '/matchups/' + str(week))

        week_data = pd.DataFrame(req.json())
        week_data['week'] = week
        matchup_data = matchup_data.append(week_data)

    matchup_data.to_csv('matchup_data_remaining.csv', index=False)
    return matchup_data


def get_remaining_strength_of_schedule(statistics):
    remaining_matchup_data = get_matchup_data_remaining()

    id_to_rss = {}

    for index, manager in roster_data.iterrows():
        # use the roster id to get the remaining matchups
        remaining_matchup_data_temp = remaining_matchup_data.copy()

        # Filter out the matchups entries with the manager's team
        remaining_matchup_data_temp = remaining_matchup_data_temp[remaining_matchup_data_temp['roster_id'] != manager['roster_id']]

        # Filter out the matchup entries where matchup id is not unique for the week
        remaining_matchup_data_temp = remaining_matchup_data_temp.drop_duplicates(subset=['week', 'matchup_id'], keep=False)

        running_total = 0
        for week in range(1, remaining_matchup_data_temp['week'].max() + 1):
            matchup_data_temp_week = remaining_matchup_data_temp[remaining_matchup_data_temp['week'] == week]
            running_total += get_optimal_roster_from_matchup(matchup_data_temp_week)

        id_to_rss[manager['roster_id']] = running_total / remaining_matchup_data_temp['week'].count()
    return id_to_rss


def calculate_analytics():
    id_to_points_for = get_total_points_for()
    id_to_points_against = get_total_points_against()
    optimal_points_for = get_optimal_points_for()
    optimal_points_against = get_optimal_points_against()

    # Print the statistics for each team
    statistics = pd.DataFrame()
    statistics['owner_id'] = roster_data['owner_id']
    statistics['roster_id'] = roster_data['roster_id']
    statistics['wins'] = roster_data['metadata'].map(lambda x: str.count(x['record'], 'W'))
    statistics['losses'] = roster_data['metadata'].map(lambda x: str.count(x['record'], 'L'))

    statistics['win_percentage'] = statistics['wins'] / (statistics['wins'] + statistics['losses'])
    statistics['win_percentage'] = statistics['win_percentage'].map(lambda x: "{:.2%}".format(x))

    statistics['points_for'] = statistics['roster_id'].map(id_to_points_for)
    statistics['points_for'] = statistics['points_for'].round(2)

    statistics['points_against'] = statistics['roster_id'].map(id_to_points_against)
    statistics['points_against'] = statistics['points_against'].round(2)

    statistics['average_points_for'] = statistics['points_for'] / (statistics['wins'] + statistics['losses'])
    statistics['average_points_for'] = statistics['average_points_for'].round(2)

    statistics['average_points_against'] = statistics['points_against'] / (statistics['wins'] + statistics['losses'])
    statistics['average_points_against'] = statistics['average_points_against'].round(2)

    statistics['points_difference'] = statistics['points_for'] - statistics['points_against']
    statistics['points_difference'] = statistics['points_difference'].round(2)

    statistics['optimal_points_for'] = statistics['roster_id'].map(optimal_points_for)
    statistics['optimal_points_for'] = statistics['optimal_points_for'].round(2)
    #
    statistics['optimal_points_against'] = statistics['roster_id'].map(optimal_points_against)
    statistics['optimal_points_against'] = statistics['optimal_points_against'].round(2)
    #
    statistics['efficiency_for'] = statistics['points_for'] / statistics['optimal_points_for']
    statistics['efficiency_for'] = statistics['efficiency_for'].map(lambda x: "{:.2%}".format(x))

    statistics['efficiency_against'] = statistics['points_against'] / statistics['optimal_points_against']
    statistics['efficiency_against'] = statistics['efficiency_against'].map(lambda x: "{:.2%}".format(x))

    statistics = statistics.sort_values(by=['points_difference'], ascending=False)

    # remaining_strength_of_schedule = get_remaining_strength_of_schedule(statistics)
    # statistics['remaining_strength_of_schedule'] = statistics['roster_id'].map(remaining_strength_of_schedule)
    # statistics['remaining_strength_of_schedule'] = statistics['remaining_strength_of_schedule'].round(2)

    print(statistics)

    # remove the roster_id column
    statistics = statistics.drop(columns=['roster_id'])
    statistics.to_csv('statistics.csv', index=False)

    return statistics

def visualize_data():
    # Get the current week
    req = requests.get('https://api.sleeper.app/v1/state/nfl')
    current_week = req.json()['week']

    # Create a figure and axis for the plot
    fig, ax = plt.subplots()

    # Create variables to store legend labels and artists
    legend_labels = []
    legend_artists = []

    # Plot 3-week moving average for each team removing the last week
    for index, manager in roster_data.iterrows():
        matchup_data_temp = matchup_data.copy()
        matchup_data_temp = matchup_data_temp[matchup_data_temp['roster_id'] == manager['roster_id']]

        # Filter out the last week
        matchup_data_temp = matchup_data_temp[matchup_data_temp['week'] != current_week]

        # Extract data
        x = matchup_data_temp['week']
        y = matchup_data_temp['points']

        # Calculate and plot the 3-week moving average
        window_size = 3
        moving_average = np.convolve(y, np.ones(window_size) / window_size, mode='valid')
        x_ma = x[window_size - 1:]  # Adjust x values for moving average

        # Round the x and y values
        x_rounded = np.round(x_ma, 2)
        y_rounded = np.round(moving_average, 2)

        # Plot the data and store the artist
        line, = ax.plot(x_rounded, y_rounded, label=manager['owner_id'])
        legend_artists.append(line)
        legend_labels.append(manager['owner_id'])

    ax.set_xlabel('Week')
    ax.set_ylabel('Points')
    ax.set_title('3-Week Moving Average with Rounded Line Segments')

    # Create a legend with two columns to the left of the plot
    ax.legend(legend_artists, legend_labels, loc='upper left', bbox_to_anchor=(0.5, 1))

    plt.savefig('rounded_line_moving_average.png')
    plt.clf()


def main():

    if not LEAGUE_ID:
        print("Please provide a league id")
        return

    global matchup_data, player_data, roster_data
    player_data = get_player_data()
    roster_data = get_roster_data()
    matchup_data = get_matchup_data()

    calculate_analytics()
    visualize_data()


if __name__ == '__main__':
    main()
