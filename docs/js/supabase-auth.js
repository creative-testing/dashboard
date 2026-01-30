/**
 * Supabase Auth Integration for Insights
 *
 * This module handles:
 * 1. Login via Supabase Auth with Facebook provider
 * 2. Syncing the Facebook token with Insights backend
 * 3. Managing auth state
 *
 * @version 2.0.0
 */

// Supabase Configuration
const SUPABASE_URL = 'https://romjdysjrgyzhlnrduro.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbWpkeXNqcmd5emhsbnJkdXJvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjQzMzc2NzMsImV4cCI6MjAzOTkxMzY3M30.qjCoEYFqFmGPO8V4k4sessNgHZLqoRU7OI2WG6NJPWE';
const INSIGHTS_API_URL = 'https://insights.theaipipe.com';

// Initialize Supabase client (loaded via CDN)
// Note: window.supabase is the SDK, _supabaseClient is our instance
let _supabaseClient = null;

function initSupabase() {
    if (_supabaseClient) {
        return true; // Already initialized
    }
    if (typeof window.supabase !== 'undefined' && window.supabase.createClient) {
        _supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        console.log('Supabase client initialized');
        return true;
    }
    console.error('Supabase SDK not loaded');
    return false;
}

/**
 * Start Facebook login via Supabase Auth
 * Requests ads_read scope for Meta Ads API access
 */
async function loginWithFacebook() {
    if (!_supabaseClient && !initSupabase()) {
        console.error('Cannot login: Supabase not initialized');
        // Fallback to direct OAuth
        window.location.href = `${INSIGHTS_API_URL}/api/auth/facebook/login`;
        return;
    }

    try {
        const { data, error } = await _supabaseClient.auth.signInWithOAuth({
            provider: 'facebook',
            options: {
                scopes: 'email,ads_read,public_profile',
                redirectTo: `${window.location.origin}/oauth-callback.html`
            }
        });

        if (error) {
            console.error('Supabase OAuth error:', error);
            // Fallback to direct OAuth
            window.location.href = `${INSIGHTS_API_URL}/api/auth/facebook/login`;
        }
        // If successful, user is redirected to Facebook login
    } catch (err) {
        console.error('Login error:', err);
        // Fallback to direct OAuth
        window.location.href = `${INSIGHTS_API_URL}/api/auth/facebook/login`;
    }
}

/**
 * Handle OAuth callback - sync Facebook token with Insights backend
 * Called from oauth-callback.html after Supabase redirects back
 *
 * Note: We parse tokens directly from URL hash instead of using getSession()
 * because getSession() doesn't always work reliably with hash-based redirects.
 */
async function handleSupabaseCallback() {
    // Parse tokens directly from URL hash (more reliable than getSession)
    const hashParams = new URLSearchParams(window.location.hash.substring(1));
    const supabaseToken = hashParams.get('access_token');
    const providerToken = hashParams.get('provider_token');

    // Check for error in hash
    if (hashParams.has('error')) {
        const error = hashParams.get('error_description') || hashParams.get('error');
        console.error('OAuth error in callback:', error);
        return { success: false, error };
    }

    if (!supabaseToken || !providerToken) {
        console.error('Missing tokens in callback URL');
        console.log('Available hash params:', [...hashParams.keys()]);
        return { success: false, error: 'Missing tokens in callback' };
    }

    console.log('✅ Tokens parsed from URL hash');
    console.log('🔄 Syncing Facebook token with Insights backend...');

    try {
        // Call our backend to sync the Facebook token
        const response = await fetch(`${INSIGHTS_API_URL}/api/auth/facebook/sync-facebook`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${supabaseToken}`
            },
            body: JSON.stringify({
                provider_token: providerToken
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error('Sync failed:', errorData);
            return { success: false, error: errorData.detail || 'Sync failed' };
        }

        const result = await response.json();
        console.log('✅ Sync successful:', result);

        // Store Insights token for API calls
        localStorage.setItem('auth_token', result.access_token);
        localStorage.setItem('tenant_id', result.tenant_id);
        localStorage.setItem('supabase_user_id', result.supabase_user_id);

        return {
            success: true,
            token: result.access_token,
            tenantId: result.tenant_id,
            adAccountsCount: result.ad_accounts_count
        };

    } catch (err) {
        console.error('Callback handling error:', err);
        return { success: false, error: err.message };
    }
}

/**
 * Check if user is authenticated with valid Insights token
 */
async function checkAuth() {
    const token = localStorage.getItem('auth_token');
    const tenantId = localStorage.getItem('tenant_id');

    if (!token || !tenantId) {
        return { authenticated: false };
    }

    try {
        const response = await fetch(`${INSIGHTS_API_URL}/api/accounts/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            return { authenticated: true, token, tenantId };
        } else {
            // Token invalid, clear storage
            localStorage.removeItem('auth_token');
            localStorage.removeItem('tenant_id');
            return { authenticated: false };
        }
    } catch (err) {
        console.error('Auth check error:', err);
        return { authenticated: false };
    }
}

/**
 * Logout - clear all auth data
 */
async function logout() {
    // Clear local storage
    localStorage.removeItem('auth_token');
    localStorage.removeItem('tenant_id');
    localStorage.removeItem('supabase_user_id');

    // Sign out from Supabase
    if (_supabaseClient) {
        await _supabaseClient.auth.signOut();
    }

    // Redirect to landing
    window.location.href = '/index-landing.html';
}

/**
 * Get accounts for authenticated user
 */
async function getAccounts() {
    const token = localStorage.getItem('auth_token');
    if (!token) return [];

    try {
        const response = await fetch(`${INSIGHTS_API_URL}/api/accounts/`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const data = await response.json();
            return data.accounts || [];
        }
        return [];
    } catch (err) {
        console.error('Error fetching accounts:', err);
        return [];
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    // Try to initialize Supabase if SDK is loaded
    if (typeof window.supabase !== 'undefined') {
        initSupabase();
    }
});

// Export for use in other scripts
window.SupabaseAuth = {
    login: loginWithFacebook,
    handleCallback: handleSupabaseCallback,
    checkAuth,
    logout,
    getAccounts,
    initSupabase
};
