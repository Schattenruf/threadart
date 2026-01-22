#!/usr/bin/env python3
"""
PDF Export - Installation & Verification Script

This script helps you install and verify the PDF export feature.
Run it to check if everything is set up correctly.

Usage:
    python verify_pdf_export.py
"""

import sys
import subprocess
from pathlib import Path


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(number, text):
    print(f"[{number}] {text}")


def check_file(filepath, description=""):
    """Check if a file exists"""
    if Path(filepath).exists():
        print(f"  ✅ {filepath} exists" + (f" ({description})" if description else ""))
        return True
    else:
        print(f"  ❌ {filepath} NOT FOUND" + (f" ({description})" if description else ""))
        return False


def check_import(module_name):
    """Check if a module can be imported"""
    try:
        __import__(module_name)
        print(f"  ✅ {module_name} is installed")
        return True
    except ImportError:
        print(f"  ❌ {module_name} is NOT installed")
        return False


def run_command(cmd, description=""):
    """Run a command and return success"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print(f"  ✅ {description}")
            return True
        else:
            print(f"  ❌ {description}")
            if result.stderr:
                print(f"     Error: {result.stderr[:100]}")
            return False
    except Exception as e:
        print(f"  ❌ {description}")
        print(f"     Error: {str(e)[:100]}")
        return False


def main():
    print_header("PDF Export Feature - Installation Verification")
    
    all_good = True
    
    # Step 1: Check files
    print_step(1, "Checking if new files exist...")
    files_to_check = [
        ("pdf_export.py", "Main PDF module"),
        ("PDF_EXPORT_README.md", "Documentation"),
        ("PDF_EXPORT_QUICKSTART.md", "Quick start guide"),
        ("PDF_EXPORT_EXAMPLES.py", "Code examples"),
        ("README_PDF_EXPORT.md", "Feature overview"),
    ]
    
    for filepath, desc in files_to_check:
        if not check_file(filepath, desc):
            all_good = False
    
    # Step 2: Check Python modules
    print_step(2, "Checking Python dependencies...")
    modules_to_check = [
        "reportlab",
        "PyPDF2",
    ]
    
    for module in modules_to_check:
        if not check_import(module):
            all_good = False
    
    # Step 3: Check Streamlit
    print_step(3, "Checking Streamlit...")
    if not check_import("streamlit"):
        print("  ⚠️  Streamlit not found - needed to run the app")
        all_good = False
    
    # Step 4: Check other dependencies
    print_step(4, "Checking other dependencies...")
    required_modules = [
        "numpy",
        "PIL",
        "sklearn",
        "plotly",
        "pandas",
    ]
    
    missing = []
    for module in required_modules:
        if not check_import(module):
            missing.append(module)
    
    if missing:
        print(f"  ⚠️  Missing: {', '.join(missing)}")
        print(f"     These are needed for the full app to work")
    
    # Step 5: Validate pdf_export.py
    print_step(5, "Validating pdf_export.py...")
    try:
        import pdf_export
        print("  ✅ pdf_export module imports successfully")
        
        # Check for key classes
        if hasattr(pdf_export, 'PictureHangerFormatter'):
            print("  ✅ PictureHangerFormatter class found")
        else:
            print("  ❌ PictureHangerFormatter class not found")
            all_good = False
        
        if hasattr(pdf_export, 'ThreadArtPDFGenerator'):
            print("  ✅ ThreadArtPDFGenerator class found")
        else:
            print("  ❌ ThreadArtPDFGenerator class not found")
            all_good = False
        
        if hasattr(pdf_export, 'export_to_pdf'):
            print("  ✅ export_to_pdf function found")
        else:
            print("  ❌ export_to_pdf function not found")
            all_good = False
            
    except ImportError as e:
        print(f"  ❌ Cannot import pdf_export: {str(e)}")
        all_good = False
    
    # Step 6: Test PictureHangerFormatter
    print_step(6, "Testing PictureHangerFormatter...")
    try:
        from pdf_export import PictureHangerFormatter
        
        formatter = PictureHangerFormatter(320)
        
        # Test node conversions
        test_cases = [
            (0, "0", "L", "Hanger   0 L"),
            (1, "0", "R", "Hanger   0 R"),
            (42, "21", "L", "Hanger  21 L"),
            (319, "159", "L", "Hanger 159 L"),
        ]
        
        all_test_pass = True
        for node_idx, exp_hanger, exp_pos, exp_label in test_cases:
            hanger_num, position, label = formatter.format_node(node_idx)
            if hanger_num == exp_hanger and position == exp_pos:
                print(f"  ✅ Node {node_idx:3d} → {label}")
            else:
                print(f"  ❌ Node {node_idx:3d} → {label} (expected {exp_label})")
                all_test_pass = False
        
        if not all_test_pass:
            all_good = False
            
    except Exception as e:
        print(f"  ❌ Error testing formatter: {str(e)}")
        all_good = False
    
    # Step 7: Check streamlit_app.py modifications
    print_step(7, "Checking streamlit_app.py modifications...")
    try:
        with open("streamlit_app.py", "r") as f:
            content = f.read()
            
        checks = [
            ('st.session_state["n_nodes_real"]', "n_nodes_real storage"),
            ('st.session_state["group_orders"]', "group_orders storage"),
            ('Generate PDF Instructions', "PDF button label"),
            ('from pdf_export import export_to_pdf', "PDF import"),
        ]
        
        for check_str, desc in checks:
            if check_str in content:
                print(f"  ✅ {desc} found")
            else:
                print(f"  ❌ {desc} NOT found")
                all_good = False
                
    except Exception as e:
        print(f"  ❌ Error checking streamlit_app.py: {str(e)}")
        all_good = False
    
    # Step 8: Summary
    print_header("Summary")
    
    if all_good:
        print("✅ All checks passed! The PDF export feature is ready to use.\n")
        print("Next steps:")
        print("  1. Run: streamlit run streamlit_app.py")
        print("  2. Upload an image")
        print("  3. Generate thread art")
        print("  4. Click the 🖨️ PDF button")
        print("  5. Download and enjoy!\n")
        return 0
    else:
        print("⚠️  Some checks failed. Please fix the issues above.\n")
        print("Common issues:")
        print("  • reportlab/PyPDF2 not installed:")
        print("    pip install reportlab PyPDF2\n")
        print("  • pdf_export.py not found:")
        print("    Make sure you're in the threadart directory\n")
        print("  • Other dependencies missing:")
        print("    pip install -r requirements.txt\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
