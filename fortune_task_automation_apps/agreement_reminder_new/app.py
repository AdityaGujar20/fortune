import os
import datetime
import shutil
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
import bcrypt
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///agreements.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['REMOVED_AGREEMENTS_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'removed_agreements')
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png'}

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'adityagujar20@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'kcku vllx alnl jevi'     # Replace with your app password
app.config['MAIL_DEFAULT_SENDER'] = 'adityagujar20@gmail.com'

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REMOVED_AGREEMENTS_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class Agreement(db.Model):
    __tablename__ = 'agreements'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    person_name = db.Column(db.String(100), nullable=False)
    email_id = db.Column(db.String(120))  # New field for email address
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    file_path = db.Column(db.String(200), nullable=False)
    renewal_count = db.Column(db.Integer, default=0)
    renewals = db.relationship('AgreementRenewal', backref='agreement', lazy=True)

class AgreementRenewal(db.Model):
    __tablename__ = 'agreement_renewals'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    agreement_id = db.Column(db.Integer, db.ForeignKey('agreements.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)  # Start date at the time of this renewal
    end_date = db.Column(db.Date, nullable=False)    # End date at the time of this renewal
    renewal_date = db.Column(db.Date, nullable=False) # Date this renewal was made

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Utility Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password').encode('utf-8')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password, user.password_hash.encode('utf-8')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/all_agreements')
@login_required
def all_agreements():
    agreements = Agreement.query.filter_by(user_id=current_user.id).all()
    today = datetime.date.today()
    
    # Calculate days left for each agreement
    agreements_with_days = []
    for agreement in agreements:
        days_left = (agreement.end_date - today).days if agreement.end_date >= today else 0
        agreements_with_days.append({
            'agreement': agreement,
            'days_left': days_left
        })

    return render_template('all_agreements.html', agreements_with_days=agreements_with_days)

@app.route('/expiring_agreements')
@login_required
def expiring_agreements():
    today = datetime.date.today()
    sixty_days_later = today + datetime.timedelta(days=60)
    agreements = Agreement.query.filter_by(user_id=current_user.id).all()

    # Filter agreements expiring in the next 60 days
    expiring_agreements = [
        a for a in agreements
        if a.end_date <= sixty_days_later and a.end_date >= today
    ]

    # Calculate days left for each expiring agreement
    expiring_with_days = []
    for agreement in expiring_agreements:
        days_left = (agreement.end_date - today).days
        expiring_with_days.append({
            'agreement': agreement,
            'days_left': days_left
        })

    # Count of expiring agreements
    expiring_count = len(expiring_agreements)

    return render_template('expiring_agreements.html', expiring_with_days=expiring_with_days, expiring_count=expiring_count)

@app.route('/send_expiry_emails', methods=['POST'])
@login_required
def send_expiry_emails():
    today = datetime.date.today()
    sixty_days_later = today + datetime.timedelta(days=60)
    agreements = Agreement.query.filter_by(user_id=current_user.id).all()

    # Filter agreements expiring in the next 60 days
    expiring_agreements = [
        a for a in agreements
        if a.end_date <= sixty_days_later and a.end_date >= today
    ]

    if not expiring_agreements:
        flash('No agreements are expiring in the next 60 days to send reminders for.', 'info')
        return redirect(url_for('expiring_agreements'))

    # Calculate days left for each expiring agreement
    expiring_with_days = []
    for agreement in expiring_agreements:
        days_left = (agreement.end_date - today).days
        expiring_with_days.append({
            'agreement': agreement,
            'days_left': days_left
        })

    try:
        # Build the HTML table for the email
        table_rows = ''
        for item in expiring_with_days:
            agreement = item['agreement']
            days_left = item['days_left']
            table_rows += f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">{agreement.company_name}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{agreement.person_name}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{agreement.email_id if agreement.email_id else '-'}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{agreement.start_date}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{agreement.end_date}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{days_left}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{agreement.renewal_count}</td>
                </tr>
            """

        # HTML email body with a table
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Agreements Expiring Soon (Next 60 Days)</h2>
            <p>Dear Aditya,</p>
            <p>The following agreements are expiring in the next 60 days:</p>
            <table style="border-collapse: collapse; width: 100%;">
                <thead>
                    <tr style="background-color: #f2f2f2;">
                        <th style="border: 1px solid #ddd; padding: 8px;">Company Name</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Person Name</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Email ID</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Start Date</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">End Date</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Days Left</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Renewal Count</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            <p>Please take appropriate action to renew or manage these agreements.</p>
            <p>Regards,<br>Agreement Tracker Team</p>
        </body>
        </html>
        """

        # Send a single email to adityagujar20@gmail.com
        msg = Message(
            subject='Agreements Expiring Soon Reminder',
            recipients=['adityagujar20@gmail.com'],
            html=html_body  # Use HTML body instead of plain text
        )
        mail.send(msg)
        flash('Expiry reminder email sent successfully to adityagujar20@gmail.com!', 'success')
    except Exception as e:
        flash(f'Failed to send email: {str(e)}', 'error')

    return redirect(url_for('expiring_agreements'))

@app.route('/remove_agreement/<int:agreement_id>', methods=['GET'])
@login_required
def remove_agreement(agreement_id):
    agreement = Agreement.query.get_or_404(agreement_id)
    if agreement.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard'))

    try:
        # Move the associated file to removed_agreements folder
        if os.path.exists(agreement.file_path):
            removed_agreements_dir = app.config['REMOVED_AGREEMENTS_FOLDER']
            filename = os.path.basename(agreement.file_path)
            new_file_path = os.path.join(removed_agreements_dir, filename)
            # Ensure no file name conflicts in removed_agreements
            base, extension = os.path.splitext(filename)
            counter = 1
            while os.path.exists(new_file_path):
                new_filename = f"{base}_{counter}{extension}"
                new_file_path = os.path.join(removed_agreements_dir, new_filename)
                counter += 1
            shutil.move(agreement.file_path, new_file_path)

        # Delete associated renewals
        AgreementRenewal.query.filter_by(agreement_id=agreement.id).delete()

        # Delete the agreement from the database
        db.session.delete(agreement)
        db.session.commit()

        flash('Agreement removed successfully and moved to removed_agreements folder!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to remove agreement: {str(e)}', 'error')

    # Redirect to the appropriate page based on the referrer
    referrer = request.referrer
    if 'expiring_agreements' in referrer:
        return redirect(url_for('expiring_agreements'))
    return redirect(url_for('all_agreements'))

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.date.today()
    sixty_days_later = today + datetime.timedelta(days=60)
    agreements = Agreement.query.filter_by(user_id=current_user.id).all()

    # Data for visualizations
    expiring_soon = sum(1 for a in agreements if (
        a.end_date <= sixty_days_later and
        a.end_date >= today
    ))

    viz_data = {
        'expiring_soon': expiring_soon
    }

    app.logger.info(f"viz_data: {viz_data}")

    return render_template('dashboard.html', viz_data=viz_data)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        person_name = request.form.get('person_name')
        email_id = request.form.get('email_id')  # New field
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        file = request.files.get('file')

        if not all([company_name, person_name, start_date, end_date, file]):
            flash('Required fields are missing', 'error')
            return redirect(url_for('upload'))

        if not allowed_file(file.filename):
            flash('Invalid file type. Allowed types: pdf, jpg, jpeg, png', 'error')
            return redirect(url_for('upload'))

        try:
            start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Use YYYY-MM-DD', 'error')
            return redirect(url_for('upload'))

        # Save the file directly in the uploads folder
        uploads_dir = app.config['UPLOAD_FOLDER']
        filename = secure_filename(file.filename)
        file_path = os.path.join(uploads_dir, f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
        file.save(file_path)

        # Save to database
        agreement = Agreement(
            user_id=current_user.id,
            company_name=company_name,
            person_name=person_name,
            email_id=email_id,  # Save the email_id
            start_date=start_date,
            end_date=end_date,
            file_path=file_path
        )
        db.session.add(agreement)
        db.session.commit()
        flash('Agreement uploaded successfully', 'success')
        return redirect(url_for('dashboard'))

    return render_template('upload.html')

@app.route('/renew/<int:agreement_id>', methods=['GET', 'POST'])
@login_required
def renew(agreement_id):
    agreement = Agreement.query.get_or_404(agreement_id)
    if agreement.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        renewed_date = request.form.get('renewed_date')
        new_start_date = request.form.get('new_start_date')
        new_end_date = request.form.get('new_end_date')
        email_id = request.form.get('email_id')  # Update email_id

        try:
            renewed_date = datetime.datetime.strptime(renewed_date, '%Y-%m-%d').date()
            new_start_date = datetime.datetime.strptime(new_start_date, '%Y-%m-%d').date()
            new_end_date = datetime.datetime.strptime(new_end_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Use YYYY-MM-DD', 'error')
            return redirect(url_for('renew', agreement_id=agreement_id))

        # Store the current dates in AgreementRenewal before updating
        renewal = AgreementRenewal(
            agreement_id=agreement.id,
            start_date=agreement.start_date,
            end_date=agreement.end_date,
            renewal_date=renewed_date
        )
        db.session.add(renewal)

        # Update the agreement with new dates, email_id, and increment renewal count
        agreement.start_date = new_start_date
        agreement.end_date = new_end_date
        agreement.email_id = email_id if email_id else None  # Update email_id
        agreement.renewal_count += 1
        db.session.commit()

        flash('Agreement renewed successfully', 'success')
        return redirect(url_for('dashboard'))

    return render_template('renew.html', agreement=agreement)

@app.route('/download/<int:agreement_id>')
@login_required
def download(agreement_id):
    agreement = Agreement.query.get_or_404(agreement_id)
    if agreement.user_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard'))
    return send_from_directory(
        os.path.dirname(agreement.file_path),
        os.path.basename(agreement.file_path),
        as_attachment=True
    )

# Initialize Database and Add a Default User
def init_db():
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()  # This is safe to call; it won't drop existing tables

        # Check if a user already exists
        existing_user = User.query.first()
        if not existing_user:
            # Create default admin user only if no users exist
            password = 'password'.encode('utf-8')
            password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
            default_user = User(
                username='admin',
                email='adityagujar20@gmail.com',
                password_hash=password_hash
            )
            db.session.add(default_user)
            db.session.commit()

if __name__ == '__main__':
    init_db()  # Initialize the database
    app.run(debug=True)