"""OpenAI service for AI operations."""

import re
import json
import os
from pathlib import Path
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
        self.temp_template_path = Path("temporary_file.html")
        self.tags_description = {}
        self._template_processed = False  # Флаг чи template вже оброблений в цій сесії
    
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
            system_prompt = """Find company executive names (CEO/founder/owner). Search: website, LinkedIn, Handelsregister. Determine industry and suitability. Return JSON."""
            
            if required_fields:
                fields_list = ", ".join(sorted(required_fields))
                user_prompt = f"""Research: {company_name}
Job: {company_info.get('title', 'N/A')}
Location: {company_info.get('location', 'N/A')}

Find: {fields_list}

Search: "{company_name} CEO", "{company_name} founder", "{company_name} Geschäftsführer", Handelsregister, LinkedIn.

NOT SUITABLE: Government, Banks, Police, IT companies.
SUITABLE: All other private companies.

Return JSON:
{{
  "contact": {{
    "COMPANY": "{company_name}",
    "FIRSTNAME": "CEO/founder first name or N/A",
    "LASTNAME": "CEO/founder last name or N/A",
    "unsubscribe": "N/A"
  }},
  "industry": "specific industry name",
  "is_suitable": true or false,
  "rejection_reason": "reason if not suitable, else empty string"
}}"""
            else:
                user_prompt = f"""Research: {company_name}
Find: business activity, industry, description.
Return JSON with contact info, industry, is_suitable, rejection_reason."""
            
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
                
                # Витягти suitability з research_data
                field_values['is_suitable'] = research_data.get('is_suitable', False)
                field_values['industry'] = research_data.get('industry', 'Unknown')
                field_values['rejection_reason'] = research_data.get('rejection_reason', '')
                
                # Витягти значення з JSON структури
                if 'contact' in research_data:
                    contact_data = research_data['contact']
                    for field in required_fields or []:
                        field_key = field.replace('contact.', '') if 'contact.' in field else field
                        if '.' in field_key:
                            field_key = field_key.split('.')[-1]
                        
                        if field_key in contact_data:
                            field_values[field] = contact_data[field_key]
                        elif 'company' in field.lower():
                            field_values[field] = company_name
                        else:
                            field_values[field] = contact_data.get(field_key, "N/A")
                else:
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
                
                field_values['_research_text'] = research_text
                return field_values
            except json.JSONDecodeError:
                parsed_values = self._parse_research_to_fields(research_text, required_fields, company_name, company_info)
                parsed_values['is_suitable'] = False
                parsed_values['industry'] = 'Unknown'
                parsed_values['rejection_reason'] = 'Failed to parse research data'
                return parsed_values
            
        except Exception as e:
            # Return default values on error
            default_values = {}
            if required_fields:
                for field in required_fields:
                    default_values[field] = f"Error: {str(e)}"
            else:
                default_values['company_description'] = f"Error researching company: {str(e)}"
            default_values['is_suitable'] = False
            default_values['industry'] = 'Unknown'
            default_values['rejection_reason'] = f'Error during research: {str(e)}'
            return default_values
    
    async def _check_company_suitability(
        self,
        company_name: str,
        company_info: dict,
        research_data: dict
    ) -> Dict[str, any]:
        """
        Check if company/vacancy is suitable based on industry.
        
        Returns:
            {
                'is_suitable': bool,
                'industry': str,
                'rejection_reason': str (if not suitable)
            }
        """
        try:
            system_prompt = """You are a company industry classifier. Your task is to:
1. Determine the company's industry/sector
2. Check if the company is suitable for our services

COMPANIES THAT ARE NOT SUITABLE (reject these):
- Government institutions (hospitals, insurance companies, fire departments, police, etc.)
- Banks and financial institutions
- Police departments and law enforcement
- IT companies and software development companies

ALL OTHER COMPANIES ARE SUITABLE (accept these):
- Manufacturing
- Retail
- Services
- Construction
- Logistics
- Hospitality
- And all other private sector companies

Return your analysis in JSON format."""
            
            # Build context from research data
            research_context = ""
            if research_data:
                if 'contact' in research_data:
                    contact = research_data.get('contact', {})
                    if isinstance(contact, dict):
                        research_context = f"Company data: {json.dumps(contact, ensure_ascii=False)}"
            
            user_prompt = f"""Analyze this company and determine if it's suitable:

Company name: {company_name}
Job title: {company_info.get('title', 'N/A')}
Location: {company_info.get('location', 'N/A')}
{research_context}

TASK:
1. Determine the company's industry/sector (e.g., "Manufacturing", "Retail", "IT", "Banking", "Healthcare", "Government", etc.)
2. Check if company is suitable:
   - NOT suitable: Government institutions, Banks, Police, IT companies
   - Suitable: All other private sector companies

Return JSON:
{{
  "industry": "specific industry name (e.g., Manufacturing, Retail, IT, Banking, Healthcare, Government, etc.)",
  "is_suitable": true or false,
  "rejection_reason": "reason why not suitable (only if is_suitable is false, otherwise empty string)"
}}

Examples:
- If company is "Deutsche Bank" → {{"industry": "Banking", "is_suitable": false, "rejection_reason": "Banking/Financial institution"}}
- If company is "Polizei Berlin" → {{"industry": "Government/Police", "is_suitable": false, "rejection_reason": "Police/Law enforcement"}}
- If company is "SAP" → {{"industry": "IT", "is_suitable": false, "rejection_reason": "IT company"}}
- If company is "BMW" → {{"industry": "Manufacturing", "is_suitable": true, "rejection_reason": ""}}
- If company is "Rewe" → {{"industry": "Retail", "is_suitable": true, "rejection_reason": ""}}"""
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Low temperature for consistent classification
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Ensure is_suitable is boolean
            is_suitable = result.get('is_suitable', False)
            if isinstance(is_suitable, str):
                is_suitable = is_suitable.lower() in ('true', '1', 'yes')
            elif not isinstance(is_suitable, bool):
                is_suitable = bool(is_suitable)
            
            return {
                'is_suitable': is_suitable,
                'industry': str(result.get('industry', 'Unknown')),
                'rejection_reason': str(result.get('rejection_reason', ''))
            }
            
        except Exception as e:
            # Fallback: assume not suitable if we can't determine
            print(f"Error checking company suitability: {e}")
            return {
                'is_suitable': False,
                'industry': 'Unknown',
                'rejection_reason': f'Error during suitability check: {str(e)}'
            }
    
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
                # Перевірити чи є оброблений template
                processed_template = await self._get_processed_template(template_content)
                
                # Підготувати field_values
                field_values = {}
                if template_fields:
                    for field in template_fields:
                        if field in company_research:
                            field_values[field] = company_research[field]
                        elif 'company' in field.lower():
                            field_values[field] = company_name
                        else:
                            field_values[field] = "N/A"
                
                # Перевірити чи template оброблений (має теги)
                found_tags = re.findall(r'\{\{([A-Z_]+)\}\}', processed_template)
                
                if not found_tags:
                    # FALLBACK: якщо template не оброблений - використати старий метод з AI
                    print("⚠️ Template not processed (no tags found), using AI fallback method")
                    print("🔄 Generating personalized HTML using old method...")
                    
                    # Генерувати персоналізований текст через AI
                    firstname = field_values.get('contact.FIRSTNAME', field_values.get('FIRSTNAME', ''))
                    lastname = field_values.get('contact.LASTNAME', field_values.get('LASTNAME', ''))
                    industry = company_research.get('industry', '')
                    
                    system_prompt = """You are an email template editor. Replace main body text with personalized content. Preserve ALL {{placeholders}}, prices, locations, HTML structure."""
                    
                    user_prompt = f"""Company: {company_name}
Recipient: {firstname} {lastname}
Job: {job_title}
Industry: {industry}

TEMPLATE:
{template_content[:5000]}

TASK: Replace ONLY the main introductory text (after greeting) with personalized text about {company_name}'s {industry} business. Keep ALL {{placeholders}}, prices, locations, HTML structure EXACTLY as is.

Return complete HTML."""
                    
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.6
                    )
                    
                    modified_template = response.choices[0].message.content.strip()
                    
                    # Extract HTML if AI wrapped it in markdown code blocks
                    if modified_template.startswith('```html'):
                        modified_template = modified_template.replace('```html', '').replace('```', '').strip()
                    elif modified_template.startswith('```'):
                        modified_template = modified_template.replace('```', '').strip()
                    
                    # Fill template placeholders with field values
                    from modules.EmailContentGenerator.template_parser import fill_template
                    filled_content = fill_template(modified_template, field_values)
                    
                    print(f"✅ Fallback method generated: {len(filled_content)} chars")
                    return filled_content
                
                # Генерувати JSON зі значеннями для тегів
                tags_json = await self._generate_tags_content(
                    processed_template,
                    company_name,
                    company_research,
                    job_title,
                    field_values
                )
                
                # Підставити значення в template
                filled_content = self._fill_tags_in_template(processed_template, tags_json, field_values)
                
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
    
    def _extract_template_style(self, template_content: str) -> str:
        """
        Extract style and structure from template without full content.
        Returns a concise description of template style/tone/structure.
        Only extracts key phrases, not full text (to save tokens).
        
        Args:
            template_content: HTML template content
            
        Returns:
            Short description of template style (max 200-300 chars)
        """
        try:
            # Extract text between tags, ignoring placeholders
            text_pattern = r'>([^<{]+?)(?=<|{{)'
            matches = re.findall(text_pattern, template_content)
            
            # Filter and collect key phrases
            key_phrases = []
            seen_phrases = set()
            
            for match in matches:
                text = match.strip()
                # Skip if placeholder, empty, or too short
                if not text or '{{' in text or len(text) < 5:
                    continue
                
                # Skip HTML/technical content
                if any(skip in text.lower() for skip in ['style=', 'class=', 'http://', 'www.', 'px', 'margin']):
                    continue
                
                # Extract meaningful phrases (sentences or key phrases)
                # Remove extra whitespace
                text = ' '.join(text.split())
                
                # Skip if already seen (avoid duplicates)
                text_lower = text.lower()
                if text_lower in seen_phrases:
                    continue
                seen_phrases.add(text_lower)
                
                # Add meaningful text (at least 10 chars, looks like content)
                if len(text) >= 10 and not text.isdigit():
                    key_phrases.append(text)
                    # Limit to 5-6 key phrases to keep it concise
                    if len(key_phrases) >= 6:
                        break
            
            # Create style description
            if key_phrases:
                # Join key phrases to show style/tone
                style_text = " | ".join(key_phrases[:5])
                # Limit total length
                if len(style_text) > 400:
                    style_text = style_text[:400] + "..."
                return style_text
            else:
                # Fallback: detect language and basic style
                if 'Guten Tag' in template_content or 'guten Tag' in template_content or 'ich hoffe' in template_content.lower():
                    return "German business email, formal professional tone, uses 'Guten Tag' greeting"
                elif 'Dear' in template_content or 'Hello' in template_content:
                    return "English business email, professional tone"
                elif 'Bonjour' in template_content or 'bonjour' in template_content:
                    return "French business email, professional tone"
                else:
                    return "Professional business email template"
        except Exception as e:
            # Ultimate fallback
            return "Professional business email template"
    
    async def _generate_personalized_text(
        self,
        template_style: str,
        company_name: str,
        company_research: Dict[str, str],
        job_title: str,
        field_values: Dict[str, str]
    ) -> str:
        """
        Generate unique personalized email text using AI, adapted to company theme.
        
        Args:
            template_style: Short description of template style
            company_name: Name of the company
            company_research: Dictionary with researched information
            job_title: Job title/position
            field_values: Dictionary with field values (FIRSTNAME, LASTNAME, etc.)
            
        Returns:
            Generated personalized text content
        """
        try:
            research_text = company_research.get('_research_text', '')
            
            # Extract company info from research (use AI to summarize if needed)
            company_info_text = ""
            if research_text:
                # Try to parse JSON research
                try:
                    research_data = json.loads(research_text)
                    # Extract any company description or business info
                    company_info_parts = []
                    if 'contact' in research_data:
                        contact = research_data['contact']
                        if isinstance(contact, dict):
                            # Get any additional company info
                            for key, value in contact.items():
                                if key not in ['FIRSTNAME', 'LASTNAME', 'COMPANY', 'unsubscribe'] and value and value != "N/A":
                                    company_info_parts.append(f"{key}: {value}")
                    
                    # Also check for other keys in research_data
                    for key, value in research_data.items():
                        if key != 'contact' and value and isinstance(value, (str, dict)):
                            if isinstance(value, str) and value != "N/A" and len(value) > 10:
                                company_info_parts.append(value)
                    
                    if company_info_parts:
                        company_info_text = " | ".join(company_info_parts[:3])  # Limit to 3 items
                    else:
                        company_info_text = f"Company: {company_name}"
                except:
                    # If not JSON, use research text directly (limited to save tokens)
                    if len(research_text) > 400:
                        # Try to extract key sentences
                        sentences = research_text.split('.')
                        key_sentences = [s.strip() for s in sentences[:3] if len(s.strip()) > 20]
                        if key_sentences:
                            company_info_text = ". ".join(key_sentences) + "."
                        else:
                            company_info_text = research_text[:400] + "..."
                    else:
                        company_info_text = research_text
            
            firstname = field_values.get('contact.FIRSTNAME', field_values.get('FIRSTNAME', ''))
            lastname = field_values.get('contact.LASTNAME', field_values.get('LASTNAME', ''))
            
            system_prompt = """You are an expert email copywriter specializing in personalized business communications. Your task is to create UNIQUE, tailored email content that:
- Matches the style and tone of the provided template reference
- Is specifically adapted to the company's business/industry/theme
- Uses completely unique wording (never reuse same phrases across companies)
- Maintains professional but warm, engaging tone
- Is personalized with the recipient's name
- Focuses on the company's specific business area and industry context

CRITICAL REQUIREMENTS:
- Create UNIQUE text for each company (don't reuse same phrases or structures)
- Adapt language, examples, and references to company's specific industry/theme
- If company is in IT: mention technology, innovation, digital solutions
- If company is in manufacturing: mention quality, production, engineering
- If company is in retail: mention customer service, products, market presence
- If company is in services: mention expertise, client satisfaction, service quality
- Keep the same general structure as template but with completely unique wording
- Make it feel personal, tailored, and specifically written for THIS company
- Use industry-appropriate terminology and examples

IMPORTANT - DO NOT INCLUDE:
- Do NOT include specific prices, rates, commissions, percentages
- Do NOT include specific locations or addresses
- Do NOT include specific proposal details or conditions
- Do NOT include lists of benefits or features
- Focus ONLY on personalized introductory text about the company and your interest in cooperation"""
            
            # Build company context for better personalization
            company_context = company_info_text if company_info_text else f"Company: {company_name}"
            if job_title:
                company_context += f" | Job posting: {job_title}"
            
            user_prompt = f"""Create personalized email text for: {company_name}

Template style reference (use as guide for tone/structure, but create COMPLETELY UNIQUE text):
{template_style}

Company information and context:
{company_context}

Recipient: {firstname} {lastname} (use name if available, otherwise use formal greeting)

TASK:
Create unique email text that:
1. Is specifically adapted to {company_name}'s business/industry theme
2. Matches the tone and structure style from template reference
3. Uses COMPLETELY different wording than template (make it unique)
4. Personalizes based on company's specific business area (use industry-appropriate language)
5. Includes appropriate greeting with recipient name if available
6. Is written in the same language as template (German if template is German, English if English, etc.)
7. Maintains professional but warm, engaging tone
8. Feels like it was written specifically for {company_name} and their industry
9. References company's business context naturally (not generic)

IMPORTANT: 
- Do NOT copy phrases from template - create new unique text
- Adapt examples and language to company's industry
- Make it feel personal and tailored to THIS specific company
- Do NOT include any proposal data (prices, rates, locations, specific offers)
- Focus on personalized introduction and interest in cooperation
- The template already contains proposal details - you only need to write the introductory text

Return ONLY the email body text (without HTML tags, without placeholders like {{contact.FIRSTNAME}}).
Write it as if it will be inserted into the template structure.
Keep it concise (2-4 paragraphs, 150-250 words).
Use natural paragraph breaks.
Focus on: greeting, appreciation for company's work, interest in cooperation - NOT on specific offers or data."""
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8  # Higher for more creativity and uniqueness
            )
            
            generated_text = response.choices[0].message.content.strip()
            return generated_text
            
        except Exception as e:
            # Fallback: return basic text
            return f"Guten Tag, {firstname if firstname else ''}\n\nWir möchten Ihnen ein Angebot für {company_name} präsentieren."
    
    async def prepare_template_with_tags(self, template_content: str) -> tuple[str, dict]:
        """
        Один раз обробляє template: замінює динамічний текст на теги.
        
        Returns:
            (modified_template, tags_description)
        """
        system_prompt = """You are a template processor. Your task is to replace ALL dynamic text content with tags like {{MAIN_MAIL}}, {{INTRO_TEXT}}, etc.

CRITICAL RULES:
1. Keep ALL HTML structure, tags, styles, attributes EXACTLY as is
2. Keep ALL {{contact.FIRSTNAME}}, {{contact.COMPANY}} placeholders EXACTLY as is - DO NOT TOUCH THEM
3. Keep ALL prices, locations, numbers, specific data EXACTLY as is
4. Keep footer, header, section titles EXACTLY as is
5. REPLACE ONLY the dynamic text paragraphs with tags

EXAMPLE:
BEFORE: <p>ich hoffe, diese Nachricht erreicht Sie in bester Verfassung. Wir möchten Ihnen ein einzigartiges Angebot...</p>
AFTER: <p>{{MAIN_MAIL}}</p>

Return JSON:
{
  "template": "full modified HTML with tags",
  "tags": {
    "{{MAIN_MAIL}}": "Main intro paragraph (2-3 sentences about company appreciation and cooperation interest)",
    "{{INTRO_TEXT}}": "Additional intro text (1-2 sentences)",
    ...
  }
}"""
        
        user_prompt = f"""Process this HTML template. Find ALL dynamic text paragraphs and replace them with tags.

FIND AND REPLACE:
- Text like "ich hoffe, diese Nachricht erreicht Sie..." → {{MAIN_MAIL}}
- Text like "Wir möchten Ihnen..." → {{INTRO_TEXT}}
- Any other dynamic personalized text → {{TAG_NAME}}

KEEP UNCHANGED:
- {{contact.FIRSTNAME}}, {{contact.COMPANY}} - DO NOT TOUCH
- Prices, numbers, locations
- Section headers like "Vorteile unseres Angebots"
- HTML structure

Template:
{template_content}

Return JSON with FULL modified template (all HTML) and tags description."""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,  # Нижче для точності
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        modified_template = result.get('template', template_content)
        tags_description = result.get('tags', {})
        
        print(f"📋 AI response received")
        print(f"📋 Modified template length: {len(modified_template)} chars")
        print(f"📋 Original template length: {len(template_content)} chars")
        print(f"📋 Tags description keys: {list(tags_description.keys())}")
        
        # ПЕРЕВІРКА чи теги створені
        found_tags = re.findall(r'\{\{([A-Z_]+)\}\}', modified_template)
        
        if not found_tags:
            print("❌ ERROR: AI did not create tags! Returning original template.")
            print(f"Template length: {len(modified_template)}")
            print(f"Template preview (first 1000 chars): {modified_template[:1000]}")
            return template_content, {}
        
        print(f"✅ Found {len(found_tags)} tags: {found_tags}")
        
        # Створити директорію якщо немає
        self.temp_template_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"📁 Directory ready: {self.temp_template_path.parent.absolute()}")
        
        # Зберегти файл
        try:
            with open(self.temp_template_path, 'w', encoding='utf-8') as f:
                f.write(modified_template)
            print(f"✅ Template file written: {self.temp_template_path.absolute()}")
            print(f"✅ File size: {self.temp_template_path.stat().st_size} bytes")
        except Exception as e:
            print(f"❌ CRITICAL ERROR saving file: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Перевірити що файл створений
        if not self.temp_template_path.exists():
            print(f"❌ CRITICAL ERROR: File does not exist after write!")
            raise Exception("File was not created after write operation!")
        
        self.tags_description = tags_description
        
        print(f"✅ Template processing COMPLETE")
        print(f"✅ File path: {self.temp_template_path.absolute()}")
        print(f"✅ Tags created: {list(tags_description.keys())}")
        
        return modified_template, tags_description
    
    async def _get_processed_template(self, original_template: str) -> str:
        """Отримує оброблений template (з тегами) або обробляє якщо немає."""
        print(f"🔍 Checking for processed template: {self.temp_template_path.absolute()}")
        print(f"🔍 Template processed flag: {self._template_processed}")
        print(f"🔍 File exists: {self.temp_template_path.exists()}")
        
        # Якщо template вже оброблений в цій сесії - читати з файлу
        if self._template_processed and self.temp_template_path.exists():
            print(f"✅ Using existing processed template from this session")
            with open(self.temp_template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"📊 Loaded template: {len(content)} chars")
                return content
        
        # ПЕРШИЙ РАЗ - ОБОВ'ЯЗКОВО обробити template
        print(f"🔄 Processing template (FIRST TIME in this session)...")
        print(f"📋 Original template length: {len(original_template)} chars")
        
        # Видалити старий файл якщо є
        if self.temp_template_path.exists():
            print(f"🗑️ Deleting old template file")
            self.temp_template_path.unlink()
        
        # Обробити template
        print(f"🚀 Starting template processing...")
        processed_template, tags_desc = await self.prepare_template_with_tags(original_template)
        self.tags_description = tags_desc
        self._template_processed = True  # Позначити що оброблено
        
        print(f"📊 Processed template: {len(processed_template)} chars")
        print(f"✅ Template file MUST be created: {self.temp_template_path.absolute()}")
        print(f"✅ File exists after processing: {self.temp_template_path.exists()}")
        
        if not self.temp_template_path.exists():
            print(f"❌ CRITICAL ERROR: File was not created!")
            raise Exception("Template file was not created!")
        
        return processed_template
    
    async def _generate_tags_content(
        self,
        template_with_tags: str,
        company_name: str,
        company_research: Dict[str, str],
        job_title: str,
        field_values: Dict[str, str]
    ) -> Dict[str, str]:
        """Генерує JSON зі значеннями для тегів у template."""
        
        # Витягнути всі теги з template
        tags = re.findall(r'\{\{([A-Z_]+)\}\}', template_with_tags)
        unique_tags = list(set(tags))
        
        print(f"🔍 Searching for tags in template ({len(template_with_tags)} chars)")
        print(f"🔍 Found tags: {unique_tags}")
        
        if not unique_tags:
            print("❌ ERROR: No tags found! Template might not be processed.")
            print("Template preview (first 500 chars):")
            print(template_with_tags[:500])
            # Шукати всі можливі теги для дебагу
            all_tags = re.findall(r'\{\{([^}]+)\}\}', template_with_tags)
            print(f"🔍 All {{}} patterns found: {all_tags[:10]}")
            return {}
        
        firstname = field_values.get('contact.FIRSTNAME', field_values.get('FIRSTNAME', ''))
        industry = company_research.get('industry', '')
        
        # Створити опис тегів для AI
        tags_info = {}
        for tag in unique_tags:
            tag_key = f"{{{{{tag}}}}}"
            if tag_key in self.tags_description:
                tags_info[tag] = self.tags_description[tag_key]
            else:
                tags_info[tag] = "Personalized content"
        
        system_prompt = """Generate personalized content for template tags. Return JSON with tag values."""
        
        user_prompt = f"""Company: {company_name}
Recipient: {firstname}
Job: {job_title}
Industry: {industry}

Generate content for these tags:
{json.dumps(tags_info, indent=2, ensure_ascii=False)}

Professional, warm tone. German language. Return JSON with tag names as keys."""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.6,
            response_format={"type": "json_object"},
            max_tokens=500
        )
        
        return json.loads(response.choices[0].message.content)
    
    def _fill_tags_in_template(
        self,
        template: str,
        tags_json: Dict[str, str],
        field_values: Dict[str, str]
    ) -> str:
        """Підставляє значення з JSON та field_values в template."""
        result = template
        
        print(f"📝 Filling template: {len(template)} chars, {len(tags_json)} tags to fill")
        
        # Підставити значення з tags_json ({{MAIN_MAIL}} тощо)
        for tag, value in tags_json.items():
            # Додати {{ }} якщо немає
            tag_with_braces = tag if tag.startswith('{{') else f'{{{{{tag}}}}}'
            if tag_with_braces in result:
                result = result.replace(tag_with_braces, value)
                print(f"✅ Replaced {tag_with_braces}")
            else:
                print(f"⚠️ Tag {tag_with_braces} not found in template")
        
        # Підставити значення з field_values ({{contact.FIRSTNAME}} тощо)
        from modules.EmailContentGenerator.template_parser import fill_template
        result = fill_template(result, field_values)
        
        print(f"📊 Final template length: {len(result)} chars")
        
        return result
    
    async def _replace_template_text(
        self, 
        template_content: str, 
        new_text: str,
        company_name: str,
        company_research: Dict[str, str]
    ) -> str:
        """
        Replace main text content in template while preserving HTML structure, placeholders,
        and all proposal data (prices, locations, specific offers).
        Uses AI to intelligently replace text while keeping data intact.
        
        Args:
            template_content: Original HTML template
            new_text: New personalized text to insert
            company_name: Name of the company (for context)
            company_research: Company research data (for context)
            
        Returns:
            Modified template with new text content
        """
        try:
            system_prompt = """You are an HTML email template editor. Your task is to replace the main email body text with new personalized text while STRICTLY preserving all important data.

CRITICAL REQUIREMENTS - DO NOT CHANGE:
1. ALL template placeholders like {{ contact.FIRSTNAME }}, {{ contact.COMPANY }} - KEEP EXACTLY AS IS
2. ALL HTML structure, tags, styles, and attributes - KEEP EXACTLY AS IS
3. ALL proposal data (prices, commissions, rates, percentages, numbers) - KEEP EXACTLY AS IS
4. ALL location information (cities, addresses, regions) - KEEP EXACTLY AS IS
5. ALL specific offers and conditions (terms, conditions, specific benefits) - KEEP EXACTLY AS IS
6. ALL structured data (lists of benefits, features, advantages) - KEEP EXACTLY AS IS
7. Section headers like "Vorteile unseres Angebots", "Benefits", etc. - KEEP EXACTLY AS IS
8. Footer text, unsubscribe links, legal text - KEEP EXACTLY AS IS
9. General tone (formal, professional) - KEEP THE SAME

WHAT TO CHANGE:
- Only replace the introductory/main body text (greeting + first few paragraphs)
- Make the text unique and personalized to the company's industry/business
- Adapt wording to company's specific business area
- Keep the same language and tone as original
- Make it feel tailored to THIS specific company

WHAT TO PRESERVE:
- All {{ placeholders }} - DO NOT TOUCH
- All numbers, prices, percentages, rates
- All location names and addresses
- All specific proposal details and conditions
- All section titles and headers
- All structured lists and benefits
- All CSS styles and HTML attributes"""
            
            user_prompt = f"""Replace the main email body text in this HTML template with new personalized text.

COMPANY: {company_name}

HTML TEMPLATE:
{template_content}

NEW PERSONALIZED TEXT TO INSERT (use this to replace main body text only):
{new_text}

STRICT INSTRUCTIONS:
1. Find the main introductory text (usually after greeting like "Guten Tag" and placeholder {{contact.FIRSTNAME}})
2. Replace ONLY the main body paragraphs with the new personalized text
3. Keep ALL {{ placeholders }} EXACTLY as they are - DO NOT MODIFY THEM
4. Keep ALL proposal data EXACTLY as is:
   - Prices, commissions, rates, percentages (e.g., "Attraktive Provision", specific numbers)
   - Locations, addresses, cities
   - Specific offers, conditions, terms
   - Lists of benefits, features, advantages
5. Keep ALL section headers EXACTLY as is (e.g., "Vorteile unseres Angebots", "Benefits")
6. Keep ALL HTML structure, tags, styles, attributes EXACTLY as they are
7. Keep the same general tone (formal, professional)
8. Make the text unique and personalized to {company_name}'s business/industry
9. Adapt wording to company's specific business area while keeping proposal data unchanged

Return the complete modified HTML template with:
- New personalized main body text
- ALL original data preserved (prices, locations, offers, conditions)
- ALL placeholders preserved
- ALL HTML structure preserved"""
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3  # Lower temperature for precise replacement
            )
            
            modified_template = response.choices[0].message.content.strip()
            
            # Extract HTML if AI wrapped it in markdown code blocks
            if modified_template.startswith('```html'):
                modified_template = modified_template.replace('```html', '').replace('```', '').strip()
            elif modified_template.startswith('```'):
                modified_template = modified_template.replace('```', '').strip()
            
            return modified_template
            
        except Exception as e:
            # If replacement fails, return original
            print(f"Error replacing template text: {e}")
            return template_content

