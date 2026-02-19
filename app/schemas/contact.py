from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class ContactRequest(BaseModel):
    """Contact form submission schema."""
    name: str
    email: EmailStr
    subject: str
    message: str
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        if len(v) > 100:
            raise ValueError('Name must be less than 100 characters')
        return v.strip()
    
    @field_validator('subject')
    @classmethod
    def validate_subject(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('Subject must be at least 3 characters long')
        if len(v) > 200:
            raise ValueError('Subject must be less than 200 characters')
        return v.strip()
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Message must be at least 10 characters long')
        if len(v) > 2000:
            raise ValueError('Message must be less than 2000 characters')
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "subject": "Question about your services",
                "message": "Hello, I would like to know more about your booking services."
            }
        }


class ContactResponse(BaseModel):
    """Response after contact form submission."""
    success: bool
    message: str