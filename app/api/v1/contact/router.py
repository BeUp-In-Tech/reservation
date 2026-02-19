from fastapi import APIRouter, HTTPException
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.email_service import EmailService

router = APIRouter()

@router.post("/contact", response_model=ContactResponse)
async def submit_contact_form(contact: ContactRequest):
    """
    Submit contact form - sends email to admin.
    
    This endpoint:
    - Receives contact form data (name, email, subject, message)
    - Validates the input
    - Sends email notification to admin
    - Returns success/failure response
    """
    try:
        # Send email to admin
        success = await EmailService.send_contact_form_to_admin(
            name=contact.name,
            email=contact.email,
            subject=contact.subject,
            message=contact.message
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to send contact form. Please try again later."
            )
        
        return ContactResponse(
            success=True,
            message="Thank you for contacting us! We'll get back to you soon."
        )
        
    except Exception as e:
        print(f"[CONTACT ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request."
        )