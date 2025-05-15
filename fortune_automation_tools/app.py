import os
import sys
import pandas as pd
import fitz  # PyMuPDF
import pdfplumber
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, session, redirect, url_for
from werkzeug.utils import secure_filename
import uuid
import shutil
import zipfile
import threading
from functools import wraps

# Helper function to get the correct path for bundled resources
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Helper function to get the base path for outputs folder (where .exe is located)
def get_output_base_path():
    """Get the directory where the .exe is running, for outputs/logs/uploads"""
    if getattr(sys, 'frozen', False):
        # When running as a PyInstaller .exe, use the directory of the executable
        return os.path.dirname(sys.executable)
    else:
        # When running as a Python script, use the current working directory
        return os.path.abspath(".")

# Initialize Flask app with dynamic template and static folder paths
app = Flask(__name__, 
            template_folder=resource_path('templates'), 
            static_folder=resource_path('static'))
app.secret_key = 'your-secret-key-here'  # Replace with a secure key in production

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
LOG_FOLDER = 'logs'
# Use get_output_base_path to ensure folders are created in the correct location
BASE_PATH = get_output_base_path()
os.makedirs(os.path.join(BASE_PATH, UPLOAD_FOLDER), exist_ok=True)
os.makedirs(os.path.join(BASE_PATH, OUTPUT_FOLDER), exist_ok=True)
os.makedirs(os.path.join(BASE_PATH, LOG_FOLDER), exist_ok=True)
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_PATH, UPLOAD_FOLDER)
ALLOWED_EXTENSIONS = {'xlsx', 'pdf'}

# Global variables to track job progress and PF mismatch data
job_progress = {}
job_status = {}
pf_mismatched_data = {}  # Store DataFrame per job_id
pf_output_files = {}  # Store output Excel filename per job_id

# Simple user database (replace with proper database in production)
USERS = {
    'hrdept': 'hr@2008'  # username: password
}

def allowed_file(filename, extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

# Set up logging
def setup_logging(log_dir=os.path.join(BASE_PATH, LOG_FOLDER)):
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"highlight_process_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# PF ECR Name Mismatch Helper Functions
def clean_name(name):
    if not isinstance(name, str):
        return ""
    name = name.replace('\n', ' ')
    name = ' '.join(name.split())
    return name.lower()

def clean_name_display(name):
    if not isinstance(name, str):
        return ""
    name = name.replace('\n', ' ')
    return ' '.join(name.split())

def get_middle_two_chars(s):
    s = s.strip()
    length = len(s)
    if length < 2:
        return s
    mid = length // 2
    return s[mid-1:mid+1]

def highlight_uans_by_site(
    job_id,
    excel_path,
    pdf_path,
    output_dir,
    highlight_type,
    uan_column,
    esic_column,
    site_column,
    expand_left=1,
    expand_right=1,
    expand_top=1,
    expand_bottom=1,
    border_color=(1, 0, 0, 1),
    special_color=(0, 0, 1, 1),
    border_width=0.5,
    highlight_mode="border",
    highlight_opacity=0.25,
    logger=None
):
    global job_progress, job_status
    if logger is None:
        logger = logging.getLogger()
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        df = pd.read_excel(excel_path)
        target_column = uan_column if highlight_type == 'uan' else esic_column
        required_columns = [target_column, site_column]
        
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"Required column not found: {col}")
                job_status[job_id] = 'error'
                return False
        
        df[target_column] = df[target_column].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        expected_length = 12 if highlight_type == 'uan' else 10
        df = df[
            (df[target_column].notna()) &
            (df[target_column] != '0') &
            (df[target_column] != 'nan') &
            (df[target_column].str.match(r'^\d+$')) &
            (df[target_column].str.len() == expected_length)
        ]
        
        if df.empty:
            logger.error("No valid data after filtering the target column")
            job_status[job_id] = 'error'
            return False
        
        sites = df[site_column].dropna().unique()
        total_sites = len(sites)
        job_progress[job_id] = 0
        
        for idx, site in enumerate(sites):
            site_df = df[df[site_column] == site]
            number_dict = {}
            
            for _, row in site_df.iterrows():
                number = str(row[target_column]).strip()
                if not number or number == "nan":
                    continue
                clean_number = number.replace(" ", "")
                number_dict[clean_number] = "regular"
            
            if not number_dict:
                continue
            
            safe_site_name = ''.join(c if c.isalnum() else '_' for c in str(site))
            output_path = os.path.join(output_dir, f"{safe_site_name}_{highlight_type}.pdf")
            
            success = process_pdf_for_site(
                pdf_path=pdf_path,
                output_path=output_path,
                number_dict=number_dict,
                site_name=site,
                highlight_type=highlight_type,
                expand_left=expand_left,
                expand_right=expand_right,
                expand_top=expand_top,
                expand_bottom=expand_bottom,
                border_color=border_color,
                special_color=special_color,
                border_width=border_width,
                highlight_mode=highlight_mode,
                highlight_opacity=highlight_opacity,
                logger=logger
            )
            
            job_progress[job_id] = int(((idx + 1) / total_sites) * 100)
            
        job_status[job_id] = 'completed'
        return True
    
    except Exception as e:
        logger.error(f"Error in highlight_uans_by_site: {e}")
        job_status[job_id] = 'error'
        return False

def process_pdf_for_site(
    pdf_path,
    output_path,
    number_dict,
    site_name,
    highlight_type,
    expand_left,
    expand_right,
    expand_top,
    expand_bottom,
    border_color,
    special_color,
    border_width,
    highlight_mode,
    highlight_opacity,
    logger
):
    try:
        doc = fitz.open(pdf_path)
        total_matches = 0
        pages_to_keep = set([0])
        if highlight_type == 'uan':
            pages_to_keep.add(len(doc) - 1)
        
        for page_num, page in enumerate(doc):
            page_matches = 0
            for number, highlight_type_item in number_dict.items():
                if not number:
                    continue
                found_instances = page.search_for(number)
                if found_instances:
                    for rect in found_instances:
                        expanded_rect = fitz.Rect(
                            rect.x0 - expand_left,
                            rect.y0 - expand_top,
                            rect.x1 + expand_right,
                            rect.y1 + expand_bottom
                        )
                        color = special_color if highlight_type_item == "special" else border_color
                        
                        if highlight_mode == "border":
                            annot = page.add_rect_annot(expanded_rect)
                            annot.set_border(width=border_width)
                            annot.set_colors(stroke=color[:3])
                            annot.set_colors(fill=None)
                            annot.update()
                        elif highlight_mode == "highlight":
                            annot = page.add_rect_annot(expanded_rect)
                            annot.set_opacity(highlight_opacity)
                            annot.set_colors(fill=color[:3])
                            annot.set_border(width=0)
                            annot.update()
                        elif highlight_mode == "underline":
                            underline_y = rect.y1 + 0.5
                            page.draw_line(
                                start=(rect.x0, underline_y),
                                end=(rect.x1, underline_y),
                                color=color[:3],
                                width=border_width
                            )
                        page_matches += 1
            if page_matches > 0:
                pages_to_keep.add(page_num)
            total_matches += page_matches
        
        if total_matches > 0:
            new_doc = fitz.open()
            for page_num in sorted(pages_to_keep):
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            new_doc.save(output_path, garbage=4, deflate=True)
            new_doc.close()
            doc.close()
            return True
        else:
            doc.close()
            return False
            
    except Exception as e:
        logger.error(f"Error processing PDF for site {site_name}: {e}")
        return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if username in USERS and USERS[username] == password:
            session['user_id'] = username
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid username or password'})
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'status': 'success'})

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_files():
    job_id = str(uuid.uuid4())
    job_progress[job_id] = 0
    job_status[job_id] = 'processing'
    
    excel_file = request.files.get('excel')
    pdf_file = request.files.get('pdf')
    
    if not excel_file or not pdf_file:
        job_status[job_id] = 'error'
        return jsonify({'job_id': job_id, 'status': 'error', 'message': 'Both Excel and PDF files are required'})
    
    if not (allowed_file(excel_file.filename, {'xlsx'}) and allowed_file(pdf_file.filename, {'pdf'})):
        job_status[job_id] = 'error'
        return jsonify({'job_id': job_id, 'status': 'error', 'message': 'Invalid file types'})
    
    excel_filename = secure_filename(excel_file.filename)
    pdf_filename = secure_filename(pdf_file.filename)
    
    job_folder = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
    output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
    os.makedirs(job_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)
    
    excel_path = os.path.join(job_folder, excel_filename)
    pdf_path = os.path.join(job_folder, pdf_filename)
    
    excel_file.save(excel_path)
    pdf_file.save(pdf_path)
    
    try:
        df = pd.read_excel(excel_path)
        columns = df.columns.tolist()
        return jsonify({'job_id': job_id, 'status': 'columns', 'columns': columns})
    except Exception as e:
        job_status[job_id] = 'error'
        return jsonify({'job_id': job_id, 'status': 'error', 'message': f'Error reading Excel: {str(e)}'})

@app.route('/process', methods=['POST'])
@login_required
def process_files():
    data = request.form
    job_id = data.get('job_id')
    highlight_type = data.get('highlight_type')
    uan_column = data.get('uan_column', '')
    esic_column = data.get('esic_column', '')
    site_column = data.get('site_column')
    highlight_mode = data.get('highlight_mode', 'border')
    color = data.get('color', 'red')
    opacity = float(data.get('opacity', '0.25'))
    
    job_folder = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
    output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
    
    excel_path = next((os.path.join(job_folder, f) for f in os.listdir(job_folder) if f.endswith('.xlsx')), None)
    pdf_path = next((os.path.join(job_folder, f) for f in os.listdir(job_folder) if f.endswith('.pdf')), None)
    
    if not excel_path or not pdf_path:
        job_status[job_id] = 'error'
        return jsonify({'status': 'error', 'message': 'Files not found'})
    
    if not site_column or (highlight_type == 'uan' and not uan_column) or (highlight_type == 'esic' and not esic_column):
        job_status[job_id] = 'error'
        return jsonify({'status': 'error', 'message': 'Required columns not selected'})
    
    def parse_color(color_str):
        color_str = color_str.lower()
        colors = {
            'red': (1, 0, 0, 1),
            'blue': (0, 0, 1, 1),
            'green': (0, 0.5, 0, 1),
            'black': (0, 0, 0, 1),
            'orange': (1, 0.5, 0, 1),
            'yellow': (1, 0.9, 0, 1)
        }
        return colors.get(color_str, (1, 0, 0, 1))
    
    logger = setup_logging()
    
    def run_processing():
        highlight_uans_by_site(
            job_id=job_id,
            excel_path=excel_path,
            pdf_path=pdf_path,
            output_dir=output_folder,
            highlight_type=highlight_type,
            uan_column=uan_column,
            esic_column=esic_column,
            site_column=site_column,
            border_color=parse_color(color),
            highlight_mode=highlight_mode,
            highlight_opacity=opacity,
            logger=logger
        )
    
    threading.Thread(target=run_processing, daemon=True).start()
    return jsonify({'status': 'processing', 'job_id': job_id})

@app.route('/pf_upload', methods=['POST'])
@login_required
def pf_upload():
    job_id = str(uuid.uuid4())
    file = request.files.get('pdf_file')
    
    if not file or not allowed_file(file.filename, {'pdf'}):
        return jsonify({'status': 'error', 'message': 'Please upload a valid PDF file'})
    
    filename = secure_filename(file.filename)
    base_filename = os.path.splitext(filename)[0]
    output_filename = f"{base_filename}_name_mismatch.xlsx"
    
    job_folder = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
    output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
    os.makedirs(job_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)
    
    file_path = os.path.join(job_folder, filename)
    output_path = os.path.join(output_folder, output_filename)
    file.save(file_path)
    
    try:
        data = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[1:-1]:  # Skip first and last page
                table = page.extract_table()
                if table:
                    for row in table[1:]:  # Skip header row
                        selected_row = [row[0], row[1], row[2], row[3]]
                        data.append(selected_row)
        
        columns = ["Sl. No", "UAN", "ECR", "UAN Repository"]
        df = pd.DataFrame(data, columns=columns)
        df = df[df['Sl. No'].notna() & (df['Sl. No'] != 'None')].reset_index(drop=True)
        
        df['ECR_clean'] = df['ECR'].apply(clean_name)
        df['UAN_Repository_clean'] = df['UAN Repository'].apply(clean_name)
        df['ECR_middle'] = df['ECR_clean'].apply(get_middle_two_chars)
        df['UAN_Repository_middle'] = df['UAN_Repository_clean'].apply(get_middle_two_chars)
        
        df['Highlight'] = (
            (df['ECR_clean'].str[:4] == df['UAN_Repository_clean'].str[:4]) &
            (df['ECR_clean'].str[-4:] == df['UAN_Repository_clean'].str[-4:]) &
            (df['ECR_middle'] == df['UAN_Repository_middle'])
        )
        
        df['ECR'] = df['ECR'].apply(clean_name_display)
        df['UAN Repository'] = df['UAN Repository'].apply(clean_name_display)
        df['ECR'] = df['ECR'].str.replace(' ', '', regex=False)
        df['UAN Repository'] = df['UAN Repository'].str.replace(' ', '', regex=False)
        
        df = df[df['Highlight'] == False]
        df = df.drop(columns=['ECR_clean', 'UAN_Repository_clean', 'ECR_middle', 'UAN_Repository_middle', 'Highlight'])
        
        if df.empty:
            return jsonify({'status': 'error', 'message': 'No mismatches found'})
        
        pf_mismatched_data[job_id] = df
        pf_output_files[job_id] = output_filename
        df.to_excel(output_path, index=False)
        
        return jsonify({
            'status': 'success',
            'job_id': job_id,
            'mismatched_data': df.to_dict(orient='records'),
            'total_mismatches': len(df)
        })
    
    except Exception as e:
        logger = setup_logging()
        logger.error(f"Error in pf_upload: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error processing PDF: {str(e)}'})

@app.route('/pf_download/<job_id>')
@login_required
def pf_download(job_id):
    logger = setup_logging()
    try:
        if job_id not in pf_output_files:
            logger.error(f"No output file found for job_id: {job_id}")
            return jsonify({'status': 'error', 'message': 'No file available for download'})
        
        output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
        filename = pf_output_files.get(job_id)
        if not filename:
            logger.error(f"Filename not found in pf_output_files for job_id: {job_id}")
            return jsonify({'status': 'error', 'message': 'No file available for download'})
        
        filepath = os.path.join(output_folder, filename)
        if not os.path.exists(filepath):
            logger.error(f"File does not exist: {filepath}")
            return jsonify({'status': 'error', 'message': f'File not found: {filename}'})
        
        logger.info(f"Serving file: {filepath}")
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Error in pf_download for job_id {job_id}: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error downloading file: {str(e)}'})

@app.route('/pf_refresh/<job_id>', methods=['POST'])
@login_required
def pf_refresh(job_id):
    logger = setup_logging()
    try:
        job_folder = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
        output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
        
        for folder in [job_folder, output_folder]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                logger.info(f"Deleted folder: {folder}")
        
        pf_mismatched_data.pop(job_id, None)
        pf_output_files.pop(job_id, None)
        
        logger.info(f"Cleaned up job_id: {job_id}")
        return jsonify({'status': 'cleaned'})
    except Exception as e:
        logger.error(f"Error in pf_refresh for job_id {job_id}: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error cleaning up: {str(e)}'})

@app.route('/progress/<job_id>')
@login_required
def get_progress(job_id):
    progress = job_progress.get(job_id, 0)
    status = job_status.get(job_id, 'processing')
    return jsonify({'progress': progress, 'status': status})

@app.route('/results/<job_id>')
@login_required
def get_results(job_id):
    logger = setup_logging()
    try:
        output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
        if not os.path.exists(output_folder):
            logger.error(f"Output folder does not exist: {output_folder}")
            return jsonify({'status': 'error', 'message': 'No results found'})
        
        files = [f for f in os.listdir(output_folder) if f.endswith('.pdf')]
        logger.info(f"Found {len(files)} PDF files for job_id: {job_id}")
        return jsonify({'status': 'completed', 'files': files})
    except Exception as e:
        logger.error(f"Error in get_results for job_id {job_id}: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error retrieving results: {str(e)}'})

@app.route('/download/<job_id>/<filename>')
@login_required
def download_file(job_id, filename):
    logger = setup_logging()
    try:
        output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
        filepath = os.path.join(output_folder, filename)
        
        if not os.path.exists(filepath):
            logger.error(f"File does not exist: {filepath}")
            return jsonify({'status': 'error', 'message': f'File not found: {filename}'})
        
        logger.info(f"Serving file: {filepath}")
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Error in download_file for job_id {job_id}, filename {filename}: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error downloading file: {str(e)}'})

@app.route('/download_zip/<job_id>')
@login_required
def download_zip(job_id):
    logger = setup_logging()
    try:
        output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
        zip_path = os.path.join(BASE_PATH, OUTPUT_FOLDER, f"{job_id}.zip")
        
        if not os.path.exists(output_folder):
            logger.error(f"Output folder does not exist: {output_folder}")
            return jsonify({'status': 'error', 'message': 'No files available for download'})
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(output_folder):
                for file in files:
                    if file.endswith('.pdf'):
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, output_folder))
                        logger.info(f"Added to ZIP: {file_path}")
        
        if not os.path.exists(zip_path):
            logger.error(f"ZIP file was not created: {zip_path}")
            return jsonify({'status': 'error', 'message': 'Failed to create ZIP file'})
        
        logger.info(f"Serving ZIP file: {zip_path}")
        return send_file(zip_path, as_attachment=True, download_name=f"highlighted_pdfs_{job_id}.zip")
    except Exception as e:
        logger.error(f"Error in download_zip for job_id {job_id}: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error creating ZIP file: {str(e)}'})
    finally:
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                logger.info(f"Deleted temporary ZIP file: {zip_path}")
            except Exception as e:
                logger.error(f"Error deleting temporary ZIP file {zip_path}: {str(e)}")

@app.route('/cleanup/<job_id>')
@login_required
def cleanup(job_id):
    logger = setup_logging()
    try:
        job_folder = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
        output_folder = os.path.join(BASE_PATH, OUTPUT_FOLDER, job_id)
        zip_path = os.path.join(BASE_PATH, OUTPUT_FOLDER, f"{job_id}.zip")
        
        for folder in [job_folder, output_folder]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                logger.info(f"Deleted folder: {folder}")
        
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logger.info(f"Deleted ZIP file: {zip_path}")
        
        job_progress.pop(job_id, None)
        job_status.pop(job_id, None)
        
        logger.info(f"Cleaned up job_id: {job_id}")
        return jsonify({'status': 'cleaned'})
    except Exception as e:
        logger.error(f"Error in cleanup for job_id {job_id}: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error cleaning up: {str(e)}'})

if __name__ == '__main__':
    # Automatically open the browser when running the app
    import webbrowser
    webbrowser.open('http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=False)