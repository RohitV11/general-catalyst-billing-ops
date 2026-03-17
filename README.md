# general-catalyst-billing-ops
CVC SP26 General Catalyst Billing Ops project

Rules:
Only work on your own branch. Only merge once complete by initiating a PR to main.
When working, create a new branch called "<Name>" (based on your name), and do the necessary work assigned.
For every PR, make the edits you are merging as details as possible in the PR message.

Data folder:
Create a save a folder in the home directory called data where you will store all the csvs/txt files from the drive.

## General data instructions
Set up a data directory:


```
general-catalyst-billing-ops/
├── data/
│   ├── PFALL24R.txt
│   ├── ccipra-v321-f1.xlsx
│   ├── ccipra-v321-f2.xlsx
│   ├── ccipra-v321-f3.xlsx
│   ├── ccipra-v321-f4.xlsx
│   ├── cpt_codes_deduped.csv
│   └── 2026_DHS_Code_List_Addendum_12_01_2025 (2).txt
```
## Instructions for pricer.py

Download the CMS Annual Physician Fee Schedule Payment Amount File (PFALL26AR.txt). Place the file in the project data directory:

## 📁 Project Structure
```
general-catalyst-billing-ops/
├── data/
│   ├── PFALL26AR.txt
│   └── ...
├── src/
│   ├── pricer.py
│   └── ...
└── ...
```

To run the script, run "python pricer.py" from the src directory.

Command line arguments can be provided to specify which file path to load data from, which HCPCS code to search for, and which locality and carrier numbers to use. Specifically:

```
--file_path FILE_PATH
    Path to the Annual Physician Fee Schedule Payment Amount File  
    Default: ../data/PFALL26AR.txt

--hcpcs_code HCPCS_CODE
    HCPCS code  
    Default: 0446T

--locality LOCALITY
    Locality number  
    Default: 00 (Ohio)

--carrier CARRIER
    Carrier number  
    Default: 15202 (Ohio)
```

A SQLite database, prices.db, will be created and stored in the data directory. This database contains the data from `PFALL26AR.txt` loaded into SQLite.
## Data needed for constraints.py

For `constraints.py`, make sure to download the 4 PTP edit table Excel files


- `ccipra-v321r0-f1.xlsx`
- `ccipra-v321r0-f2.xlsx`
- `ccipra-v321r0-f3.xlsx`
- `ccipra-v321r0-f4.xlsx`

## LLM Parser

To run the LLM parser, first load the folder data in the Task 3 folder from the shared google drive. Then, put the data folder in the directory at the src level (not in src). Run the dhs_code_parser file first, and then run the parser.py file second. Additionally, make sure to add a .env file using your specific Gemini API key. 

Sample LLM Parser JSON Format:

[
  {
    "cpt_code": "90792",
    "description": "Psychiatric diagnostic evaluation with medical services",
    "rationale": "The note documents a comprehensive initial psychiatric evaluation, including a history of present illness, past psychiatric and medical history, a detailed mental status examination ...  .",
    "official_description": "Psych diag eval w/med srvcs"
  }
]


Sample Usage

```
from pathlib import Path
from src.parser import load_cpt_code_dict, parse_note, model, CPT_JSON_FILE

note_text = Path("/absolute/path/to/file.txt").read_text(encoding="utf-8", errors="ignore")
valid_codes_dict = load_cpt_code_dict(CPT_JSON_FILE)
result = parse_note(note_text, valid_codes_dict, model)
```

## Optimizer usage

`optimizer.py` takes the structured parser output (list of items with `cpt_code`) from stdin and returns the single highest-reimbursing code plus the single highest-reimbursing valid subset after pairwise `check_pair` validation. The subset output identifies whether any included codes require modifiers.

Run from repo root:

```bash
python3 src/optimizer.py < path/to/codes.json
```

Expected input shape:

```json
[
  {"cpt_code": "97597"},
  {"cpt_code": "11042"}
]
```

Output shape:

```json
{
  "input_codes": ["97597", "11042"],
  "highest_reimbursing_code": {
    "cpt_code": "11042",
    "total_reimbursement": 137.16,
    "requires_modifier": false,
    "status": "valid"
  },
  "highest_reimbursing_subset": {
    "codes": ["97597"],
    "total_reimbursement": 48.92,
    "requires_modifier": false,
    "code_statuses": [{"cpt_code": "97597", "status": "valid"}]
  }
}
```

## Testing

To run the full test suite, install pytest and run from the repo root:


pip install pytest
python3 -m pytest testing/ -v