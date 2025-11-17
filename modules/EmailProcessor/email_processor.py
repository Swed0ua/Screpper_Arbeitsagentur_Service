"""Email processor module for generating email content from Excel files."""

import asyncio
from config import OPENAI_API_KEY, OPENAI_MODEL, MAX_CONCURRENT_EMAIL_PROCESSES
from modules.AIService.openai_service import OpenAIService
from modules.ExcelProcessor.excel_processor import ExcelProcessor


class EmailProcessor:
    """Process Excel files and generate email content for companies."""
    
    # Class variable to track active processes
    _active_processes = 0
    _lock = asyncio.Lock()
    
    def __init__(self):
        """Initialize email processor."""
        self.ai_service = OpenAIService(api_key=OPENAI_API_KEY, model=OPENAI_MODEL)
        self._progress_callback = None
    
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
            
            # Process each company
            for i, company in enumerate(companies, 1):
                company_name = company.get('company_name', '').strip()
                
                if not company_name:
                    email_contents.append("")
                    await self._update_progress(i, total, f"Пропущено (немає назви)")
                    continue
                
                await self._update_progress(i, total, f"Обробка: {company_name}")
                
                # Research company
                company_research = await self.ai_service.research_company(
                    company_name=company_name,
                    company_info=company
                )
                
                # Generate email content
                email_content = await self.ai_service.generate_email_content(
                    company_name=company_name,
                    company_research=company_research,
                    job_title=company.get('title', '')
                )
                
                email_contents.append(email_content)
            
            await self._update_progress(total, total, "Збереження файлу...")
            
            # Add email column to DataFrame
            processor.add_email_column(email_contents)
            
            # Save file
            output_path = file_path.replace('.csv', '_with_emails.csv').replace('.xlsx', '_with_emails.xlsx')
            await processor.save_file(output_path)
            
            await self._update_progress(total, total, "Завершено!")
            
            return output_path
        finally:
            await self.finish_process()

