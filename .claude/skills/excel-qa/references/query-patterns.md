# Excel Query Patterns

Common pandas patterns for answering questions from Excel data.

## Loading Data with Detected Header

```python
import pandas as pd

# Load with header row from schema discovery
df = pd.read_excel("file.xlsx", sheet_name=0, header=HEADER_ROW - 1)  # Convert to 0-indexed
```

## Lookup Patterns

### Single Value Lookup
```python
# "What is the revenue for product X?"
result = df.loc[df['Product'] == 'X', 'Revenue'].values
answer = result[0] if len(result) > 0 else "Not found"
```

### Multiple Conditions
```python
# "What is the sales for product X in region Y?"
mask = (df['Product'] == 'X') & (df['Region'] == 'Y')
result = df.loc[mask, 'Sales'].values
```

### Case-Insensitive Lookup
```python
result = df.loc[df['Name'].str.lower() == 'john', 'Salary']
```

### Partial Match
```python
result = df.loc[df['Description'].str.contains('keyword', case=False, na=False)]
```

## Aggregation Patterns

### Sum
```python
# "What is the total revenue?"
total = df['Revenue'].sum()
```

### Conditional Sum
```python
# "Total sales for region East"
total = df.loc[df['Region'] == 'East', 'Sales'].sum()
```

### Count
```python
# "How many orders are pending?"
count = (df['Status'] == 'Pending').sum()
```

### Average
```python
avg = df['Price'].mean()
```

### Group By Aggregation
```python
# "Total sales by region"
result = df.groupby('Region')['Sales'].sum()

# "Average price by category"
result = df.groupby('Category')['Price'].mean()
```

### Multiple Aggregations
```python
result = df.groupby('Region').agg({
    'Sales': 'sum',
    'Orders': 'count',
    'Price': 'mean'
})
```

## Date Handling

### Parse Date Columns
```python
df['Date'] = pd.to_datetime(df['Date'])
```

### Filter by Date Range
```python
mask = (df['Date'] >= '2024-01-01') & (df['Date'] <= '2024-12-31')
result = df.loc[mask]
```

### Group by Month/Year
```python
df['Month'] = df['Date'].dt.to_period('M')
monthly = df.groupby('Month')['Sales'].sum()
```

## Numeric String Handling

```python
# Clean currency/percentage strings
df['Amount'] = df['Amount'].replace('[\$,]', '', regex=True).astype(float)
df['Rate'] = df['Rate'].replace('%', '', regex=True).astype(float) / 100
```

## Result Formatting

### Format Currency
```python
f"${value:,.2f}"
```

### Format Large Numbers
```python
f"{value:,}"
```

### Top N Results
```python
top_5 = df.nlargest(5, 'Revenue')[['Name', 'Revenue']]
```

## Safety Patterns

### Handle Missing Data
```python
# Check if column exists
if 'Revenue' in df.columns:
    result = df['Revenue'].sum()

# Handle NaN
result = df['Revenue'].fillna(0).sum()
```

### Limit Output Rows
```python
# Never return more than 20 rows to context
result_df = result_df.head(20)
```
