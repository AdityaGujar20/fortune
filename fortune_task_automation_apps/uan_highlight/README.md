# PDF UAN Highlighter Web Application

A Flask-based web application for highlighting UAN numbers in PDF documents based on site criteria.

## Features

- Upload Excel files with UAN numbers and site information
- Upload PDF files to be processed
- Configure highlight options:
  - Choose between border, highlight, or underline modes
  - Select colors for regular and special highlights
  - Adjust border width and highlight opacity
  - Configure expansion settings for better visibility
- Process PDFs and generate site-specific output files
- Real-time log streaming during processing
- Download individual site PDFs or all PDFs as a ZIP file
- Track job progress with status updates

## Installation

1. Clone this repository or download the files

2. Create a virtual environment (recommended)

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages
   ```bash
   pip install -r requirements.txt
   ```

## Required Dependencies

This application requires the following Python packages:

```
flask
pandas
PyMuPDF
werkzeug
openpyxl
```

These are listed in the `requirements.txt` file.

## Project Structure

```
pdf-uan-highlighter/
├── app.py                # Main Flask application
├── highlight_script.py   # Core highlighting functionality
├── templates/            # HTML templates
│   └── index.html        # Main page template
├── static/               # Static files
│   └── css/
│       └── style.css     # Custom styles
├── uploads/              # Directory for uploaded files
├── results/              # Directory for processed PDFs
├── logs/                 # Directory for log files
└── requirements.txt      # Python dependencies
```

## Usage

1. Start the application

   ```bash
   python app.py
   ```

2. Open your web browser and navigate to `http://127.0.0.1:5000`

3. Upload an Excel file containing:

   - A column with UAN numbers
   - A column with site names
   - Optionally, a column for special highlighting criteria

4. Upload a PDF file that contains the UAN numbers

5. Configure your highlighting options:

   - Select the UAN column and Site column from your Excel file
   - Optionally select a Special column for additional highlighting
   - Adjust highlighting mode, colors, and other settings

6. Click "Process Highlighting" to start the job

7. Monitor progress in the logs section

8. Once completed, download individual site PDFs or all PDFs as a ZIP file

## Highlighting Modes

- **Border**: Adds a rectangle border around UAN numbers
- **Highlight**: Fills a rectangle behind UAN numbers with semi-transparent color
- **Underline**: Draws a line under UAN numbers

## Special Highlighting

If you select a Special column, any UAN with a non-empty value in that column will be highlighted with the special color instead of the primary color.

## Folder Structure

- **uploads/**: Stores uploaded Excel and PDF files
- **results/**: Contains generated site-specific PDFs
- **logs/**: Stores application logs
