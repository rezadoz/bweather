#!/usr/bin/env python3
# by bryan 2025-03-20
# uses OpenWeather (API key filepath below)
# ~/.config/bweather/bweather.config

import sys
import time
import argparse
from pathlib import Path
import requests
import curses
import signal
from functools import partial
import datetime

exit_flag = False

def signal_handler(sig, frame):
    global exit_flag
    exit_flag = True

signal.signal(signal.SIGINT, signal_handler)

def get_api_key():
    config_dir = Path.home() / '.config' / 'bweather'
    config_file = config_dir / 'bweather.config'

    config_dir.mkdir(parents=True, exist_ok=True)

    if not config_file.exists():
        print("no OpenWeather API key found, enter one now")
        api_key = input().strip()
        with open(config_file, 'w') as f:
            f.write("# OpenWeather API goes here\n")
            f.write(f"{api_key}\n")
        return api_key

    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                return line

    print("Invalid API key configuration")
    sys.exit(1)

def get_weather_data(api_key, zipcode):
    urls = []
    try:
        # Get coordinates
        geo_url = f"http://api.openweathermap.org/geo/1.0/zip?zip={zipcode},us&appid={api_key}"
        urls.append(geo_url)
        geo_response = requests.get(geo_url)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        lat = geo_data['lat']
        lon = geo_data['lon']

        # Get weather data
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
        urls.append(weather_url)
        weather_response = requests.get(weather_url)
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        # Process data
        temp_k = weather_data['main']['temp']
        temp_f = (temp_k - 273.15) * 9/5 + 32
        humidity = weather_data['main']['humidity']

        # Wind data
        wind_speed = weather_data['wind']['speed'] * 2.23694  # m/s to mph
        wind_gust = weather_data['wind'].get('gust', wind_speed) * 2.23694
        wind_deg = weather_data['wind']['deg']

        # Precipitation (convert mm to inches)
        rain_1h = weather_data.get('rain', {}).get('1h', 0) * 0.0393701
        snow_1h = weather_data.get('snow', {}).get('1h', 0) * 0.0393701
        precip_in = rain_1h + snow_1h

        # Wind direction
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                     'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        wind_dir = directions[int((wind_deg + 11.25) / 22.5) % 16]

        return {
            'temp_f': temp_f,
            'humidity': humidity,
            'precip_in': precip_in,
            'wind_dir': wind_dir,
            'wind_speed_mph': wind_speed,
            'wind_gust_mph': wind_gust
        }, urls
    except Exception as e:
        print(f"Weather fetch error: {str(e)}", file=sys.stderr)
        return None, urls

def split_frame(frame):
    parts = []
    current = []
    for c in frame:
        if c in '()':
            if current:
                parts.append(''.join(current))
                current = []
            parts.append(c)
        else:
            current.append(c)
    if current:
        parts.append(''.join(current))
    return parts

def main(stdscr, api_key, zipcode, debug=False, log_config=None):
    global exit_flag
    curses.curs_set(0)
    stdscr.nodelay(1)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_BLACK)  # Orange not available, using magenta
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(8, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(9, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(10, curses.COLOR_BLUE, curses.COLOR_BLACK)
    red = curses.color_pair(1)
    stdscr.timeout(500)

    # Configure frames based on logging
    original_frames = [
        '   live   ',
        '  (live)  ',
        ' ( live ) ',
        '(  live  )'
    ]
    if log_config:
        log_base = log_config['base']
        frames = [f.replace('live', log_base) for f in original_frames]
    else:
        frames = original_frames.copy()
    frame_index = 0
    last_update = 0
    data = None
    current_urls = []
    last_log_time = 0

    while not exit_flag:
        key = stdscr.getch()
        if key in [ord('q'), 27]:
            break

        if time.time() - last_update > 60 or not data:
            new_data, urls = get_weather_data(api_key, zipcode)
            if new_data:
                data = new_data
                last_update = time.time()
            if debug:
                current_urls = urls

        # Handle logging
        if log_config and data:
            current_time = time.time()
            if current_time - last_log_time >= log_config['interval']:
                try:
                    timestamp = datetime.datetime.now().isoformat()
                    with open(log_config['filename'], 'a') as f:
                        f.write(f"{timestamp} {data['temp_f']:.1f} {data['humidity']} "
                                f"{data['precip_in']:.2f} {data['wind_dir']} "
                                f"{data['wind_speed_mph']:.1f} {data['wind_gust_mph']:.1f}\n")
                    last_log_time = current_time
                except Exception as e:
                    pass

        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()
        start_y = (max_y // 2) - 2  # Center vertically for 4 main lines

        if data:
            frame = frames[frame_index]
            frame_index = (frame_index + 1) % 4

            # Header line
            header_zip = f"{zipcode} "
            frame_parts = split_frame(frame)
            header_total_length = len(header_zip) + sum(len(p) for p in frame_parts)
            start_x_header = (max_x - header_total_length) // 2

            current_line = start_y
            x_pos = start_x_header
            stdscr.addstr(current_line, x_pos, header_zip)
            x_pos += len(header_zip)
            for part in frame_parts:
                if part in '()':
                    stdscr.addstr(current_line, x_pos, part, red)
                else:
                    stdscr.addstr(current_line, x_pos, part)
                x_pos += len(part)

            # Temperature and Humidity line
            temp_str = f"{data['temp_f']:.0f}°F"
            separator = " :: "
            humidity_str = f"{data['humidity']}% RH"
            line1 = temp_str + separator + humidity_str
            line1_length = len(line1)
            start_x_line1 = (max_x - line1_length) // 2

            temp_f = data['temp_f']
            if temp_f > 90:
                temp_color = curses.color_pair(1)
            elif 80 <= temp_f <= 90:
                temp_color = curses.color_pair(2)
            elif 70 <= temp_f < 80:
                temp_color = curses.color_pair(3)
            elif 60 <= temp_f < 70:
                temp_color = curses.color_pair(4)
            elif 50 <= temp_f < 60:
                temp_color = curses.color_pair(5)
            else:
                temp_color = curses.color_pair(6)

            humidity = data['humidity']
            if humidity < 60:
                humidity_color = curses.color_pair(7)
            elif 60 <= humidity <= 79:
                humidity_color = curses.color_pair(8)
            elif 80 <= humidity <= 95:
                humidity_color = curses.color_pair(9)
            else:
                humidity_color = curses.color_pair(10)

            stdscr.addstr(current_line + 1, start_x_line1, temp_str, temp_color)
            stdscr.addstr(current_line + 1, start_x_line1 + len(temp_str), separator)
            stdscr.addstr(current_line + 1, start_x_line1 + len(temp_str) + len(separator), humidity_str, humidity_color)

            # Wind line
            wind_line = f"wind {data['wind_dir']} {data['wind_speed_mph']:.0f}mph ({data['wind_gust_mph']:.0f}mph)"
            start_x_wind = (max_x - len(wind_line)) // 2
            stdscr.addstr(current_line + 2, start_x_wind, wind_line)

            # Precipitation line
            precip_line = f"{data['precip_in']:.2f}\"/h precipitation"
            start_x_precip = (max_x - len(precip_line)) // 2
            precip = data['precip_in']
            if precip == 0.0:
                precip_color = curses.color_pair(6)
            elif 0.01 <= precip <= 0.1:
                precip_color = curses.color_pair(5)
            elif 0.1 < precip <= 0.3:
                precip_color = curses.color_pair(8)
            elif 0.3 < precip <= 1.0:
                precip_color = curses.color_pair(9)
            else:
                precip_color = curses.color_pair(10)
            stdscr.addstr(current_line + 3, start_x_precip, precip_line, precip_color)

            # Debug URLs
            if debug and current_urls:
                debug_start_line = current_line + 4
                for i, url in enumerate(current_urls):
                    if debug_start_line + i < max_y:
                        stdscr.addstr(debug_start_line + i, 0, f"API {i+1}: {url}")
        else:
            # Fetching message
            message = "Fetching weather data..."
            start_x = (max_x - len(message)) // 2
            start_y_message = (max_y // 2)
            stdscr.addstr(start_y_message, start_x, message)

        stdscr.refresh()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Display live weather', add_help=False)
    parser.add_argument('-l', '--log', nargs=2, metavar=('MINUTES', 'FILE'), help='Enable logging mode')
    parser.add_argument('-d', '--debug', action='store_true', help='Show API URLs')
    parser.add_argument('zipcode', nargs='?', help='ZIP code')
    args = parser.parse_args()

    if not args.zipcode:
        print("usage: bweather 69420")
        print("       bweather -l MINUTES FILE 69420")
        print("as in include a zipcode")
        print("-d for debug will output API call URLs")
        print("-l enable logging mode with interval (minutes) and file")
        sys.exit(1)

    try:
        api_key = get_api_key()
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(0)

    # Validate API key and zipcode
    try:
        geo_url = f"http://api.openweathermap.org/geo/1.0/zip?zip={args.zipcode},us&appid={api_key}"
        geo_response = requests.get(geo_url)
        geo_response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e.response.json().get('message', 'Invalid API key or zipcode')}")
        sys.exit(1)

    log_config = None
    if args.log:
        try:
            log_interval_min = int(args.log[0])
            log_filename = args.log[1]
            log_config = {
                'interval': log_interval_min * 60,
                'filename': log_filename,
                'base': Path(log_filename).stem
            }
        except ValueError:
            print("Invalid log interval")
            sys.exit(1)

    try:
        curses.wrapper(partial(main,
                            api_key=api_key,
                            zipcode=args.zipcode,
                            debug=args.debug,
                            log_config=log_config))
    except KeyboardInterrupt:
        print("\nExited gracefully")
