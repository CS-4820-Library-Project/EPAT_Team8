from PyQt6.QtWidgets import QFileDialog, QApplication, QMessageBox, QProgressDialog
from PyQt6.QtCore import Qt
from src.data_processing import database, Scraping
import sys
import datetime
from src.utility.logger import m_logger
from src.utility.settings_manager import Settings


settings_manager = Settings()
language = settings_manager.get_setting("language")


def upload_and_process_file():
    """
    Upload and process local files into local database
    """
    language = settings_manager.get_setting("language")
    app = QApplication.instance()  # Try to get the existing application instance
    if app is None:  # If no instance exists, create a new one
        app = QApplication(sys.argv)

    options = QFileDialog.Option.ReadOnly

    file_paths, _ = QFileDialog.getOpenFileNames(None, "Open File" if language == "english" else "Ouvrir le fichier", "", 
                                                "CSV TSV or Excel (*.csv *.tsv *.xlsx);;All Files (*)" if language == "english" else
                                                "CSV TSV ou Excel (*.csv *.tsv *.xlsx);;Tous les fichiers (*)", options=options)

    # Iterate through selected file(s) to process them
    if file_paths:
        for file_path in file_paths:
            process_file(file_path)


def process_file(file_path):
    """
    Process file and store in local database - similar to Scraping.download_files, but for local files
    :param file_path: string containing the path to the file 
    """
    app = QApplication.instance()  # Try to get the existing application instance
    if app is None:  # If no instance exists, create a new one
        app = QApplication(sys.argv)

    # Feedback pop-up
    progress_dialog = QProgressDialog("Processing File..." if language == "english" else "Fichier en cours de traitement", None, 0, 0)
    progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
    progress_dialog.setMinimumDuration(0)
    progress_dialog.show()

    connection = database.connect_to_database()

    # Get file_name and date for table information
    file_name = file_path.split("/")[-1].split(".")
    date = datetime.datetime.now()
    date = date.strftime("%Y_%m_%d")

    # Check if local file is already in database
    result = Scraping.compare_file([file_name[0], date], "local", connection)

    # If result is update, check if they want to update it
    if result == "UPDATE":
        reply = QMessageBox.question(None, "Replace File" if language == "english" else "Remplacer le fichier",
                                     f"{file_name[0]}\nA file with the same name is already in the local database. Would you like to replace it with the new file?" if language == "english" else f"{file_name[0]}\nUn fichier du même nom se trouve déjà dans la base de données locale. Souhaitez-vous le remplacer par le nouveau fichier ?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            database.close_database(connection)
            progress_dialog.cancel()
            return

    try:
        # Get our dataframe, check if it's good
        file_df = file_to_df(file_name, file_path)
        if (file_df is None):
            database.close_database(connection)
            progress_dialog.cancel()
            return

        # Check if in correct format
        valid_file = Scraping.check_file_format(file_df)
        if not valid_file:
            m_logger.error("Invalid file format.")
            QMessageBox.warning(None, "Invalid File Format" if language == "english" else "Format de fichier invalide", 
                                f"{file_name[0]}\nThe file was not in the correct format.\nUpload aborted." if language == "english" else 
                                f"{file_name[0]}\nLe fichier n'était pas au bon format.\nTéléchargement interrompu.", QMessageBox.StandardButton.Ok)
            database.close_database(connection)
            progress_dialog.cancel()   
            return
        
        # If there are new institutions, check if the user wants to add them.
        # If no, cancel upload of file
        new_institutions = get_new_institutions(file_df)
        if len(new_institutions) > 0: # Get a display string of 5 institutions
            new_institutions_display = '\n'.join(new_institutions[:5]) 
            if len(new_institutions) > 5:
                new_institutions_display += '...'
            reply = QMessageBox.question(None, "New Institutions", f"{len(new_institutions)} institution name{'s' if len(new_institutions) > 1 else ''} found that " +
                                        f"{'are' if len(new_institutions) > 1 else 'is'} not a CRKN institution and {'are' if len(new_institutions) > 1 else 'is'} not on the list of local institutions.\n" +
                                        f"{new_institutions_display}\n" +
                                        "Would you like to add them to the local list? \n'No' - The file will not be uploaded. \n'Yes' - The new institution names will be added as options" + 
                                        "and available in the settings menu.",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                database.close_database(connection)
                progress_dialog.cancel()
                return
            
        # Add new institutions
        for institution in new_institutions:
            settings_manager.add_local_institution(institution)

        Scraping.upload_to_database(file_df, "local_" + file_name[0], connection)
        Scraping.update_tables([file_name[0], date], "local", connection, result)

        QMessageBox.information(None, "File Upload" if language == "english" else "Téléchargement de fichiers", f"{file_name[0]}\nYour file has been uploaded. {len(file_df)} rows have been added." if language == "english" else f"{file_name[0]}\nVotre fichier a été téléchargé. {len(file_df)} lignes ont été ajoutées.", QMessageBox.StandardButton.Ok)
            

    except Exception as e:
        m_logger.error(f"{file_name[0]}\nAn error occurred during file processing: {str(e)}")
        QMessageBox.critical(None, "Error" if language == "english" else "Erreur", f"{file_name[0]}\nAn error occurred during file processing: {str(e)}" if language == "english" else f"{file_name[0]}\nUne erreur s'est produite lors du traitement du fichier: {str(e)}", QMessageBox.StandardButton.Ok)

    database.close_database(connection)
    progress_dialog.cancel()


def remove_local_file(file_name):
    """
    Remove local file from database - helper function for Scraping.update_tables
    :param file_name: the name of the file to remove
    """
    connection = database.connect_to_database()
    Scraping.update_tables([file_name], "local", connection, "DELETE")
    database.close_database(connection)


def get_new_institutions(file_df):
    """
    Get and return list of institutions that are not in either the CRKN or local list from a new file dataframe
    :param file_df: file in the form of a pandas dataframe
    :return: list of new string institutions
    """

    # If no dataframe, there's no new institutions
    if file_df is None:
        return []
    headers = file_df.columns.to_list()
    new_inst = []

    # For institution in institution section of dataframe
    for inst in headers[8:-2]:
        if inst not in settings_manager.get_setting("CRKN_institutions"):
            if inst not in settings_manager.get_setting("local_institutions"):
                # If not in either list, add to new list
                new_inst.append(inst)
    return new_inst

def file_to_df(file_name, file_path):
    """
    Convert a file to a dataframe
    :param file_name: An array of format ['filename', 'file_extension']
    :param file_path: A string containing the file path.
    :return: Dataframe or None
    """
    m_logger.info(f"Processing file: {file_path}")
    # Convert file into dataframe
    if file_name[-1] == "csv":
        file_df = Scraping.file_to_dataframe_csv(".".join(file_name), file_path)
    elif file_name[-1] == "xlsx":
        file_df = Scraping.file_to_dataframe_excel(".".join(file_name), file_path)
    elif file_name[-1] == "tsv":
        file_df = Scraping.file_to_dataframe_tsv(".".join(file_name), file_path)
    else:
        m_logger.error("Invalid file type selected.")
        QMessageBox.warning(None, "Invalid File Type" if language == "english" else "Type de fichier invalide", f"{file_name[0]}\nSelect only valid xlsx, csv or tsv files." if language == "english" else f"{file_name[0]}\nSélectionnez uniquement les fichiers xlsx, csv ou tsv valides.", QMessageBox.StandardButton.Ok)
        return None
    return file_df