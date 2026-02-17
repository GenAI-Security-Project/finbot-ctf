from fastapi import Request, Form, HTTPException
from finbot.agents.workflow_runner import run_invoice_lifecycle_workflow
from finbot.core.templates import TemplateResponse
from fastapi.responses import HTMLResponse
from fastapi import APIRouter
router = APIRouter()

import asyncio

template_response = TemplateResponse("finbot/apps/web/templates")

@router.get("/admin-dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # Default to fraud agent enabled on initial load
    return template_response(request, "pages/admin-dashboard.html", {"fraud_enabled": True})

@router.post("/admin-dashboard", response_class=HTMLResponse)
async def admin_dashboard_post(request: Request, csrf_token: str = Form(None)):
    # Debug: Log what we receive
    import logging
    logger = logging.getLogger(__name__)
    
    # Get form data from request.state (set by CSRF middleware)
    form_data = getattr(request.state, 'form_data', None)
    
    if form_data is None:
        # Fallback: try to read it ourselves (shouldn't happen)
        logger.warning("Form data not found in request.state, reading directly")
        form_data = await request.form()
    
    logger.info(f"Full form data: {dict(form_data)}")
    logger.info(f"enable_fraud_agent values: {form_data.getlist('enable_fraud_agent')}")
    
    # Get the last value (checkbox overrides hidden field if checked)
    all_values = form_data.getlist('enable_fraud_agent')
    fraud_agent_value = all_values[-1] if all_values else "false"
    logger.info(f"Using value: {fraud_agent_value!r}")
    
    # Convert to boolean
    fraud_enabled = fraud_agent_value == "true"
    logger.info(f"Calculated fraud_enabled: {fraud_enabled}")
    logger.info(f"Will pass to template: fraud_enabled={fraud_enabled}")
    
    # Run workflow and save settings
    result = await run_invoice_lifecycle_workflow(enable_fraud_agent=fraud_enabled)
    
    # Log what we're about to return
    logger.info(f"Returning to template with fraud_enabled={fraud_enabled}")
    
    # Return with saved state and results
    return template_response(request, "pages/admin-dashboard.html", {
        "result": result, 
        "fraud_enabled": fraud_enabled,
        "settings_saved": True
    })


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return template_response(request, "pages/home.html")


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """About page"""
    return template_response(request, "pages/about.html")


@router.get("/work", response_class=HTMLResponse)
async def work(request: Request):
    """Our Work page"""
    return template_response(request, "pages/work.html")


@router.get("/partners", response_class=HTMLResponse)
async def partners(request: Request):
    """Partners page"""
    return template_response(request, "pages/partners.html")


@router.get("/careers", response_class=HTMLResponse)
async def careers(request: Request):
    """Careers page"""
    return template_response(request, "pages/careers.html")


@router.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    """Contact page"""
    return template_response(request, "pages/contact.html")


@router.get("/portals", response_class=HTMLResponse)
async def portals(request: Request):
    """Portals page - access vendor, admin, and CTF portals"""
    return template_response(request, "pages/portals.html")


# Test routes for error pages (for development/testing)
@router.get("/test/404")
async def test_404():
    """Test 404 error page"""
    raise HTTPException(status_code=404, detail="Test 404 error")


# API test routes to demonstrate JSON error responses
@router.get("/api/test/404")
async def api_test_404():
    """Test 404 API error response"""
    raise HTTPException(status_code=404, detail="API endpoint not found")


@router.get("/api/test/500")
async def api_test_500():
    """Test 500 API error response"""
    raise HTTPException(status_code=500, detail="Internal API error")


@router.get("/test/403")
async def test_403():
    """Test 403 error page"""
    raise HTTPException(status_code=403, detail="Test 403 error")


@router.get("/test/400")
async def test_400():
    """Test 400 error page"""
    raise HTTPException(status_code=400, detail="Test 400 error")


@router.get("/test/500")
async def test_500():
    """Test 500 error page"""
    raise HTTPException(status_code=500, detail="Test 500 error")


@router.get("/test/503")
async def test_503():
    """Test 503 error page"""
    raise HTTPException(status_code=503, detail="Test 503 error")


@router.post("/run-workflow")
async def run_workflow(request: Request, enable_fraud_agent: bool = Form(True)):
    # Call the runner with the flag
    result = await run_invoice_lifecycle_workflow(enable_fraud_agent=enable_fraud_agent)
    return template_response(request, "pages/workflow_result.html", {"result": result})
