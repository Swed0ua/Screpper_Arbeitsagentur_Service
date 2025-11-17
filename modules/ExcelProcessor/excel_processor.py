"""Excel file processor for reading and writing company data."""

import pandas as pd
import os


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
        Save DataFrame to Excel file.
        
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
            self.df.to_excel(save_path, index=False, engine='openpyxl')

