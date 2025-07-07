from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import pandas as pd
import tempfile
import shutil
import zipfile
import io
import os
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)

# Import models AFTER app configuration
from models import db, ColumnMapping

# Initialize db with app
db.init_app(app)

def create_tables():
    """Create database tables if they don't exist"""
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully!")
            
            # Verify table creation
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Tables created: {tables}")
            
        except Exception as e:
            print(f"Error creating tables: {e}")

@app.route('/test-db', methods=['GET'])
def test_db():
    """Test endpoint to verify database connectivity"""
    try:
        count = ColumnMapping.query.count()
        return jsonify({"status": "success", "table_count": count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/view-mappings', methods=['GET'])
def view_mappings():
    """View all stored mappings"""
    try:
        mappings = ColumnMapping.query.all()
        mapping_list = []
        for mapping in mappings:
            mapping_list.append({
                "id": mapping.id,
                "fbdi_module": mapping.fbdi_module,
                "fbdi_subset": mapping.fbdi_subset,
                "template_column": mapping.template_column,
                "raw_column": mapping.raw_column,
                "status": mapping.status,
                "created_at": mapping.created_at.strftime('%Y-%m-%d %H:%M:%S') if mapping.created_at else None
            })
        return jsonify({"status": "success", "mappings": mapping_list, "total_count": len(mapping_list)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/generate-fbdi', methods=['POST'])
def generate_fbdi():
    try:
        # Ensure tables exist before operations
        with app.app_context():
            db.create_all()
        
        # Receive uploaded files
        template_file = request.files['template_file']
        raw_file = request.files['raw_file']

        # Save files temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsm") as tmp_template, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_raw:
            shutil.copyfileobj(template_file.stream, tmp_template)
            shutil.copyfileobj(raw_file.stream, tmp_raw)

        # Read template and raw data
        template_df = pd.read_excel(tmp_template.name, sheet_name="RA_INTERFACE_LINES_ALL", header=None)
        raw_sheets = pd.read_excel(tmp_raw.name, sheet_name=None)
        raw_df = pd.read_excel(tmp_raw.name, sheet_name=list(raw_sheets.keys())[0], header=None)

        # Header rows
        template_header_row = 3  # 0-based index
        raw_header_row = 1

        template_columns = template_df.iloc[template_header_row].tolist()
        raw_columns = raw_df.iloc[raw_header_row].tolist()
        raw_data = raw_df.iloc[raw_header_row + 1:].reset_index(drop=True)

        start_row = template_header_row + 1
        num_rows = raw_data.shape[0]
        rows_needed = start_row + num_rows

        # Extend template if needed
        if template_df.shape[0] < rows_needed:
            empty_rows = pd.DataFrame([[""] * template_df.shape[1]] * (rows_needed - template_df.shape[0]))
            template_df = pd.concat([template_df, empty_rows], ignore_index=True)

        # Store mappings in database (keep all historical mappings)
        mappings_inserted = 0
        
        # Fill template from raw, except "*Buisness Unit Name"
        for col_idx, template_col in enumerate(template_columns):
            # Skip empty/null template columns
            if pd.isna(template_col) or template_col == "":
                continue
                
            if template_col in raw_columns and template_col != "*Buisness Unit Name":
                raw_col_idx = raw_columns.index(template_col)
                template_df.iloc[start_row:start_row + num_rows, col_idx] = raw_data.iloc[:, raw_col_idx].values
                raw_col_name = raw_columns[raw_col_idx]
                status = 'Y'
            else:
                raw_col_name = ""
                status = 'N'

            # Save mapping to database
            mapping = ColumnMapping(
                fbdi_module="AR",
                fbdi_subset="RA_INTERFACE_LINES_ALL",
                template_column=str(template_col),
                raw_column=str(raw_col_name) if raw_col_name else "",
                status=status
            )
            db.session.add(mapping)
            mappings_inserted += 1

        # Handle special case: copy '*Buisness Unit Name' from raw to 'Comments' in template
        if "*Buisness Unit Name" in raw_columns and "Comments" in template_columns:
            raw_bu_col_idx = raw_columns.index("*Buisness Unit Name")
            comments_col_idx = template_columns.index("Comments")
            template_df.iloc[start_row:start_row + num_rows, comments_col_idx] = raw_data.iloc[:, raw_bu_col_idx].values
            
            # Add special mapping for this case
            special_mapping = ColumnMapping(
                fbdi_module="AR",
                fbdi_subset="RA_INTERFACE_LINES_ALL",
                template_column="Comments",
                raw_column="*Buisness Unit Name",
                status='Y'
            )
            db.session.add(special_mapping)
            mappings_inserted += 1

        # Commit all mappings to database
        db.session.commit()
        print(f"✓ Inserted {mappings_inserted} column mappings into database")

        # Save CSV and zip it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_csv:
            template_df.to_csv(tmp_csv.name, index=False, header=False)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(tmp_csv.name, arcname="fbdi_output.csv")
            zip_buffer.seek(0)

        # Cleanup
        os.remove(tmp_template.name)
        os.remove(tmp_raw.name)
        os.remove(tmp_csv.name)

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='fbdi_output.zip'
        )

    except Exception as e:
        print(f"Error in generate_fbdi: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/clear-mappings', methods=['DELETE'])
def clear_mappings():
    """Clear all stored mappings (optional endpoint for testing)"""
    try:
        deleted_count = ColumnMapping.query.count()
        ColumnMapping.query.delete()
        db.session.commit()
        return jsonify({"status": "success", "message": f"Deleted {deleted_count} mappings"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    print("Starting Flask application...")
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    create_tables()  # Create tables before running the app
    
    # Check if database file was created
    if os.path.exists('instance/db.sqlite3') or os.path.exists('db.sqlite3'):
        print("✓ Database file created successfully!")
    else:
        print("✗ Database file was not created!")
    
    app.run(debug=True)
