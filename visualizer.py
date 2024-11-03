import gpxpy
import pandas as pd
import matplotlib.pyplot as plt
from datetime import timedelta
from matplotlib.colors import LogNorm
import contextily as ctx
import geopandas as gpd
from pyproj import CRS

def load_gpx_data(gpx_file):
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
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp']) # convert timestamp to datatime object for ping data
    return df

def match_ping_to_location(gpx_df, ping_df):
    matched_data = []
    for _, ping_row in ping_df.iterrows():
        ping_time = ping_row['timestamp']
        
        # Find absolute time difference with all GPS points
        time_diffs = abs(gpx_df['timestamp'] - ping_time)
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
    
    
    if synthetic_entries:
        synthetic_df = pd.DataFrame(synthetic_entries)
        df = pd.concat([df, synthetic_df], ignore_index=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
    
    return df

gpx_file_paths = ["1strun.gpx", "run2.gpx"]
ping_csv_paths = ["ping_log.csv", "ping_log2.csv"]


gpx_df = pd.DataFrame()
ping_df = pd.DataFrame()


for gpx_path, ping_path in zip(gpx_file_paths, ping_csv_paths):
    current_gpx_df = load_gpx_data(gpx_path)
    gpx_df = pd.concat([gpx_df, current_gpx_df], ignore_index=True)

    current_ping_df = load_ping_data(ping_path)
    current_ping_df = fill_gaps_with_synthetic_data(current_ping_df)
    ping_df = pd.concat([ping_df, current_ping_df], ignore_index=True)

# Sort both DataFrames by timestamp to ensure proper ordering
gpx_df = gpx_df.sort_values('timestamp').reset_index(drop=True)
ping_df = ping_df.sort_values('timestamp').reset_index(drop=True)


matched_data = match_ping_to_location(gpx_df, ping_df)

matched_data = matched_data[matched_data["time_diff_seconds"] <= 10]

gdf = gpd.GeoDataFrame(
    matched_data, 
    geometry=gpd.points_from_xy(matched_data.longitude, matched_data.latitude),
    crs=CRS('EPSG:4326')
)


gdf = gdf.to_crs(epsg=3857)

bounds = gdf.geometry.total_bounds
center_x = (bounds[0] + bounds[2]) / 2
center_y = (bounds[1] + bounds[3]) / 2
span = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
padding = 1.2

fig, ax = plt.subplots(figsize=(12, 12))

ax.set_xlim(center_x - span / 2 * padding, center_x + span / 2 * padding)
ax.set_ylim(center_y - span / 2 * padding, center_y + span / 2 * padding)

ax.set_aspect('equal')

scatter = ax.scatter(
    gdf.geometry.x,
    gdf.geometry.y,
    c=gdf['avg_ms'],
    cmap='RdYlGn_r',
    s=100,
    alpha=0.6,
    norm=LogNorm(vmin=10, vmax=4000)  # Log scale normalization for color
)


ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron)


cbar = plt.colorbar(scatter, label='Average Ping (ms)')


plt.title('Ping Times by Location')
ax.set_axis_off()  
plt.tight_layout() 


plt.show()




fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 24))


for ax in [ax1, ax2]:
    ax.set_xlim(center_x - span/2 * padding, center_x + span/2 * padding)
    ax.set_ylim(center_y - span/2 * padding, center_y + span/2 * padding)
    ax.set_aspect('equal')
    ax.set_axis_off()

# Perform kriging
grid_xx, grid_yy, field, sigma = perform_ordinary_kriging(gdf)

# Plot 1: Interpolated values
im1 = ax1.pcolormesh(
    grid_xx, grid_yy, field,
    cmap='RdYlGn_r',
    norm=LogNorm(vmin=10, vmax=4000),
    shading='auto',
    alpha=0.5  # Reduced from 0.7
)

scatter = ax1.scatter(
    gdf.geometry.x,
    gdf.geometry.y,
    c=gdf['avg_ms'],
    cmap='RdYlGn_r',
    s=50,
    alpha=0.4,  # Reduced from 0.6
    norm=LogNorm(vmin=10, vmax=4000),
    edgecolor='black',
    linewidth=0.5
)

# Plot 2: Uncertainty
im2 = ax2.pcolormesh(
    grid_xx, grid_yy, sigma,
    cmap='viridis',
    shading='auto',
    alpha=0.5  # Reduced from 0.7
)


ctx.add_basemap(ax1, source=ctx.providers.CartoDB.Positron)
ctx.add_basemap(ax2, source=ctx.providers.CartoDB.Positron) 


cbar1 = plt.colorbar(im1, ax=ax1, label='Average Ping (ms)', shrink=0.7)
cbar2 = plt.colorbar(im2, ax=ax2, label='Kriging Standard Deviation', shrink=0.7)


ax1.set_title('Interpolated Ping Times (ms)', pad=20)
ax2.set_title('Uncertainty Map', pad=20)

plt.tight_layout()
plt.show()