# PDFDownloader :page_with_curl:

## Overview
The **PDFDownloader** project provides a convenient way to download PDFs from one or more Excel files containing links. It displays real-time progress via a Tkinter GUI and logs each download to an Excel “status file,” ensuring that any previously attempted downloads (successful or failed) aren’t retried. This tool is especially handy for large datasets, as it reads files in **chunks** to avoid overwhelming memory and allows multiple concurrent download threads for better performance.

---

## Table of Contents
1. [Features](#features)
2. [Requirements](#requirements)
3. [Setup & Installation](#setup--installation)
4. [Usage](#usage)
5. [Configurable Variables](#configurable-variables)
6. [File Structure](#file-structure)
7. [How It Works](#how-it-works)
    - [Chunk-Based Reading](#chunk-based-reading)
    - [Concurrency & Status Updates](#concurrency--status-updates)
    - [UI Components](#ui-components)
    - [Status File Tracking](#status-file-tracking)
8. [Contributing](#contributing)

---

## Features
- **Multi-File XLSX** Support: Pass in multiple Excel files; it will read chunks from each, combine them, shuffle, and download.
- **Concurrent Downloads**: Utilize multiple threads to speed up retrieval (configurable).
- **Fallback URL**: If the primary URL fails, the program tries a secondary link column.
- **Real-Time GUI**: Displays current download progress, status text, and success/failure counters.
- **Resumable**: A “status” Excel file ensures PDFs already attempted (successfully or otherwise) are skipped on subsequent runs.
- **Chunk-Based Reading**: Only loads a portion of the Excel file(s) at a time, making it scalable for large datasets.

---

## Requirements
- **Python 3.8+** (recommended)
- **pip** for installing packages

See [`requirements.txt`](#requirements-file) below for the exact Python dependencies.

---

## Setup & Installation

1. **Clone** this repository:
   ```bash
   git clone https://github.com/RazorSDU/PDFDownloader.git
   cd PDFDownloader
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   This installs pandas, requests, openpyxl, PyPDF2, and other needed libraries.

3. **Place or Prepare Excel Files**:

   - Put your `.xlsx` data sources in the `data/` folder.
   - Ensure the Excel columns match the expected fields (e.g., `Pdf_URL`, `BRnum`, and optionally `Report Html Address` for a fallback URL).

4. **Check/Set Output Folder**:

   - By default, PDFs will download to `data/PDFs/`. This folder is `.gitignored` to avoid committing large files.
   - You can change this location in the code if desired.

5. **Run the Program**:
   ```bash
   python main.py
   ```

   A Tkinter GUI will appear, and downloads will start in a background thread.  
   Press the window’s close button when you want to stop. The program will wait for active downloads to finish before exiting.

---

## Usage

### Automatic Download Start
Once you run `python main.py`, the code automatically begins reading your Excel file(s) and spawns download threads.

### Real-Time UI
- You’ll see a **Successes** counter and a **Failures** counter at the top.
- Each worker thread has a row below, showing a status label (`Idle`, `Attempting`, `Downloading`) and a progress bar.
- Progress bars update in near real-time.

### Stopping the Process
- Close the Tkinter window to stop.
- If any downloads are in progress, the main script will wait until they complete (or fail) before fully exiting.
- Rerun the program at any time. Already “Success” or “Failure” items won’t be attempted again.

---

## Configurable Variables

You can change these variables in the code (mostly located in `main.py` or in `downloader.py`):

- `xlsx_paths`:  
  Paths to the Excel file(s) you want to read.  
  Example:
  ```python
  ["data/GRI_2017_2020.xlsx", "data/Metadata2006_2016.xlsx"]
  ```

- `output_folder`:  
  The folder to store downloaded PDFs.  
  Default: `data/PDFs`

- `status_file`:  
  Path to the Excel file used to record each PDF’s outcome.  
  Default: `data/DownloadedStatus.xlsx`

- `dev_mode` (boolean):  
  If `True`, limits the number of successful downloads to `max_success` (useful for testing).

- `max_success` (integer):  
  Applies when `dev_mode` is `True`.  
  The downloader stops after this many successes.

- `max_concurrent_workers` (integer):  
  How many download threads you want to run in parallel.

- `chunk_size` (integer):  
  How many rows to read from each Excel at a time.  
  Larger values read more data at once but use more memory.

---

## File Structure
```
PDFDownloader/
├─ main.py                  # Entry point that starts the UI and spawns the downloader thread
├─ pdf_downloader/
│  └─ downloader.py         # Core logic for reading Excel chunks and downloading PDFs
├─ ui/
│  └─ app.py                # Tkinter GUI to display download progress
├─ utils/
│  ├─ xlsx_chunk_reader.py  # Helper for reading Excel files in chunks
│  └─ logging_setup.py      # Sets up the logger (if present)
├─ data/
│  ├─ PDFs/                 # Default folder to store downloaded PDFs (gitignored)
│  ├─ DownloadedStatus.xlsx # Status file to keep track of success/fail
│  └─ your_excel_files.xlsx # Place your actual data .xlsx files here
├─ requirements.txt         # Python dependencies
└─ README.md                # This documentation
```

---

## How It Works

### Chunk-Based Reading
The program uses `read_xlsx_in_chunks(...)` to read slices of each Excel file.  
Each chunk is combined into a single DataFrame, shuffled, and then filtered to exclude rows already listed as success/failure in the status file.

### Concurrency & Status Updates
A `ThreadPoolExecutor` with `max_concurrent_workers` threads is used to download multiple PDFs in parallel.  
Progress updates (thread status, counters, progress percentage) are sent through a `Queue` to the GUI so it can refresh labels and progress bars.

### UI Components
- **Success/Failure Counters**: Show how many downloads have succeeded or failed so far.
- **Thread Rows**: Each worker thread row displays:
  - A status label (e.g., “Idle”, “Attempting Primary”, “Downloading …”)
  - A progress bar that updates if the server provides `Content-Length`.

### Status File Tracking
A dedicated Excel file (by default `data/DownloadedStatus.xlsx`) records each row’s outcome.  
Each row includes:
- `BRnum` (the unique identifier)
- `Status` (“Success” or “Failure”)
- `Info` (details on errors if any)

The code checks this file before attempting any new downloads, saving time by skipping items that have already been processed.

---

## Contributing

Feel free to fork the repository and submit pull requests!  
If you find bugs or have feature suggestions, please open an issue.

---
