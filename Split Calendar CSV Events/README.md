# How to Use the Script
Follow these simple steps to run the script from your terminal.

## 1. Save the Script

Open a plain text editor (like TextEdit, VS Code, or Sublime Text).

Copy the Python code and paste it into the new file.

Save the file as split_csv.py in a convenient location.

## 2. Prepare Your CSV File

Make sure your main CSV file (e.g., AllUsersPrimaryEvents.csv) is in the same folder as the split_csv.py script you just saved.

Confirm that the first column's header is exactly primaryEmail.

In GAM7 you can run this command:
```
gam redirect csv ./AllUsersPrimaryEvents.csv all users print events primary
```

This will make a CSV with all the Events from all the users in your Google Workspace tenant's events. 

## 3. Run from the Terminal

Open the Terminal app.

Navigate to the folder where you saved the script and your CSV file. For example, if you saved them on your Desktop, you would type:

cd Desktop
Now, run the script by typing python3, followed by the script's name, and then the name of your CSV file. For example, if your main file is named AllUsersPrimaryEvents.csv, you would run:

```
python3 split_csv.py AllUsersPrimaryEvents.csv
```
The script will then run, and you will see messages in the terminal for each new file it creates (e.g., Successfully created: name_email_com.csv). Once it's finished, all the new, individual CSV files will be in that same folder.

## split_by_size.py
This is a second script that is run the same way. However this breaks the CSV file into 5 mb chunks. You can modify the size, but it makes it easier to open in Excel or Google Sheets.

```
python3 split_csv.py AllUsersPrimaryEvents.csv
```

## filter_and_split.py
This script breaks the files into more managable pieces, here you will run it with the number of days you want to filter on. This example brings in the last 30 days of events. 

```
python3 filter_and_split.py '/Users/paulogier/GAMWork/AllUsersPrimaryEvents.csv' 30
```