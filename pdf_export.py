"""
PDF Export Module for Thread Art Generator
Generates printable instructions for creating thread art using picture hangers (Bilderaufhänger)
instead of nails. Each hanger has two attachment points per hook.
"""

import os
import math
import numpy as np
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple, Optional

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, inch
    from reportlab.lib.colors import HexColor, black, gray, white, blue
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from PyPDF2 import PdfMerger, PdfReader
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class PictureHangerFormatter:
    """Formats instructions for picture hangers instead of nails.
    Each hanger has two attachment points: left (0) and right (-1) or equivalent."""
    
    def __init__(self, n_nodes: int, hanger_spacing: float = 1.0):
        """
        Initialize formatter for picture hangers.
        
        Args:
            n_nodes: Total number of nodes/hooks
            hanger_spacing: Spacing between hangers (for display purposes)
        """
        self.n_nodes = n_nodes
        self.hanger_spacing = hanger_spacing
        self.n_hangers = (n_nodes + 1) // 2  # Each hanger has 2 attachment points
    
    def format_node(self, node_idx: int) -> Tuple[str, str, str]:
        """
        Convert node index to hanger-friendly format.
        
        Returns:
            (hanger_number, position, full_label)
            - hanger_number: Which hanger (0-indexed)
            - position: "L" for left (0) or "R" for right (-1)
            - full_label: Complete label like "Hanger 42 Left"
        """
        hanger_num = node_idx // 2
        position_idx = node_idx % 2
        position = "L" if position_idx == 0 else "R"
        
        label = f"Hanger {hanger_num:3d} {position}"
        return str(hanger_num), position, label
    
    def get_hanger_display(self, node_idx: int) -> str:
        """Get a nicely formatted display string for instructions."""
        hanger_num, position, label = self.format_node(node_idx)
        return label


class ThreadArtPDFGenerator:
    """Generates professional PDF instructions for thread art."""
    
    def __init__(self, font_size: int = 11, use_custom_font: bool = True):
        """
        Initialize PDF generator.
        
        Args:
            font_size: Base font size in points
            use_custom_font: Whether to try loading a custom TTF font
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab and PyPDF2 are required for PDF export")
        
        self.font_size = font_size
        self.using_font = False
        self.font_name = "Helvetica"
        
        if use_custom_font:
            self._setup_custom_font()
    
    def _setup_custom_font(self) -> None:
        """Try to setup a custom monospace font."""
        try:
            font_paths = [
                'lines/courier-prime.regular.ttf',
                'fonts/courier-prime.regular.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf'
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('CourierPrime', font_path))
                    self.font_name = 'CourierPrime'
                    self.using_font = True
                    break
        except Exception as e:
            print(f"Warning: Could not load custom font: {e}")
    
    def generate_pdf(
        self,
        line_sequence: List[Dict],
        color_names: List[str],
        group_orders: str,
        output_path: str,
        n_nodes: int,
        num_cols: int = 3,
        num_rows: int = 18,
        include_stats: bool = True,
        version: str = "n+1"
    ) -> str:
        """
        Generate a complete PDF with instructions.
        
        Args:
            line_sequence: List of line dicts with step, color_index, from_pin, to_pin, etc.
            color_names: List of color names
            group_orders: String indicating the order of colors (e.g., "0011223")
            output_path: Base output path (without extension)
            n_nodes: Total number of nodes/attachment points
            num_cols: Number of columns per page
            num_rows: Number of rows per page
            include_stats: Whether to include statistics
            version: Version numbering ("n+1" for auto-increment, None for single, or int)
        
        Returns:
            Path to generated PDF
        """
        formatter = PictureHangerFormatter(n_nodes)
        
        # Group lines by color
        line_dict = self._group_lines_by_color(line_sequence, color_names)
        
        # Generate individual pages
        page_list = self._generate_instruction_pages(
            line_dict=line_dict,
            group_orders=group_orders,
            color_names=color_names,
            formatter=formatter,
            output_path=output_path,
            num_cols=num_cols,
            num_rows=num_rows
        )
        
        # Merge pages into single PDF
        final_pdf = self._merge_pages_to_pdf(page_list, output_path, version)
        
        # Generate statistics if requested
        if include_stats:
            self._generate_statistics(line_dict, formatter, output_path)
        
        return final_pdf
    
    def _group_lines_by_color(
        self,
        line_sequence: List[Dict],
        color_names: List[str]
    ) -> Dict[str, List[Tuple[int, int]]]:
        """Group lines by color name."""
        line_dict = {color: [] for color in color_names}
        
        for entry in line_sequence:
            try:
                color_idx = entry.get("color_index", 1) - 1  # Convert to 0-based, default to 1
                from_pin = entry.get("from_pin", 0)
                to_pin = entry.get("to_pin", 0)
                
                # Ensure pins are integers
                from_pin = int(from_pin)
                to_pin = int(to_pin)
                
                if 0 <= color_idx < len(color_names):
                    color_name = color_names[color_idx]
                    line_dict[color_name].append((from_pin, to_pin))
            except (KeyError, ValueError, TypeError) as e:
                # Skip malformed entries
                print(f"Warning: Skipping malformed entry: {entry} ({e})")
                continue
        
        return line_dict
    
    def _generate_instruction_pages(
        self,
        line_dict: Dict[str, List[Tuple[int, int]]],
        group_orders: str,
        color_names: List[str],
        formatter: PictureHangerFormatter,
        output_path: str,
        num_cols: int,
        num_rows: int
    ) -> List[str]:
        """Generate individual instruction pages."""
        width, height = A4
        page_list = []
        all_instructions = self._build_instructions(
            line_dict, group_orders, color_names, formatter
        )
        
        page_counter = 0
        while all_instructions:
            page_instructions = all_instructions[:num_rows * num_cols]
            all_instructions = all_instructions[num_rows * num_cols:]
            
            page_path = f"{output_path}_page_{page_counter:03d}.pdf"
            self._draw_page(
                page_path, page_instructions, num_cols, num_rows,
                width, height
            )
            page_list.append(page_path)
            page_counter += 1
        
        return page_list
    
    def _build_instructions(
        self,
        line_dict: Dict[str, List[Tuple[int, int]]],
        group_orders: str,
        color_names: List[str],
        formatter: PictureHangerFormatter
    ) -> List[Dict]:
        """Build complete instruction list with color groupings."""
        instructions = []
        total_lines = sum(len(lines) for lines in line_dict.values())
        lines_so_far = 0
        
        # Debug: Check structure
        print(f"\n[DEBUG _build_instructions]")
        print(f"  line_dict keys: {list(line_dict.keys())}")
        print(f"  line_dict total entries: {total_lines}")
        
        for color_name, lines in line_dict.items():
            if lines:
                first_line = lines[0]
                print(f"  {color_name}: {len(lines)} lines, first entry type={type(first_line)}, content={first_line}")
                break
        
        # Parse group orders with safety checks
        color_map = {i: color_names[i] for i in range(len(color_names))}
        color_groups = {}
        
        # Ensure group_orders is a string
        if not isinstance(group_orders, str):
            group_orders = str(group_orders) if group_orders else ""
        
        print(f"  group_orders: {repr(group_orders)}")
        
        for i, char in enumerate(group_orders):
            if char.isdigit():
                idx = int(char)
                if idx < len(color_names):  # Safety check
                    if idx not in color_groups:
                        color_groups[idx] = []
                    color_groups[idx].append(i)
        
        print(f"  color_groups: {color_groups}")
        
        # If no groups parsed, create default grouping
        if not color_groups:
            for idx, color_name in enumerate(color_names):
                color_groups[idx] = [idx]
        
        # Generate instructions per color group
        for idx, group_positions in sorted(color_groups.items()):
            if idx not in color_map:
                continue
            
            color_name = color_map[idx]
            lines_for_color = line_dict.get(color_name, [])
            
            # Ensure it's a list
            if not isinstance(lines_for_color, list):
                print(f"  ERROR: lines_for_color is {type(lines_for_color)}, expected list for color {color_name}")
                continue
            
            if not lines_for_color:
                continue
            
            # Debug: Check first line
            first_line = lines_for_color[0]
            print(f"  Processing color {color_name}: {len(lines_for_color)} lines")
            print(f"    First line type: {type(first_line)}")
            print(f"    First line content: {first_line}")
            
            # Split lines into groups
            lines_per_group = len(lines_for_color) // len(group_positions) + 1
            
            for group_idx, pos in enumerate(group_positions):
                start_idx = group_idx * lines_per_group
                end_idx = min((group_idx + 1) * lines_per_group, len(lines_for_color))
                
                group_lines = lines_for_color[start_idx:end_idx]
                if not group_lines:
                    continue
                
                # Add section header with "By Now" and "By End" format
                lines_at_start = lines_so_far
                lines_at_end = lines_so_far + len(group_lines)
                
                # "By Now X/total"
                instructions.append({
                    "type": "info",
                    "text": f"By Now {lines_at_start}/{total_lines}"
                })
                
                # "By End Y/total"
                instructions.append({
                    "type": "info",
                    "text": f"By End {lines_at_end}/{total_lines}"
                })
                
                # "Now = color X/Y"
                instructions.append({
                    "type": "color_header",
                    "text": f"{color_name} {group_idx + 1}/{len(group_positions)}"
                })
                
                # Add line instructions
                for line_entry in group_lines:
                    try:
                        # Handle both tuple and dict formats
                        if isinstance(line_entry, tuple) and len(line_entry) >= 2:
                            from_pin, to_pin = line_entry[0], line_entry[1]
                        elif isinstance(line_entry, dict):
                            from_pin = line_entry.get("from_pin", 0)
                            to_pin = line_entry.get("to_pin", 0)
                        else:
                            print(f"  ERROR: Unexpected line_entry format: {type(line_entry)} = {line_entry}")
                            continue
                        
                        # Get hanger info for both pins
                        from_hanger_num, from_pos, _ = formatter.format_node(int(from_pin))
                        to_hanger_num, to_pos, _ = formatter.format_node(int(to_pin))
                        
                        instructions.append({
                            "type": "instruction",
                            "from_hanger": from_hanger_num,
                            "to_hanger": to_hanger_num,
                            "from_pos": from_pos,
                            "to_pos": to_pos
                        })
                        lines_so_far += 1
                    except Exception as e:
                        print(f"  ERROR processing line entry {line_entry}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                instructions.append({
                    "type": "footer",
                    "text": f"Completed: {color_name} group {group_idx + 1}/{len(group_positions)}"
                })
                instructions.append({"type": "spacer", "height": 12})
        
        return instructions
    
    def _draw_page(
        self,
        output_path: str,
        instructions: List[Dict],
        num_cols: int,
        num_rows: int,
        width: float,
        height: float
    ) -> None:
        """Draw a single instruction page with 3 main columns."""
        c = canvas.Canvas(output_path, pagesize=(width, height))
        
        # Layout: 3 main columns, max 20 rows per column
        margin = 0.5 * cm
        usable_width = width - 2 * margin
        usable_height = height - 2 * margin
        
        main_col_width = usable_width / 3
        max_rows_per_col = 20
        
        # Draw vertical separators between main columns
        c.setStrokeColor(black)
        c.setLineWidth(2)
        for i in range(1, 3):
            x = margin + i * main_col_width
            c.line(x, margin, x, height - margin)
        
        # Process instructions and group into columns
        current_main_col = 0
        y_start = height - margin - 1 * cm
        row_height = (usable_height - 2 * cm) / max_rows_per_col
        current_row = 0
        
        # Sub-column widths within each main column
        # [Start] [End] [Pos] layout
        start_col_width = main_col_width * 0.35
        end_col_width = main_col_width * 0.35
        pos_col_width = main_col_width * 0.3
        
        # Track if we're in a header section
        in_header = False
        header_lines = []
        
        for instruction in instructions:
            try:
                if not isinstance(instruction, dict):
                    continue
                
                instr_type = instruction.get("type", "unknown")
                
                # Calculate base x position for current main column
                base_x = margin + current_main_col * main_col_width + 0.2 * cm
                y = y_start - current_row * row_height
                
                # Check if we need to move to next column
                if current_row >= max_rows_per_col:
                    current_main_col += 1
                    current_row = 0
                    in_header = False
                    
                    if current_main_col >= 3:
                        # Page is full
                        break
                    
                    base_x = margin + current_main_col * main_col_width + 0.2 * cm
                    y = y_start
                
                if instr_type == "header":
                    # Start of new color section - draw separator
                    in_header = True
                    header_lines = []
                    c.setStrokeColor(gray)
                    c.setLineWidth(0.5)
                    c.line(base_x - 0.1 * cm, y, base_x + main_col_width - 0.4 * cm, y)
                    current_row += 1
                    continue
                
                elif instr_type == "info":
                    # "By Now" or "By End" lines
                    c.setFont(self.font_name, 8)
                    c.setFillColor(black)
                    text = instruction.get("text", "")
                    c.drawString(base_x, y, text)
                    current_row += 1
                    in_header = True
                
                elif instr_type == "color_header":
                    # "Now = white 1/3" format
                    c.setFont(self.font_name, 9)
                    c.setFillColor(black)
                    text = instruction.get("text", "")
                    c.drawString(base_x, y, f"NOW = {text}")
                    current_row += 1
                    
                    # Draw separator after header
                    y_sep = y - 0.3 * cm
                    c.setStrokeColor(gray)
                    c.setLineWidth(0.5)
                    c.line(base_x - 0.1 * cm, y_sep, base_x + main_col_width - 0.4 * cm, y_sep)
                    current_row += 1
                    in_header = False
                
                elif instr_type == "instruction":
                    # Main instruction line: [Start] [End] [Pos]
                    from_hanger = instruction.get('from_hanger', '0')
                    to_hanger = instruction.get('to_hanger', '0')
                    from_pos = instruction.get('from_pos', 'L')
                    to_pos = instruction.get('to_pos', 'R')
                    
                    # Calculate x positions for 3 sub-columns
                    start_x = base_x
                    end_x = base_x + start_col_width
                    pos_x = base_x + start_col_width + end_col_width
                    
                    # Draw Start hanger (black, size 32)
                    c.setFont(self.font_name, 32)
                    c.setFillColor(black)
                    c.drawString(start_x, y, str(from_hanger))
                    
                    # Draw End hanger (black, size 32)
                    c.drawString(end_x, y, str(to_hanger))
                    
                    # Draw Position (blue, size 32)
                    # Show only from_pos (0 or 1)
                    pos_digit = '0' if from_pos == 'L' else '1'
                    c.setFillColor(blue)
                    c.drawString(pos_x, y, pos_digit)
                    c.setFillColor(black)
                    
                    current_row += 1
                
                elif instr_type == "footer":
                    # End of color group - no visual marker needed
                    pass
                
                elif instr_type == "spacer":
                    # Small gap
                    current_row += 0.5
                
            except Exception as e:
                print(f"Error drawing instruction {instruction}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        c.save()
    
    def _merge_pages_to_pdf(
        self,
        page_list: List[str],
        output_path: str,
        version: str
    ) -> str:
        """Merge all pages into a single PDF."""
        if not page_list:
            raise ValueError("No pages to merge")
        
        merger = PdfMerger()
        
        for page_path in page_list:
            try:
                with open(page_path, "rb") as f:
                    merger.append(PdfReader(f))
                os.remove(page_path)
            except Exception as e:
                print(f"Error processing {page_path}: {e}")
        
        # Determine output filename
        if version is None:
            pdf_filename = f"{output_path}.pdf"
        elif isinstance(version, int):
            pdf_filename = f"{output_path}_{version:02d}.pdf"
        elif version == "n+1":
            version_num = 1
            while os.path.exists(f"{output_path}_{version_num:02d}.pdf"):
                version_num += 1
            pdf_filename = f"{output_path}_{version_num:02d}.pdf"
        else:
            raise ValueError("version must be None, int, or 'n+1'")
        
        merger.write(pdf_filename)
        merger.close()
        
        print(f"Generated PDF: {pdf_filename}")
        return pdf_filename
    
    def _generate_statistics(
        self,
        line_dict: Dict[str, List[Tuple[int, int]]],
        formatter: PictureHangerFormatter,
        output_path: str
    ) -> None:
        """Generate statistics about the thread art."""
        print("\n" + "="*60)
        print("THREAD ART STATISTICS")
        print("="*60)
        
        total_lines = sum(len(lines) for lines in line_dict.values())
        print(f"Total lines: {total_lines}")
        
        # Lines per color
        print("\nLines per color:")
        for color_name, lines in sorted(line_dict.items(), key=lambda x: -len(x[1])):
            count = len(lines)
            percentage = (count / total_lines * 100) if total_lines > 0 else 0
            print(f"  {color_name:20s}: {count:5d} lines ({percentage:5.1f}%)")
        
        # Hanger usage
        print(f"\nTotal hangers needed: {formatter.n_hangers}")
        
        hanger_usage = Counter()
        for lines in line_dict.values():
            for from_pin, to_pin in lines:
                hanger_usage[from_pin // 2] += 1
                hanger_usage[to_pin // 2] += 1
        
        if hanger_usage:
            avg_usage = np.mean(list(hanger_usage.values()))
            print(f"Average lines per hanger: {avg_usage:.1f}")
            print(f"Most used hanger: Hanger {max(hanger_usage, key=hanger_usage.get)} ({hanger_usage[max(hanger_usage, key=hanger_usage.get)]} connections)")
            print(f"Least used hanger: Hanger {min(hanger_usage, key=hanger_usage.get)} ({hanger_usage[min(hanger_usage, key=hanger_usage.get)]} connections)")


def export_to_pdf(
    line_sequence: List[Dict],
    color_names: List[str],
    group_orders: str,
    output_path: str,
    n_nodes: int,
    **kwargs
) -> Optional[str]:
    """
    Convenience function to export thread art to PDF.
    
    Args:
        line_sequence: List of line dicts from streamlit session
        color_names: List of color names
        group_orders: String of group order
        output_path: Output file path (without extension)
        n_nodes: Total nodes
        **kwargs: Additional arguments for ThreadArtPDFGenerator.generate_pdf()
    
    Returns:
        Path to generated PDF or None if failed
    """
    if not REPORTLAB_AVAILABLE:
        print("Error: reportlab and PyPDF2 are required for PDF export")
        print("Install with: pip install reportlab PyPDF2")
        return None
    
    # Debug validation
    print(f"PDF Export Debug Info:")
    print(f"  line_sequence type: {type(line_sequence)}, length: {len(line_sequence) if isinstance(line_sequence, (list, tuple)) else 'N/A'}")
    if line_sequence and len(line_sequence) > 0:
        first_entry = line_sequence[0]
        print(f"  First entry type: {type(first_entry)}")
        if isinstance(first_entry, dict):
            print(f"  First entry keys: {first_entry.keys()}")
        else:
            print(f"  First entry content: {first_entry}")
    print(f"  color_names: {color_names}")
    print(f"  group_orders: {repr(group_orders)}")
    print(f"  n_nodes: {n_nodes}")
    
    try:
        generator = ThreadArtPDFGenerator()
        return generator.generate_pdf(
            line_sequence=line_sequence,
            color_names=color_names,
            group_orders=group_orders,
            output_path=output_path,
            n_nodes=n_nodes,
            **kwargs
        )
    except Exception as e:
        print(f"\n❌ Error generating PDF: {e}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return None
