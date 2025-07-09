# Invoice extractor
Scripts extracting data from the Czech invoices in JSON and checking validity of VAT tax payer. First script uses Anthropic Claude 3.5 Haiku and you need **API key** for its running. The second script uses Llama 4 Maverick provided by Groq. For cheaper processing, script turns multipage invoices in PDF to individual images and only use the first invoice page. According to our intense testing of many types of invoices we achieve accuracy of extraction 92-93% for Haiku 3.5 model. If you would like to get better results with accuracy around 95% you would need to employ the more powerful model Claude Sonnet 4. To do so, you have to change one line of code with the end point of the Sonnet model. Using Llama 4 Maverick is with similar accuracy level like Sonnet 4.  

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
- **groq**: Official Python client for the Groq API 
- **PyMuPDF**: Library for working with PDF files (also known as `fitz`)
- **Pillow**: Python Imaging Library for handling various image formats

---

## Llama 4 using Groq as inference provider

### Create virtual environment for "my_project"
```bash
python3 -m venv my_project_venv
```
### Activate venv
```bash
source my_project_venv/bin/activate  # Linux/Mac
# or
my_project_venv\Scripts\activate     # Windows
```
### Install environment variables with Groq API Key 
```bash
echo "GROQ_API_KEY=your_groq_key_here" > .env
```
### Instal libraries and dependencies
```bash
pip install groq PyMuPDF Pillow requests
```

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
