"""OpenAI service for AI operations."""

import re
import json
from typing import Optional, Set, Dict
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
    
    async def research_company(
        self, 
        company_name: str, 
        company_info: dict,
        required_fields: Optional[Set[str]] = None
    ) -> Dict[str, str]:
        """
        Research company information using AI with focus on required template fields.
        
        Args:
            company_name: Name of the company
            company_info: Dictionary with available company info
            required_fields: Set of template fields that need to be filled
                            (e.g., {'contact.FIRSTNAME', 'contact.COMPANY'})
            
        Returns:
            Dictionary with researched information for each field
        """
        try:
            # МАКСИМАЛЬНО АГРЕСИВНИЙ промпт - ОБОВ'ЯЗКОВО шукати
            system_prompt = """You are an expert company researcher. Your ONLY job is to FIND information, NOT return "N/A".

MANDATORY REQUIREMENTS:
- You MUST search for FIRSTNAME and LASTNAME for EVERY company
- Search CEO, founder, managing director, owner, Geschäftsführer
- Search company website, LinkedIn, business registries, Handelsregister
- Search parent companies, subsidiaries, franchise owners
- Try ALL possible search strategies before giving up
- "N/A" is ONLY allowed if you searched EVERYTHING and found NOTHING
- If you find even PARTIAL info (just first name OR last name), provide it
- DO NOT be lazy - SEARCH ACTIVELY"""
            
            # Build user prompt with required fields
            user_prompt = f"""Research this company: {company_name}
            
            Available information from job posting:
            - Job title: {company_info.get('title', 'N/A')}
            - Location: {company_info.get('location', 'N/A')}
            - Type of employment: {company_info.get('type_offer', 'N/A')}
            - Company name: {company_name}
            
            Required information to find:"""
            
            if required_fields:
                fields_list = ", ".join(sorted(required_fields))
                user_prompt += f"""
                
            REQUIRED TEMPLATE FIELDS TO FILL:
            {fields_list}
            
            MANDATORY TASK: Find executives for company: {company_name}
            
            CRITICAL INSTRUCTIONS:
            1. COMPANY: Use exact name: "{company_name}"
            
            2. FIRSTNAME/LASTNAME - MANDATORY SEARCH (DO NOT RETURN "N/A" WITHOUT SEARCHING):
               - Search: "{company_name} CEO"
               - Search: "{company_name} founder"
               - Search: "{company_name} Geschäftsführer"
               - Search: "{company_name} owner"
               - Search: "{company_name} managing director"
               - Search: "{company_name} Vorstand"
               - Check company website
               - Check LinkedIn company page
               - Check Handelsregister (German commercial register)
               - If franchise/chain: search regional owner/manager
               - If subsidiary: search parent company executives
               - Try company name variations (with/without GmbH, Ltd, etc.)
               - Search business registries and public records
               - Check press releases, news articles about the company
            
            3. DO NOT RETURN "N/A" FOR FIRSTNAME/LASTNAME UNLESS YOU SEARCHED EVERYTHING
            
            Return your findings in this EXACT JSON format:
            {{
              "contact": {{
                "COMPANY": "{company_name}",
                "FIRSTNAME": "MUST SEARCH - find CEO/founder/owner first name",
                "LASTNAME": "MUST SEARCH - find CEO/founder/owner last name",
                "unsubscribe": "N/A"
              }}
            }}
            
            REMEMBER: SEARCH ACTIVELY. "N/A" only if you searched EVERYTHING and found NOTHING."""
            else:
                user_prompt += "\n- Main business activity, industry, and products/services"
                user_prompt += "\n- Company description (2-3 sentences)"
            
            user_prompt += """
            
            Format your response as JSON with the structure shown above."""
            
            # Перший запит з більш активною температурою
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,  # Вище для більш активного пошуку
                response_format={"type": "json_object"}
            )
            
            research_text = response.choices[0].message.content
            
            # Парсити JSON відповідь
            try:
                research_data = json.loads(research_text)
                field_values = {}
                
                # Витягти значення з JSON структури
                if 'contact' in research_data:
                    contact_data = research_data['contact']
                    for field in required_fields or []:
                        # Знайти поле в contact (може бути contact.FIRSTNAME або просто FIRSTNAME)
                        field_key = field.replace('contact.', '') if 'contact.' in field else field
                        # Також перевірити без префіксу contact
                        if '.' in field_key:
                            field_key = field_key.split('.')[-1]
                        
                        if field_key in contact_data:
                            field_values[field] = contact_data[field_key]
                        elif 'company' in field.lower():
                            field_values[field] = company_name
                        else:
                            field_values[field] = contact_data.get(field_key, "N/A")
                else:
                    # Якщо структура інша, спробувати знайти поля безпосередньо
                    for field in required_fields or []:
                        field_key = field.replace('contact.', '') if 'contact.' in field else field
                        if '.' in field_key:
                            field_key = field_key.split('.')[-1]
                        
                        if field_key in research_data:
                            field_values[field] = research_data[field_key]
                        elif 'company' in field.lower():
                            field_values[field] = company_name
                        else:
                            field_values[field] = "N/A"
                
                # ОБОВ'ЯЗКОВИЙ RETRY якщо FIRSTNAME або LASTNAME = "N/A"
                needs_retry = False
                for field in required_fields or []:
                    field_key = field.replace('contact.', '') if 'contact.' in field else field
                    if '.' in field_key:
                        field_key = field_key.split('.')[-1]
                    
                    if field_key in ['FIRSTNAME', 'LASTNAME']:
                        current_value = field_values.get(field, "N/A")
                        if current_value == "N/A" or not current_value or current_value.strip() == "":
                            needs_retry = True
                            break
                
                # RETRY з максимально агресивним промптом
                if needs_retry:
                    retry_system = """You MUST find executive names. This is MANDATORY. Search EVERYWHERE.
                    - Company websites
                    - LinkedIn
                    - Business registries
                    - News articles
                    - Press releases
                    - Company profiles
                    DO NOT return "N/A" unless you searched EVERYTHING."""
                    
                    retry_prompt = f"""URGENT: Find CEO/founder/owner names for: {company_name}
                    
                    Location: {company_info.get('location', '')}
                    
                    MANDATORY SEARCH QUERIES (try ALL):
                    1. "{company_name}" CEO
                    2. "{company_name}" founder
                    3. "{company_name}" Geschäftsführer
                    4. "{company_name}" owner
                    5. "{company_name}" managing director
                    6. "{company_name}" Vorstand
                    7. Check if part of larger group - search parent company
                    8. Check franchise/chain - search regional owner
                    9. Search Handelsregister (German commercial register)
                    10. Search company website "Impressum" or "About Us"
                    
                    Search your knowledge base THOROUGHLY.
                    If company is German, check Handelsregister.
                    If company is retail/chain, check franchise owner.
                    
                    Return JSON:
                    {{
                      "contact": {{
                        "FIRSTNAME": "first name - MUST search, not N/A",
                        "LASTNAME": "last name - MUST search, not N/A"
                      }}
                    }}
                    
                    CRITICAL: Only "N/A" if you searched EVERYTHING and found NOTHING."""
                    
                    try:
                        retry_response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": retry_system},
                                {"role": "user", "content": retry_prompt}
                            ],
                            temperature=0.7,  # Вище для більш креативного пошуку
                            response_format={"type": "json_object"}
                        )
                        
                        retry_data = json.loads(retry_response.choices[0].message.content)
                        if 'contact' in retry_data:
                            retry_contact = retry_data['contact']
                            # Оновити значення
                            for field in required_fields or []:
                                field_key = field.replace('contact.', '') if 'contact.' in field else field
                                if '.' in field_key:
                                    field_key = field_key.split('.')[-1]
                                
                                if field_key in ['FIRSTNAME', 'LASTNAME']:
                                    retry_value = retry_contact.get(field_key, "N/A")
                                    if retry_value and retry_value != "N/A" and retry_value.strip():
                                        field_values[field] = retry_value
                    except Exception as retry_error:
                        print(f"Retry failed: {retry_error}")
                
                field_values['_research_text'] = research_text
                return field_values
            except json.JSONDecodeError:
                # Якщо не JSON, використати старий метод
                return self._parse_research_to_fields(research_text, required_fields, company_name, company_info)
            
        except Exception as e:
            # Return default values on error
            default_values = {}
            if required_fields:
                for field in required_fields:
                    default_values[field] = f"Error: {str(e)}"
            else:
                default_values['company_description'] = f"Error researching company: {str(e)}"
            return default_values
    
    def _parse_research_to_fields(
        self, 
        research_text: str, 
        required_fields: Optional[Set[str]],
        company_name: str,
        company_info: dict
    ) -> Dict[str, str]:
        """
        Parse research text to extract field values.
        
        This is a helper method that tries to extract specific information
        from the AI response. For now, it returns a basic structure.
        """
        field_values = {}
        
        if required_fields:
            # Try to extract specific fields from research text
            # Default: use company name for COMPANY field
            if any('company' in f.lower() for f in required_fields):
                for field in required_fields:
                    if 'company' in field.lower():
                        field_values[field] = company_name
            
            # For other fields, we'll need to extract from research text
            # For now, store the full research text
            field_values['_research_text'] = research_text
        else:
            field_values['company_description'] = research_text
        
        return field_values
    
    async def generate_email_content(
        self, 
        company_name: str, 
        company_research: Dict[str, str],
        job_title: str,
        template_content: Optional[str] = None,
        template_fields: Optional[Set[str]] = None
    ) -> str:
        """
        Generate personalized email content by filling template.
        
        Args:
            company_name: Name of the company
            company_research: Dictionary with researched information
            job_title: Job title/position
            template_content: HTML template content (if None, generates from scratch)
            template_fields: Set of template field names
            
        Returns:
            Generated email content in HTML format
        """
        try:
            if template_content:
                # Fill template with researched values
                from modules.EmailContentGenerator.template_parser import fill_template
                
                # Prepare values dictionary
                research_text = company_research.get('_research_text', '')
                
                # Use AI to extract specific field values from research
                field_values = await self._extract_field_values_from_research(
                    research_text, 
                    template_fields,
                    company_name,
                    company_research
                )
                
                # Fill template
                filled_content = fill_template(template_content, field_values)
                
                return filled_content
            else:
                # Original logic: generate from scratch
                research_text = company_research.get('company_description', company_research.get('_research_text', ''))
                
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

                About the company: {research_text}
                
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
    
    async def _extract_field_values_from_research(
        self,
        research_text: str,
        template_fields: Optional[Set[str]],
        company_name: str,
        company_research: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Use AI to extract specific field values from research text.
        """
        if not template_fields:
            return {}
        
        system_prompt = """You are a data extraction assistant. Extract specific information from company research text.
        Return ONLY the requested values. If information is not available, return "N/A"."""
        
        fields_list = ", ".join(template_fields)
        user_prompt = f"""From the following company research text, extract values for these fields: {fields_list}

        Research text:
        {research_text}
        
        Company name: {company_name}
        
        For each field, provide the value in format: FIELD_NAME: value
        If a field cannot be determined, use: FIELD_NAME: N/A"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2
            )
            
            # Parse response to extract field values
            result_text = response.choices[0].message.content
            field_values = {}
            
            for field in template_fields:
                # Try to find field value in response
                pattern = rf"{re.escape(field)}:\s*(.+?)(?=\n|$)"
                match = re.search(pattern, result_text, re.IGNORECASE)
                if match:
                    field_values[field] = match.group(1).strip()
                else:
                    # Default values based on field name
                    if 'company' in field.lower():
                        field_values[field] = company_name
                    else:
                        field_values[field] = "N/A"
            
            return field_values
            
        except Exception as e:
            # Return defaults on error
            field_values = {}
            for field in template_fields:
                if 'company' in field.lower():
                    field_values[field] = company_name
                else:
                    field_values[field] = "N/A"
            return field_values

