# Pandas to Polars Migration Guide

## Overview
This project has been migrated from pandas to polars to reduce dependency size from ~80MB to ~20MB, helping with Vercel deployment limits.

## Files Changed

### 1. requirements.txt
- **Before**: `pandas==2.0.3`
- **After**: `polars==0.20.2`

### 2. New Files Created
- `seo_insights_polars.py` - Polars version of insights functions
- `seo_audit_polars.py` - Polars version of main audit script
- `polars_migration_utils.py` - Helper utilities for migration

### 3. Updated Files
- `app.py` - Now imports from `seo_audit_polars`

## Key Differences: Pandas vs Polars

### Import Statement
```python
# Pandas
import pandas as pd

# Polars
import polars as pl
```

### DataFrame Creation
```python
# Pandas
df = pd.DataFrame(data)

# Polars
df = pl.DataFrame(data)
```

### Reading JSON Lines
```python
# Pandas
df = pd.read_json(file_path, lines=True)

# Polars
df = pl.read_ndjson(file_path)
```

### Column Operations
```python
# Pandas
df['new_col'] = df['old_col'].fillna(0).astype(int)

# Polars
df = df.with_columns(
    pl.col('old_col').fill_null(0).cast(pl.Int64).alias('new_col')
)
```

### Numeric Conversion
```python
# Pandas
pd.to_numeric(series, errors='coerce')

# Polars
series.cast(pl.Float64, strict=False).fill_null(0)
```

### Aggregations
```python
# Pandas
df['column'].sum()

# Polars
df.select(pl.col('column').sum()).item()
```

### Filtering
```python
# Pandas
df[df['column'] > 5]

# Polars
df.filter(pl.col('column') > 5)
```

### Concatenation
```python
# Pandas
pd.concat([df1, df2], ignore_index=True)

# Polars
pl.concat([df1, df2])
```

### Value Counts
```python
# Pandas
df['column'].value_counts()

# Polars
df.group_by('column').agg(pl.count().alias('count'))
```

## Benefits of Migration

1. **Smaller Size**: ~60MB reduction in dependencies
2. **Better Performance**: Polars is often faster than pandas
3. **Memory Efficiency**: Better memory usage patterns
4. **Modern API**: More consistent and intuitive API

## Compatibility Notes

- Some advertools functions still require pandas DataFrames
- The migration includes conversion helpers for pandas/polars interop
- NetworkX integration requires pandas DataFrames for edge lists

## Testing the Migration

1. Install new requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Test the polars version:
   ```bash
   python seo_audit_polars.py test_customer https://example.com
   ```

3. Compare with original (if needed):
   ```bash
   python seo_audit_extd.py test_customer https://example.com
   ```

## Rollback Plan

If issues arise, you can rollback by:
1. Reverting `requirements.txt` to use pandas
2. Updating `app.py` to import from `seo_audit_extd`
3. The original files are preserved for this purpose

## Size Comparison

| Dependency | Pandas Version | Polars Version | Savings |
|------------|----------------|----------------|---------|
| Data Processing | pandas (~80MB) | polars (~20MB) | ~60MB |
| PDF Generation | weasyprint (~150MB) | weasyprint (~150MB) | 0MB |
| **Total Estimated** | **~250MB+** | **~190MB** | **~60MB** |

## Next Steps

To further reduce size for Vercel deployment, consider:
1. Replace weasyprint with reportlab (~135MB savings)
2. Use lightweight alternatives for other heavy dependencies
3. Implement hybrid architecture with external processing service