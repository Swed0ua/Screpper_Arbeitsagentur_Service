"""OpenAI service for AI operations."""

from openai import AsyncOpenAI


class OpenAIService:
    """OpenAI service for generating text and researching companies."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        """
        Initialize OpenAI service.
        
        Args:
            api_key: OpenAI API key
            model: Model name (default: gpt-4)
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def research_company(self, company_name: str, company_info: dict) -> str:
        """
        Research company information using AI.
        
        Args:
            company_name: Name of the company
            company_info: Dictionary with available company info
            
        Returns:
            Research text about the company
        """
        try:
            system_prompt = """You are an expert in company research. 
            Analyze the company and identify its main business activity, industry, and products/services.
            Provide short but informative description (2-3 sentences)."""
            
            user_prompt = f"""Research this company: {company_name}
            
            Available information:
            - Job title: {company_info.get('title', 'N/A')}
            - Location: {company_info.get('location', 'N/A')}
            - Type of employment: {company_info.get('type_offer', 'N/A')}
            
            Identify what this company does (production, services, industry type, etc.)
            and provide brief description."""
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error researching company: {str(e)}"
    
    async def generate_email_content(self, company_name: str, company_research: str, job_title: str) -> str:
        """
        Generate personalized email content based on company research.
        
        Args:
            company_name: Name of the company
            company_research: Researched information about the company
            job_title: Job title/position
            
        Returns:
            Generated email content in HTML format
        """
        try:
            system_prompt = """You are a professional marketer writing personalized business emails.
            Create a warm, professional email that:
            - Shows appreciation for the company's work/products/services
            - Expresses interest in cooperation
            - Is personalized based on company's business type
            - Is short (100-150 words)
            - Uses HTML format with <p> tags
            
            Examples:
            - If company produces jewelry: "We appreciate your beautiful jewelry creations..."
            - If company is in IT: "We value your innovative IT solutions..."
            - If company is in manufacturing: "We admire your high-quality manufacturing..."."""
            
            user_prompt = f"""Create a personalized email for: {company_name}

            About the company: {company_research}
            
            Position: {job_title}
            
            Write a professional email expressing interest in cooperation,
            showing appreciation for what the company does, and proposing collaboration.
            Make it personalized based on the company's business type."""
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating email: {str(e)}"

