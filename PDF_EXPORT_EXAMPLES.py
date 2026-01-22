"""
Quick Integration Guide for PDF Export

This file shows how to integrate the PDF export into your code.
Note: This is a documentation file with code examples. Not all code is executable here.
See streamlit_app.py for the actual implementation.
"""

# ============================================================================
# STREAMLIT INTEGRATION (Already done in streamlit_app.py)
# ============================================================================

"""
In your Download Options section of streamlit_app.py:

if st.session_state.get("line_sequence"):
    seq = st.session_state.line_sequence
    
    col1, col2, col3 = st.columns(3)
    
    # CSV Export
    with col1:
        import io as _io
        csv_buf = _io.StringIO()
        csv_buf.write("step,color_index,color_hex,r,g,b,from_pin,to_pin\\n")
        for row in seq:
            r, g, b = row["rgb"]
            csv_buf.write(f"{row['step']},{row['color_index']},{row['color_hex']},{r},{g},{b},{row['from_pin']},{row['to_pin']}\\n")
        csv_bytes = csv_buf.getvalue().encode("utf-8")
        st.download_button(
            label="📊 CSV",
            data=csv_bytes,
            file_name=f"{name or 'thread_art'}_sequence.csv",
            mime="text/csv",
        )

    # JSON Export
    with col2:
        json_bytes = json.dumps(seq, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label="📄 JSON",
            data=json_bytes,
            file_name=f"{name or 'thread_art'}_sequence.json",
            mime="application/json",
        )
    
    # PDF Export (Picture Hangers)
    with col3:
        if st.button("🖨️ Generate PDF Instructions", key="gen_pdf"):
            try:
                from pdf_export import export_to_pdf
                
                # Get color information
                detected_colors = st.session_state.get("all_found_colors", [])
                color_names = [c["color_name"] for c in detected_colors]
                group_orders = st.session_state.get("group_orders", "")
                n_nodes = st.session_state.get("n_nodes_real", 320)
                
                # Generate PDF
                output_path = f"outputs_drawing/{name or 'thread_art'}_instructions"
                pdf_path = export_to_pdf(
                    line_sequence=seq,
                    color_names=color_names,
                    group_orders=group_orders,
                    output_path=output_path,
                    n_nodes=n_nodes,
                    num_cols=3,
                    num_rows=18,
                    include_stats=True,
                    version="n+1"
                )
                
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        pdf_data = f.read()
                    
                    st.download_button(
                        label="💾 Download PDF",
                        data=pdf_data,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf",
                    )
                    st.success(f"✅ PDF generated: {os.path.basename(pdf_path)}")
                else:
                    st.error("❌ PDF generation failed")
            
            except ImportError:
                st.error("❌ reportlab and PyPDF2 required: `pip install reportlab PyPDF2`")
            except Exception as e:
                st.error(f"❌ Error generating PDF: {str(e)}")
"""


# ============================================================================
# SESSION STATE SETUP (Already done in streamlit_app.py)
# ============================================================================

"""
Store variables in session_state for PDF export:

# Store n_nodes_real for PDF export
st.session_state["n_nodes_real"] = n_nodes_real

# Store group_orders for PDF export
st.session_state["group_orders"] = group_orders
"""


# ============================================================================
# STANDALONE USAGE (without Streamlit)
# ============================================================================

"""
Example 1: Basic PDF Export

from pdf_export import export_to_pdf, ThreadArtPDFGenerator, PictureHangerFormatter

# Example data
line_sequence = [
    {
        "step": 1,
        "color_index": 1,
        "color_hex": "#000000",
        "rgb": [0, 0, 0],
        "from_pin": 0,
        "to_pin": 50,
    },
    {
        "step": 2,
        "color_index": 1,
        "color_hex": "#000000",
        "rgb": [0, 0, 0],
        "from_pin": 50,
        "to_pin": 100,
    },
    # ... more lines
]

color_names = ["Black", "Red", "White"]
group_orders = "0011223"
n_nodes = 320

# Generate PDF
pdf_path = export_to_pdf(
    line_sequence=line_sequence,
    color_names=color_names,
    group_orders=group_orders,
    output_path="my_art_instructions",
    n_nodes=n_nodes,
    include_stats=True
)

print(f"PDF saved to: {pdf_path}")
"""


# ============================================================================
# ADVANCED USAGE
# ============================================================================

"""
Example 2: Custom Layout

from pdf_export import ThreadArtPDFGenerator

# Create generator with custom font size
generator = ThreadArtPDFGenerator(font_size=12, use_custom_font=True)

# Generate with custom layout
pdf_path = generator.generate_pdf(
    line_sequence=line_sequence,
    color_names=color_names,
    group_orders=group_orders,
    output_path="my_custom_art",
    n_nodes=n_nodes,
    num_cols=4,      # 4 columns per page
    num_rows=20,     # 20 rows per page
    include_stats=True,
    version="n+1"    # Auto-incrementing version
)
"""


# ============================================================================
# FORMATTER USAGE
# ============================================================================

"""
Example 3: Using PictureHangerFormatter

from pdf_export import PictureHangerFormatter

formatter = PictureHangerFormatter(n_nodes=320)

# Convert node indices to hanger format
for node_idx in [0, 1, 42, 43, 319, 320]:
    hanger_num, position, label = formatter.format_node(node_idx)
    print(f"Node {node_idx:3d} → {label}")

# Output:
# Node   0 → Hanger   0 L
# Node   1 → Hanger   0 R
# Node  42 → Hanger  21 L
# Node  43 → Hanger  21 R
# Node 319 → Hanger 159 L
# Node 320 → Hanger 160 R
"""


# ============================================================================
# REQUIREMENTS
# ============================================================================

# Add to requirements.txt:
# reportlab>=4.0.0
# PyPDF2>=3.16.0

# Install with:
# pip install reportlab PyPDF2
