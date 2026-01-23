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
    
    def __init__(self, n_nodes: int, hanger_spacing: float = 1.0, use_hangers: bool = True):
        """
        Initialize formatter for picture hangers or nails.
        
        Args:
            n_nodes: Total number of nodes/hooks
            hanger_spacing: Spacing between hangers (for display purposes)
            use_hangers: True for hangers (2 nodes per hanger), False for nails (1 node = 1 nail)
        """
        self.n_nodes = n_nodes
        self.hanger_spacing = hanger_spacing
        self.use_hangers = use_hangers
        self.n_hangers = (n_nodes + 1) // 2  # Each hanger has 2 attachment points
    
    def format_node(self, node_idx: int) -> Tuple[str, str, str]:
        """Format a node index for hanger or nail mode.

        Returns:
            - Hanger mode: (hanger_number, "L"/"R", "Hanger 42 L")
            - Nail mode: (node_number, "", "Nail 84")
        """
        if self.use_hangers:
            hanger_num = node_idx // 2
            position_idx = node_idx % 2
            position = "L" if position_idx == 0 else "R"
            label = f"Hanger {hanger_num:3d} {position}"
            return str(hanger_num), position, label
        else:
            # Nail mode: 1 nail = 1 node
            label = f"Nail {node_idx:3d}"
            return str(node_idx), "", label
    
    def get_hanger_display(self, node_idx: int) -> str:
        """Get a nicely formatted display string for instructions."""
        hanger_num, position, label = self.format_node(node_idx)
        return label


class ThreadArtPDFGenerator:
    """Generates professional PDF instructions for thread art."""
    
    # Mapping of common color names to hex values
    COLOR_MAP = {
        'schwarz': '#000000',
        'black': '#000000',
        'weiß': '#FFFFFF',
        'white': '#FFFFFF',
        'rot': '#FF0000',
        'red': '#FF0000',
        'grün': '#00AA00',
        'green': '#00AA00',
        'blau': '#0000FF',
        'blue': '#0000FF',
        'gelb': '#FFFF00',
        'yellow': '#FFFF00',
        'orange': '#FFA500',
        'lila': '#800080',
        'purple': '#800080',
        'rosa': '#FFC0CB',
        'pink': '#FFC0CB',
        'braun': '#8B4513',
        'brown': '#8B4513',
        'grau': '#808080',
        'gray': '#808080',
        'türkis': '#40E0D0',
        'cyan': '#00FFFF',
        'magenta': '#FF00FF',
    }
    
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
    
    def _get_color_hex(self, color_name: str) -> str:
        """Get hex color for color name. Returns black if not found."""
        color_lower = color_name.lower()
        return self.COLOR_MAP.get(color_lower, '#000000')
    
    def generate_pdf(
        self,
        line_sequence: List[Dict],
        color_names: List[str],
        group_orders: str,
        output_path: str,
        n_nodes: int,
        color_info_list: List[Dict] = None,
        num_cols: int = 3,
        num_rows: int = 18,
        include_stats: bool = True,
        version: str = "n+1",
        use_hangers: bool = True
    ) -> str:
        """
        Generate a complete PDF with instructions.
        
        Args:
            line_sequence: List of line dicts with step, color_index, from_pin, to_pin, etc.
            color_names: List of color names
            color_info_list: List of color info dicts (optional, from streamlit)
            group_orders: String indicating the order of colors (e.g., "2,3,4,1,3,2,1")
            output_path: Base output path (without extension)
            n_nodes: Total number of nodes/attachment points
            num_cols: Number of columns per page
            num_rows: Number of rows per page
            include_stats: Whether to include statistics
            version: Version numbering ("n+1" for auto-increment, None for single, or int)
        
        Returns:
            Path to generated PDF
        """
        formatter = PictureHangerFormatter(n_nodes, use_hangers=use_hangers)
        
        # Build line_dict (lines grouped by color name)
        line_dict = self._group_lines_by_color(line_sequence, color_names)
        
        # Generate individual pages following group_orders EXACTLY
        page_list = self._generate_instruction_pages_by_group_orders(
            line_dict=line_dict,
            color_names=color_names,
            color_info_list=color_info_list,
            group_orders=group_orders,
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
    
    
    def _generate_instruction_pages_by_group_orders(
        self,
        line_dict: Dict[str, List[Tuple[int, int]]],
        color_names: List[str],
        color_info_list: List[Dict],
        group_orders: str,
        formatter: PictureHangerFormatter,
        output_path: str,
        num_cols: int,
        num_rows: int
    ) -> List[str]:
        """Generate instruction pages following group_orders EXACTLY (like the template)."""
        width, height = A4
        page_list = []
        
        total_lines = sum(len(lines) for lines in line_dict.values())
        
        print(f"\n[DEBUG _generate_instruction_pages_by_group_orders]")
        print(f"  Total lines: {total_lines}")
        print(f"  group_orders: {repr(group_orders)}")
        print(f"  color_names: {color_names}")
        
        # Parse group_orders: "2,3,4,1,3,2,1" → ["2", "3", "4", "1", "3", "2", "1"]
        if ',' in group_orders:
            go_list = group_orders.split(',')
        else:
            # Single digit repeated: "5" → "1,2,3,4,5,1,2,3,4,5,..." (5 loops)
            go_list = list(group_orders) * int(group_orders) if group_orders.isdigit() else list(group_orders)
        
        print(f"  go_list: {go_list}")
        
        # Build group_len_list: consecutive blocks of same color
        # e.g., "2,3,4,1,3,2,1" → [["2", 1], ["3", 1], ["4", 1], ["1", 1], ["3", 1], ["2", 1], ["1", 1]]
        group_len_list = []
        for go_char in go_list:
            if group_len_list and group_len_list[-1][0] == go_char:
                group_len_list[-1][1] += 1
            else:
                group_len_list.append([go_char, 1])
        
        print(f"  group_len_list: {group_len_list}")
        
        # Build instructions following group_len_list
        all_instructions = []
        total_lines_so_far = 0
        color_occurrence_count = {color: 0 for color in set(go_list)}
        
        for group_idx, (color_idx_str, group_len) in enumerate(group_len_list):
            # Convert color index to 0-based
            try:
                color_idx = int(color_idx_str) - 1  # group_orders uses 1-based indices
            except (ValueError, TypeError):
                print(f"  ERROR: Invalid color_idx {color_idx_str}")
                continue
            
            if color_idx < 0 or color_idx >= len(color_names):
                print(f"  ERROR: color_idx {color_idx} out of range for {len(color_names)} colors")
                continue
            
            color_name = color_names[color_idx]
            lines_for_color = line_dict.get(color_name, [])
            
            if not lines_for_color:
                print(f"  WARNING: No lines for color {color_name} (idx {color_idx})")
                continue
            
            # Count how many times this color appears total in group_len_list
            total_groups_this_color = sum(1 for c_idx, _ in group_len_list if c_idx == color_idx_str)
            
            # Track which occurrence of this color we're on
            color_occurrence_count[color_idx_str] += 1
            this_occurrence = color_occurrence_count[color_idx_str]
            
            # Calculate line range for this group (divide lines equally among groups of this color)
            start_line_idx = ((this_occurrence - 1) * len(lines_for_color)) // total_groups_this_color
            end_line_idx = (this_occurrence * len(lines_for_color)) // total_groups_this_color
            group_lines = lines_for_color[start_line_idx:end_line_idx]
            
            if not group_lines:
                print(f"  WARNING: Empty group for {color_name}")
                continue
            
            # Get color hex
            color_hex = "#000000"
            if color_info_list and color_idx < len(color_info_list):
                color_info = color_info_list[color_idx]
                color_hex = color_info.get('hex', '#000000')
            
            print(f"  Group {group_idx}: {color_name} ({total_groups_this_color} total, this is #{this_occurrence}), {len(group_lines)} lines, hex={color_hex}")
            
            # Create instructions for this group
            lines_at_start = total_lines_so_far
            lines_at_end = total_lines_so_far + len(group_lines)
            
            all_instructions.append({
                "type": "info",
                "text": f"By Now {lines_at_start}/{total_lines}"
            })
            all_instructions.append({
                "type": "info",
                "text": f"By End {lines_at_end}/{total_lines}"
            })
            all_instructions.append({
                "type": "color_header",
                "text": f"{color_name} {this_occurrence}/{total_groups_this_color} ({color_hex})",
                "color_name": color_name,
                "color_hex": color_hex
            })
            
            # Add line instructions
            for from_pin, to_pin in group_lines:
                from_hanger_num, from_pos, _ = formatter.format_node(int(from_pin))
                to_hanger_num, to_pos, _ = formatter.format_node(int(to_pin))
                
                all_instructions.append({
                    "type": "instruction",
                    "from_hanger": from_hanger_num,
                    "to_hanger": to_hanger_num,
                    "from_pos": from_pos,
                    "to_pos": to_pos
                })
            
            all_instructions.append({
                "type": "footer",
                "text": f"Completed: {color_name} {this_occurrence}/{total_groups_this_color}"
            })
            all_instructions.append({"type": "spacer", "height": 12})
            
            total_lines_so_far = lines_at_end
        
        # Now convert all_instructions into pages
        page_counter = 0
        current_page_instructions = []
        
        for instruction in all_instructions:
            # Add instruction
            current_page_instructions.append(instruction)
            
            # Check if page is full
            instruction_count = sum(1 for i in current_page_instructions if i.get("type") in ("instruction", "info", "color_header"))
            
            if instruction_count >= (num_cols * num_rows):
                # Save page
                page_path = f"{output_path}_page_{page_counter:03d}.pdf"
                self._draw_page(page_path, current_page_instructions, num_cols, num_rows, width, height)
                page_list.append(page_path)
                page_counter += 1
                current_page_instructions = []
        
        # Save last page
        if current_page_instructions:
            page_path = f"{output_path}_page_{page_counter:03d}.pdf"
            self._draw_page(page_path, current_page_instructions, num_cols, num_rows, width, height)
            page_list.append(page_path)
        
        return page_list


    # Old methods no longer needed - everything is handled by _generate_instruction_pages_by_group_orders
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
        
        # Ensure group_orders is a string
        if not isinstance(group_orders, str):
            group_orders = str(group_orders) if group_orders else ""
        
        print(f"  group_orders: {repr(group_orders)}")
        
        # Build sequence of groups in exact order from group_orders
        # Each character is a separate group, groups with same color are separate
        group_sequence = []  # List of (color_idx, position_in_string)
        
        for i, char in enumerate(group_orders):
            if char.isdigit():
                idx = int(char)
                if idx < len(color_names):
                    group_sequence.append((idx, i))
        
        print(f"  group_sequence: {group_sequence}")
        
        # Count lines per color to split them
        color_line_counts = {}
        for idx, pos in group_sequence:
            if idx not in color_line_counts:
                color_line_counts[idx] = 0
            color_line_counts[idx] += 1
        
        print(f"  color_line_counts: {color_line_counts}")
        
        # Track current position in each color's lines
        color_line_progress = {idx: 0 for idx in color_line_counts.keys()}
        
        # Generate instructions per group in exact order
        for color_idx, pos in group_sequence:
            if color_idx not in color_map:
                continue
            
            color_name = color_map[color_idx]
            lines_for_color = line_dict.get(color_name, [])
            
            # Ensure it's a list
            if not isinstance(lines_for_color, list):
                print(f"  ERROR: lines_for_color is {type(lines_for_color)}, expected list for color {color_name}")
                continue
            
            if not lines_for_color:
                continue
            
            # Calculate how many lines this group should get
            total_groups_for_this_color = color_line_counts[color_idx]
            lines_per_group = len(lines_for_color) // total_groups_for_this_color
            remainder = len(lines_for_color) % total_groups_for_this_color
            
            # Get lines for this specific group
            start_idx = color_line_progress[color_idx]
            group_size = lines_per_group + (1 if color_line_progress[color_idx] < remainder else 0)
            end_idx = start_idx + group_size
            
            group_lines = lines_for_color[start_idx:end_idx]
            color_line_progress[color_idx] = end_idx
            
            # Track which occurrence of this color (1/2, 2/2, etc.)
            current_occurrence = sum(1 for idx, _ in group_sequence[:group_sequence.index((color_idx, pos)) + 1] if idx == color_idx)
            
            if not group_lines:
                continue
            
            # Debug
            print(f"  Processing color {color_name} occurrence {current_occurrence}/{total_groups_for_this_color}: {len(group_lines)} lines")
            
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
            
            # "Now = color X/Y" with hex + position info
            # Get color info if available
            color_hex = "#000000"
            if color_info_list and color_idx < len(color_info_list):
                color_info = color_info_list[color_idx]
                color_hex = color_info.get('hex', '#000000')
            
            instructions.append({
                "type": "color_header",
                "text": f"{color_name} {current_occurrence}/{total_groups_for_this_color} ({color_hex})",
                "color_name": color_name,
                "color_hex": color_hex
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
                "text": f"Completed: {color_name} occurrence {current_occurrence}/{total_groups_for_this_color}"
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
                    # "By Now" or "By End" lines - compact font size 13
                    c.setFont(self.font_name, 13)
                    c.setFillColor(black)
                    text = instruction.get("text", "")
                    c.drawString(base_x, y, text)
                    current_row += 0.5  # Half row for header
                
                elif instr_type == "color_header":
                    # "Now = white 1/3 (#hex)" format - size 15, with color
                    c.setFont(self.font_name, 15)
                    
                    # Get color from instruction
                    color_hex = instruction.get("color_hex", "#000000")
                    
                    try:
                        # Parse hex color if available
                        color_obj = HexColor(color_hex)
                        c.setFillColor(color_obj)
                    except:
                        # Default to black if color parsing fails
                        c.setFillColor(black)
                    
                    text = instruction.get("text", "")
                    c.drawString(base_x, y, f"NOW = {text}")
                    c.setFillColor(black)
                    current_row += 1
                    
                    # Draw separator after header
                    y_sep = y - 0.5 * cm
                    c.setStrokeColor(gray)
                    c.setLineWidth(0.5)
                    c.line(base_x - 0.1 * cm, y_sep, base_x + main_col_width - 0.4 * cm, y_sep)
                    current_row += 0.5  # Half row for separator
                
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
                    
                    # Draw Start hanger (black, size 28)
                    c.setFont(self.font_name, 28)
                    c.setFillColor(black)
                    c.drawString(start_x, y, str(from_hanger))
                    
                    # Draw End hanger (black, size 28)
                    c.drawString(end_x, y, str(to_hanger))
                    
                    # Draw Position (blue, size 28)
                    # Show L or R
                    pos_text = from_pos  # Already 'L' or 'R' from formatter
                    c.setFillColor(blue)
                    c.drawString(pos_x, y, pos_text)
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
    color_info_list: List[Dict] = None,
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
            color_info_list=color_info_list,
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
