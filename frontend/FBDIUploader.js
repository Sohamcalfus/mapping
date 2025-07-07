import React, { useState } from "react";
 
const FBDIUploader = () => {

  const [templateFile, setTemplateFile] = useState(null);

  const [rawFile, setRawFile] = useState(null);

  const [loading, setLoading] = useState(false);
 
  const handleSubmit = async (e) => {

    e.preventDefault();
 
    if (!templateFile || !rawFile) {

      alert("Please upload both files.");

      return;

    }
 
    const formData = new FormData();

    formData.append("template_file", templateFile);

    formData.append("raw_file", rawFile);
 
    setLoading(true);
 
    try {

      const response = await fetch("http://localhost:5000/generate-fbdi", {

        method: "POST",

        body: formData,

      });
 
      if (!response.ok) {

        throw new Error("Failed to generate FBDI file");

      }
 
      const blob = await response.blob();

      const downloadUrl = window.URL.createObjectURL(blob);

      const a = document.createElement("a");

      a.href = downloadUrl;

      a.download = "fbdi_output.zip";

      document.body.appendChild(a);

      a.click();

      a.remove();

    } catch (error) {

      alert("Error: " + error.message);

    } finally {

      setLoading(false);

    }

  };
 
  return (
<div className="container mt-5" style={{ maxWidth: "480px" }}>
<h2 className="mb-4 text-center">FBDI File Generator</h2>
<form onSubmit={handleSubmit}>
<div className="mb-3">
<label htmlFor="templateFile" className="form-label">

            Template File (.xlsm)
</label>
<input

            type="file"

            className="form-control"

            id="templateFile"

            accept=".xlsm"

            onChange={(e) => setTemplateFile(e.target.files[0])}

          />
</div>
 
        <div className="mb-3">
<label htmlFor="rawFile" className="form-label">

            Raw Data File (.xlsx)
</label>
<input

            type="file"

            className="form-control"

            id="rawFile"

            accept=".xlsx"

            onChange={(e) => setRawFile(e.target.files[0])}

          />
</div>
 
        <button

          type="submit"

          className="btn btn-primary w-100"

          disabled={loading}
>

          {loading ? (
<>
<span

                className="spinner-border spinner-border-sm me-2"

                role="status"

                aria-hidden="true"
></span>

              Generating...
</>

          ) : (

            "Generate FBDI ZIP"

          )}
</button>
</form>
<p className="mt-3 text-muted text-center">

        Select your files and click generate.
</p>
</div>

  );

};
 
export default FBDIUploader;

 
