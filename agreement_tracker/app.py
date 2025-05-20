from flask import Flask, render_template, request, redirect, send_from_directory, url_for, abort, send_file, session, flash
import os
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import io
import matplotlib.pyplot as plt
import base64
from functools import wraps

app = Flask(__name__)
app.config['ALL_AGREEMENTS_FOLDER'] = 'all_agreements'
app.config['SECRET_KEY'] = 'your-secret-key'  # Required for session management
os.makedirs(app.config['ALL_AGREEMENTS_FOLDER'], exist_ok=True)

# Email configuration (replace with your own SMTP settings)
EMAIL_ADDRESS = "fortunegroup.gujar@hotmail.com"  # Replace with your Gmail address
EMAIL_PASSWORD = "your-app-specific-password"  # Replace with your app-specific password
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Set matplotlib to use a non-interactive backend
plt.switch_backend('Agg')

# User credentials
USERS = {
    'hrdept': 'hragree@2008'
}

# --- Initialize DB ---
def init_db():
    conn = sqlite3.connect('agreements.db')
    c = conn.cursor()
    # Create the table with new fields: second_person_name and second_email_id
    c.execute('''CREATE TABLE IF NOT EXISTS agreements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT,
        person_name TEXT,
        designation TEXT,
        contact_number TEXT,  -- Can be NULL (optional)
        email_id TEXT,       -- Can be NULL (optional)
        start_date TEXT,
        end_date TEXT,
        filename TEXT,
        previous_agreement_id INTEGER,
        status TEXT DEFAULT 'Active',
        second_person_name TEXT,  -- New optional field
        second_email_id TEXT,     -- New optional field
        FOREIGN KEY(previous_agreement_id) REFERENCES agreements(id)
    )''')
    
    # Check if the new columns exist; if not, add them
    c.execute("PRAGMA table_info(agreements)")
    columns = [col[1] for col in c.fetchall()]
    
    # Add second_person_name if not exists
    if 'second_person_name' not in columns:
        print("Adding second_person_name column to agreements table...")
        c.execute("ALTER TABLE agreements ADD COLUMN second_person_name TEXT")
    
    # Add second_email_id if not exists
    if 'second_email_id' not in columns:
        print("Adding second_email_id column to agreements table...")
        c.execute("ALTER TABLE agreements ADD COLUMN second_email_id TEXT")
    
    # Check if the status column exists; if not, add it and migrate existing data
    if 'status' not in columns:
        print("Adding status column to agreements table...")
        c.execute("ALTER TABLE agreements ADD COLUMN status TEXT DEFAULT 'Active'")
        
        # Migrate existing data
        today = datetime.today().date()
        c.execute("SELECT * FROM agreements")
        rows = c.fetchall()
        for row in rows:
            row_id = row[0]  # id
            end_date_str = row[7]  # end_date
            
            # Determine initial status
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if end_date <= today:
                    status = "Expired"
                else:
                    status = "Active"
            except (ValueError, TypeError):
                status = "Active"  # Default if end_date is invalid
            
            # Update the status in the database
            c.execute("UPDATE agreements SET status = ? WHERE id = ?", (status, row_id))
        
        conn.commit()
        print("Database migration completed: status column added and data migrated.")
    else:
        # Update any "Superseded" or "Replaced" to "Renewed" for consistency
        c.execute("UPDATE agreements SET status = 'Renewed' WHERE status = 'Superseded' OR status = 'Replaced'")
        conn.commit()

    conn.close()

init_db()

# --- Login Required Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Login Route ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in USERS and USERS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

# --- Logout Route ---
@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Helper Function to Convert Plot to Base64 ---
def plot_to_base64():
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
    return image_base64

# --- Root Route ---
@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# --- Dashboard Route ---
@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM agreements')
    rows = c.fetchall()

    today = datetime.today().date()
    data = []
    for row in rows:
        try:
            end_date = datetime.strptime(row['end_date'], "%Y-%m-%d").date()
            days_remaining = (end_date - today).days
        except (ValueError, TypeError):
            days_remaining = None

        # Update status if the agreement has expired
        status = row['status']
        if status == "Active" and days_remaining is not None and end_date <= today:
            status = "Expired"
            c.execute("UPDATE agreements SET status = 'Expired' WHERE id = ?", (row['id'],))

        data.append({
            'status': status,
            'days_remaining': days_remaining
        })

    conn.commit()
    conn.close()

    # Check if there are any agreements
    if not rows:
        # No agreements found, render template with None values for charts
        return render_template('dashboard.html', pie_chart=None, bar_chart=None, histogram=None, no_agreements=True)

    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(data)

    # 1. Pie Chart: Distribution of Agreements by Status
    status_counts = df['status'].value_counts()
    plt.figure(figsize=(6, 6))
    plt.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', colors=['#ff9999', '#66b3ff', '#99ff99'])
    plt.title('Distribution of Agreements by Status')
    pie_chart = plot_to_base64()

    # 2. Bar Chart: Agreements Expiring in Days-Left Ranges (0-10, 11-30, 31-60)
    expiring_counts = {'0-10': 0, '11-30': 0, '31-60': 0}
    for days in df['days_remaining']:
        if days is not None and 0 <= days <= 60:
            if 0 <= days <= 10:
                expiring_counts['0-10'] += 1
            elif 11 <= days <= 30:
                expiring_counts['11-30'] += 1
            elif 31 <= days <= 60:
                expiring_counts['31-60'] += 1

    plt.figure(figsize=(8, 6))
    plt.bar(expiring_counts.keys(), expiring_counts.values(), color=['#ff6666', '#ffcc66', '#66cc66'])
    plt.title('Agreements Expiring by Days Remaining')
    plt.xlabel('Days Remaining')
    plt.ylabel('Number of Agreements')
    for i, v in enumerate(expiring_counts.values()):
        plt.text(i, v + 0.1, str(v), ha='center')
    bar_chart = plot_to_base64()

    # 3. Histogram: Distribution of Days Remaining (All Agreements)
    days_data = df['days_remaining'].dropna()
    plt.figure(figsize=(8, 6))
    plt.hist(days_data, bins=20, color='#66b3ff', edgecolor='black')
    plt.title('Distribution of Days Remaining for All Agreements')
    plt.xlabel('Days Remaining')
    plt.ylabel('Frequency')
    histogram = plot_to_base64()

    return render_template('dashboard.html', pie_chart=pie_chart, bar_chart=bar_chart, histogram=histogram, no_agreements=False)

# --- Upload Agreement ---
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_agreement():
    if request.method == 'POST':
        company = request.form['company_name']
        person = request.form['person_name']
        designation = request.form['designation']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        contact_number = request.form.get('contact_number')  # Optional
        email_id = request.form.get('email_id')  # Optional
        second_person_name = request.form.get('second_person_name')  # Optional
        second_email_id = request.form.get('second_email_id')  # Optional
        file = request.files['document']

        # Log the start_date for debugging
        print(f"Received start_date: {start_date}")

        # Validate start_date format and extract year
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            year = start_date.split("-")[0]
            print(f"Extracted year: {year}")
        except ValueError:
            flash("Invalid start date format. Please use YYYY-MM-DD.", "danger")
            return redirect(url_for('upload_agreement'))

        if file and file.filename:
            year_folder = os.path.join(app.config['ALL_AGREEMENTS_FOLDER'], year)
            os.makedirs(year_folder, exist_ok=True)

            filename = secure_filename(file.filename)
            # Store relative path in the database
            relative_path = os.path.join(year, filename).replace(os.sep, '/')
            # Store physical file with full path
            file_path = os.path.join(app.config['ALL_AGREEMENTS_FOLDER'], relative_path)
            
            # Log file path before saving
            print(f"Attempting to save file to: {file_path}")
            file.save(file_path)

            # Verify the file was saved
            if not os.path.isfile(file_path):
                print(f"Failed to save file to: {file_path}")
                flash(f"Failed to save file to {file_path}", "danger")
                return redirect(url_for('upload_agreement'))

            # Log the saved file path
            print(f"Uploaded file saved to: {file_path}, stored in DB as: {relative_path}")

            conn = sqlite3.connect('agreements.db')
            c = conn.cursor()
            c.execute('''INSERT INTO agreements 
                        (company_name, person_name, designation, contact_number, 
                        email_id, start_date, end_date, filename, previous_agreement_id, status,
                        second_person_name, second_email_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'Active', ?, ?)''',
                    (company, person, designation, contact_number, 
                    email_id, start_date, end_date, relative_path,
                    second_person_name, second_email_id))
            agreement_id = c.lastrowid  # Get the ID of the newly inserted agreement
            conn.commit()
            conn.close()

            print(f"Agreement added successfully with ID: {agreement_id}")
            flash("Agreement uploaded successfully!", "success")
            return redirect(url_for('view_agreements'))
        
        flash("No file uploaded or invalid file.", "danger")
        return redirect(url_for('upload_agreement'))
    
    return render_template('upload.html')

# --- View Agreements ---
@app.route('/agreements')
@login_required
def view_agreements():
    # Get the status filter from query parameter (default to 'all')
    status_filter = request.args.get('status', 'all')

    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row  # This enables column access by name
    c = conn.cursor()
    c.execute('SELECT * FROM agreements')
    rows = c.fetchall()

    today = datetime.today().date()
    enriched_rows = []
    for row in rows:
        try:
            end_date = datetime.strptime(row['end_date'], "%Y-%m-%d").date()
            days_remaining = (end_date - today).days
        except (ValueError, TypeError):
            days_remaining = None

        # Update status if the agreement has expired
        status = row['status']
        if status == "Active" and days_remaining is not None and end_date <= today:
            status = "Expired"
            c.execute("UPDATE agreements SET status = 'Expired' WHERE id = ?", (row['id'],))

        # Apply status filter
        if status_filter == 'all' or status == status_filter:
            # Create a dict from the row
            agreement = dict(row)
            agreement['days_remaining'] = days_remaining
            agreement['status'] = status
            enriched_rows.append(agreement)

    conn.commit()
    conn.close()

    # Sort by days_remaining, handling None values
    enriched_rows.sort(key=lambda x: (x['days_remaining'] is None, 
                                     x['days_remaining'] if x['days_remaining'] is not None else float('inf')))
    return render_template('view.html', agreements=enriched_rows, status=status_filter)

# --- Expiring Agreements ---
@app.route('/expiring')
@login_required
def expiring_agreements():
    # Get the filters from query parameters (default to 'all')
    range_filter = request.args.get('range', 'all')
    status_filter = request.args.get('status', 'all')

    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM agreements')
    rows = c.fetchall()

    today = datetime.today().date()
    expiring_rows = []
    # Initialize counts for each range
    counts = {'0-10': 0, '11-30': 0, '31-60': 0}

    for row in rows:
        try:
            end_date = datetime.strptime(row['end_date'], "%Y-%m-%d").date()
            days_remaining = (end_date - today).days
        except (ValueError, TypeError):
            days_remaining = None
        
        # Update status if the agreement has expired
        status = row['status']
        if status == "Active" and days_remaining is not None and end_date <= today:
            status = "Expired"
            c.execute("UPDATE agreements SET status = 'Expired' WHERE id = ?", (row['id'],))

        # Count agreements expiring within 60 days for the summary
        if days_remaining is not None and 0 <= days_remaining <= 60:
            if 0 <= days_remaining <= 10:
                counts['0-10'] += 1
            elif 11 <= days_remaining <= 30:
                counts['11-30'] += 1
            elif 31 <= days_remaining <= 60:
                counts['31-60'] += 1

            # Apply filters for the table display
            if range_filter == 'all' or (
                range_filter == '0-10' and 0 <= days_remaining <= 10) or (
                range_filter == '11-30' and 11 <= days_remaining <= 30) or (
                range_filter == '31-60' and 31 <= days_remaining <= 60):
                # Apply status filter
                if status_filter == 'all' or status == status_filter:
                    agreement = dict(row)
                    agreement['days_remaining'] = days_remaining
                    agreement['status'] = status
                    expiring_rows.append(agreement)

    conn.commit()
    conn.close()

    # Sort by days_remaining in ascending order
    expiring_rows.sort(key=lambda x: x['days_remaining'])
    return render_template('expiring.html', agreements=expiring_rows, range=range_filter, status=status_filter, counts=counts)

# --- Renew Agreement Form ---
@app.route('/renew/<int:agreement_id>', methods=['GET', 'POST'])
@login_required
def renew_agreement(agreement_id):
    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM agreements WHERE id = ?', (agreement_id,))
    agreement = c.fetchone()
    
    if not agreement:
        conn.close()
        flash("Agreement not found.", "danger")
        return redirect(url_for('view_agreements'))

    if request.method == 'POST':
        person = request.form['person_name']
        designation = request.form['designation']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        contact_number = request.form.get('contact_number')  # Optional
        email_id = request.form.get('email_id')  # Optional
        second_person_name = request.form.get('second_person_name')  # Optional
        second_email_id = request.form.get('second_email_id')  # Optional
        file = request.files['document']

        # Validate start_date format
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            year = start_date.split("-")[0]
        except ValueError:
            flash("Invalid start date format in renewal. Please use YYYY-MM-DD.", "danger")
            return redirect(url_for('renew_agreement', agreement_id=agreement_id))

        year_folder = os.path.join(app.config['ALL_AGREEMENTS_FOLDER'], year)
        os.makedirs(year_folder, exist_ok=True)

        filename = secure_filename(file.filename)
        # Store relative path in the database
        relative_path = os.path.join(year, filename).replace(os.sep, '/')
        # Store physical file with full path
        file_path = os.path.join(app.config['ALL_AGREEMENTS_FOLDER'], relative_path)
        file.save(file_path)

        # Verify the file was saved
        if not os.path.isfile(file_path):
            flash(f"Failed to save file to {file_path}", "danger")
            return redirect(url_for('renew_agreement', agreement_id=agreement_id))

        # Log the saved file path for debugging
        print(f"Renewed file saved to: {file_path}, stored in DB as: {relative_path}")

        # Mark the old agreement as Renewed
        c.execute("UPDATE agreements SET status = 'Renewed' WHERE id = ?", (agreement_id,))

        # Insert the new agreement with status Active
        c.execute('''INSERT INTO agreements 
                    (company_name, person_name, designation, contact_number, 
                    email_id, start_date, end_date, filename, previous_agreement_id, status,
                    second_person_name, second_email_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)''',
                (agreement['company_name'], person, designation, contact_number, 
                email_id, start_date, end_date, relative_path, agreement_id,
                second_person_name, second_email_id))
        conn.commit()
        conn.close()

        flash("Agreement renewed successfully!", "success")
        return redirect(url_for('view_agreements'))

    conn.close()
    return render_template('renew.html', agreement=agreement)

# --- Agreement History ---
@app.route('/history/<int:agreement_id>')
@login_required
def agreement_history(agreement_id):
    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    chain = []
    current_id = agreement_id

    while current_id:
        c.execute('SELECT * FROM agreements WHERE id = ?', (current_id,))
        row = c.fetchone()
        if not row:
            break
        # Update status if the agreement has expired
        try:
            end_date = datetime.strptime(row['end_date'], "%Y-%m-%d").date()
            today = datetime.today().date()
            if row['status'] == "Active" and end_date <= today:
                c.execute("UPDATE agreements SET status = 'Expired' WHERE id = ?", (row['id'],))
                row = dict(row)
                row['status'] = "Expired"
        except (ValueError, TypeError):
            pass

        chain.append(dict(row))  # Convert Row to dict
        current_id = row['previous_agreement_id']  # Use named column access

    chain.reverse()  # Reverse to show oldest first (chronological order)
    conn.commit()
    conn.close()
    
    if not chain:
        flash("No history found for this agreement.", "danger")
        return redirect(url_for('view_agreements'))
        
    return render_template('history.html', chain=chain)

# --- Remove Agreement ---
@app.route('/remove/<int:agreement_id>')
@login_required
def remove_agreement(agreement_id):
    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch the agreement to get the filename
    c.execute('SELECT * FROM agreements WHERE id = ?', (agreement_id,))
    agreement = c.fetchone()

    if not agreement:
        conn.close()
        flash("Agreement not found.", "danger")
        return redirect(url_for('view_agreements'))

    # Delete the file if it exists
    filename = agreement['filename']
    file_path = os.path.join(app.config['ALL_AGREEMENTS_FOLDER'], filename)
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
        except Exception as e:
            print(f"Error deleting file {file_path}: {str(e)}")

    # Update any agreements that reference this one as previous_agreement_id
    c.execute('UPDATE agreements SET previous_agreement_id = NULL WHERE previous_agreement_id = ?', (agreement_id,))

    # Delete the agreement from the database
    c.execute('DELETE FROM agreements WHERE id = ?', (agreement_id,))
    conn.commit()
    conn.close()

    flash("Agreement removed successfully.", "success")
    return redirect(url_for('view_agreements'))

# --- Terminate Agreement ---
@app.route('/terminate/<int:agreement_id>')
@login_required
def terminate_agreement(agreement_id):
    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch the agreement
    c.execute('SELECT * FROM agreements WHERE id = ?', (agreement_id,))
    agreement = c.fetchone()

    if not agreement:
        conn.close()
        flash("Agreement not found.", "danger")
        return redirect(url_for('view_agreements'))

    # Update the end_date to today's date and set status to Expired
    today = datetime.today().strftime('%Y-%m-%d')
    c.execute("UPDATE agreements SET end_date = ?, status = 'Expired' WHERE id = ?", (today, agreement_id))
    conn.commit()
    conn.close()

    flash("Agreement terminated successfully.", "success")
    return redirect(url_for('view_agreements'))

# --- Select Email to Send ---
@app.route('/select_email/<int:agreement_id>', methods=['GET', 'POST'])
@login_required
def select_email(agreement_id):
    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM agreements WHERE id = ?', (agreement_id,))
    agreement = c.fetchone()
    conn.close()

    if not agreement:
        flash("Agreement not found.", "danger")
        return redirect(url_for('view_agreements'))

    if request.method == 'POST':
        selected_email = request.form.get('selected_email')
        if not selected_email:
            flash("Please select an email address.", "danger")
            return redirect(url_for('select_email', agreement_id=agreement_id))

        # Prepare email content
        recipient_email = selected_email
        subject = f"Renewal Reminder: Agreement ID {agreement['id']}"
        body = f"""
        Dear {agreement['person_name']},

        This is a reminder to renew your agreement with {agreement['company_name']}.
        
        Agreement Details:
        - Agreement ID: {agreement['id']}
        - Company: {agreement['company_name']}
        - Person: {agreement['person_name']}
        - End Date: {agreement['end_date']}
        
        Please take action to renew the agreement before it expires.

        Best regards,
        Agreement Management Team
        """

        # Create the email message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Send the email
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())
            server.quit()
            print(f"Email sent to {recipient_email} for agreement ID {agreement_id}")
            flash("Email sent successfully.", "success")
        except Exception as e:
            print(f"Error sending email to {recipient_email}: {str(e)}")
            flash(f"Failed to send email: {str(e)}", "danger")

        return redirect(url_for('view_agreements'))

    # Collect available email addresses
    emails = []
    if agreement['email_id']:
        emails.append(agreement['email_id'])
    if agreement['second_email_id']:
        emails.append(agreement['second_email_id'])

    return render_template('select_email.html', agreement=agreement, emails=emails)

# --- Send Email ---
@app.route('/send_email/<int:agreement_id>')
@login_required
def send_email(agreement_id):
    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM agreements WHERE id = ?', (agreement_id,))
    agreement = c.fetchone()
    conn.close()

    if not agreement:
        flash("Agreement not found.", "danger")
        return redirect(url_for('view_agreements'))

    # Check if there are multiple email addresses
    emails = []
    if agreement['email_id']:
        emails.append(agreement['email_id'])
    if agreement['second_email_id']:
        emails.append(agreement['second_email_id'])

    if len(emails) > 1:
        # Redirect to email selection page if more than one email is present
        return redirect(url_for('select_email', agreement_id=agreement_id))
    elif len(emails) == 1:
        # If only one email, send directly
        recipient_email = emails[0]
    else:
        # No email addresses provided
        flash("No email addresses provided for this agreement.", "danger")
        return redirect(url_for('view_agreements'))

    # Prepare email content
    subject = f"Renewal Reminder: Agreement ID {agreement['id']}"
    body = f"""
    Dear {agreement['person_name']},

    This is a reminder to renew your agreement with {agreement['company_name']}.
    
    Agreement Details:
    - Agreement ID: {agreement['id']}
    - Company: {agreement['company_name']}
    - Person: {agreement['person_name']}
    - End Date: {agreement['end_date']}
    
    Please take action to renew the agreement before it expires.

    Best regards,
    Agreement Management Team
    """

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Send the email
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())
        server.quit()
        print(f"Email sent to {recipient_email} for agreement ID {agreement_id}")
        flash("Email sent successfully.", "success")
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {str(e)}")
        flash(f"Failed to send email: {str(e)}", "danger")

    return redirect(url_for('view_agreements'))

# --- Download Excel for View Agreements ---
@app.route('/download_excel')
@login_required
def download_excel():
    # Get the status filter from query parameter
    status_filter = request.args.get('status', 'all')

    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM agreements')
    rows = c.fetchall()

    today = datetime.today().date()
    data = []
    for row in rows:
        try:
            end_date = datetime.strptime(row['end_date'], "%Y-%m-%d").date()
            days_remaining = (end_date - today).days
        except (ValueError, TypeError):
            days_remaining = None

        # Update status if the agreement has expired
        status = row['status']
        if status == "Active" and days_remaining is not None and end_date <= today:
            status = "Expired"
            c.execute("UPDATE agreements SET status = 'Expired' WHERE id = ?", (row['id'],))

        # Apply status filter
        if status_filter == 'all' or status == status_filter:
            data.append({
                'ID': row['id'],
                'Company': row['company_name'],
                'Person Name': row['person_name'],
                '2nd Person Name': row['second_person_name'] or 'N/A',
                'Designation': row['designation'],
                'Contact': row['contact_number'] or 'N/A',
                'Email': row['email_id'] or 'N/A',
                '2nd Email': row['second_email_id'] or 'N/A',
                'Start Date': row['start_date'],
                'End Date': row['end_date'],
                'Days Remaining': days_remaining if days_remaining is not None else 'N/A',
                'Status': status
            })

    conn.commit()
    conn.close()

    # Create a DataFrame
    df = pd.DataFrame(data)

    # Create a BytesIO buffer to write the Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Agreements')
    output.seek(0)

    # Include status in the filename if not 'all'
    filename = f"all_agreements_{status_filter.lower().replace(' ', '_')}.xlsx" if status_filter != 'all' else "all_agreements.xlsx"

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# --- Download Excel for Expiring Agreements ---
@app.route('/download_expiring_excel')
@login_required
def download_expiring_excel():
    # Get the filters from query parameters
    range_filter = request.args.get('range', 'all')
    status_filter = request.args.get('status', 'all')

    conn = sqlite3.connect('agreements.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM agreements')
    rows = c.fetchall()

    today = datetime.today().date()
    data = []
    for row in rows:
        try:
            end_date = datetime.strptime(row['end_date'], "%Y-%m-%d").date()
            days_remaining = (end_date - today).days
        except (ValueError, TypeError):
            days_remaining = None
        
        # Update status if the agreement has expired
        status = row['status']
        if status == "Active" and days_remaining is not None and end_date <= today:
            status = "Expired"
            c.execute("UPDATE agreements SET status = 'Expired' WHERE id = ?", (row['id'],))

        # Filter agreements expiring within 60 days
        if days_remaining is not None and 0 <= days_remaining <= 60:
            # Apply range filter
            if range_filter == 'all' or (
                range_filter == '0-10' and 0 <= days_remaining <= 10) or (
                range_filter == '11-30' and 11 <= days_remaining <= 30) or (
                range_filter == '31-60' and 31 <= days_remaining <= 60):
                # Apply status filter
                if status_filter == 'all' or status == status_filter:
                    data.append({
                        'ID': row['id'],
                        'Company': row['company_name'],
                        'Person Name': row['person_name'],
                        '2nd Person Name': row['second_person_name'] or 'N/A',
                        'Designation': row['designation'],
                        'Contact': row['contact_number'] or 'N/A',
                        'Email': row['email_id'] or 'N/A',
                        '2nd Email': row['second_email_id'] or 'N/A',
                        'Start Date': row['start_date'],
                        'End Date': row['end_date'],
                        'Days Remaining': days_remaining if days_remaining is not None else 'N/A',
                        'Status': status
                    })

    conn.commit()
    conn.close()

    # Create a DataFrame
    df = pd.DataFrame(data)

    # Create a BytesIO buffer to write the Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Expiring Agreements')
    output.seek(0)

    # Include filters in the filename
    filename = f"expiring_agreements_{range_filter}_{status_filter.lower().replace(' ', '_')}.xlsx" if status_filter != 'all' else f"expiring_agreements_{range_filter}.xlsx"

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# --- Download File ---
@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    try:
        # Log the requested filename for debugging
        print(f"Attempting to download file: {filename}")

        # Normalize the path and ensure forward slashes for consistency
        filename = os.path.normpath(filename).replace(os.sep, '/')
        file_path = os.path.join(app.config['ALL_AGREEMENTS_FOLDER'], filename)

        # Log the full file path being accessed
        print(f"Full file path: {file_path}")

        # Check if the file exists
        if not os.path.isfile(file_path):
            flash(f"File {filename} not found.", "danger")
            return redirect(url_for('view_agreements'))
        
        return send_from_directory(app.config['ALL_AGREEMENTS_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        print(f"Error in download_file: {str(e)}")
        flash(f"Error accessing file {filename}: {str(e)}", "danger")
        return redirect(url_for('view_agreements'))

# --- View File ---
@app.route('/view/<path:filename>')
@login_required
def view_file(filename):
    try:
        # Log the requested filename for debugging
        print(f"Attempting to view file: {filename}")

        # Normalize the path and ensure forward slashes for consistency
        filename = os.path.normpath(filename).replace(os.sep, '/')
        file_path = os.path.join(app.config['ALL_AGREEMENTS_FOLDER'], filename)

        # Log the full file path being accessed
        print(f"Full file path: {file_path}")

        # Check if the file exists
        if not os.path.isfile(file_path):
            flash(f"File {filename} not found.", "danger")
            return redirect(url_for('view_agreements'))
        
        return send_from_directory(app.config['ALL_AGREEMENTS_FOLDER'], filename)
    except Exception as e:
        print(f"Error in view_file: {str(e)}")
        flash(f"Error accessing file {filename}: {str(e)}", "danger")
        return redirect(url_for('view_agreements'))

if __name__ == '__main__':
    app.run(debug=True)