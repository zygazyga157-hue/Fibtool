"""
Simple test script using curl commands.
Run this in PowerShell after starting the server.
"""

# Test 1: Health Check
Write-Host "`n=== Testing Health Check ===" -ForegroundColor Cyan
curl http://localhost:8000/health

# Test 2: Root Endpoint
Write-Host "`n=== Testing Root Endpoint ===" -ForegroundColor Cyan
curl http://localhost:8000/

# Test 3: Get Plans (No auth required)
Write-Host "`n=== Testing Get Plans ===" -ForegroundColor Cyan
curl http://localhost:8000/api/v1/plans

# Test 4: Register User
Write-Host "`n=== Testing User Registration ===" -ForegroundColor Cyan
$registerBody = @{
    email = "testuser@example.com"
    password = "testpass123"
    name = "Test User"
} | ConvertTo-Json

curl -Method POST -Uri "http://localhost:8000/api/v1/auth/register" `
     -ContentType "application/json" `
     -Body $registerBody

# Test 5: Login User
Write-Host "`n=== Testing User Login ===" -ForegroundColor Cyan
$loginBody = @{
    email = "testuser@example.com"
    password = "testpass123"
} | ConvertTo-Json

$loginResponse = curl -Method POST -Uri "http://localhost:8000/api/v1/auth/login" `
     -ContentType "application/json" `
     -Body $loginBody | ConvertFrom-Json

$token = $loginResponse.access_token
Write-Host "Token: $token" -ForegroundColor Green

# Test 6: Get Current User
Write-Host "`n=== Testing Get Current User ===" -ForegroundColor Cyan
curl -Uri "http://localhost:8000/api/v1/auth/me" `
     -Headers @{Authorization = "Bearer $token"}

# Test 7: Get Dashboard
Write-Host "`n=== Testing Dashboard ===" -ForegroundColor Cyan
curl -Uri "http://localhost:8000/api/v1/dashboard" `
     -Headers @{Authorization = "Bearer $token"}

Write-Host "`n=== All Basic Tests Complete ===" -ForegroundColor Green
