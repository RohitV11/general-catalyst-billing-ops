import sqlite3
import pandas as pd
import argparse
import os


def load_data(file_path):
    try:
        df = pd.read_csv(file_path, header=None, low_memory=False)
    except Exception as e:
        print(f"Error: Unable to read the file at {file_path}.")
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

    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/prices.db")
    df.to_sql("Prices", conn, if_exists="replace", index=False)
    conn.close()

    return True


def code_price(hcpcs_code, locality, carrier):
    if not os.path.isfile("data/prices.db"):
        print("Error: The database file 'data/prices.db' does not exist.")
        return None

    conn = sqlite3.connect("data/prices.db")

    query = """
    SELECT [Facility Fee Schedule Amount]
    FROM Prices
    WHERE [HCPCS Code] = ?
    AND [Locality] = ?
    AND [Carrier Number] = ?
    """

    result = pd.read_sql_query(query, conn, params=(hcpcs_code, locality, carrier))
    conn.close()

    if result.empty:
        return result

    # pick highest price (handles TC/PC/global)
    max_price = result["Facility Fee Schedule Amount"].max()

    return pd.DataFrame({"Facility Fee Schedule Amount": [max_price]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Return PFS reimbursement for a given HCPCS code."
    )

    parser.add_argument("--file_path", default="data/PFALL24R.txt")
    parser.add_argument("--hcpcs_code", default="0446T")
    parser.add_argument("--locality", default="00")
    parser.add_argument("--carrier", default="15202")

    args = parser.parse_args()

    if not load_data(args.file_path):
        exit(1)

    price_info = code_price(args.hcpcs_code, args.locality, args.carrier)

    if price_info is None:
        print("Error: Database not initialized.")
        exit(1)
    elif not price_info.empty:
        print(price_info.to_string(index=False))
    else:
        print(
            f"No price found for HCPCS code {args.hcpcs_code}, "
            f"locality {args.locality}, carrier {args.carrier}."
        )