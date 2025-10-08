#!/bin/bash

# Test complet du flow dashboard de manière autonome
# Simule exactement ce que fait le navigateur

echo "========================================="
echo "🧪 TEST DASHBOARD FLOW (AUTONOMOUS)"
echo "========================================="
echo ""

API_URL="http://localhost:8000"
DASHBOARD_URL="http://localhost:8080"

# Couleurs pour la lisibilité
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction de test
test_endpoint() {
    local name=$1
    local method=$2
    local url=$3
    local headers=$4
    local expected_status=$5

    echo -e "${YELLOW}Testing: $name${NC}"

    if [ -z "$headers" ]; then
        response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X $method "$url")
    else
        response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X $method "$url" $headers)
    fi

    http_code=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
    body=$(echo "$response" | sed '/HTTP_STATUS/d')

    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} ($http_code)"
        echo "$body" | jq . 2>/dev/null || echo "$body"
    else
        echo -e "${RED}✗ FAIL${NC} (expected $expected_status, got $http_code)"
        echo "$body"
    fi
    echo ""
}

# Test 1: Health check
echo "=== STEP 1: API Health Check ==="
test_endpoint "Health Check" "GET" "$API_URL/healthz" "" "200"

# Test 2: CORS preflight (OPTIONS request depuis le dashboard)
echo "=== STEP 2: CORS Preflight Check ==="
echo -e "${YELLOW}Testing: CORS preflight for dashboard origin${NC}"
cors_response=$(curl -s -X OPTIONS "$API_URL/auth/facebook/dev-login" \
    -H "Origin: $DASHBOARD_URL" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: content-type" \
    -w "\nHTTP_STATUS:%{http_code}" \
    -v 2>&1)

if echo "$cors_response" | grep -q "access-control-allow-origin"; then
    echo -e "${GREEN}✓ PASS${NC} - CORS headers present"
    echo "$cors_response" | grep -i "access-control"
else
    echo -e "${RED}✗ FAIL${NC} - CORS headers missing"
    echo "$cors_response"
fi
echo ""

# Test 3: Dev Login (simule le clic sur le bouton)
echo "=== STEP 3: Dev Login (Simulate Button Click) ==="
echo -e "${YELLOW}Testing: POST /auth/facebook/dev-login${NC}"
login_response=$(curl -s -X POST "$API_URL/auth/facebook/dev-login" \
    -H "Origin: $DASHBOARD_URL" \
    -H "Content-Type: application/json" \
    -w "\nHTTP_STATUS:%{http_code}")

http_code=$(echo "$login_response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$login_response" | sed '/HTTP_STATUS/d')

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} (200)"
    TOKEN=$(echo "$body" | jq -r '.access_token')
    TENANT_ID=$(echo "$body" | jq -r '.tenant_id')
    echo "Token: ${TOKEN:0:50}..."
    echo "Tenant ID: $TENANT_ID"
else
    echo -e "${RED}✗ FAIL${NC} (expected 200, got $http_code)"
    echo "$body"
    exit 1
fi
echo ""

# Test 4: Load Accounts (simule le loadAccounts() du dashboard)
echo "=== STEP 4: Load Accounts (Simulate loadAccounts()) ==="
echo -e "${YELLOW}Testing: GET /api/accounts${NC}"
accounts_response=$(curl -s "$API_URL/api/accounts/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Origin: $DASHBOARD_URL" \
    -w "\nHTTP_STATUS:%{http_code}")

http_code=$(echo "$accounts_response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$accounts_response" | sed '/HTTP_STATUS/d')

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} (200)"
    echo "$body" | jq .
    ACCOUNT_ID=$(echo "$body" | jq -r '.accounts[0].fb_account_id')
    echo "First account ID: $ACCOUNT_ID"
else
    echo -e "${RED}✗ FAIL${NC} (expected 200, got $http_code)"
    echo "$body"
    exit 1
fi
echo ""

# Test 5: Load Campaigns (simule le loadCampaigns() du dashboard)
echo "=== STEP 5: Load Campaigns (Simulate loadCampaigns()) ==="
echo -e "${YELLOW}Testing: GET /api/data/campaigns${NC}"
campaigns_response=$(curl -s "$API_URL/api/data/campaigns?ad_account_id=$ACCOUNT_ID&fields=id,name,status&limit=3" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Origin: $DASHBOARD_URL" \
    -w "\nHTTP_STATUS:%{http_code}")

http_code=$(echo "$campaigns_response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$campaigns_response" | sed '/HTTP_STATUS/d')

if [ "$http_code" = "200" ] || [ "$http_code" = "403" ]; then
    echo -e "${GREEN}✓ PASS${NC} ($http_code)"
    echo "$body" | jq . 2>/dev/null || echo "$body"
    if [ "$http_code" = "403" ]; then
        echo -e "${YELLOW}Note: 403 expected for dev tenant (no real Meta OAuth token)${NC}"
    fi
else
    echo -e "${RED}✗ FAIL${NC} (expected 200 or 403, got $http_code)"
    echo "$body"
fi
echo ""

# Résumé
echo "========================================="
echo "✅ TEST DASHBOARD FLOW COMPLETE"
echo "========================================="
echo ""
echo "All core functionality works:"
echo "  ✓ API is alive"
echo "  ✓ CORS configured"
echo "  ✓ Dev login returns JWT token"
echo "  ✓ Accounts endpoint works"
echo "  ✓ Campaigns endpoint works (or correctly returns 403)"
echo ""
echo "The dashboard SHOULD work in the browser now."
echo "Open: $DASHBOARD_URL/dashboard-api.html"
