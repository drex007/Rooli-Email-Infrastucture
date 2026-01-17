import pandas as pd
import io
from typing import List, Dict, Any, Union

class FileExtractor:
    """Extract data from Excel/CSV files (from file path or bytes) into dictionary arrays"""
    
    @staticmethod
    def extract_from_csv_bytes(file_bytes: bytes, encoding='utf-8') -> List[Dict[str, Any]]:
        """
        Extract CSV from bytes into list of dictionaries
        
        Args:
            file_bytes: CSV file as bytes
            encoding: File encoding (default: utf-8)
            
        Returns:
            List of dictionaries where each dict represents a row
        """
        try:
            # Convert bytes to StringIO
            csv_string = file_bytes.decode(encoding)
            csv_buffer = io.StringIO(csv_string)
            
            df = pd.read_csv(csv_buffer)
            dict_array = df.to_dict('records')
            print(f"✓ Extracted {len(dict_array)} rows from CSV bytes")
            return dict_array
        except Exception as e:
            print(f"✗ Error reading CSV bytes: {e}")
            return []
    
    @staticmethod
    def extract_from_excel_bytes(file_bytes: bytes, sheet_name=0) -> List[Dict[str, Any]]:
        """
        Extract Excel from bytes into list of dictionaries
        
        Args:
            file_bytes: Excel file as bytes
            sheet_name: Sheet name or index (default: 0 for first sheet)
            
        Returns:
            List of dictionaries where each dict represents a row
        """
        try:
            # Convert bytes to BytesIO
            excel_buffer = io.BytesIO(file_bytes)
            
            df = pd.read_excel(excel_buffer, sheet_name=sheet_name)
            dict_array = df.to_dict('records')
            print(f"✓ Extracted {len(dict_array)} rows from Excel bytes")
            return dict_array
        except Exception as e:
            print(f"✗ Error reading Excel bytes: {e}")
            return []
    
    @staticmethod
    def extract_from_bytes(file_bytes: bytes, file_type: str, encoding='utf-8', sheet_name=0) -> List[Dict[str, Any]]:
        """
        Universal extractor for bytes (auto-detects or uses file_type)
        
        Args:
            file_bytes: File as bytes
            file_type: 'csv', 'xlsx', or 'xls'
            encoding: For CSV files (default: utf-8)
            sheet_name: For Excel files (default: 0)
            
        Returns:
            List of dictionaries
        """
        if file_type.lower() == 'csv' or file_type.lower() == 'text/csv':
            return FileExtractor.extract_from_csv_bytes(file_bytes, encoding)
        elif file_type.lower() in ['xlsx', 'xls', 'excel']:
            return FileExtractor.extract_from_excel_bytes(file_bytes, sheet_name)
        else:
            print("✗ Unsupported file type")
            return []
    
    @staticmethod
    def extract_from_file_path(file_path: str, sheet_name=0) -> List[Dict[str, Any]]:
        """
        Extract from file path (for backward compatibility)
        
        Args:
            file_path: Path to file
            sheet_name: For Excel files
            
        Returns:
            List of dictionaries
        """
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                print("✗ Unsupported file format")
                return []
            
            dict_array = df.to_dict('records')
            print(f"✓ Extracted {len(dict_array)} rows from file")
            return dict_array
        except Exception as e:
            print(f"✗ Error reading file: {e}")
            return []
    
    @staticmethod
    def get_file_info_from_bytes(file_bytes: bytes, file_type: str) -> Dict[str, Any]:
        """
        Get detailed information about the file from bytes
        
        Returns:
            Dictionary with file metadata
        """
        try:
            if file_type.lower() == 'csv':
                csv_string = file_bytes.decode('utf-8')
                df = pd.read_csv(io.StringIO(csv_string))
            elif file_type.lower() in ['xlsx', 'xls', 'excel']:
                df = pd.read_excel(io.BytesIO(file_bytes))
            else:
                return {"error": "Unsupported file format"}
            
            info = {
                "num_rows": len(df),
                "num_columns": len(df.columns),
                "columns": df.columns.tolist(),
                "column_types": {k: str(v) for k, v in df.dtypes.to_dict().items()},
                "memory_usage": f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB",
                "file_size": f"{len(file_bytes) / 1024:.2f} KB"
            }
            
            return info
        except Exception as e:
            return {"error": str(e)}




file_extractor = FileExtractor()