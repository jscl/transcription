# Transcription Tool

An AI-based transcription tool designed for documents, PDFs, and historical analysis (newspapers, books, handwritten documents etc.).
_Currently only supports Gemini-3-pro-preview model._

## Features

- **AI Transcription**: Uses Google Gemini Pro Vision to transcribe text from images and documents.
- **Local Input**: Support for local files (`--input-file`). Files from web resources (http, https) are downloaded and processed.
- **PDF Handling**:
    - **Page Selection**: Transcribe specific pages (`--pages "1-3,5"`).
    - **OCR Removal**: Automatically removes embedded text layers via redaction to force visual re-analysis (can be disabled with `--keep-ocr`).
    - **Parallel Processing**: Processes multiple pages concurrently for faster execution (`--parallel-pages`).
- **Flexible Output**:
    - **Output Organization**: Automatically organizes outputs into subfolders matching the input filename (`--create-subfolder`).
    - **Page-level Results**: Option to save individual transcribed pages (`--save-single-pages`).
    - **Meta Information**: Saves run configuration and token usage details alongside the transcription.
- **Overwrite Protection**: Prevents accidental data loss by skipping processing if the output file already exists (disable with `--overwrite`).

## Requirements

- Python 3.13+ (Tested, could also work with lower versions)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Dependencies
- `google-genai`
- `pymupdf`
- `rich`
- `requests`

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

**Parallel Processing:**
Process 20 pages at a time:
```bash
uv run python main.py --input-file "book.pdf" --parallel-pages 20
```

### Output Control

**Save Individual Pages:**
Save a separate `.md` file for each processed page in addition to the combined transcript:
```bash
uv run python main.py --input-file "book.pdf" --save-single-pages
```

**Disable Subfolder Creation:**
By default, outputs are saved in `output/<filename>/`. To save directly in `output/`:
```bash
uv run python main.py --input-file "book.pdf" --no-create-subfolder
```

### Overwrite Protection

By default, if the output file exists, the tool **skips processing**. To force overwrite:
```bash
uv run python main.py --input-file "doc.pdf" --overwrite
```

## Command Line Arguments

| Argument | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `--input-file` | `-if` | Local path to image/PDF. | Required |
| `--pages` | | Page ranges for PDF (e.g., `'1-3, 5'`). | All pages |
| `--keep-ocr` | | Keep embedded OCR layer in PDF. Default is to remove it. | `False` |
| `--parallel-pages` | `-pa` | Max number of parallel pages to process. | `10` |
| `--prompt-file` | `-pf` | Path to a file containing the custom system prompt. | |
| `--prompt` | `-p` | Direct string prompt. Overrides `--prompt-file`. | |
| `--output-directory` | `-o` | Directory for output files. | `./output` |
| `--create-subfolder` | `-cs` | Create a subfolder for outputs (file based). disable with `--no-create-subfolder`. | `True` |
| `--save-single-pages` | `-sp` | Save single copies of every transcribed page. | `False` |
| `--delete-temporary-files` | | Delete temporary split files after processing. disable with `--no-delete-temporary-files`. | `True` |
| `--overwrite` | | Overwrite output files if they exist. Default is to skip processing. | `False` |
| `--gemini-api-key` | `-gk` | API key. Overrides `GEMINI_API_KEY` env var. | |

## Output Structure

By default (with `--create-subfolder`), processing `data/document.pdf` will yield:

```
output/
└── document/
    ├── document.pdf.md          # Combined transcription
    ├── document.pdf.meta.txt    # Metadata (model, tokens, prompt)
    ├── document_page_1.pdf.md   # (If --save-single-pages is on)
    └── ...
```
## Limitations
- Currently only supports Gemini-3-pro-preview model.
- No separation between system and user prompt.

## License

[License Name]
