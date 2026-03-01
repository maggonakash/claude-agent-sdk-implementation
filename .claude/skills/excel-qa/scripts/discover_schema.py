#!/usr/bin/env python3
"""
Discover Excel file schema: detect headers, column types, and sample data.
Handles cases where headers may not be on row 1.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import pandas as pd
    import openpyxl
except ImportError:
    print("Error: Required packages not installed. Run: pip install pandas openpyxl")
    sys.exit(1)


def detect_header_row(df_sample: pd.DataFrame, max_scan_rows: int = 30) -> int:
    """
    Detect the most likely header row by scoring each row.

    Heuristics:
    - Headers are usually strings
    - Headers have mostly non-empty values
    - Row after headers typically has different types (numbers, dates)
    - Headers often have unique values
    """
    best_row = 0
    best_score = -1

    scan_limit = min(max_scan_rows, len(df_sample))

    for idx in range(scan_limit):
        row = df_sample.iloc[idx]
        score = 0

        # Count non-empty cells
        non_empty = row.notna().sum()
        if non_empty == 0:
            continue

        non_empty_ratio = non_empty / len(row)
        score += non_empty_ratio * 30

        # Count string values (headers are usually strings)
        string_count = sum(1 for val in row if isinstance(val, str) and val.strip())
        string_ratio = string_count / max(non_empty, 1)
        score += string_ratio * 40

        # Check if next row has different types (numeric/date values)
        if idx + 1 < len(df_sample):
            next_row = df_sample.iloc[idx + 1]
            numeric_count = sum(1 for val in next_row if isinstance(val, (int, float)) and pd.notna(val))
            if numeric_count > 0:
                score += 20

        # Penalize rows that look like data (mostly numbers)
        numeric_in_current = sum(1 for val in row if isinstance(val, (int, float)) and pd.notna(val))
        if numeric_in_current > non_empty * 0.7:
            score -= 30

        # Check for unique values (headers should be unique)
        non_null_values = [v for v in row if pd.notna(v)]
        if len(non_null_values) == len(set(str(v) for v in non_null_values)):
            score += 10

        if score > best_score:
            best_score = score
            best_row = idx

    return best_row


def infer_column_type(series: pd.Series) -> str:
    """Infer the semantic type of a column."""
    # Drop nulls for analysis
    non_null = series.dropna()
    if len(non_null) == 0:
        return "empty"

    # Check pandas dtype
    dtype = series.dtype

    if pd.api.types.is_numeric_dtype(dtype):
        if pd.api.types.is_integer_dtype(dtype):
            return "integer"
        return "decimal"

    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"

    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"

    # For object dtype, sample values to determine type
    sample = non_null.head(20)

    # Check if dates stored as strings
    date_count = 0
    for val in sample:
        if isinstance(val, str):
            try:
                pd.to_datetime(val)
                date_count += 1
            except:
                pass
    if date_count > len(sample) * 0.7:
        return "date_string"

    # Check if numeric strings
    numeric_count = 0
    for val in sample:
        if isinstance(val, str):
            try:
                float(val.replace(',', '').replace('$', '').replace('%', ''))
                numeric_count += 1
            except:
                pass
    if numeric_count > len(sample) * 0.7:
        return "numeric_string"

    return "text"


def get_sample_values(series: pd.Series, n: int = 5) -> list:
    """Get sample non-null values from a series."""
    non_null = series.dropna().head(n * 2).unique()[:n]
    return [str(v)[:100] for v in non_null]  # Truncate long values


def discover_schema(file_path: str, sheet: int = 0) -> dict:
    """
    Discover the schema of an Excel file.

    Args:
        file_path: Path to Excel file
        sheet: Sheet number (0-indexed)

    Returns:
        Dictionary with schema information
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        # Get sheet names
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names

        if sheet >= len(sheet_names):
            return {"error": f"Sheet {sheet} does not exist. File has {len(sheet_names)} sheets: {sheet_names}"}

        sheet_name = sheet_names[sheet]

        # Read first 50 rows without header to detect header row
        df_raw = pd.read_excel(file_path, sheet_name=sheet, header=None, nrows=50)

        # Detect header row
        header_row = detect_header_row(df_raw)

        # Read full sample with detected header
        df_sample = pd.read_excel(
            file_path,
            sheet_name=sheet,
            header=header_row,
            nrows=100  # Read 100 rows for better type inference
        )

        # Get total row count (without loading all data)
        # Use openpyxl for efficiency
        wb = openpyxl.load_workbook(file_path, read_only=True)
        ws = wb[sheet_name]
        total_rows = ws.max_row - header_row - 1  # Subtract header row
        wb.close()

        # Build column info
        columns = []
        for col_name in df_sample.columns:
            col_data = df_sample[col_name]
            columns.append({
                "name": str(col_name),
                "type": infer_column_type(col_data),
                "non_null_count": int(col_data.notna().sum()),
                "sample_values": get_sample_values(col_data)
            })

        # Get sample rows as text
        sample_rows = []
        for idx in range(min(5, len(df_sample))):
            row_dict = {}
            for col in df_sample.columns:
                val = df_sample.iloc[idx][col]
                if pd.notna(val):
                    row_dict[str(col)] = str(val)[:100]
            sample_rows.append(row_dict)

        return {
            "file": str(path.name),
            "sheet_number": sheet,
            "sheet_name": sheet_name,
            "all_sheets": sheet_names,
            "header_row": header_row + 1,  # 1-indexed for user clarity
            "total_rows": total_rows,
            "total_columns": len(columns),
            "columns": columns,
            "sample_rows": sample_rows
        }

    except Exception as e:
        return {"error": f"Failed to read Excel file: {str(e)}"}


def main():
    parser = argparse.ArgumentParser(description="Discover Excel file schema")
    parser.add_argument("file_path", help="Path to Excel file")
    parser.add_argument("--sheet", type=int, default=0, help="Sheet number (0-indexed)")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")

    args = parser.parse_args()

    schema = discover_schema(args.file_path, args.sheet)

    if args.format == "json":
        print(json.dumps(schema, indent=2))
    else:
        # Human-readable format
        if "error" in schema:
            print(f"ERROR: {schema['error']}")
            sys.exit(1)

        print(f"FILE: {schema['file']}")
        print(f"SHEET: {schema['sheet_name']} (#{schema['sheet_number']})")
        print(f"ALL SHEETS: {', '.join(schema['all_sheets'])}")
        print(f"HEADER ROW: {schema['header_row']}")
        print(f"TOTAL ROWS: {schema['total_rows']:,}")
        print(f"TOTAL COLUMNS: {schema['total_columns']}")
        print()
        print("COLUMNS:")
        print("-" * 80)
        for col in schema["columns"]:
            samples = ", ".join(col["sample_values"][:3])
            print(f"  {col['name']}")
            print(f"    Type: {col['type']} | Non-null: {col['non_null_count']}")
            print(f"    Samples: {samples}")
        print()
        print("SAMPLE ROWS:")
        print("-" * 80)
        for i, row in enumerate(schema["sample_rows"], 1):
            print(f"  Row {i}: {row}")


if __name__ == "__main__":
    main()
