import time
import csv
from datetime import datetime
import subprocess
import statistics
import speedtest
import threading
import regex as re

def get_connected_wifi_signal_strength():
    try:
        output = subprocess.check_output(['sudo', 'wdutil', 'info'], stderr=subprocess.STDOUT, text=True)
        rssi_pattern = r'RSSI\s+:\s+([-+]?\d+)\s+dBm'
        match = re.search(rssi_pattern, output)

        if match:
            rssi = int(match.group(1))
            strength = max(0, min(100, (rssi + 100) * 2))
            print(f"RSSI: {rssi} dBm, Strength: {strength}%")
            return rssi, strength

        print("RSSI value not found in the output.")
        return None, None

    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e.output}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None, None

def get_ping_stats(host="8.8.8.8", count=3):
    """Ping Google's DNS server and return statistics"""
    try:
        output = subprocess.check_output(
            ['ping', '-c', str(count), host],
            encoding='utf-8'
        )
        
        time_pattern = r'time=(\d+\.\d+) ms'
        loss_pattern = r'(\d+)% packet loss'
        stats_pattern = r'round-trip min/avg/max/stddev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms'
        
        times = [float(t) for t in re.findall(time_pattern, output)]
        loss_match = re.search(loss_pattern, output)
        packet_loss = float(loss_match.group(1)) if loss_match else 0.0
        
        stats_match = re.search(stats_pattern, output)
        if stats_match:
            min_time, avg_time, max_time, stddev_time = map(float, stats_match.groups())
        else:
            min_time = min(times) if times else None
            max_time = max(times) if times else None
            avg_time = statistics.mean(times) if times else None

        return {
            'min': min_time,
            'max': max_time,
            'avg': avg_time,
            'packet_loss': packet_loss
        }

    except Exception as e:
        print(f"Ping Error: {str(e)}")
        return None

def get_speed_test():
    try:
        print("Starting speed test...")
        st = speedtest.Speedtest()
        st.get_best_server()
        
        download_speed = st.download() / 1_000_000
        upload_speed = st.upload() / 1_000_000
        ping = st.results.ping
        
        return {
            'download': round(download_speed, 2),
            'upload': round(upload_speed, 2),
            'ping': round(ping, 2)
        }
    except Exception as e:
        print(f"Speed Test Error: {str(e)}")
        return None

def write_to_csv(filename, data, fieldnames):
    with open(filename, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if csvfile.tell() == 0:
            writer.writeheader()
        writer.writerow(data)
        csvfile.flush()

def speed_test_loop():
    """Run speed tests every 5 minutes"""
    fieldnames = ['timestamp', 'download_mbps', 'upload_mbps', 'ping_ms']
    while True:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        results = get_speed_test()
        
        if results:
            data = {
                'timestamp': timestamp,
                'download_mbps': results['download'],
                'upload_mbps': results['upload'],
                'ping_ms': results['ping']
            }
            write_to_csv('speed_log2.csv', data, fieldnames)
            print(f"\n[{timestamp}] Speed Test:")
            print(f"Download: {results['download']} Mbps")
            print(f"Upload: {results['upload']} Mbps")
            print(f"Ping: {results['ping']} ms")
        
        time.sleep(120)

def ping_loop():
    """Run ping tests every 5 seconds"""
    fieldnames = ['timestamp', 'min_ms', 'avg_ms', 'max_ms', 'packet_loss']
    while True:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        results = get_ping_stats(count=3)
        
        if results:
            data = {
                'timestamp': timestamp,
                'min_ms': round(results['min'], 2),
                'avg_ms': round(results['avg'], 2),
                'max_ms': round(results['max'], 2),
                'packet_loss': round(results['packet_loss'], 2)
            }
            write_to_csv('ping_log2.csv', data, fieldnames)
            print(f"Ping: {data['avg_ms']}ms", end='\r')
        
        time.sleep(5)

def main():
    print("Starting network performance logging... Press Ctrl+C to stop.")
    
    speed_thread = threading.Thread(target=speed_test_loop, daemon=True)
    ping_thread = threading.Thread(target=ping_loop, daemon=True)
    
    speed_thread.start()
    ping_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nData collection stopped.")

if __name__ == "__main__":
    main()