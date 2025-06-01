# PDF Highlighter Application

A Flask-based web application that highlights UAN/ESIC numbers in PDF documents and identifies PF ECR name mismatches. Designed for HR departments to process payroll documents efficiently.

## Features

### UAN/ESIC Highlighting
- Upload Excel files containing employee data and corresponding PDF documents
- Highlight UAN (12-digit) or ESIC (10-digit) numbers in PDFs
- Process documents by site/location for organized output
- Multiple highlighting modes: border, highlight, or underline
- Customizable colors and opacity settings
- Batch processing with progress tracking

### PF ECR Name Mismatch Detection
- Upload PF ECR PDF files
- Automatically detect name mismatches between ECR and UAN Repository
- Export mismatched records to Excel format
- Smart name matching using fuzzy logic

## Prerequisites

- Python 3.7+
- Required Python packages (see Installation section)

## Installation

1. **Clone or download the application files**

2. **Install required packages:**
   ```bash
   pip install flask pandas PyMuPDF pdfplumber werkzeug
   ```

3. **Create required directories:**
   The application will automatically create these directories:
   - `uploads/` - Temporary file storage
   - `outputs/` - Processed files
   - `logs/` - Application logs

## Usage

### Starting the Application

1. **Run the application:**
   ```bash
   python app.py
   ```

2. **Access the web interface:**
   - The application will automatically open in your default browser
   - Or manually navigate to: `http://localhost:5000`

3. **Login credentials:**
   - Username: `hrdept`
   - Password: `hr@2008`

### UAN/ESIC Highlighting Process

1. **Upload Files:**
   - Select an Excel file containing employee data
   - Select the corresponding PDF document to highlight
   - Click "Upload Files"

2. **Configure Highlighting:**
   - Choose highlight type: UAN or ESIC
   - Select the appropriate columns from your Excel file:
     - UAN Column (for UAN highlighting)
     - ESIC Column (for ESIC highlighting)
     - Site Column (to organize output by location)
   - Choose highlighting options:
     - Mode: Border, Highlight, or Underline
     - Color: Red, Blue, Green, Black, Orange, or Yellow
     - Opacity: 0.1 to 1.0 (for highlight mode)

3. **Process and Download:**
   - Click "Start Processing"
   - Monitor progress in real-time
   - Download individual files or all files as a ZIP

### PF ECR Name Mismatch Detection

1. **Upload PF ECR PDF:**
   - Select "PF ECR Name Mismatch" tab
   - Upload a PF ECR PDF file
   - Click "Process PDF"

2. **Review Results:**
   - View mismatched records in the web interface
   - Download the Excel file containing all mismatches
   - Use "Start Fresh" to process another file

## File Requirements

### Excel Files
- Must be in `.xlsx` format
- Should contain columns for:
  - UAN numbers (12 digits)
  - ESIC numbers (10 digits)
  - Site/location information

### PDF Files
- Must be in `.pdf` format
- Should contain searchable text
- For PF ECR files: Must follow standard PF ECR format

## Technical Details

### Supported Formats
- **Input:** Excel (.xlsx), PDF (.pdf)
- **Output:** PDF (highlighted), Excel (.xlsx for mismatches)

### Highlighting Logic
- **UAN:** Validates 12-digit numeric strings
- **ESIC:** Validates 10-digit numeric strings
- Filters out invalid entries (null, zero, non-numeric)
- Creates separate output files for each site/location

### Name Matching Algorithm
- Compares first 4 and last 4 characters
- Analyzes middle characters for similarity
- Removes whitespace and normalizes case
- Identifies potential mismatches for manual review

## Security Features

- Session-based authentication
- Secure file handling with filename sanitization
- Temporary file cleanup after processing
- Input validation and error handling

## Troubleshooting

### Common Issues

1. **Files not uploading:**
   - Check file formats (.xlsx for Excel, .pdf for PDF)
   - Ensure files are not corrupted or password-protected

2. **No highlights appearing:**
   - Verify UAN/ESIC numbers are in correct format
   - Check if PDF contains searchable text
   - Ensure column mappings are correct

3. **Processing errors:**
   - Check application logs in the `logs/` directory
   - Verify Excel file contains required columns
   - Ensure PDF is not password-protected

### Log Files
Application logs are stored in the `logs/` directory with timestamps. Check these files for detailed error information.

## Deployment

### Standalone Executable
The application can be packaged using PyInstaller:
```bash
pip install pyinstaller
pyinstaller --onefile --add-data "templates:templates" --add-data "static:static" app.py
```

### Production Deployment
For production use:
1. Change the secret key in the application
2. Use a proper database instead of the simple user dictionary
3. Configure appropriate logging levels
4. Set up SSL/HTTPS
5. Use a production WSGI server like Gunicorn

## File Structure

```
├── app.py                 # Main application file
├── templates/            # HTML templates
│   ├── index.html        # Main interface
│   └── login.html        # Login page
├── static/              # CSS, JS, and other static files
├── uploads/             # Temporary uploaded files (auto-created)
├── outputs/             # Processed output files (auto-created)
└── logs/                # Application logs (auto-created)
```

## License

This application is for internal use. Ensure compliance with your organization's software usage policies.

## Support

For technical support or feature requests, contact your IT department or the application maintainer.

## Version History

- **v1.0** - Initial release with UAN/ESIC highlighting and PF ECR mismatch detection
- Features include multi-site processing, customizable highlighting, and web-based interface