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
from modules.DatabaceSQLiteController.async_sq_lite_connector import AsyncSQLiteConnector, EmailDatabase


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
        self._first_html_saved = False  # Флаг чи вже збережено перший HTML
        self.email_db = None  # Ініціалізується в process_file
        
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
        # Ініціалізувати БД для email
        db_connector = AsyncSQLiteConnector("sent_emails_db")
        await db_connector.connect()
        self.email_db = EmailDatabase(db_connector)
        await self.email_db.init_table()
        
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
            suitability_results = []  # List of {'is_suitable': bool, 'industry': str, 'rejection_reason': str}
            
            # Process each company
            for i, company in enumerate(companies, 1):
                company_name = company.get('company_name', '').strip()
                
                if not company_name:
                    email_contents.append("")
                    company_researches.append("")
                    suitability_results.append({'is_suitable': False, 'industry': 'Unknown', 'rejection_reason': 'No company name'})
                    await self._update_progress(i, total, f"Пропущено (немає назви)")
                    continue
                
                # Перевірити email перед обробкою
                email = company.get('email', '').strip()
                if email:
                    can_send = await self.email_db.can_send_email(email)
                    if not can_send:
                        email_contents.append("")
                        company_researches.append("")
                        suitability_results.append({'is_suitable': False, 'industry': 'Unknown', 'rejection_reason': f'Email відправлявся менше 3 місяців тому'})
                        await self._update_progress(i, total, f"Пропущено: {company_name} (email відправлявся нещодавно)")
                        print(f"⏭️ Пропущено {company_name}: email {email} відправлявся менше 3 місяців тому")
                        continue
                
                await self._update_progress(i, total, f"Обробка: {company_name}")
                
                # Research company with template fields
                company_research = await self.ai_service.research_company(
                    company_name=company_name,
                    company_info=company,
                    required_fields=self.template_fields
                )
                
                # Check if company is suitable
                is_suitable = company_research.get('is_suitable', False)
                industry = company_research.get('industry', 'Unknown')
                rejection_reason = company_research.get('rejection_reason', '')
                
                suitability_results.append({
                    'is_suitable': is_suitable,
                    'industry': industry,
                    'rejection_reason': rejection_reason
                })
                
                # Generate email content ONLY if company is suitable
                if is_suitable:
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
                    
                    # Зберегти перший непустий HTML для перевірки
                    if not self._first_html_saved and email_content and email_content.strip():
                        try:
                            with open('t1.html', 'w', encoding='utf-8') as f:
                                f.write(email_content)
                            print(f"✅ Збережено перший HTML в t1.html ({len(email_content)} chars) для {company_name}")
                            self._first_html_saved = True
                        except Exception as e:
                            print(f"⚠️ Помилка збереження t1.html: {e}")
                    
                    # Записати email після успішної генерації
                    if email:
                        await self.email_db.record_sent_email(email, company_name, company.get('title', ''))
                        print(f"✅ Записано відправлений email: {email} для {company_name}")
                else:
                    # Not suitable - don't generate email, just add empty string
                    email_contents.append("")
                    print(f"Company {company_name} is not suitable: {rejection_reason}")
                
                # Store research text for the research column
                research_text = company_research.get('_research_text', '')
                if not research_text:
                    research_text = company_research.get('company_description', '')
                company_researches.append(research_text)
            
            await self._update_progress(total, total, "Збереження файлу...")
            
            # Add columns to DataFrame (company_research before email_content)
            processor.add_company_research_column(company_researches)
            processor.add_suitability_columns(suitability_results)
            processor.add_email_column(email_contents)
            
            # Save file
            output_path = file_path.replace('.csv', '_with_emails.csv').replace('.xlsx', '_with_emails.xlsx')
            await processor.save_file(output_path)
            
            await self._update_progress(total, total, "Завершено!")
            
            return output_path
        finally:
            # Закрити підключення до БД
            if self.email_db and self.email_db.db_connector:
                await self.email_db.db_connector.disconnect()
            await self.finish_process()

