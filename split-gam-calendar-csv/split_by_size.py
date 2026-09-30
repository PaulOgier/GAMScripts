import os
import sys
import csv

def split_csv_by_size(input_filename, max_size_mb=5):
    """
    Splits a large CSV file into smaller chunks of a specified maximum size.

    Args:
        input_filename (str): The path to the large CSV file.
        max_size_mb (int): The maximum size for each chunk in megabytes.
    """
    if not os.path.exists(input_filename):
        print(f"Error: File not found at '{input_filename}'")
        return

    # Convert megabytes to bytes
    max_size_bytes = max_size_mb * 1024 * 1024
    file_count = 1
    
    # Get the base name for output files (e.g., 'AllUsers' from 'AllUsers.csv')
    output_base_name = os.path.splitext(os.path.basename(input_filename))[0]

    try:
        with open(input_filename, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            
            # Read the header, which will be added to every chunk
            try:
                header = next(reader)
            except StopIteration:
                print("Error: The CSV file is empty.")
                return

            current_chunk_rows = []
            current_chunk_size = 0

            for row in reader:
                # Estimate row size in bytes (simple but effective)
                row_string = ','.join(row) + '\n'
                row_size = len(row_string.encode('utf-8'))

                # If adding the next row exceeds the max size, write the current chunk
                if current_chunk_size + row_size > max_size_bytes and current_chunk_rows:
                    write_chunk(output_base_name, file_count, header, current_chunk_rows)
                    file_count += 1
                    current_chunk_rows = []
                    current_chunk_size = 0
                
                # Add the row to the current chunk
                current_chunk_rows.append(row)
                current_chunk_size += row_size

            # Write any remaining rows to the last chunk file
            if current_chunk_rows:
                write_chunk(output_base_name, file_count, header, current_chunk_rows)
        
        print("\nSplitting process completed successfully.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def write_chunk(base_name, part_number, header, rows):
    """Writes a list of rows to a new CSV file chunk."""
    output_filename = f"{base_name}_part_{part_number}.csv"
    print(f"Creating chunk: {output_filename}...")
    
    with open(output_filename, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(header)
        writer.writerows(rows)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_by_size.py <path_to_your_large_file.csv> [max_size_in_mb]")
        print("Example: python split_by_size.py data.csv 5")
    else:
        input_file = sys.argv[1]
        
        # Optional: Allow user to specify a different size
        size = 5
        if len(sys.argv) > 2:
            try:
                size = int(sys.argv[2])
            except ValueError:
                print("Error: The size must be a valid integer (e.g., 5).")
                sys.exit(1) # Exit the script
        
        split_csv_by_size(input_file, max_size_mb=size)