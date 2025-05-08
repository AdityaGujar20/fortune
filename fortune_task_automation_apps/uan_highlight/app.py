import os
import pandas as pd
import fitz  # PyMuPDF
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
import uuid
import shutil
import zipfile
import threading
import time

app = Flask(__name__)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
LOG_FOLDER = 'logs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'xlsx', 'pdf'}

# Global variable to track job progress
job_progress = {}
job_status = {}

def allowed_file(filename, extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

# Set up logging
def setup_logging(log_dir=LOG_FOLDER):
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

def highlight_uans_by_site(
    job_id,
    excel_path,
    pdf_path,
    output_dir,
    uan_column,
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
        if uan_column not in df.columns or site_column not in df.columns:
            logger.error(f"Required columns not found: {uan_column}, {site_column}")
            job_status[job_id] = 'error'
            return False
        
        df[uan_column] = df[uan_column].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        sites = df[site_column].dropna().unique()
        total_sites = len(sites)
        job_progress[job_id] = 0
        
        for idx, site in enumerate(sites):
            site_df = df[df[site_column] == site]
            uan_dict = {}
            for _, row in site_df.iterrows():
                uan = str(row[uan_column]).strip()
                if not uan or uan == "nan":
                    continue
                clean_uan = uan.replace(" ", "")
                uan_dict[clean_uan] = "regular"
            
            if not uan_dict:
                continue
            
            safe_site_name = ''.join(c if c.isalnum() else '_' for c in str(site))
            output_path = os.path.join(output_dir, f"{safe_site_name}.pdf")
            
            success = process_pdf_for_site(
                pdf_path=pdf_path,
                output_path=output_path,
                uan_dict=uan_dict,
                site_name=site,
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
    uan_dict,
    site_name,
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
        pages_to_keep = set([0, len(doc) - 1])
        
        for page_num, page in enumerate(doc):
            page_matches = 0
            for uan, highlight_type in uan_dict.items():
                if not uan:
                    continue
                found_instances = page.search_for(uan)
                if found_instances:
                    for rect in found_instances:
                        expanded_rect = fitz.Rect(
                            rect.x0 - expand_left,
                            rect.y0 - expand_top,
                            rect.x1 + expand_right,
                            rect.y1 + expand_bottom
                        )
                        color = special_color if highlight_type == "special" else border_color
                        
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
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
    output_folder = os.path.join(OUTPUT_FOLDER, job_id)
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
def process_files():
    data = request.form
    job_id = data.get('job_id')
    uan_column = data.get('uan_column')
    site_column = data.get('site_column')
    highlight_mode = data.get('highlight_mode', 'border')
    color = data.get('color', 'red')
    opacity = float(data.get('opacity', '0.25'))
    
    job_folder = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
    output_folder = os.path.join(OUTPUT_FOLDER, job_id)
    
    excel_path = next((os.path.join(job_folder, f) for f in os.listdir(job_folder) if f.endswith('.xlsx')), None)
    pdf_path = next((os.path.join(job_folder, f) for f in os.listdir(job_folder) if f.endswith('.pdf')), None)
    
    if not excel_path or not pdf_path:
        job_status[job_id] = 'error'
        return jsonify({'status': 'error', 'message': 'Files not found'})
    
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
            uan_column=uan_column,
            site_column=site_column,
            border_color=parse_color(color),
            highlight_mode=highlight_mode,
            highlight_opacity=opacity,
            logger=logger
        )
    
    threading.Thread(target=run_processing, daemon=True).start()
    return jsonify({'status': 'processing', 'job_id': job_id})

@app.route('/progress/<job_id>')
def get_progress(job_id):
    progress = job_progress.get(job_id, 0)
    status = job_status.get(job_id, 'processing')
    return jsonify({'progress': progress, 'status': status})

@app.route('/results/<job_id>')
def get_results(job_id):
    output_folder = os.path.join(OUTPUT_FOLDER, job_id)
    if not os.path.exists(output_folder):
        return jsonify({'status': 'error', 'message': 'No results found'})
    
    files = [f for f in os.listdir(output_folder) if f.endswith('.pdf')]
    return jsonify({'status': 'completed', 'files': files})

@app.route('/download/<job_id>/<filename>')
def download_file(job_id, filename):
    output_folder = os.path.join(OUTPUT_FOLDER, job_id)
    return send_from_directory(output_folder, filename, as_attachment=True)

@app.route('/download_zip/<job_id>')
def download_zip(job_id):
    output_folder = os.path.join(OUTPUT_FOLDER, job_id)
    zip_path = os.path.join(OUTPUT_FOLDER, f"{job_id}.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_folder):
            for file in files:
                if file.endswith('.pdf'):
                    zipf.write(os.path.join(root, file), file)
    
    return send_file(zip_path, as_attachment=True, download_name=f"highlighted_pdfs_{job_id}.zip")

@app.route('/cleanup/<job_id>')
def cleanup(job_id):
    job_folder = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
    output_folder = os.path.join(OUTPUT_FOLDER, job_id)
    zip_path = os.path.join(OUTPUT_FOLDER, f"{job_id}.zip")
    
    for folder in [job_folder, output_folder]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    if os.path.exists(zip_path):
        os.remove(zip_path)
    
    job_progress.pop(job_id, None)
    job_status.pop(job_id, None)
    
    return jsonify({'status': 'cleaned'})

if __name__ == '__main__':
    app.run(debug=True)