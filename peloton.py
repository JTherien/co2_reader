import pandas as pd
import requests
import yaml

def get_workouts():

    with open('config.yaml', 'r') as stream:

        config = yaml.safe_load(stream)

    USER = config['peloton_user']
    PASSWORD = config['peloton_pass']

    # Authenticate user
    s = requests.Session()
    payload = {'username_or_email':USER, 'password':PASSWORD}
    s.post('https://api.onepeloton.com/auth/login', json=payload)

    # First API Call - GET User ID for all other calls
    # Get User ID to pass into other calls
    me_url = 'https://api.onepeloton.com/api/me'
    response = s.get(me_url)
    apidata = s.get(me_url).json()

    my_id = apidata['id']

    # Second API Call - GET Workout, Ride & Instructor Details
    # API URL
    url = f'https://api.onepeloton.com/api/user/{my_id}/workouts?joins=ride,ride.instructor&limit=250&page=0'
    response = s.get(url)
    data = s.get(url).json()

    # Flatten API reponse into a temporary dataframe
    df_workouts = pd.json_normalize(data['data'])
    df_workouts['created_at_clean'] = pd.to_datetime(df_workouts.created_at, unit='s')
    df_workouts['end_time_clean'] = pd.to_datetime(df_workouts.end_time, unit='s')
    df_workouts['duration'] = df_workouts.end_time_clean - df_workouts.created_at_clean

    return df_workouts