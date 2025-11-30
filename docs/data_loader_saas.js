/**
 * SaaS Data Loader - Charge depuis API avec JWT auth
 * Version adaptée de data_adapter.js pour mode SaaS multi-tenant
 * @version 2.0.0 - Nov 2025 (SaaS unifié)
 *
 * Retourne: { success: boolean, noData: boolean, error?: string }
 * - success=true, noData=false → données chargées OK
 * - success=false, noData=true → 404, données pas encore générées
 * - success=false, noData=false → autre erreur (réseau, auth, etc.)
 */

// Import DataAdapter class from data_adapter.js (will be loaded separately)
// This file only overrides the loadOptimizedData function

const API_URL = 'https://creative-testing.theaipipe.com';

// Global function to load optimized data from API
async function loadOptimizedData() {
    try {
        console.log('📦 Loading optimized data from API...');

        // Get auth params from URL
        const urlParams = new URLSearchParams(window.location.search);
        const accountId = urlParams.get('account_id');
        const token = urlParams.get('token');

        if (!token) {
            console.error('Missing token in URL');
            return { success: false, noData: false, error: 'Missing authentication token' };
        }

        const headers = { 'Authorization': `Bearer ${token}` };
        const timestamp = Date.now();

        let meta, agg, summary;
        let is404 = false;

        // MODE 1: Aggregated tenant-wide (all accounts)
        if (!accountId || accountId === 'all') {
            console.log('📊 Loading aggregated data for ALL accounts (tenant-wide)...');

            const response = await fetch(`${API_URL}/api/data/tenant-aggregated?t=${timestamp}`, { headers });

            if (response.status === 404) {
                console.warn('⚠️ No data available yet (404) - first time user?');
                is404 = true;
            } else if (!response.ok) {
                throw new Error(`Failed to load aggregated data: ${response.status} ${response.statusText}`);
            } else {
                const aggregatedData = await response.json();
                meta = aggregatedData.meta_v1;
                agg = aggregatedData.agg_v1;
                summary = aggregatedData.summary_v1;

                console.log(`✅ Loaded aggregated data: ${aggregatedData.metadata.accounts_loaded} accounts, ${agg.ads.length} total ads`);
                if (aggregatedData.metadata.accounts_failed > 0) {
                    console.warn(`⚠️ ${aggregatedData.metadata.accounts_failed} accounts failed to load:`, aggregatedData.metadata.failed_accounts);
                }
            }
        }
        // MODE 2: Single account
        else {
            console.log(`📊 Loading data for single account: ${accountId}...`);

            // Try to load meta first to check if data exists
            const metaResponse = await fetch(`${API_URL}/api/data/files/${accountId}/meta_v1.json?t=${timestamp}`, { headers });

            if (metaResponse.status === 404) {
                console.warn(`⚠️ No data for account ${accountId} (404) - needs refresh`);
                is404 = true;
            } else if (!metaResponse.ok) {
                throw new Error(`Failed to load meta: ${metaResponse.status}`);
            } else {
                meta = await metaResponse.json();

                // Load the rest
                [agg, summary] = await Promise.all([
                    fetch(`${API_URL}/api/data/files/${accountId}/agg_v1.json?t=${timestamp}`, { headers }).then(r => r.json()),
                    fetch(`${API_URL}/api/data/files/${accountId}/summary_v1.json?t=${timestamp}`, { headers }).then(r => r.json())
                ]);

                console.log(`✅ Loaded ${agg.ads.length} ads from account ${accountId}`);
            }
        }

        // Handle 404 case - data not ready yet
        if (is404) {
            return { success: false, noData: true, error: 'Data not available yet' };
        }

        console.log(`✅ Total ads loaded: ${agg.ads.length}`);

        // Create adapter (DataAdapter class is loaded from data_adapter.js)
        const adapter = new DataAdapter(meta, agg, summary);

        // Convert for each period and store in global periodsData
        if (!window.periodsData) {
            window.periodsData = {};
        }

        // Convert ONLY 7d first for fast initial load
        const initialPeriod = '7d';
        const initialConverted = adapter.convertToOldFormat(initialPeriod);
        if (initialConverted) {
            window.periodsData[7] = initialConverted;
            console.log(`✅ Converted ${initialPeriod}: ${initialConverted.ads.length} ads (initial load)`);
        }

        // Store adapter for background loading
        window.dataAdapter = adapter;

        // Load other periods in background after initial display
        setTimeout(() => {
            console.log('🔄 Loading other periods in background...');
            ['3d', '14d', '30d', '90d'].forEach(period => {
                const numericKey = parseInt(period.replace('d', ''));
                if (!window.periodsData[numericKey]) {
                    const converted = adapter.convertToOldFormat(period);
                    if (converted) {
                        window.periodsData[numericKey] = converted;
                        console.log(`✅ Background loaded ${period}: ${converted.ads.length} ads`);

                        // Rebuild dropdown after 90d is loaded to include all accounts
                        if (period === '90d' && typeof buildAccountOptions === 'function') {
                            console.log('🔄 Rebuilding account dropdown with all periods data...');
                            buildAccountOptions();
                        }
                    }
                }
            });
            console.log('✅ All periods loaded in background');
        }, 100);

        // Keep the on-demand function as fallback
        window.loadPeriodData = function(periodDays) {
            const periodStr = periodDays + 'd';
            if (!window.periodsData[periodDays] && window.dataAdapter) {
                console.log(`⏳ Loading ${periodStr} data on demand...`);
                const converted = window.dataAdapter.convertToOldFormat(periodStr);
                if (converted) {
                    window.periodsData[periodDays] = converted;
                    console.log(`✅ Loaded ${periodStr}: ${converted.ads.length} ads`);
                }
            }
            return window.periodsData[periodDays];
        };

        // Previous week data - try to load from API, fallback to compute from 14d-7d
        setTimeout(async () => {
            try {
                console.log('📥 Loading previous week data...');

                // Try to load from API (if backend generates it in the future)
                try {
                    const prevWeekResponse = await fetch(`${API_URL}/api/data/files/${accountId}/prev_week_v1.json`, { headers });
                    if (prevWeekResponse.ok) {
                        const prevWeekRawData = await prevWeekResponse.json();
                        console.log('✅ Loaded prev week from API:', prevWeekRawData.ads?.length || 0, 'ads');
                        window.prevWeekData = prevWeekRawData;

                        if (window.updateComparisonTable) {
                            window.updateComparisonTable();
                        }
                        return;
                    }
                } catch (e) {
                    console.log('No prev_week file on API, computing from 14d-7d...');
                }

                // Fallback: compute prev week = (14d - 7d) from optimized agg
                console.log('❌ No prev_week file. Computing prev week = (14d - 7d)...');
                const adapter = window.dataAdapter;
                if (!adapter) {
                    console.error('No dataAdapter available for fallback');
                    return;
                }

                const pIdx7 = adapter.aggData.periods.indexOf('7d');
                const pIdx14 = adapter.aggData.periods.indexOf('14d');
                if (pIdx7 === -1 || pIdx14 === -1) {
                    console.error('Periods 7d/14d not found in agg; cannot build fallback prev week.');
                    return;
                }

                const computed = [];
                for (let i = 0; i < adapter.aggData.ads.length; i++) {
                    const m7 = adapter.getAggMetrics(i, pIdx7);
                    const m14 = adapter.getAggMetrics(i, pIdx14);

                    const diffSpend = Math.max(0, (m14.spend - m7.spend));
                    const diffPurch = Math.max(0, (m14.purchases - m7.purchases));
                    const diffPval  = Math.max(0, (m14.purchase_value - m7.purchase_value));
                    const diffImpr  = Math.max(0, (m14.impressions - m7.impressions));
                    const diffClk   = Math.max(0, (m14.clicks - m7.clicks));

                    if (diffSpend > 0 || diffPurch > 0) {
                        const meta = adapter.metaData.ads[i];
                        const campaign = adapter.metaData.campaigns[meta.cid] || {};
                        const adset = adapter.metaData.adsets[meta.aid] || {};
                        const account = adapter.metaData.accounts[meta.acc] || {};

                        computed.push({
                            ad_id: meta.id,
                            ad_name: meta.name || '',
                            campaign_name: campaign.name || '',
                            adset_name: adset.name || '',
                            account_name: account.name || '',
                            impressions: diffImpr,
                            clicks: diffClk,
                            spend: diffSpend,
                            purchases: diffPurch,
                            purchase_value: diffPval,
                            reach: 0,
                            roas: diffSpend > 0 ? (diffPval / diffSpend) : 0,
                            cpa: diffPurch > 0 ? (diffSpend / diffPurch) : 0
                        });
                    }
                }

                window.prevWeekData = { period: "prev_week", ads: computed };

                const totals = computed.reduce((acc, ad) => ({
                    impressions: acc.impressions + ad.impressions,
                    clicks: acc.clicks + ad.clicks,
                    purchases: acc.purchases + ad.purchases,
                    spend: acc.spend + ad.spend,
                    purchase_value: acc.purchase_value + ad.purchase_value
                }), { impressions: 0, clicks: 0, purchases: 0, spend: 0, purchase_value: 0 });

                window.prevWeekData.summary = {
                    total_impressions: totals.impressions,
                    total_clicks: totals.clicks,
                    total_purchases: totals.purchases,
                    total_spend: totals.spend,
                    total_purchase_value: totals.purchase_value,
                    avg_roas: totals.spend > 0 ? (totals.purchase_value / totals.spend) : 0
                };

                console.log('✅ Built prev week from 14d-7d:', computed.length, 'ads');

                if (window.updateComparisonTable) {
                    window.updateComparisonTable();
                }
            } catch (error) {
                console.error('❌ Error loading previous week data:', error);
            }
        }, 500);

        // Store raw optimized data for direct access if needed
        window.optimizedData = { meta, agg, summary, adapter };

        return { success: true, noData: false };
    } catch (error) {
        console.error('❌ Error loading optimized data:', error);
        return { success: false, noData: false, error: error.message };
    }
}

/**
 * Trigger refresh for all accounts of the current tenant
 * Uses /api/accounts/refresh-tenant-accounts endpoint
 */
async function triggerRefreshAll() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (!token) {
        return { success: false, error: 'Missing token' };
    }

    try {
        const response = await fetch(`${API_URL}/api/accounts/refresh-tenant-accounts`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ Refresh API error:', response.status, errorText);
            return { success: false, error: `${response.status}: ${errorText}` };
        }

        const data = await response.json();
        console.log('🔄 Refresh triggered:', data);
        return { success: true, ...data };
    } catch (error) {
        console.error('❌ Failed to trigger refresh:', error);
        return { success: false, error: error.message };
    }
}

/**
 * Load demographics data from SaaS API
 * Called by loadDemographics() in index-saas.html
 *
 * @param {string} accountId - Ad account ID (e.g., "act_123456")
 * @param {number} period - Period in days (3, 7, 14, 30, 90)
 * @returns {object|null} Demographics data or null if not available
 */
async function loadDemographicsFromAPI(accountId, period) {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (!token) {
        console.error('Missing token for demographics');
        return null;
    }

    try {
        const response = await fetch(`${API_URL}/api/data/demographics/${accountId}/${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.status === 404) {
            console.warn(`No demographics data for ${accountId} (${period}d)`);
            return null;
        }

        if (!response.ok) {
            throw new Error(`Failed to load demographics: ${response.status}`);
        }

        const data = await response.json();
        console.log(`✅ Loaded demographics for ${accountId} (${period}d): ${data.segments?.length || 0} segments`);
        return data;
    } catch (error) {
        console.error('Error loading demographics:', error);
        return null;
    }
}

/**
 * Load all demographics periods for an account
 * Useful for frontend period selector
 *
 * @param {string} accountId - Ad account ID
 * @returns {object|null} All periods data
 */
async function loadAllDemographicsPeriods(accountId) {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (!token) {
        return null;
    }

    try {
        const response = await fetch(`${API_URL}/api/data/demographics/all-periods/${accountId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error('Error loading all demographics periods:', error);
        return null;
    }
}

/**
 * Check if data is ready (for polling)
 */
async function checkDataReady() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const accountId = urlParams.get('account_id');

    if (!token) return false;

    try {
        const endpoint = (!accountId || accountId === 'all')
            ? `${API_URL}/api/data/tenant-aggregated?t=${Date.now()}`
            : `${API_URL}/api/data/files/${accountId}/meta_v1.json?t=${Date.now()}`;

        const response = await fetch(endpoint, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        return response.ok;
    } catch {
        return false;
    }
}
