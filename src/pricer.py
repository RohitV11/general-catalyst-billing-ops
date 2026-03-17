import sqlite3
import pandas as pd
import argparse
import os

def load_data(file_path):
    try:
        df = pd.read_csv(file_path, header=None, low_memory=False)
    except Exception as e:
        print(f"Error: Unable to read the file at {file_path}. Please check the file path and try again.")
        return False
    df.columns = [
        "Year",
        "Carrier Number",
        "Locality",
        "HCPCS Code",
        "Modifier",
        "Non Facility Fee Schedule Amount",
        "Facility Fee Schedule Amount",
        "Filler",
        "PCTC Indicator",
        "Status Code",
        "Multiple Surgery Indicator",
        "50% Therapy Reduction Amount (Section 1848)",
        "50% Therapy Reduction Amount (Section 1834)",
        "OPPS Indicator",
        "OPPS Non Facility Fee Amount",
        "OPPS Facility Fee Amount",
    ]
    df = df.drop("Filler", axis=1)
    os.makedirs("../data", exist_ok=True)
    conn = sqlite3.connect("../data/prices.db")
    df.to_sql("Prices", conn, if_exists="replace", index=False)
    conn.close()
    return True

def code_price(hcpcs_code, locality, carrier):
    if not os.path.isfile("../data/prices.db"):
        print("Error: The database file '../data/prices.db' does not exist. Please run the script with " \
        "the correct --file_path argument to load the data first.")
        return None
    conn = sqlite3.connect("../data/prices.db")
    query = f"SELECT [Facility Fee Schedule Amount] FROM Prices WHERE [HCPCS Code] = '{hcpcs_code}' AND [Locality] = '{locality}' AND [Carrier Number] = '{carrier}'"
    result = pd.read_sql_query(query, conn)
    conn.close()
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A script that accepts a file path to the Annual Physician Fee Schedule Payment " \
        "Amount File and a HCPCS code, and returns the corresponding Facility Fee Schedule Amount."
    )
    parser.add_argument("--file_path", default="../data/PFALL24R.txt", help="Path to the Annual Physician " \
    "Fee Schedule Payment Amount File, default value: ../data/PFALL24R.txt")
    parser.add_argument("--hcpcs_code", default="0446T", help="HCPCS code, default value: 0446T")
    parser.add_argument("--locality", default="00", help="Locality number, default value: 00 (Ohio)")
    parser.add_argument("--carrier", default="15202", help="Carrier number, default value: 15202 (Ohio)")
    args = parser.parse_args()
    if not load_data(args.file_path):
        exit(1)
    price_info = code_price(args.hcpcs_code, args.locality, args.carrier)
    if (price_info is None):
        print(f"Error: Unable to retrieve price information for HCPCS code {args.hcpcs_code} because ../data/prices.db does not exist.")
        exit(1)
    elif (not price_info.empty):
        print(f"The Facility Fee Schedule Amounts for HCPCS code {args.hcpcs_code} is: \n"f"{price_info.to_string(justify='left')}")
    else:
        print(f"No Facility Fee Schedule Amount found for HCPCS code {args.hcpcs_code}, locality number {args.locality}, carrier number {args.carrier}.")