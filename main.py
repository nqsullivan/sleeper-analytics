import os

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt
import argparse

parser = argparse.ArgumentParser(description="Analyze and visualize data from multiple Sleeper fantasy football leagues")
parser.add_argument('league_ids', nargs='+', type=str, help='List of league ids to analyze (e.g., 12345 67890)')
LEAGUE_IDS = parser.parse_args().league_ids

global LEAGUE_ID
LEAGUE_ID = LEAGUE_IDS[0]

global matchup_data, player_data, roster_data
matchup_data = pd.DataFrame()
player_data = pd.DataFrame()
roster_data = pd.DataFrame()


def get_player_data():
    player_data_file = f'player_data_{LEAGUE_ID}.csv'  # Append league_id to the file name

    # try and load from local file
    if os.path.exists(player_data_file):
        player_data = pd.read_csv(player_data_file)
        return player_data

    # Make a request to https://api.sleeper.app/v1/players/nfl
    req = requests.get('https://api.sleeper.app/v1/players/nfl')
    player_data = pd.DataFrame(req.json())
    player_data = player_data.T
    player_data = player_data.reset_index()
    player_data.to_csv(player_data_file, index=False)
    return player_data



def get_roster_data():
    roster_data_file = f'roster_data_{LEAGUE_ID}.csv'  # Append league_id to the file name

    # Make a request to https://api.sleeper.app/v1/league/<league_id>/rosters
    req = requests.get(f'https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters')
    roster_data = pd.DataFrame(req.json())

    # For each roster, get the name of the owner
    for index, row in roster_data.iterrows():
        req = requests.get(f'https://api.sleeper.app/v1/user/{row["owner_id"]}')
        roster_data.loc[index, 'owner_id'] = req.json()['display_name']

    roster_data.to_csv(roster_data_file, index=False)
    return roster_data


def get_matchup_data():
    matchup_data_file = f'matchup_data_{LEAGUE_ID}.csv'  # Append league_id to the file name

    # Get the league metadata to determine how many weeks the season has
    req = requests.get(f'https://api.sleeper.app/v1/league/{LEAGUE_ID}')
    league_info = req.json()

    # Determine the total number of weeks in the season
    total_weeks = league_info.get('settings', {}).get('playoff_week_start', 17) - 1

    # Initialize an empty DataFrame for matchup data
    matchup_data = pd.DataFrame()

    # Iterate through all weeks of the season
    for week in range(1, total_weeks + 1):
        req = requests.get(f'https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{week}')
        week_data = pd.DataFrame(req.json())
        week_data['week'] = week
        matchup_data = pd.concat([matchup_data, week_data])

    # Save the data to a CSV file
    matchup_data.to_csv(matchup_data_file, index=False)

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
    # Lineups are superflex: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 SUPERFLEX, 1 DEF, 1 K

    # Use the list of player ids to get the player data
    roster_for_week = pd.DataFrame()
    for index, matchup in matchup_data_temp.iterrows():
        for idx, player_id in enumerate(matchup['players']):
            player = player_data[player_data['player_id'] == player_id]
            roster_for_week.loc[idx, 'player_name'] = player['full_name'].values[0]
            roster_for_week.loc[idx, 'position'] = player['position'].values[0]
            roster_for_week.loc[idx, 'points'] = matchup['players_points'].get(player_id, 0)

    # Sort the roster by points
    roster_for_week = roster_for_week.sort_values(by=['points'], ascending=False)

    # Get the mandatory positions: 1 QB, 2 RB, 2 WR, 1 TE, 1 DEF, 1 K
    optimal_roster = pd.DataFrame()

    # qb
    optimal_roster = pd.concat([optimal_roster, roster_for_week[roster_for_week['position'] == 'QB'].head(1)])
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'QB'].head(1).index, inplace=True)

    # rb
    optimal_roster = pd.concat([optimal_roster, roster_for_week[roster_for_week['position'] == 'RB'].head(2)])
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'RB'].head(2).index, inplace=True)

    # wr
    optimal_roster = pd.concat([optimal_roster, roster_for_week[roster_for_week['position'] == 'WR'].head(2)])
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'WR'].head(2).index, inplace=True)

    # te
    optimal_roster = pd.concat([optimal_roster, roster_for_week[roster_for_week['position'] == 'TE'].head(1)])
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'TE'].head(1).index, inplace=True)

    # DEF
    optimal_roster = pd.concat([optimal_roster, roster_for_week[roster_for_week['position'] == 'DEF'].head(1)])
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'DEF'].head(1).index, inplace=True)

    # k
    optimal_roster = pd.concat([optimal_roster, roster_for_week[roster_for_week['position'] == 'K'].head(1)])
    roster_for_week.drop(roster_for_week[roster_for_week['position'] == 'K'].head(1).index, inplace=True)

    # Now for FLEX and SUPERFLEX, sort remaining players by points
    # flex: 1 RB, WR, or TE
    flex_players = roster_for_week[(roster_for_week['position'] == 'RB') | 
                                   (roster_for_week['position'] == 'WR') | 
                                   (roster_for_week['position'] == 'TE')].head(1)
    optimal_roster = pd.concat([optimal_roster, flex_players])
    roster_for_week.drop(flex_players.index, inplace=True)

    # superflex: 1 QB, RB, WR, or TE
    superflex_players = roster_for_week[(roster_for_week['position'] == 'QB') | 
                                        (roster_for_week['position'] == 'RB') | 
                                        (roster_for_week['position'] == 'WR') | 
                                        (roster_for_week['position'] == 'TE')].head(1)
    optimal_roster = pd.concat([optimal_roster, superflex_players])

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
    matchup_data_remaining_file = f'matchup_data_remaining_{LEAGUE_ID}.csv'  # Append league_id to the file name

    # Get the league metadata to determine how many weeks the season has
    req = requests.get(f'https://api.sleeper.app/v1/league/{LEAGUE_ID}')
    league_info = req.json()

    # Determine the total number of weeks in the season
    total_weeks = league_info.get('settings', {}).get('playoff_week_start', 17) - 1

    # Initialize an empty DataFrame for remaining matchup data
    matchup_data = pd.DataFrame()

    # Iterate through remaining weeks of the season
    for week in range(total_weeks + 1, 18):  # Adjust this range as needed
        req = requests.get(f'https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{week}')
        week_data = pd.DataFrame(req.json())
        week_data['week'] = week
        matchup_data = pd.concat([matchup_data, week_data])

    # Save the data to a CSV file
    matchup_data.to_csv(matchup_data_remaining_file, index=False)
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


def calculate_worst_10_efficiency_weeks():
    # Get the league metadata to determine how many weeks the season has and extract the year
    req = requests.get(f'https://api.sleeper.app/v1/league/{LEAGUE_ID}')
    league_info = req.json()

    # Determine the total number of weeks in the season
    total_weeks = league_info.get('settings', {}).get('playoff_week_start', 17) - 1

    # Extract the year from the league metadata ('season' field)
    league_year = league_info.get('season', 'Unknown')

    league_name = league_info.get('name', 'Unknown')

    # Create a list to store data for all weeks that will be converted into a DataFrame
    all_efficiency_data = []

    for index, manager in roster_data.iterrows():
        matchup_data_temp = matchup_data.copy()
        matchup_data_temp = matchup_data_temp[matchup_data_temp['roster_id'] == manager['roster_id']]

        # Iterate through weeks that have happened (<= total_weeks)
        for week in range(1, total_weeks + 1):
            matchup_data_temp_week = matchup_data_temp[matchup_data_temp['week'] == week]

            if not matchup_data_temp_week.empty:
                # Calculate actual points for and optimal points for the given week
                actual_pf = matchup_data_temp_week['points'].sum()
                max_pf = get_optimal_roster_from_matchup(matchup_data_temp_week)

                # Skip the week if max_pf is 0
                if max_pf == 0:
                    continue

                # Calculate efficiency for the week
                efficiency_for_week = actual_pf / max_pf if max_pf > 0 else 0

                # Calculate points missed out on for the week
                points_missed = max_pf - actual_pf

                # Append the data to the list, including the year
                all_efficiency_data.append({
                    'Team': manager['owner_id'],
                    'Name': league_name,
                    'Week': week,
                    'Year': league_year,  # Add the league year to the data
                    'Max PF': max_pf,
                    'Actual PF': actual_pf,
                    'Points Missed': points_missed,
                    'Efficiency': efficiency_for_week,  # Store the actual numeric efficiency
                    'roster_id': manager['roster_id']  # Store the roster_id to retrieve the worst team's lineup later
                })

    # Convert the list to a DataFrame
    df_efficiency = pd.DataFrame(all_efficiency_data)

    # Sort the DataFrame by Efficiency in ascending order
    df_efficiency = df_efficiency.sort_values(by='Efficiency', ascending=True)

    # Select the worst 10 weeks based on efficiency
    df_worst_10_efficiency = df_efficiency.head(10)

    # Convert Efficiency back to percentage format for display
    df_worst_10_efficiency['Efficiency'] = df_worst_10_efficiency['Efficiency'].apply(lambda x: "{:.2%}".format(x))

    return df_worst_10_efficiency


def calculate_worst_10_weeks():
    # Get the league metadata to determine how many weeks the season has and extract the year
    req = requests.get(f'https://api.sleeper.app/v1/league/{LEAGUE_ID}')
    league_info = req.json()

    # Determine the total number of weeks in the season
    total_weeks = league_info.get('settings', {}).get('playoff_week_start', 17) - 1

    # Extract the year from the league metadata ('season' field)
    league_year = league_info.get('season', 'Unknown')

    league_name = league_info.get('name', 'Unknown')

    # Create a list to store data for all weeks that will be converted into a DataFrame
    all_data = []

    for index, manager in roster_data.iterrows():
        matchup_data_temp = matchup_data.copy()
        matchup_data_temp = matchup_data_temp[matchup_data_temp['roster_id'] == manager['roster_id']]

        # Iterate through weeks that have happened (<= total_weeks)
        for week in range(1, total_weeks + 1):
            matchup_data_temp_week = matchup_data_temp[matchup_data_temp['week'] == week]

            if not matchup_data_temp_week.empty and matchup_data_temp_week['points'].sum() > 0:
                # Calculate actual points for the given week
                actual_pf = matchup_data_temp_week['points'].sum()

                # Append the data to the list, including the year
                all_data.append({
                    'Team': manager['owner_id'],
                    'Name': league_name,
                    'Week': week,
                    'Year': league_year,  # Add the league year to the data
                    'Actual PF': actual_pf,
                    'roster_id': manager['roster_id']  # Store the roster_id to retrieve the worst team's lineup later
                })

    # Convert the list to a DataFrame
    df = pd.DataFrame(all_data)

    # Sort the DataFrame by Actual PF in ascending order
    df = df.sort_values(by='Actual PF', ascending=True)

    # Select the worst 10 weeks based on Actual PF
    df_worst_10 = df.head(10)

    return df_worst_10


def calculate_best_10_weeks():
    # Get the league metadata to determine how many weeks the season has and extract the year
    req = requests.get(f'https://api.sleeper.app/v1/league/{LEAGUE_ID}')
    league_info = req.json()

    # Determine the total number of weeks in the season
    total_weeks = league_info.get('settings', {}).get('playoff_week_start', 17) - 1

    # Extract the year from the league metadata ('season' field)
    league_year = league_info.get('season', 'Unknown')

    league_name = league_info.get('name', 'Unknown')

    # Create a list to store data for all weeks that will be converted into a DataFrame
    all_data = []

    for index, manager in roster_data.iterrows():
        matchup_data_temp = matchup_data.copy()
        matchup_data_temp = matchup_data_temp[matchup_data_temp['roster_id'] == manager['roster_id']]

        # Iterate through weeks that have happened (<= total_weeks)
        for week in range(1, total_weeks + 1):
            matchup_data_temp_week = matchup_data_temp[matchup_data_temp['week'] == week]

            if not matchup_data_temp_week.empty and matchup_data_temp_week['points'].sum() > 0:
                # Calculate actual points for the given week
                actual_pf = matchup_data_temp_week['points'].sum()

                # Append the data to the list, including the year
                all_data.append({
                    'Team': manager['owner_id'],
                    'Name': league_name,
                    'Week': week,
                    'Year': league_year,  # Add the league year to the data
                    'Actual PF': actual_pf,
                    'roster_id': manager['roster_id']  # Store the roster_id to retrieve the worst team's lineup later
                })

    # Convert the list to a DataFrame
    df = pd.DataFrame(all_data)

    # Sort the DataFrame by Actual PF in ascending order
    df = df.sort_values(by='Actual PF', ascending=False)

    # Select the worst 10 weeks based on Actual PF
    df_best_10 = df.head(10)

    return df_best_10



def main():
    global LEAGUE_IDS, LEAGUE_ID

    if not LEAGUE_ID:
        print("Please provide a league id")
        return

    combined_team_stats = pd.DataFrame()

    top_10_worst_efficiency_weeks = []
    top_10_worst_weeks = []
    top_10_best_weeks = []

    for LEAGUE_ID in LEAGUE_IDS:
        print(f"Analyzing league {LEAGUE_ID}")

        # Reload global data for each league
        global matchup_data, player_data, roster_data
        player_data = get_player_data()
        roster_data = get_roster_data()
        matchup_data = get_matchup_data()

        # Concatenate stats from each league
        combined_team_stats = pd.concat([combined_team_stats, calculate_analytics()])

        # Collect top 10 weeks data
        top_10_worst_efficiency_weeks.append(calculate_worst_10_efficiency_weeks())
        top_10_worst_weeks.append(calculate_worst_10_weeks())
        top_10_best_weeks.append(calculate_best_10_weeks())

    # After processing all leagues, group by owner_id to avoid duplication across leagues
    combined_team_stats = combined_team_stats.groupby('owner_id', as_index=False).agg({
        'wins': 'sum',
        'losses': 'sum',
        'points_for': 'sum',
        'points_against': 'sum',
        'optimal_points_for': 'sum',
        'optimal_points_against': 'sum',
        'points_difference': 'sum'
    })

    combined_team_stats['win_percentage'] = combined_team_stats['wins'] / (combined_team_stats['wins'] + combined_team_stats['losses'])
    combined_team_stats['average_points_for'] = combined_team_stats['points_for'] / (combined_team_stats['wins'] + combined_team_stats['losses'])
    combined_team_stats['average_points_against'] = combined_team_stats['points_against'] / (combined_team_stats['wins'] + combined_team_stats['losses'])
    combined_team_stats['efficiency_for'] = combined_team_stats['points_for'] / combined_team_stats['optimal_points_for']
    combined_team_stats['efficiency_against'] = combined_team_stats['points_against'] / combined_team_stats['optimal_points_against']

    combined_team_stats = combined_team_stats.sort_values(by=['points_difference'], ascending=False)

    # Recalculate aggregated metrics after combining all leagues
    combined_team_stats['win_percentage'] = (combined_team_stats['wins'] / 
                                             (combined_team_stats['wins'] + combined_team_stats['losses'])).map(lambda x: "{:.2%}".format(x))

    combined_team_stats['average_points_for'] = (combined_team_stats['points_for'] / 
                                                 (combined_team_stats['wins'] + combined_team_stats['losses'])).round(2)

    combined_team_stats['average_points_against'] = (combined_team_stats['points_against'] / 
                                                     (combined_team_stats['wins'] + combined_team_stats['losses'])).round(2)

    combined_team_stats['efficiency_for'] = (combined_team_stats['points_for'] / 
                                             combined_team_stats['optimal_points_for']).map(lambda x: "{:.2%}".format(x))

    combined_team_stats['efficiency_against'] = (combined_team_stats['points_against'] / 
                                                 combined_team_stats['optimal_points_against']).map(lambda x: "{:.2%}".format(x))

    # Sort combined team stats by points_difference
    combined_team_stats = combined_team_stats.sort_values(by=['points_difference'], ascending=False).reset_index(drop=True)

    # Process top 10 worst and best weeks across all leagues
    combined_worst_efficiency_weeks = pd.concat(top_10_worst_efficiency_weeks).sort_values(by='Efficiency', ascending=True).head(10)
    combined_worst_weeks = pd.concat(top_10_worst_weeks).sort_values(by='Actual PF', ascending=True).head(10)
    combined_best_weeks = pd.concat(top_10_best_weeks).sort_values(by='Actual PF', ascending=False).head(10)

    # Display the results
    print()
    print("Combined team stats")
    print(combined_team_stats)
    print()
    print("Top 10 worst efficiency weeks across all years")
    print(combined_worst_efficiency_weeks)
    print()
    print("Top 10 worst weeks across all years")
    print(combined_worst_weeks)
    print()
    print("Top 10 best weeks across all years")
    print(combined_best_weeks)
    print()



if __name__ == '__main__':
    main()