import gpxpy
import pandas as pd
from datetime import timedelta

def load_gpx_data(gpx_file):
    """Load GPX file and extract timestamps and coordinates, adjusting UTC time to local time (EST)"""
    with open(gpx_file, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # Adjust UTC time to local time (subtract 5 hours for EST)
                local_time = point.time.replace(tzinfo=None) - timedelta(hours=7)
                points.append({
                    'timestamp': local_time,
                    'latitude': point.latitude,
                    'longitude': point.longitude
                })
    
    return pd.DataFrame(points)

def load_ping_data(csv_file):
    """Load ping data from CSV file."""
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp']) # convert timestamp to datatime object for ping data
    return df

def match_ping_to_location(gpx_df, ping_df):
    """Match ping data to closest GPS coordinates by timestamp."""
    matched_data = []
    for _, ping_row in ping_df.iterrows():
        ping_time = ping_row['timestamp']
        
        # Find absolute time difference with all GPS points
        time_diffs = abs(gpx_df['timestamp'] - ping_time)
        
        # Get the index of the closest point
        closest_idx = time_diffs.argmin()
        closest_point = gpx_df.iloc[closest_idx]
        
        matched_data.append({
            'timestamp': ping_time,
            'latitude': closest_point['latitude'],
            'longitude': closest_point['longitude'],
            'min_ms': ping_row['min_ms'],
            'avg_ms': ping_row['avg_ms'],
            'max_ms': ping_row['max_ms'],
            'packet_loss': ping_row['packet_loss'],
            'time_diff_seconds': time_diffs[closest_idx].total_seconds()
        })
    
    return pd.DataFrame(matched_data)

def fill_gaps_with_synthetic_data(df, threshold_seconds=7):
    '''Checks gaps between consecutive timestamps in ping, filling gaps over threshold_seconds with syntthetic entries'''
    df = df.sort_values('timestamp').copy()
    synthetic_entries = []
    
    for i in range(len(df) - 1):
        current_time = df.iloc[i]['timestamp']
        next_time = df.iloc[i + 1]['timestamp']
        time_diff = (next_time - current_time).total_seconds()
        
        if time_diff > threshold_seconds:
            # Calculate number of missing entries
            missing_intervals = int(time_diff / 5) - 1  # 5 seconds is normal interval

            #  Adds synthetic data for each missing interval, assuming 100% packet loss to represent downtime.
            for j in range(missing_intervals):
                synthetic_time = current_time + timedelta(seconds=(j + 1) * 5)
                synthetic_entries.append({
                    'timestamp': synthetic_time,
                    'min_ms': 4000,
                    'avg_ms': 4000,
                    'max_ms': 4000,
                    'packet_loss': 100.0  # 100% packet loss
                })
    
    # Add synthetic entries to original dataframe
    if synthetic_entries:
        synthetic_df = pd.DataFrame(synthetic_entries)
        df = pd.concat([df, synthetic_df], ignore_index=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
    
    return df

# File paths for both runs
gpx_file_paths = ["1strun.gpx", "run2.gpx"]
ping_csv_paths = ["ping_log.csv", "ping_log2.csv"]

# Initialize empty DataFrames
gpx_df = pd.DataFrame()
ping_df = pd.DataFrame()

# Load and combine data from both sets
for gpx_path, ping_path in zip(gpx_file_paths, ping_csv_paths):
    # Load and combine GPX data
    current_gpx_df = load_gpx_data(gpx_path)
    gpx_df = pd.concat([gpx_df, current_gpx_df], ignore_index=True)
    
    # Load and combine ping data
    current_ping_df = load_ping_data(ping_path)
    current_ping_df = fill_gaps_with_synthetic_data(current_ping_df)
    ping_df = pd.concat([ping_df, current_ping_df], ignore_index=True)

# Sort both DataFrames by timestamp to ensure proper ordering
gpx_df = gpx_df.sort_values('timestamp').reset_index(drop=True)
ping_df = ping_df.sort_values('timestamp').reset_index(drop=True)
