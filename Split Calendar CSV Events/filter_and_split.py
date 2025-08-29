import csv
import sys
import os
from collections import defaultdict
from datetime import datetime, timedelta, date

def filter_and_split_by_date(input_filename, days_ago):
    """
    Filters a CSV by a date range and splits the result into separate files
    for each user, using only standard Python libraries.
    """
    try:
        # 1. Calculate the cutoff date (using naive local time)
        cutoff_datetime = datetime.now() - timedelta(days=days_ago)
        print(f"Filtering events on or after: {cutoff_datetime.strftime('%Y-%m-%d')} (local time)...")

        # 2. Read, filter, and group data in one pass
        grouped_data = defaultdict(list)
        headers = []
        
        with open(input_filename, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            headers = reader.fieldnames

            required_headers = ['primaryEmail', 'start.date', 'start.dateTime']
            if not all(h in headers for h in required_headers):
                print(f"Error: CSV must contain the headers: {', '.join(required_headers)}")
                return

            for row in reader:
                event_datetime = None
                start_datetime_str = row.get('start.dateTime')
                start_date_str = row.get('start.date')

                try:
                    # Prioritize the more specific 'start.dateTime'
                    if start_datetime_str:
                        # Use the built-in fromisoformat and remove timezone to make it naive
                        event_datetime = datetime.fromisoformat(start_datetime_str).replace(tzinfo=None)
                    # Fallback to 'start.date' for all-day events
                    elif start_date_str:
                        event_date_obj = date.fromisoformat(start_date_str)
                        # Combine date with midnight to create a naive datetime
                        event_datetime = datetime.combine(event_date_obj, datetime.min.time())

                    # If we have a valid date and it's within our range, group it
                    if event_datetime and event_datetime >= cutoff_datetime:
                        email = row['primaryEmail']
                        if email:
                            grouped_data[email].append(row)

                except (ValueError, TypeError):
                    # Silently skip rows with malformed dates or empty values
                    continue

        # 3. Write the filtered, grouped data to individual files
        if not grouped_data:
            print("\nNo events found within the specified date range.")
            return

        print(f"\nFound {len(grouped_data)} users with events in the last {days_ago} days. Creating files...")
        
        for email, rows in grouped_data.items():
            filename_safe_email = email.replace('@', '_').replace('.', '_')
            output_filename = f"{filename_safe_email}_filtered_events.csv"
            
            with open(output_filename, mode='w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
            print(f"Created: {output_filename} with {len(rows)} event(s).")

    except FileNotFoundError:
        print(f"Error: The file '{input_filename}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python filter_and_split.py <path_to_file.csv> <days_ago>")
        print("Example: python filter_and_split.py AllUsers.csv 30")
    else:
        try:
            file_path = sys.argv[1]
            days_filter = int(sys.argv[2])
            filter_and_split_by_date(file_path, days_filter)
        except ValueError:
            print("Error: The second argument (days_ago) must be an integer.")