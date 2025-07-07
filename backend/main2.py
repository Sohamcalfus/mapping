from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import pandas as pd
import tempfile
import shutil
import zipfile
import io
import os

app = Flask(__name__)
CORS(app)

@app.route('/generate-fbdi', methods=['POST'])
def generate_fbdi():
    try:
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

        # Identify header rows
        template_header_row = 3 
        raw_header_row = 1       

        template_columns = template_df.iloc[template_header_row].tolist()
        raw_columns = raw_df.iloc[raw_header_row].tolist()
        raw_data = raw_df.iloc[raw_header_row + 1:].reset_index(drop=True)

        # Prepare to fill the template
        start_row = template_header_row + 1
        num_rows = raw_data.shape[0]
        rows_needed = start_row + num_rows

        # Extend template if needed
        if template_df.shape[0] < rows_needed:
            empty_rows = pd.DataFrame([[""] * template_df.shape[1]] * (rows_needed - template_df.shape[0]))
            template_df = pd.concat([template_df, empty_rows], ignore_index=True)

        # Fill template with raw data, preserving hard-coded values
                # Fill template with raw data, preserving hard-coded values
                # Step 1: Fill from raw data for all columns except '*Buisness Unit Name'
        for col_idx, template_col in enumerate(template_columns):
            if template_col in raw_columns and template_col != "*Buisness Unit Name":
                raw_col_idx = raw_columns.index(template_col)
                template_df.iloc[start_row:start_row + num_rows, col_idx] = raw_data.iloc[:, raw_col_idx].values

        # Step 2: Copy '*Buisness Unit Name' from raw file into 'Comments' column in template
        if "*Buisness Unit Name" in raw_columns and "Comments" in template_columns:
            raw_bu_col_idx = raw_columns.index("*Buisness Unit Name")
            comments_col_idx = template_columns.index("Comments")
            template_df.iloc[start_row:start_row + num_rows, comments_col_idx] = raw_data.iloc[:, raw_bu_col_idx].values



        # Save CSV to temp and zip it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_csv:
            template_df.to_csv(tmp_csv.name, index=False, header=False)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(tmp_csv.name, arcname="fbdi_output.csv")
            zip_buffer.seek(0)

        # Cleanup temp files
        os.remove(tmp_template.name)
        os.remove(tmp_raw.name)
        os.remove(tmp_csv.name)

        # Return ZIP file
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='fbdi_output.zip'
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
