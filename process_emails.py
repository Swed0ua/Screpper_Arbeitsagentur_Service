"""Main script for processing Excel file and generating email content."""

import asyncio
from config import OPENAI_API_KEY, OPENAI_MODEL
from modules.AIService.openai_service import OpenAIService
from modules.ExcelProcessor.excel_processor import ExcelProcessor


async def main():
    """Process Excel file, research companies, generate emails, and save results."""
    
    # Initialize OpenAI service
    ai_service = OpenAIService(api_key=OPENAI_API_KEY, model=OPENAI_MODEL)
    
    # Load Excel file
    file_path = "data/example.csv"
    processor = ExcelProcessor(file_path)
    await processor.load_file()
    
    # Get companies data
    companies = processor.get_companies_data()
    
    print(f"Processing {len(companies)} companies...")
    
    email_contents = []
    
    # Process each company
    for i, company in enumerate(companies, 1):
        company_name = company.get('company_name', '').strip()
        
        if not company_name:
            email_contents.append("")
            continue
        
        print(f"[{i}/{len(companies)}] Processing: {company_name}")
        
        # Research company
        company_research = await ai_service.research_company(
            company_name=company_name,
            company_info=company
        )
        
        # Generate email content
        email_content = await ai_service.generate_email_content(
            company_name=company_name,
            company_research=company_research,
            job_title=company.get('title', '')
        )
        
        email_contents.append(email_content)
    
    # Add email column to DataFrame
    processor.add_email_column(email_contents)
    
    # Save file
    output_path = file_path.replace('.csv', '_with_emails.csv').replace('.xlsx', '_with_emails.xlsx')
    await processor.save_file(output_path)
    
    print(f"\nDone! Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())

