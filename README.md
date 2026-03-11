# general-catalyst-billing-ops
CVC SP26 General Catalyst Billing Ops project

Rules:
Only work on your own branch. Only merge once complete by initiating a PR to main.
When working, create a new branch called "<Name>" (based on your name), and do the necessary work assigned.
For every PR, make the edits you are merging as details as possible in the PR message.

Data folder:
Create a save a folder in the home directory called data where you will store all the csvs/txt files from the drive.

## Data needed for constraints.py

For `constraints.py`, make sure to download the 4 PTP edit table Excel files


- `ccipra-v321r0-f1.xlsx`
- `ccipra-v321r0-f2.xlsx`
- `ccipra-v321r0-f3.xlsx`
- `ccipra-v321r0-f4.xlsx`


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
