"""Template parser for extracting and filling template variables."""

import re
from typing import List, Dict, Set
from pathlib import Path


def extract_template_fields(html_content: str) -> Set[str]:
    """
    Extract all template fields from HTML content.
    
    Args:
        html_content: HTML template content with {{ }} placeholders
        
    Returns:
        Set of unique field names (e.g., {'contact.FIRSTNAME', 'contact.COMPANY'})
    """
    # Pattern to match {{ field }} or {{ field | default : "" }}
    pattern = r'\{\{\s*([^}|]+?)(?:\s*\|\s*[^}]+)?\s*\}\}'
    
    matches = re.findall(pattern, html_content)
    
    # Clean up field names (remove whitespace, handle nested structures)
    fields = set()
    for match in matches:
        field = match.strip()
        # Remove any default values or filters
        if '|' in field:
            field = field.split('|')[0].strip()
        fields.add(field)
    
    return fields


def load_template_file(file_path: str) -> str:
    """
    Load HTML template from file.
    
    Args:
        file_path: Path to HTML template file
        
    Returns:
        Template content as string
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def fill_template(html_content: str, values: Dict[str, str]) -> str:
    """
    Fill template with provided values.
    
    Args:
        html_content: HTML template content
        values: Dictionary mapping field names to values
                (e.g., {'contact.FIRSTNAME': 'John', 'contact.COMPANY': 'Acme Inc'})
        
    Returns:
        Filled HTML content
    """
    result = html_content
    
    # Pattern to match {{ field }} or {{ field | default : "" }}
    pattern = r'\{\{\s*([^}|]+?)(?:\s*\|\s*[^}]+)?\s*\}\}'
    
    def replace_field(match):
        full_match = match.group(0)
        field = match.group(1).strip()
        
        # Remove default value if present
        if '|' in field:
            field = field.split('|')[0].strip()
        
        # Get value from dictionary
        value = values.get(field, '')
        
        # If no value and there's a default, use empty string
        if not value and '|' in match.group(0):
            return ''
        
        return str(value) if value else ''
    
    result = re.sub(pattern, replace_field, result)
    
    return result

