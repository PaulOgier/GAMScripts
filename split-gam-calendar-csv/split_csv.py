import csv
import sys
from collections import defaultdict

def split_csv_by_email(input_filename):
    """
    Reads a master CSV file, groups rows by the 'primaryEmail' column,
    and saves each group into its own separate CSV file.
    """
    try:
        # Phase 1: Read the entire CSV and group rows by email address in memory
        # defaultdict(list) creates a dictionary where each value is a list by default
        grouped_data = defaultdict(list)
        headers = []

        with open(input_filename, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            headers = reader.fieldnames

            if 'primaryEmail' not in headers:
                print("Error: A header column named 'primaryEmail' was not found.")
                return

            for row in reader:
                email = row['primaryEmail']
                if email:
                    grouped_data[email].append(row)
                else:
                    print("Warning: Found a row with an empty 'primaryEmail'. Skipping.")
        
        if not grouped_data:
            print("No data was found to process.")
            return

        # Phase 2: Write the grouped data to individual files
        print(f"\nFound data for {len(grouped_data)} unique emails. Creating files...")
        for email, rows in grouped_data.items():
            # Create a safe filename from the email address
            # name@email.com -> name_email_com.csv
            new_filename = email.replace('@', '_').replace('.', '_') + '.csv'

            with open(new_filename, mode='w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=headers)
                writer.writeheader()  # Write the header row
                writer.writerows(rows) # Write all the rows for this email at once

            print(f"Successfully created: {new_filename} with {len(rows)} event(s).")

    except FileNotFoundError:
        print(f"Error: The file '{input_filename}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_csv.py <your_main_file.csv>")
    else:
        csv_file_to_split = sys.argv[1]
        split_csv_by_email(csv_file_to_split)