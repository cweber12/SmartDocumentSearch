import os
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, 
    QFileDialog, QTextEdit, QMessageBox, QHBoxLayout
)
import s3_operations  # Import functions from s3_operations.py


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("S3 Document Uploader & Query")
        self.layout = QVBoxLayout()
        
        # Upload Section
        self.upload_label = QLabel("Upload Files or Folders:")
        self.layout.addWidget(self.upload_label)
        
        upload_buttons_layout = QHBoxLayout()
        self.upload_file_btn = QPushButton("Upload File")
        self.upload_file_btn.clicked.connect(self.handle_upload_file)
        upload_buttons_layout.addWidget(self.upload_file_btn)
        
        self.upload_folder_btn = QPushButton("Upload Folder")
        self.upload_folder_btn.clicked.connect(self.handle_upload_folder)
        upload_buttons_layout.addWidget(self.upload_folder_btn)
        
        self.layout.addLayout(upload_buttons_layout)
        
        # Query Section
        self.query_label = QLabel("Enter keyword to search documents:")
        self.layout.addWidget(self.query_label)
        
        self.keyword_input = QLineEdit()
        self.layout.addWidget(self.keyword_input)
        
        self.query_btn = QPushButton("Query Documents")
        self.query_btn.clicked.connect(self.handle_query_documents)
        self.layout.addWidget(self.query_btn)
        
        # Log Output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.layout.addWidget(self.log_output)
        
        self.setLayout(self.layout)
    
    def append_log(self, message):
        self.log_output.append(message)
    
    def handle_upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if file_path:
            result = s3_operations.upload_file(file_path)
            self.append_log(result)
    
    def handle_upload_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Upload")
        if folder_path:
            # Upload all files in the folder (non-recursive)
            for item in os.listdir(folder_path):
                full_path = os.path.join(folder_path, item)
                if os.path.isfile(full_path):
                    result = s3_operations.upload_file(full_path)
                    self.append_log(result)
    
    def handle_query_documents(self):
        keyword = self.keyword_input.text().strip()
        if not keyword:
            QMessageBox.warning(self, "Input Error", "Please enter a keyword to query.")
            return
        found_links, log_messages = s3_operations.query_documents(keyword)
        self.append_log(log_messages)
        if found_links:
            self.append_log("\nDocuments where keyword was found (click the link to view):")
            for s3_key, url in found_links:
                self.append_log(f"{s3_key}: {url}")
        else:
            self.append_log("No matching documents found.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

