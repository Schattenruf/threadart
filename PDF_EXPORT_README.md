# Thread Art PDF Export - Picture Hanger Instructions

## Overview

This module generates professional PDF instructions for creating thread art using **picture hangers** (Bilderaufhänger) instead of nails. Each picture hanger has two attachment points (left and right).

## Features

✨ **Professional PDF Generation**
- Clear, readable instruction pages
- Organized by color groups
- Progress tracking
- Color-coded sections

🖼️ **Picture Hanger Support**
- Converts pin indices to hanger numbers and positions
- Supports L/R (left/right) positioning per hanger
- Clearly labeled attachment points

📊 **Statistics**
- Lines per color breakdown
- Hanger usage analysis
- Distribution metrics

## Installation

The module requires:
```bash
pip install reportlab PyPDF2
```

These are already included in `requirements.txt`.

## Usage in Streamlit App

The PDF export button is integrated directly into the Download Options section:

```python
with col3:
    if st.button("🖨️ Generate PDF Instructions"):
        from pdf_export import export_to_pdf
        
        pdf_path = export_to_pdf(
            line_sequence=line_sequence,
            color_names=color_names,
            group_orders=group_orders,
            output_path="outputs_drawing/my_art_instructions",
            n_nodes=320,  # Your max nodes
            num_cols=3,   # Columns per page
            num_rows=18,  # Rows per page
            include_stats=True
        )
```

## Node to Hanger Conversion

### Mapping Logic

- **Node Index** → **Hanger Number & Position**
- `0, 1` → Hanger 0 (Left, Right)
- `2, 3` → Hanger 1 (Left, Right)
- `4, 5` → Hanger 2 (Left, Right)
- etc.

### Example Display

```
From: Hanger  42 L
To:   Hanger  87 R
```

## PDF Structure

Each generated PDF includes:

1. **Instruction Pages**
   - 3 columns × 18 rows (customizable)
   - From/To hanger instructions
   - Color group markers
   - Progress indicators

2. **Section Headers**
   - Color name
   - Group number (e.g., "Red 1/3")
   - Progress bar
   - Completion status

3. **Statistics** (optional)
   - Total lines per color
   - Lines per hanger analysis
   - Usage distribution

## Output Files

Generated files are saved with auto-incrementing version numbers:
- `outputs_drawing/my_art_instructions_01.pdf`
- `outputs_drawing/my_art_instructions_02.pdf`
- etc.

## Customization

### Font

The module attempts to load `Courier Prime` for a monospace font. If unavailable, it falls back to Helvetica.

### Page Layout

Customize columns and rows:
```python
pdf_path = export_to_pdf(
    ...,
    num_cols=4,   # 4 columns per page
    num_rows=20,  # 20 rows per page
)
```

### Font Size

```python
generator = ThreadArtPDFGenerator(font_size=12)
pdf = generator.generate_pdf(...)
```

## API Reference

### `ThreadArtPDFGenerator` Class

```python
generator = ThreadArtPDFGenerator(
    font_size: int = 11,
    use_custom_font: bool = True
)

pdf_path = generator.generate_pdf(
    line_sequence: List[Dict],           # From streamlit session
    color_names: List[str],              # List of color names
    group_orders: str,                   # Color order string
    output_path: str,                    # Output path without extension
    n_nodes: int,                        # Total attachment points
    num_cols: int = 3,                   # Columns per page
    num_rows: int = 18,                  # Rows per page
    include_stats: bool = True,          # Show statistics
    version: str = "n+1"                 # "n+1" (auto), None, or int
)
```

### `PictureHangerFormatter` Class

```python
formatter = PictureHangerFormatter(
    n_nodes: int,
    hanger_spacing: float = 1.0
)

# Format a node index to hanger information
hanger_num, position, label = formatter.format_node(node_idx)
# Returns: ("42", "L", "Hanger  42 L")

# Get display-friendly label
label = formatter.get_hanger_display(node_idx)
# Returns: "Hanger  42 L"
```

### `export_to_pdf()` Function

Convenience wrapper:
```python
from pdf_export import export_to_pdf

pdf_path = export_to_pdf(
    line_sequence=seq,
    color_names=color_names,
    group_orders=group_orders,
    output_path=output_path,
    n_nodes=n_nodes,
    **kwargs
)
```

Returns: `str` (path to PDF) or `None` if failed.

## Example Workflow

1. **Generate Thread Art in Streamlit**
   - Select image
   - Configure parameters
   - Click "Generate Thread Art"
   - Line sequence is captured automatically

2. **Export to PDF**
   - Click "🖨️ Generate PDF Instructions" button
   - Module processes the line sequence
   - Creates multi-page PDF with color grouping
   - Displays statistics
   - Provides download button

3. **Use Instructions**
   - Print PDF
   - Follow hanger and position labels
   - Connect threads according to instructions

## Error Handling

If `reportlab` or `PyPDF2` are not installed:
```
❌ reportlab and PyPDF2 required: `pip install reportlab PyPDF2`
```

Install missing dependencies and refresh the page.

## Performance

- **Small projects** (~500 lines): <1 second
- **Medium projects** (~5000 lines): ~2-3 seconds  
- **Large projects** (~10000 lines): ~5-10 seconds

PDF generation happens in-memory for better performance.

## Troubleshooting

### PDF Not Generated
- Check that `line_sequence` is not empty
- Verify `color_names` list is populated
- Ensure `outputs_drawing/` directory exists

### Font Issues
- If custom font is not found, Helvetica will be used automatically
- To use a custom font, place TTF file in `lines/courier-prime.regular.ttf`

### Memory Issues (Large Projects)
- Reduce `num_rows` to process fewer lines per page
- Increase `num_cols` to spread content wider

## License

Part of the Thread Art Generator project.
