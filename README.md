# Invoice extractor
Script extracting data from the Czech invoices in JSON and checking validity of VAT tax payer. Script uses Anthropic Claude 3.5 Haiku and you need **API key** for its running. For cheaper processing, use for multipage invoices PDF Splitter and only the first invoice page. 

## Installation Instructions

## Using Traditional Venv + Pip

**On macOS/Linux:**
```bash
# Create virtual environment
python3 -m venv invoice_env

# Activate virtual environment
source invoice_env/bin/activate
```

###  Install Dependencies
```bash
# Upgrade pip (optional but recommended)
pip install --upgrade pip

# Install required packages
pip install anthropic PyMuPDF Pillow
```

### Place Your Files and Run
```bash
# Copy the invoice_extractor.py script to the project directory
# Copy your invoice files (PDF/images) to the same directory
# Edit the script to add your API key

# Run the script
python3 invoice_extractor.py
```

### Deactivate Environment (When Done)
```bash
deactivate
```

## Quick Setup Script

### For Venv Users (macOS/Linux):
```bash
mkdir invoice-extractor && cd invoice-extractor
python3 -m venv invoice_env
source invoice_env/bin/activate
pip install anthropic PyMuPDF Pillow
# Copy your script and invoice files here
# Edit API key in the script
python invoice_extractor.py
```

---

## Package Descriptions

- **anthropic**: Official Python client for the Anthropic API
- **PyMuPDF**: Library for working with PDF files (also known as `fitz`)
- **Pillow**: Python Imaging Library for handling various image formats

---

## Troubleshooting

### Common Issues:

1. **Python not found**: Make sure Python 3.8+ is installed
2. **Permission errors on Windows**: Run PowerShell as Administrator for UV installation
3. **Virtual environment activation issues**: Check your shell (bash, zsh, PowerShell)
4. **Package installation fails**: Try upgrading pip first: `pip install --upgrade pip`

### Verifying Installation:
```bash
# Check Python version
python --version  # Should be 3.8 or higher

# Check if packages are installed (after activation)
python -c "import anthropic, fitz, PIL; print('All packages installed successfully!')"
```
