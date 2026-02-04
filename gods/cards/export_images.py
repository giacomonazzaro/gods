import fitz  # PyMuPDF
import os

def pdf_to_jpg(pdf_path, output_folder):
    # Create output directory if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Open the PDF
    doc = fitz.open(pdf_path)
    
    print(f"Total pages: {len(doc)}")

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        
        # Increase resolution (2.0 = 2x zoom/DPI)
        # Without this, the default export can be blurry
        zoom = 2.0 
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        output_filename = f"page_{page_index + 1}.jpg"
        output_path = os.path.join(output_folder, output_filename)
        
        pix.save(output_path)
        print(f"Saved: {output_path}")

    doc.close()
    print("Done! Check the 'output_images' folder.")

# USAGE: Put your filename here
import sys
pdf_to_jpg(sys.argv[1], sys.argv[2])