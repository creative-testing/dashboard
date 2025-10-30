/**
 * SaaS Data Loader - Charge depuis API Render avec JWT auth
 * Version adaptée de data_adapter.js pour mode SaaS multi-tenant
 */

// Import DataAdapter class from data_adapter.js (will be loaded separately)
// This file only overrides the loadOptimizedData function

// Global function to load optimized data from Render API
async function loadOptimizedData() {
    try {
        console.log('📦 Loading optimized data from Render API...');

        // Get auth params from URL
        const urlParams = new URLSearchParams(window.location.search);
        const accountId = urlParams.get('account_id');
        const token = urlParams.get('token');

        if (!token) {
            console.error('Missing token in URL');
            return false;
        }

        const API_URL = 'https://creative-testing.theaipipe.com';
        const headers = { 'Authorization': `Bearer ${token}` };
        const timestamp = Date.now();

        let meta, agg, summary;

        // MODE 1: Aggregated tenant-wide (all accounts)
        if (!accountId || accountId === 'all') {
            console.log('📊 Loading aggregated data for ALL accounts (tenant-wide)...');

            const response = await fetch(`${API_URL}/api/data/tenant-aggregated?t=${timestamp}`, { headers });
            if (!response.ok) {
                throw new Error(`Failed to load aggregated data: ${response.status} ${response.statusText}`);
            }

            const aggregatedData = await response.json();
            meta = aggregatedData.meta_v1;
            agg = aggregatedData.agg_v1;
            summary = aggregatedData.summary_v1;

            console.log(`✅ Loaded aggregated data: ${aggregatedData.metadata.accounts_loaded} accounts, ${agg.ads.length} total ads`);
            if (aggregatedData.metadata.accounts_failed > 0) {
                console.warn(`⚠️ ${aggregatedData.metadata.accounts_failed} accounts failed to load:`, aggregatedData.metadata.failed_accounts);
            }
        }
        // MODE 2: Single account
        else {
            console.log(`📊 Loading data for single account: ${accountId}...`);

            if (!accountId) {
                console.error('Missing account_id in URL for single-account mode');
                return false;
            }

            // Load all optimized files from API
            [meta, agg, summary] = await Promise.all([
                fetch(`${API_URL}/api/data/files/${accountId}/meta_v1.json?t=${timestamp}`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/data/files/${accountId}/agg_v1.json?t=${timestamp}`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/data/files/${accountId}/summary_v1.json?t=${timestamp}`, { headers }).then(r => r.json())
            ]);

            console.log(`✅ Loaded ${agg.ads.length} ads from account ${accountId}`);
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

        return true;
    } catch (error) {
        console.error('❌ Error loading optimized data from Render API:', error);
        return false;
    }
}
