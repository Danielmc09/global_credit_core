from typing import Callable

from fastapi import FastAPI


def get_custom_openapi(app: FastAPI) -> Callable:
    """Create a custom OpenAPI schema function for the FastAPI app.
    
    This function returns a callable that will be assigned to app.openapi.
    It adds:
    - Enhanced API description with authentication instructions
    - JWT Bearer token security scheme
    - Security configuration for protected endpoints
    
    Args:
        app: The FastAPI application instance
        
    Returns:
        A callable that generates the custom OpenAPI schema
    """
    # Save the original FastAPI openapi function
    _original_openapi = app.openapi
    
    def custom_openapi():
        """Generate custom OpenAPI schema with security configuration."""
        if app.openapi_schema:
            return app.openapi_schema
            
        # Use the original FastAPI openapi function to avoid recursion
        openapi_schema = _original_openapi()
        
        # Add enhanced description with authentication instructions
        openapi_schema["info"]["description"] = """
            Multi-country credit application system with async processing.

            ## Authentication

            This API uses JWT (JSON Web Tokens) for authentication. To use protected endpoints:

            1. Obtain a JWT token (see `/docs` for authentication endpoint or check `docs/authentication.md`)
            2. Click the **"Authorize"** button above
            3. Enter your token in the format: `Bearer <your-token>`
            4. All authenticated requests will include the token in the Authorization header

            ## Security

            - **JWT Tokens**: Required for most endpoints (except health check and docs)
            - **Admin Role**: Required for PATCH and DELETE operations on applications
            - **Webhook Signatures**: Required for webhook endpoints (HMAC-SHA256)

            For more details, see `docs/authentication.md`
        """
        
        # Ensure components dict exists
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
            
        # Add security schemes
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter your JWT token. Format: Bearer <token>"
            }
        }
        
        # Cache the schema
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    return custom_openapi
