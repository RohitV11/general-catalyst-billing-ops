# general-catalyst-billing-ops
CVC SP26 General Catalyst Billing Ops project

Rules:
Only work on your own branch. Only merge once complete by initiating a PR to main.
When working, create a new branch called "<Name>" (based on your name), and do the necessary work assigned.
For every PR, make the edits you are merging as details as possible in the PR message.

Data folder:
Create a save a folder in the home directory called data where you will store all the csvs/txt files from the drive.

## Instructions for pricer.py

Download the CMS Annual Physician Fee Schedule Payment Amount File (PFALL26AR.txt). Place the file in the project data directory:

general-catalyst-billing-ops/
│
├── data/
│   └── PFALL26AR.txt
│   └── ...
│
├── src/
│   └── pricer.py
│   └── ...
|
├── ...

To run the script, run "python pricer.py" from the src directory.

Command line arguments can be provided to specify which file path to load data from, which HCPCS code to search for, and which locality and carrier numbers to use. Specifically:

--file_path FILE_PATH
                    Path to the Annual Physician Fee Schedule Payment Amount File, default value: ../data/PFALL26AR.txt
--hcpcs_code HCPCS_CODE
                    HCPCS code, default value: 0446T
--locality LOCALITY 
                    Locality number, default value: 00 (Ohio)
--carrier CARRIER   
                    Carrier number, default value: 15202 (Ohio)

A SQLite database, prices.db, will be created and stored in the data directory. This database contains the data from `PFALL26AR.txt` loaded into SQLite.