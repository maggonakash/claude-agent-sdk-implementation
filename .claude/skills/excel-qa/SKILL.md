---
name: excel-qa
description: Answer questions from Excel files using natural language. Handles files with unknown schemas, headers on any row, and large datasets (100k+ rows). Use when the user provides an Excel file path, sheet number, and a question to answer. Supports lookups ("What is the value for X?") and aggregations ("Total sales by region"). Returns text summary answers.
---

# Excel Q&A

Answer natural language questions from Excel files by discovering schema, writing pandas queries, and summarizing results.

## Inputs

- **File path**: Path to .xlsx file
- **Sheet number**: 0-indexed sheet number
- **Query**: Natural language question

## Workflow

### Step 1: Discover Schema

Run the schema discovery script to understand the Excel structure:

```bash
python3 {SKILL_PATH}/scripts/discover_schema.py "<file_path>" --sheet <sheet_number>
```

This returns:
- Header row location (handles headers not on row 1)
- Column names and types
- Sample values for each column
- Total row count

### Step 2: Write Query

Based on the schema and user question, write pandas code to answer the question.

Key considerations:
- Use the detected header row: `header=HEADER_ROW - 1` (convert to 0-indexed)
- Match column names exactly as shown in schema
- For lookups: use `.loc[]` with conditions
- For aggregations: use `.sum()`, `.mean()`, `.groupby()`
- Handle case sensitivity with `.str.lower()` or `case=False`
- Limit results to prevent context overflow

See `references/query-patterns.md` for common patterns.

### Step 3: Execute and Summarize

Execute the pandas code and format the result as a clear text summary.

Example outputs:
- "The revenue for Product X is $45,230.50"
- "Total sales by region: East ($120K), West ($95K), North ($78K)"
- "There are 342 pending orders in the dataset"

## Example

**User**: "What is the total revenue for Q1 2024?"

**Process**:

1. Run schema discovery:
```bash
python3 scripts/discover_schema.py "sales.xlsx" --sheet 0
```

Output shows:
- Header row: 3
- Columns: Date (datetime), Product (text), Revenue (decimal), Quarter (text)

2. Write pandas query:
```python
import pandas as pd
df = pd.read_excel("sales.xlsx", sheet_name=0, header=2)  # Row 3 = index 2
q1_revenue = df.loc[df['Quarter'] == 'Q1 2024', 'Revenue'].sum()
print(f"${q1_revenue:,.2f}")
```

3. Execute and respond:
"The total revenue for Q1 2024 is $1,245,678.90"

## Handling Edge Cases

### Column name mismatch
If the user's question mentions a column that doesn't exist, check for similar column names in the schema and clarify with the user if needed.

### Large result sets
For queries that return many rows, summarize the top results:
- "Top 5 products by revenue: ..."
- "Showing first 10 of 500 matching rows..."

### No matches found
If a lookup returns empty results, state this clearly:
- "No records found for Product 'XYZ'. Available products include: A, B, C..."

### Numeric strings
If numeric columns show as text type with currency/percentage symbols, clean them:
```python
df['Amount'] = df['Amount'].replace('[\$,]', '', regex=True).astype(float)
```
