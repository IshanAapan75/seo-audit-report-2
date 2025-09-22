"""
Utility functions to help migrate from pandas to polars
"""
import polars as pl
import json
from typing import Any, Dict, List, Optional, Union

def pd_to_polars_migration():
    """
    Common pandas to polars conversions for this project
    """
    
    # Helper functions to replace common pandas operations
    
    @staticmethod
    def read_json_lines(file_path: str) -> pl.DataFrame:
        """Replace pd.read_json(lines=True)"""
        try:
            return pl.read_ndjson(file_path)
        except:
            # Fallback for complex JSON structures
            with open(file_path, 'r') as f:
                data = [json.loads(line) for line in f]
            return pl.DataFrame(data)
    
    @staticmethod
    def to_numeric(series: pl.Series, errors: str = "coerce") -> pl.Series:
        """Replace pd.to_numeric()"""
        if errors == "coerce":
            return series.cast(pl.Float64, strict=False).fill_null(0)
        else:
            return series.cast(pl.Float64)
    
    @staticmethod
    def isna(value) -> bool:
        """Replace pd.isna()"""
        return value is None or (isinstance(value, float) and pl.Float64.is_nan(value))
    
    @staticmethod
    def notna(value) -> bool:
        """Replace pd.notna()"""
        return not pd_to_polars_migration.isna(value)
    
    @staticmethod
    def concat(dfs: List[pl.DataFrame], ignore_index: bool = False) -> pl.DataFrame:
        """Replace pd.concat()"""
        if not dfs:
            return pl.DataFrame()
        
        result = dfs[0]
        for df in dfs[1:]:
            result = result.vstack(df)
        
        return result
    
    @staticmethod
    def create_series(data, dtype=None, name=None) -> pl.Series:
        """Replace pd.Series()"""
        if dtype == "int":
            dtype = pl.Int64
        elif dtype == "float":
            dtype = pl.Float64
        elif dtype == "str":
            dtype = pl.Utf8
            
        return pl.Series(name=name, values=data, dtype=dtype)

# Monkey patch for easier migration
pl.isna = pd_to_polars_migration.isna
pl.notna = pd_to_polars_migration.notna
pl.to_numeric = pd_to_polars_migration.to_numeric
pl.concat = pd_to_polars_migration.concat
pl.Series = pd_to_polars_migration.create_series