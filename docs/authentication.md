# Authentication Guide

This document describes how to authenticate with the Global Credit Core API.

## Overview

The API uses **JWT (JSON Web Tokens)** for authentication. Most endpoints require a valid JWT token in the Authorization header.

## Authentication Flow

### 1. Obtain a JWT Token

JWT tokens are generated using the `create_access_token()` function. In a production environment, you would typically have a dedicated authentication endpoint (e.g., `/api/v1/auth/login`).

For development and testing, you can generate tokens using the Python code:

```python
from app.core.security import create_access_token
from datetime import timedelta

# Generate token for regular user
token = create_access_token(
    data={
        "sub": "user-id",
        "email": "user@example.com",
        "role": "user"
    },
    expires_delta=timedelta(minutes=60)
)

# Generate token for admin user
admin_token = create_access_token(
    data={
        "sub": "admin-id",
        "email": "admin@example.com",
        "role": "admin"
    },
    expires_delta=timedelta(minutes=60)
)
```

### 2. Use the Token in Requests

Include the token in the `Authorization` header of your requests:

```
Authorization: Bearer <your-jwt-token>
```

## Endpoint Security

### Public Endpoints (No Authentication Required)

- `GET /health` - Health check
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation
- `GET /api/v1/applications/meta/supported-countries` - Supported countries list

### Protected Endpoints (Authentication Required)

These endpoints require a valid JWT token with any role:

- `POST /api/v1/applications` - Create application
- `GET /api/v1/applications` - List applications
- `GET /api/v1/applications/{id}` - Get application by ID
- `GET /api/v1/applications/{id}/audit` - Get application audit logs
- `GET /api/v1/applications/stats/country/{country_code}` - Get country statistics

### Admin-Only Endpoints

These endpoints require a JWT token with `role: "admin"`:

- `PATCH /api/v1/applications/{id}` - Update application
- `DELETE /api/v1/applications/{id}` - Delete application

### Webhook Endpoints

Webhook endpoints use HMAC-SHA256 signature verification instead of JWT:

- `POST /api/v1/webhooks/bank-confirmation` - Requires `X-Webhook-Signature` header

## Using Swagger UI

1. Navigate to `/docs` in your browser
2. Click the **"Authorize"** button at the top right
3. Enter your token in the format: `Bearer <your-token>`
   - Example: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
4. Click "Authorize"
5. All authenticated requests will now include the token automatically

## Examples

### cURL Examples

#### Create Application (Authenticated)

```bash
# Set your token
TOKEN="your-jwt-token-here"

# Create application
curl -X POST "http://localhost:8000/api/v1/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "ES",
    "full_name": "Juan Pérez García",
    "identity_document": "12345678Z",
    "requested_amount": 10000.00,
    "monthly_income": 3000.00,
    "country_specific_data": {}
  }'
```

#### List Applications (Authenticated)

```bash
curl -X GET "http://localhost:8000/api/v1/applications" \
  -H "Authorization: Bearer $TOKEN"
```

#### Get Application by ID (Authenticated)

```bash
APPLICATION_ID="your-application-id"
curl -X GET "http://localhost:8000/api/v1/applications/$APPLICATION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

#### Update Application (Admin Only)

```bash
ADMIN_TOKEN="your-admin-jwt-token-here"
APPLICATION_ID="your-application-id"

curl -X PATCH "http://localhost:8000/api/v1/applications/$APPLICATION_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "APPROVED",
    "risk_score": 75.5
  }'
```

#### Delete Application (Admin Only)

```bash
curl -X DELETE "http://localhost:8000/api/v1/applications/$APPLICATION_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Python Examples

#### Using httpx (Async)

```python
import httpx
import asyncio

async def create_application():
    token = "your-jwt-token-here"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/applications",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "country": "ES",
                "full_name": "Juan Pérez García",
                "identity_document": "12345678Z",
                "requested_amount": 10000.00,
                "monthly_income": 3000.00,
                "country_specific_data": {}
            }
        )
        return response.json()

# Run
result = asyncio.run(create_application())
print(result)
```

#### Using requests (Sync)

```python
import requests

token = "your-jwt-token-here"

response = requests.post(
    "http://localhost:8000/api/v1/applications",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    json={
        "country": "ES",
        "full_name": "Juan Pérez García",
        "identity_document": "12345678Z",
        "requested_amount": 10000.00,
        "monthly_income": 3000.00,
        "country_specific_data": {}
    }
)

print(response.json())
```

### JavaScript/TypeScript Examples

#### Using fetch

```javascript
const token = "your-jwt-token-here";

const response = await fetch("http://localhost:8000/api/v1/applications", {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    country: "ES",
    full_name: "Juan Pérez García",
    identity_document: "12345678Z",
    requested_amount: 10000.00,
    monthly_income: 3000.00,
    country_specific_data: {}
  })
});

const data = await response.json();
console.log(data);
```

#### Using axios

```javascript
const axios = require('axios');

const token = "your-jwt-token-here";

const response = await axios.post(
  "http://localhost:8000/api/v1/applications",
  {
    country: "ES",
    full_name: "Juan Pérez García",
    identity_document: "12345678Z",
    requested_amount: 10000.00,
    monthly_income: 3000.00,
    country_specific_data: {}
  },
  {
    headers: {
      "Authorization": `Bearer ${token}`
    }
  }
);

console.log(response.data);
```

## Error Responses

### 401 Unauthorized

Returned when:
- No token is provided
- Token is invalid or expired
- Token format is incorrect

```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden

Returned when:
- Token is valid but user doesn't have required role (e.g., admin)
- Endpoint requires authentication but token is missing

```json
{
  "detail": "Operation forbidden: Admin privileges required"
}
```

## Token Structure

JWT tokens contain the following claims:

- `sub`: User identifier
- `email`: User email
- `role`: User role (`user` or `admin`)
- `exp`: Expiration timestamp
- `iat`: Issued at timestamp

## Token Expiration

By default, tokens expire after **60 minutes**. This can be configured via the `JWT_EXPIRATION_MINUTES` environment variable.

## Security Best Practices

1. **Never commit tokens to version control**
2. **Use HTTPS in production** - Never send tokens over unencrypted connections
3. **Store tokens securely** - Use environment variables or secure storage
4. **Rotate tokens regularly** - Generate new tokens periodically
5. **Validate tokens on the client** - Check expiration before making requests
6. **Use appropriate roles** - Only grant admin tokens to trusted users

## Webhook Authentication

Webhooks use HMAC-SHA256 signature verification instead of JWT. See `docs/webhooks.md` for details.

## Troubleshooting

### Token Not Working

1. Verify the token format: `Bearer <token>` (note the space)
2. Check token expiration
3. Ensure the token was generated with the correct secret
4. Verify the `Authorization` header is being sent correctly

### Getting 403 Forbidden

1. Check if the endpoint requires admin role
2. Verify your token has the correct role claim
3. Ensure you're using an admin token for admin-only endpoints

### Getting 401 Unauthorized

1. Verify the token is included in the request
2. Check token expiration
3. Ensure the token was generated with the same secret as the server

## Additional Resources

- [JWT.io](https://jwt.io/) - JWT token decoder and validator
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) - FastAPI security documentation
- [OpenAPI Specification](https://swagger.io/specification/) - OpenAPI security schemes
