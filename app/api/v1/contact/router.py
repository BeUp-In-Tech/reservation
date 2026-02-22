from fastapi import APIRouter, HTTPException, status
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.email_service import EmailService

router = APIRouter()

@router.post("/contact", response_model=ContactResponse)
async def submit_contact_form(contact: ContactRequest):
    """
    Submit contact form - sends email to admin using Resend.
    """
    try:
        success = await EmailService.send_contact_form_to_admin(
            name=contact.name,
            email=contact.email,
            subject=contact.subject,
            message=contact.message,
        )

        if not success:
            # Email/Resend failed
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service unavailable. Please try again later.",
            )

        return ContactResponse(
            success=True,
            message="Thank you for contacting us! We'll get back to you soon.",
        )

    except HTTPException:
        # Let FastAPI return the same HTTPException we raised
        raise

    except Exception as e:
        print(f"[CONTACT ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service unavailable. Please try again later.",
        )