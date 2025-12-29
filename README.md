# Transcription Tool

A powerful AI-based transcription tool using Google Gemini, designed for documents, PDFs, and historical analysis.

## Features

- **AI Transcription**: Uses Google Gemini Pro Vision to transcribe text from images and documents.
- **Local Input**: Support for local files (`--input-file`).
- **PDF Handling**:
    - **Page Selection**: Transcribe specific pages (`--pages "1-3,5"`).
    - **OCR Removal**: Automatically removes embedded text layers via redaction to force visual re-analysis (can be disabled with `--keep-ocr`).
- **Overwrite Protection**: Prevents accidental data loss by skipping processing if the output file already exists (disable with `--overwrite`).

## Requirements

- Python 3.13+ (Tested, could also work with lower versions)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Dependencies
- `google-genai`
- `pymupdf` (fitz)
- `rich`

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd transcription
    ```

2.  **Install dependencies** (using uv):
    ```bash
    uv sync
    ```
    Or using pip:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

You must provide your Google Gemini API key via the command line or an environment variable.

```bash
export GEMINI_API_KEY="your_api_key_here"
```

### Basic Transcription

**From a Local File:**
```bash
uv run python main.py --input-file "documents/scan.jpg"
```

### PDF Options

**Select Specific Pages:**
```bash
uv run python main.py --input-file "book.pdf" --pages "1-3, 10"
```

**Keep Original OCR Layer:**
By default, the tool removes existing text layers to force the AI to read the visual data. To prevent this:
```bash
uv run python main.py --input-file "book.pdf" --keep-ocr
```

### Overwrite Protection

By default, if the output file exists, the tool **skips processing**. To force overwrite:
```bash
uv run python main.py --input-file "doc.pdf" --overwrite
```

## Command Line Arguments

| Argument | Short | Description |
| :--- | :--- | :--- |
| `--input-file` | `-if` | Local path to image/PDF. |
| `--pages` | | Page ranges for PDF (e.g., `'1-3, 5'`). Only used with `--input-file`. |
| `--keep-ocr` | | Keep embedded OCR layer in PDF. Default is to remove it using redaction. |
| `--prompt-file` | `-pf` | Path to a file containing the custom system prompt. |
| `--prompt` | `-p` | Direct string prompt. Overrides `--prompt-file`. |
| `--output-directory` | `-o` | Directory for output files. Defaults to `./output`. |
| `--overwrite` | | Overwrite output files if they exist. Default is to skip processing. |
| `--gemini-api-key` | `-gk` | API key. Overrides `GEMINI_API_KEY` env var. |

## License

[License Name]
