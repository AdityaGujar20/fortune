# Agreement Management System

A comprehensive Flask-based web application for managing business agreements, contracts, and renewals with automated tracking, email notifications, and detailed analytics.

## Features

### Core Functionality
- **Agreement Upload & Storage**: Upload and organize agreements by year with secure file handling
- **Status Tracking**: Automatic status updates (Active, Expired, Renewed) based on end dates
- **Renewal Management**: Easy agreement renewal with history tracking
- **Email Notifications**: Send renewal reminders to primary and secondary contacts
- **Document Management**: View and download agreement documents directly from the web interface

### Analytics & Reporting
- **Dashboard**: Visual analytics with pie charts, bar charts, and histograms
- **Expiring Agreements**: Track agreements expiring in 0-10, 11-30, and 31-60 day ranges
- **Excel Export**: Download filtered agreement data as Excel files
- **Agreement History**: View complete renewal chain for any agreement

### User Management
- Secure login system with session management
- Role-based access control

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Required Python Packages
```bash
pip install flask sqlite3 pandas matplotlib openpyxl werkzeug
```

### Setup Instructions

1. **Clone or download the application files**
2. **Create the required directory structure**:
   ```
   your-app-directory/
   ├── app.py
   ├── all_agreements/
   ├── templates/
   └── static/
   ```

3. **Configure Email Settings** (Optional):
   Edit the email configuration in `app.py`:
   ```python
   EMAIL_ADDRESS = "your-email@gmail.com"
   EMAIL_PASSWORD = "your-app-password"
   SMTP_SERVER = "smtp.gmail.com"
   SMTP_PORT = 587
   ```

4. **Set Secret Key**:
   Replace the default secret key in `app.py`:
   ```python
   app.config['SECRET_KEY'] = 'your-unique-secret-key'
   ```

5. **Run the application**:
   ```bash
   python app.py
   ```

6. **Access the application**:
   Open your browser and navigate to `http://localhost:5000`

## Usage Guide

### 1. Login
Access the system using the provided credentials or your configured login details.

### 2. Dashboard
The main dashboard provides:
- **Status Distribution**: Pie chart showing Active, Expired, and Renewed agreements
- **Expiring Soon**: Bar chart of agreements expiring in different time ranges
- **Days Remaining Distribution**: Histogram of all agreement timelines

### 3. Upload Agreement
Navigate to `/upload` to add new agreements:
- Fill in company and contact details
- Upload the agreement document (PDF, DOC, etc.)
- Set start and end dates
- Optionally add secondary contact information

### 4. View Agreements
- **All Agreements**: `/agreements` - View all agreements with filtering options
- **Expiring Soon**: `/expiring` - Focus on agreements expiring within 60 days
- Filter by status: Active, Expired, Renewed
- Sort by days remaining (ascending)

### 5. Agreement Actions
For each agreement, you can:
- **View Document**: Open the uploaded file in browser
- **Download**: Save the document to your computer
- **Send Email**: Send renewal reminders to contacts
- **Renew**: Create a new agreement linked to the current one
- **Terminate**: Set end date to today and mark as expired
- **View History**: See the complete renewal chain
- **Remove**: Delete the agreement and associated file

### 6. Export Data
- Download filtered agreement lists as Excel files
- Available for both all agreements and expiring agreements views
- Includes all relevant fields and calculated days remaining

## File Organization

Uploaded agreements are automatically organized by year:
```
all_agreements/
├── 2023/
│   ├── agreement1.pdf
│   └── agreement2.docx
├── 2024/
│   ├── agreement3.pdf
│   └── agreement4.docx
└── 2025/
    └── agreement5.pdf
```

## Database Schema

The application uses SQLite with the following structure:

```sql
CREATE TABLE agreements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT,
    person_name TEXT,
    designation TEXT,
    contact_number TEXT,
    email_id TEXT,
    start_date TEXT,
    end_date TEXT,
    filename TEXT,
    previous_agreement_id INTEGER,
    status TEXT DEFAULT 'Active',
    second_person_name TEXT,
    second_email_id TEXT,
    FOREIGN KEY(previous_agreement_id) REFERENCES agreements(id)
);
```

## Security Features

- **Session Management**: Secure user sessions with login requirements
- **File Security**: Secure filename handling to prevent directory traversal
- **Input Validation**: Form validation and sanitization
- **Access Control**: Login required for all operations

## Configuration Options

### Email Configuration
For Gmail SMTP (recommended):
- Enable 2-factor authentication on your Gmail account
- Generate an app-specific password
- Use the app password in the `EMAIL_PASSWORD` field

### File Upload Settings
- Supported file types: PDF, DOC, DOCX, TXT, and other document formats
- Files are stored in the `all_agreements` directory
- Automatic year-based organization

## Troubleshooting

### Common Issues

1. **Database not found**: The application automatically creates `agreements.db` on first run
2. **File upload errors**: Ensure the `all_agreements` directory has write permissions
3. **Email sending fails**: Verify SMTP settings and app password configuration
4. **Login issues**: Check username/password in the `USERS` dictionary

### Debug Mode
The application runs in debug mode by default. For production:
```python
app.run(debug=False, host='0.0.0.0', port=5000)
```

## Maintenance

### Regular Tasks
1. **Backup Database**: Regular backups of `agreements.db`
2. **File Cleanup**: Monitor disk space in `all_agreements` directory
3. **Update Dependencies**: Keep Python packages updated
4. **Security Updates**: Change default passwords and secret keys

### Database Migrations
The application automatically handles database schema updates when you restart it.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Redirect to dashboard or login |
| `/login` | GET/POST | User authentication |
| `/dashboard` | GET | Main dashboard with analytics |
| `/upload` | GET/POST | Upload new agreements |
| `/agreements` | GET | View all agreements |
| `/expiring` | GET | View expiring agreements |
| `/renew/<id>` | GET/POST | Renew specific agreement |
| `/history/<id>` | GET | View agreement history |
| `/send_email/<id>` | GET | Send renewal reminder |
| `/download/<filename>` | GET | Download agreement file |
| `/download_excel` | GET | Export agreements to Excel |

## Contributing

When modifying the application:
1. Test all functionality after changes
2. Update database schema carefully
3. Maintain backward compatibility
4. Document any new features

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the Flask application logs
3. Verify database integrity
4. Test with a clean database if needed

---

**Version**: 1.0  
**Last Updated**: 2025  
**Framework**: Flask 2.x  
**Database**: SQLite 3  
**Python**: 3.7+