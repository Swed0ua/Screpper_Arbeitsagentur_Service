"""Email processor module for generating email content from Excel files."""

import asyncio
from typing import Optional
from pathlib import Path
from config import OPENAI_API_KEY, OPENAI_MODEL, MAX_CONCURRENT_EMAIL_PROCESSES
from modules.AIService.openai_service import OpenAIService
from modules.ExcelProcessor.excel_processor import ExcelProcessor
from modules.EmailContentGenerator.template_parser import (
    load_template_file, 
    extract_template_fields
)


class EmailProcessor:
    """Process Excel files and generate email content for companies."""
    
    # Class variable to track active processes
    _active_processes = 0
    _lock = asyncio.Lock()
    
    def __init__(self, template_path: Optional[str] = None):
        """
        Initialize email processor.
        
        Args:
            template_path: Optional path to HTML template file
        """
        self.ai_service = OpenAIService(api_key=OPENAI_API_KEY, model=OPENAI_MODEL)
        self._progress_callback = None
        self.template_path = template_path
        self.template_content = None
        self.template_fields = None
        
        # Load template if provided
        if template_path:
            self._load_template()
        else:
            # Try to load default template
            self._load_template()
    
    def _load_template(self):
        """Load and parse template."""
        try:
            if self.template_path and Path(self.template_path).exists():
                self.template_content = load_template_file(self.template_path)
                self.template_fields = extract_template_fields(self.template_content)
            else:
                # Use default template
                default_template = Path("template.html")
                if default_template.exists():
                    self.template_content = load_template_file(str(default_template))
                    self.template_fields = extract_template_fields(self.template_content)
        except Exception as e:
            print(f"Warning: Could not load template: {e}")
            self.template_content = None
            self.template_fields = None
    
    def set_progress_callback(self, callback):
        """Set callback function for progress updates."""
        self._progress_callback = callback
    
    async def _update_progress(self, current: int, total: int, company_name: str = ""):
        """Update progress if callback is set."""
        if self._progress_callback:
            await self._progress_callback(current, total, company_name)
        else:
            # Print to console if no callback
            print(f"[{current}/{total}] {company_name}")
    
    @classmethod
    async def can_start_process(cls) -> tuple:
        """
        Check if new process can be started.
        
        Returns:
            (can_start, active_count) - tuple with permission and current active count
        """
        async with cls._lock:
            if cls._active_processes >= MAX_CONCURRENT_EMAIL_PROCESSES:
                return False, cls._active_processes
            cls._active_processes += 1
            return True, cls._active_processes
    
    @classmethod
    async def finish_process(cls):
        """Mark process as finished."""
        async with cls._lock:
            cls._active_processes = max(0, cls._active_processes - 1)
    
    async def process_file(self, file_path: str) -> str:
        """
        Process Excel/CSV file and generate email content.
        
        Args:
            file_path: Path to Excel or CSV file
            
        Returns:
            Path to output file with email content
        """
        try:
            # Load file
            processor = ExcelProcessor(file_path)
            await processor.load_file()
            
            # Get companies data
            companies = processor.get_companies_data()
            total = len(companies)
            
            await self._update_progress(0, total, "Початок обробки...")
            
            email_contents = []
            company_researches = []
            
            # Process each company
            for i, company in enumerate(companies, 1):
                company_name = company.get('company_name', '').strip()
                
                if not company_name:
                    email_contents.append("")
                    company_researches.append("")
                    await self._update_progress(i, total, f"Пропущено (немає назви)")
                    continue
                
                await self._update_progress(i, total, f"Обробка: {company_name}")
                
                # Research company with template fields
                company_research = await self.ai_service.research_company(
                    company_name=company_name,
                    company_info=company,
                    required_fields=self.template_fields
                )
                
                # Generate email content using template
                email_content = await self.ai_service.generate_email_content(
                    company_name=company_name,
                    company_research=company_research,
                    job_title=company.get('title', ''),
                    template_content=self.template_content,
                    template_fields=self.template_fields
                )
                
                # Перевірка довжини HTML
                if email_content:
                    html_length = len(email_content)
                    print(f"Generated HTML length for {company_name}: {html_length} chars")
                    
                    # Якщо HTML занадто короткий (менше 1000 символів для повного шаблону)
                    if html_length < 1000 and self.template_content:
                        expected_length = len(self.template_content)
                        print(f"WARNING: HTML seems too short for {company_name}")
                        print(f"  Expected ~{expected_length} chars, got {html_length} chars")
                        print(f"  Difference: {expected_length - html_length} chars")
                
                email_contents.append(email_content)
                # Store research text for the research column
                research_text = company_research.get('_research_text', '')
                if not research_text:
                    research_text = company_research.get('company_description', '')
                company_researches.append(research_text)
            
            await self._update_progress(total, total, "Збереження файлу...")
            
            # Add columns to DataFrame (company_research before email_content)
            processor.add_company_research_column(company_researches)
            processor.add_email_column(email_contents)
            
            # Save file
            output_path = file_path.replace('.csv', '_with_emails.csv').replace('.xlsx', '_with_emails.xlsx')
            await processor.save_file(output_path)
            
            await self._update_progress(total, total, "Завершено!")
            
            return output_path
        finally:
            await self.finish_process()

