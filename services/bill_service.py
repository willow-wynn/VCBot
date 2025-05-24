"""
Bill service for handling legislative document operations.
"""

import os
import re
import json
import traceback
from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any
from google.genai import types
import requests
import geminitools
from pydantic import BaseModel
from pathlib import Path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exceptions import BillProcessingError, NetworkError, ParseError, AIServiceError
from logging_config import logger


class BillReferenceResponse(BaseModel):
    """Response schema for bill reference detection."""
    is_reference: bool
    bill_type: str
    reference_number: int


@dataclass
class BillResult:
    """Result of adding a bill to database."""
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    bill_name: Optional[str] = None


@dataclass
class ReferenceUpdate:
    """Result of updating a bill reference."""
    success: bool
    message: str
    bill_type: Optional[str] = None
    reference_number: Optional[int] = None


class BillService:
    """Service for handling bill-related operations."""
    
    def __init__(self, genai_client, bill_directories: Dict[str, str], file_manager=None):
        """Initialize bill service.
        
        Args:
            genai_client: Google Generative AI client
            bill_directories: Dictionary of bill storage directories
            file_manager: FileManager instance for file operations
        """
        self.genai_client = genai_client
        self.bill_directories = bill_directories
        self.file_manager = file_manager
    
    async def add_bill(self, bill_link: str, database_type: Literal["bills"]) -> BillResult:
        """Add a bill to the database.
        
        Args:
            bill_link: Google Docs link to the bill
            database_type: Type of database to add to
            
        Returns:
            BillResult with success status and file path
            
        Raises:
            BillProcessingError: If bill processing fails
            NetworkError: If network request fails
        """
        try:
            # Fetch bill text
            bill_text = geminitools.fetch_public_gdoc_text(bill_link)
            if not bill_text.strip():
                raise BillProcessingError("Empty bill text retrieved from link")
            
            # Generate filename using AI
            resp = self.genai_client.models.generate_content(
                model="gemini-2.0-flash-exp",
                config=types.GenerateContentConfig(
                    system_instruction="Generate a filename for the bill. The filename should be in the format of 'Bill Title.txt'. The title should be a short description of the bill."
                ),
                contents=[types.Content(role='user', parts=[types.Part.from_text(text=bill_text)])]
            )
            
            if not resp.text:
                raise AIServiceError("Failed to generate bill filename")
            
            bill_name = self._sanitize_filename(resp.text)
            if not bill_name.lower().endswith(".txt"):
                bill_name += ".txt"
            
            # Save text file
            bill_dir = self.bill_directories[database_type]
            if self.file_manager:
                # Use FileManager for file operations
                if not self.file_manager.directory_exists(bill_dir):
                    raise BillProcessingError(f"Bill directory does not exist: {bill_dir}")
                
                bill_location = self.file_manager.save_text(
                    content=bill_text,
                    filename=bill_name,
                    directory=bill_dir
                )
                bill_location = str(bill_location)  # Convert Path to string for compatibility
            else:
                # Fallback to direct file operations
                if not Path(bill_dir).exists():
                    raise BillProcessingError(f"Bill directory does not exist: {bill_dir}")
                
                bill_location = str(Path(bill_dir) / bill_name)
                with open(bill_location, "w", encoding="utf-8") as f:
                    f.write(bill_text)
            
            # Try to download PDF version
            pdf_path = await self._download_bill_pdf(bill_link, bill_name)
            
            # Embed the text file
            from makeembeddings import embed_txt_file
            embed_txt_file(bill_location)
            logger.info(f"Added bill '{bill_name}' to embeddings")
            
            return BillResult(
                success=True,
                file_path=bill_location,
                bill_name=bill_name
            )
            
        except (BillProcessingError, NetworkError, AIServiceError):
            raise
        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch bill from link: {str(e)}",
                             context={"bill_link": bill_link})
        except Exception as e:
            raise BillProcessingError(f"Unexpected error adding bill: {str(e)}",
                                    context={"bill_link": bill_link, "database_type": database_type})
    
    async def generate_economic_impact(self, bill_link: str, 
                                     recent_news: list,
                                     additional_context: str = None) -> str:
        """Generate economic impact report for a bill.
        
        Args:
            bill_link: Google Docs link to the bill
            recent_news: List of recent news messages
            additional_context: Optional additional context
            
        Returns:
            Economic impact report text
            
        Raises:
            BillProcessingError: If bill processing fails
            NetworkError: If network request fails
            AIServiceError: If AI generation fails
        """
        try:
            # Fetch bill text
            bill_text = geminitools.fetch_public_gdoc_text(bill_link)
            if not bill_text.strip():
                raise BillProcessingError("Empty bill text retrieved from link")
            
            # Build system prompt
            system_prompt = f"""You are a legislative assistant for the Virtual Congress Discord server. You are given a chunk of text from a legislative document.
    You will be generating an economic impact statement that indicates how such a bill would impact the economy.
    Your goal is to generate a full detailed economic impact statement.
    Recent news is presented below: {recent_news}.
    You will be provided a bill by the user."""
            
            if additional_context:
                system_prompt += f"\n The user has provided additional information for you regarding the intended contents of your economic impact report: {additional_context}"
            
            # Generate report
            response = self.genai_client.models.generate_content(
                model='gemini-2.0-flash-exp',
                config=types.GenerateContentConfig(
                    tools=None,
                    system_instruction=system_prompt
                ),
                contents=[types.Content(role='user', parts=[types.Part.from_text(text=bill_text)])]
            )
            
            if not response.text:
                raise AIServiceError("Empty response from AI model for economic impact")
            
            return response.text
            
        except (BillProcessingError, NetworkError, AIServiceError):
            raise
        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch bill for economic impact: {str(e)}",
                             context={"bill_link": bill_link})
        except Exception as e:
            raise BillProcessingError(f"Failed to generate economic impact: {str(e)}",
                                    context={"bill_link": bill_link})
    
    async def update_reference(self, message_content: str) -> ReferenceUpdate:
        """Update bill reference from message content.
        
        Args:
            message_content: The message to analyze
            
        Returns:
            ReferenceUpdate with results
        """
        try:
            response = self.genai_client.models.generate_content(
                model="gemini-2.0-flash-thinking-exp",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BillReferenceResponse,
                    system_instruction="""You are a helper for the Virtual Congress Discord server. Your goal is to determine whether or not the current message contains a bill reference.

                    Analyze the message and determine:
                    - is_reference: True if the message contains a bill reference (like H.R.123, H.RES.45, etc.), False otherwise
                    - bill_type: If it's a reference, extract the bill type (hr, hres, hjres, hconres). If not a reference, use empty string "".
                    - reference_number: If it's a reference, extract the bill number. If not a reference, use 0.
                    
                    You MUST provide all three fields in your response. Never omit any field.
                    
                    Examples of bill references: H.R.123, H.RES.45, H.J.RES.12, H.CON.RES.8, **H.C.REP.4**
                    """
                ),
                contents=[types.Content(role='user', parts=[types.Part.from_text(text=message_content)])],
            )
            
            # Parse response
            respdict = json.loads(response.text)
            
            if not respdict.get("is_reference"):
                return ReferenceUpdate(success=False, message="No bill reference found")
            
            bill_type = respdict["bill_type"]
            reference_number = respdict["reference_number"]
            
            # Validate
            if not bill_type or reference_number <= 0:
                return ReferenceUpdate(
                    success=False,
                    message=f"Invalid bill reference data: type='{bill_type}', number={reference_number}"
                )
            
            return ReferenceUpdate(
                success=True,
                bill_type=bill_type,
                reference_number=reference_number,
                message=f"Found {bill_type.upper()} {reference_number}"
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in update_reference: {e}")
            return ReferenceUpdate(success=False, message="Failed to parse AI response")
        except Exception as e:
            logger.exception(f"Unexpected error in update_reference")
            return ReferenceUpdate(success=False, message=f"Error: {e}")
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for safe file system use."""
        name = re.sub(r'[^\w\s.-]', '', name)
        return name.strip()
    
    async def _download_bill_pdf(self, bill_link: str, bill_name: str) -> Optional[str]:
        """Try to download PDF version of a bill.
        
        Args:
            bill_link: Google Docs link
            bill_name: Base filename
            
        Returns:
            Path to PDF if successful, None otherwise
        """
        try:
            # Extract Google Doc ID
            file_id_match = re.search(r"/document/d/([a-zA-Z0-9-_]+)", bill_link)
            if not file_id_match:
                return None
            
            file_id = file_id_match.group(1)
            pdf_url = f"https://docs.google.com/document/d/{file_id}/export?format=pdf"
            
            resp_pdf = requests.get(pdf_url)
            if resp_pdf.status_code != 200:
                return None
            
            # Prepare PDF filename
            pdf_name = bill_name[:-4] + ".pdf" if bill_name.lower().endswith(".txt") else bill_name + ".pdf"
            pdf_dir = self.bill_directories.get("billpdfs")
            if not pdf_dir:
                return None
            
            if self.file_manager:
                # Use FileManager for file operations
                pdf_path = self.file_manager.save_bytes(
                    content=resp_pdf.content,
                    filename=pdf_name,
                    directory=pdf_dir
                )
                pdf_path = str(pdf_path)  # Convert Path to string for compatibility
            else:
                # Fallback to direct file operations
                Path(pdf_dir).mkdir(parents=True, exist_ok=True)
                pdf_path = str(Path(pdf_dir) / pdf_name)
                
                with open(pdf_path, "wb") as pdf_file:
                    pdf_file.write(resp_pdf.content)
            
            logger.info(f"Downloaded PDF: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.warning(f"Failed to download PDF for bill: {e}")
            return None