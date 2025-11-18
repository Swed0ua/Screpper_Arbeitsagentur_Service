"""Excel file processor for reading and writing company data."""

import pandas as pd
import os
from openpyxl import load_workbook
from openpyxl.styles import Alignment


class ExcelProcessor:
    """Process Excel/CSV files with company data."""
    
    def __init__(self, file_path: str):
        """
        Initialize Excel processor.
        
        Args:
            file_path: Path to Excel or CSV file
        """
        self.file_path = file_path
        self.df = None
    
    async def load_file(self):
        """Load Excel or CSV file into DataFrame."""
        file_extension = os.path.splitext(self.file_path)[1].lower()
        
        if file_extension == '.csv':
            self.df = pd.read_csv(self.file_path)
        else:
            self.df = pd.read_excel(self.file_path)
        
        return self.df
    
    def get_companies_data(self) -> list:
        """
        Extract company data from DataFrame.
        
        Returns:
            List of dictionaries with company information
        """
        if self.df is None:
            raise ValueError("File not loaded. Call load_file() first.")
        
        companies = []
        for _, row in self.df.iterrows():
            company_data = {
                'company_name': self._get_value(row, 'Роботодавець') or self._get_value(row, 'employer_company_name', ''),
                'title': self._get_value(row, 'Назва вакансії') or self._get_value(row, 'title', ''),
                'location': self._get_value(row, 'Місцезнаходження') or self._get_value(row, 'location', ''),
                'type_offer': self._get_value(row, 'Тип зайнятості') or self._get_value(row, 'type_offer', ''),
                'email': self._get_value(row, 'Електронна пошта') or self._get_value(row, 'email', ''),
                'phone': self._get_value(row, 'Мобільний номер') or self._get_value(row, 'phone', ''),
                'link': self._get_value(row, 'Посилання на вакансію') or self._get_value(row, 'link', ''),
                'job_title': self._get_value(row, 'Назва вакансії') or self._get_value(row, 'title', ''),
                'address': self._get_value(row, 'Поштова адреса') or self._get_value(row, 'address', ''),
            }
            companies.append(company_data)
        
        return companies
    
    def _get_value(self, row, key: str, default: str = '') -> str:
        """Helper to safely get value from row."""
        if key in row.index:
            value = row[key]
            return str(value) if pd.notna(value) else default
        return default
    
    def add_company_research_column(self, company_researches: list):
        """
        Add company research column to DataFrame.
        
        Args:
            company_researches: List of company research strings
        """
        if self.df is None:
            raise ValueError("File not loaded. Call load_file() first.")
        
        self.df['company_research'] = company_researches
    
    def add_email_column(self, email_contents: list):
        """
        Add email content column to DataFrame.
        
        Args:
            email_contents: List of email content strings
        """
        if self.df is None:
            raise ValueError("File not loaded. Call load_file() first.")
        
        self.df['email_content'] = email_contents
    
    async def save_file(self, output_path: str = None):
        """
        Save DataFrame to Excel file with formatting.
        
        Args:
            output_path: Output file path (if None, overwrites original)
        """
        if self.df is None:
            raise ValueError("No data to save.")
        
        save_path = output_path or self.file_path
        
        file_extension = os.path.splitext(save_path)[1].lower()
        
        if file_extension == '.csv':
            self.df.to_csv(save_path, index=False, encoding='utf-8')
        else:
            # Save to Excel
            self.df.to_excel(save_path, index=False, engine='openpyxl')
            
            # Format Excel file
            wb = load_workbook(save_path)
            ws = wb.active
            
            # Get column names from DataFrame
            column_names = list(self.df.columns)
            
            # Set column widths
            for idx, column in enumerate(ws.columns):
                max_length = 0
                column_letter = column[0].column_letter
                column_name = column_names[idx] if idx < len(column_names) else ""
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                # Set width based on column type
                if column_name in ['company_research', 'email_content']:
                    # Wider for research and email columns
                    adjusted_width = min(max(max_length + 2, 40), 80)
                elif idx == 0:  # First column
                    adjusted_width = min(max(max_length + 2, 15), 30)
                else:
                    # Standard width for other columns
                    adjusted_width = min(max(max_length + 2, 15), 50)
                
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Set row heights (smaller, compact)
            for row_num in range(1, ws.max_row + 1):
                ws.row_dimensions[row_num].height = 20
            
            # Set text wrapping and alignment
            for row in ws.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(
                        wrap_text=True,
                        vertical='top',
                        horizontal='left'
                    )
            
            wb.save(save_path)

