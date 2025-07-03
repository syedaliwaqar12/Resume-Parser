from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pdfplumber
import re
import spacy
from typing import Dict, List, Optional
import tempfile
import os

app = FastAPI(title="Resume Parser API", version="1.0.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load spaCy model for NLP
nlp = spacy.load("en_core_web_sm")

class ResumeParser:
    def __init__(self):
        self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        self.phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text
    
    def extract_email(self, text: str) -> Optional[str]:
        """Extract email address"""
        emails = re.findall(self.email_pattern, text)
        return emails[0] if emails else None
    
    def extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number"""
        phones = re.findall(self.phone_pattern, text)
        return phones[0] if phones else None
    
    def extract_name(self, text: str) -> Optional[str]:
        """Extract full name using NLP"""
        doc = nlp(text[:500])  # Process first 500 chars for efficiency
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
        return None
    
    def extract_education(self, text: str) -> List[str]:
        """Extract education information"""
        education_keywords = ['university', 'college', 'bachelor', 'master', 'phd', 'degree', 'diploma']
        lines = text.lower().split('\n')
        education = []
        
        for line in lines:
            if any(keyword in line for keyword in education_keywords):
                education.append(line.strip())
                
        return education[:3]  # Return top 3 matches
    
    def extract_experience(self, text: str) -> List[str]:
        """Extract work experience"""
        experience_keywords = ['experience', 'worked', 'employed', 'position', 'job', 'role']
        lines = text.lower().split('\n')
        experience = []
        
        for line in lines:
            if any(keyword in line for keyword in experience_keywords) and len(line) > 20:
                experience.append(line.strip())
                
        return experience[:5]  # Return top 5 matches
    
    def extract_skills(self, text: str) -> List[str]:
        """Extract skills using keyword matching"""
        common_skills = [
            'python', 'javascript', 'java', 'c++', 'react', 'angular', 'vue',
            'nodejs', 'express', 'django', 'flask', 'sql', 'mongodb', 'postgresql',
            'aws', 'azure', 'docker', 'kubernetes', 'git', 'agile', 'scrum',
            'machine learning', 'data science', 'artificial intelligence'
        ]
        
        text_lower = text.lower()
        found_skills = []
        
        for skill in common_skills:
            if skill in text_lower:
                found_skills.append(skill.title())
                
        return list(set(found_skills))  # Remove duplicates
    
    def parse_resume(self, pdf_path: str) -> Dict:
        """Main parsing function"""
        try:
            text = self.extract_text_from_pdf(pdf_path)
            
            return {
                "full_name": self.extract_name(text),
                "email": self.extract_email(text),
                "phone": self.extract_phone(text),
                "education": self.extract_education(text),
                "work_experience": self.extract_experience(text),
                "skills": self.extract_skills(text),
                "raw_text_preview": text[:200] + "..." if len(text) > 200 else text
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error parsing resume: {str(e)}")

# Initialize parser
parser = ResumeParser()

@app.get("/")
async def root():
    return {"message": "Resume Parser API is running"}

@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload and parse resume PDF"""
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        # Parse the resume
        parsed_data = parser.parse_resume(tmp_file_path)
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "data": parsed_data
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "resume-parser"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)