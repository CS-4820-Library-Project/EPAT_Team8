"""
Isaac Wolters
January 26, 2024,

This file includes functions for scraping from the CRKN website and uploading the new data to the database
Some functions can also be re-used for the local file uploads (compare_file)

Works well I think - should test the update functionality

I tested new files and the same files, but not when the file has a newer date (to update)
"""
import requests.exceptions
from bs4 import BeautifulSoup
import requests
import pandas as pd
from src.utility.settings_manager import Settings
from src.data_processing import database
import os

settings_manager = Settings()
settings_manager.load_settings()
crkn_url = settings_manager.get_setting('CRKN_url')


def scrapeCRKN():
    """Scrape the CRKN website for listed ebook files."""
    error = ""
    try:
        # Make a request to the CRKN website
        response = requests.get(crkn_url)
        # Check if request was successful (status 200)
        response.raise_for_status()
        # If request successful, process text
        page_text = response.text

    except requests.exceptions.HTTPError as http_err:
        # Handle HTTP errors
        error = http_err
        page_text = None
    except requests.exceptions.ConnectionError as conn_err:
        # Handle errors like refused connections
        error = conn_err
        page_text = None
    except requests.exceptions.Timeout as timeout_err:
        # Handle request timeout
        error = timeout_err
        page_text = None
    except Exception as e:
        # Handle any other exceptions
        error = e
        page_text = None

    # We will need to address how to show errors to the users when they happen (something like show a pop up instead of returning); will leave like this for now
    if page_text is None:
        print(f"An error occurred: {error}")
        return

    soup = BeautifulSoup(page_text, "html.parser")

    # Extend list to include csv and other excel format files as well, pretty easy to update rest of code too.
    links = soup.find_all('a', href=lambda href: href and (href.endswith('.xlsx')))

    # List of files that need to be updated/added to the local database
    files = []

    # Check if links on CRKN website need to be added/updated in local database
    connection = database.connect_to_database()
    for link in links:
        file_link = link.get("href")
        file_first, file_date = split_CRKN_file_name(file_link)
        result = compare_file([file_first, file_date], "CRKN", connection)

        if result:
            files.append([link, result])
    database.close_database(connection)

    # Ask user if they want to perform scraping (slightly time-consuming)
    if len(files) > 0:
        if len(files) == 1:
            ans = input(f"There is {len(files)} files to update in the database. Would you like to do the update now? Y/N")
        else:
            ans = input(f"There are {len(files)} files to update in the database. Would you like to do the update now? Y/N")
        if ans == "Y":
            download_files(files)


def download_files(files):
    """
    For all files that need downloading from CRKN, do so and store in local database.
    :param files: list of files to download from CRKN
    """

    connection = database.connect_to_database()

    for [link, command] in files:
        file_link = link.get("href")
        file_first, file_date = split_CRKN_file_name(file_link)
        update_tables([file_first, file_date], "CRKN", connection, command)

        # Write file to temporary local file, then convert that file into a dataframe to upload to database
        with open(f"{os.path.abspath(os.path.dirname(__file__))}/temp.xlsx", 'wb') as file:
            response = requests.get(settings_manager.get_setting("CRKN_root_url") + file_link)
            file.write(response.content)
        file_df = file_to_dataframe_excel(f"{os.path.abspath(os.path.dirname(__file__))}/temp.xlsx")
        upload_to_database(file_df, file_first, connection)

    database.close_database(connection)
    os.remove(f"{os.path.abspath(os.path.dirname(__file__))}/temp.xlsx")


def compare_file(file, method, connection):
    """
    Compare file to see if it is already in database.
    :param file: file name information - [publisher, date/version number]
    :param method: CRKN or local
    :param connection: database connection object
    :return: False if no update needed. Update command if update needed (INSERT INTO or UPDATE)
    """
    if method != "CRKN" and method != "local":
        raise Exception("Incorrect method type (CRKN or local) to indicate type/location of file")

    cursor = connection.cursor()
    files = cursor.execute(f"SELECT * FROM {method}_file_names WHERE file_name = '{file[0]}'").fetchall()
    if not files:
        return "INSERT INTO"
    else:
        files_dates = cursor.execute(
            f"SELECT * FROM {method}_file_names WHERE file_name = '{file[0]}' and file_date = '{file[1]}'").fetchall()
        if not files_dates:
            return "UPDATE"
        print(f"File already there - {file[0]}, {file[1]}")
        return False


def update_tables(file, method, connection, command):
    """
    Update table with file information in local database.
    :param file: file name information - [publisher, date/version number]
    :param method: CRKN or local
    :param connection: database connection object
    :param command: INSERT INTO or UPDATE
    """
    if method != "CRKN" and method != "local":
        raise Exception("Incorrect method type (CRKN or local) to indicate type/location of file")

    cursor = connection.cursor()

    # Table does not exist, insert name and data/version
    if command == "INSERT INTO":
        cursor.execute(f"INSERT INTO {method}_file_names (file_name, file_date) VALUES ('{file[0]}', '{file[1]}')")
        print(f"file name inserted - {file[0]}, {file[1]}")

    # File exists, but needs to be updated, change date/version
    elif command == "UPDATE":
        cursor.execute(f"UPDATE {method}_file_names SET file_date = '{file[1]}' WHERE file_name = '{file[0]}';")
        print(f"file name updated - {file[0]}, {file[1]}")


def split_CRKN_file_name(file_name):
    """
    Split CRKN file name.
    :param file_name: string CRKN file name
    :return: list of two elements - publisher name and date/version number
    """
    file = file_name.split("/")[-1]
    a = file.split("_")
    c = "_".join(a[3:]).split(".")[0]

    # a[2] = Publisher name, c = data/update version
    return [a[2], c]


def file_to_dataframe_excel(file):
    """
    Convert Excel file to pandas dataframe.
    File can be either a file or a URL link to a file.
    :param file: local file to convert to dataframe
    :return: dataframe
    """
    try:
        return pd.read_excel(file, sheet_name="PA-Rights", header=2)
    # Following line isn't needed anymore, unless we keep/modify for exceptions
    except ValueError:
        return pd.read_excel(file, sheet_name="PA-rights", header=2)


def file_to_dataframe_csv(file):
    """
    Convert csv file to pandas dataframe.
    File can be either a file or a URL link to a file.
    :param file: local file to convert to dataframe
    :return: dataframe
    """
    try:
        return pd.read_csv(file, header=2)
    except ValueError:
        raise Exception("Unable to read csv file.")


def upload_to_database(df, table_name, connection):
    """
    Upload file dataframe to table in database.
    :param df: dataframe with data
    :param table_name: table to insert data into
    :param connection: database connection object
    """
    df.to_sql(
        name=table_name,
        con=connection,
        if_exists="replace",
        index=False
    )
