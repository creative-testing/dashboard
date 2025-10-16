/**
 * SaaS Data Loader - Loads optimized data from API instead of static files
 * Wraps data_adapter.js DataAdapter class for SaaS authentication
 */

async function loadOptimizedDataFromAPI(accountId, apiUrl) {
    try {
        console.log(`📦 Loading optimized data for ${accountId}...`);

        // Load all optimized files from API with cache buster
        const timestamp = Date.now();
        const base = `${apiUrl}/api/data/files/${accountId}`;

        const [meta, agg, summary] = await Promise.all([
            authFetch(`${base}/meta_v1.json?t=${timestamp}`).then(r => {
                if (!r.ok) throw new Error(`meta_v1: ${r.status}`);
                return r.json();
            }),
            authFetch(`${base}/agg_v1.json?t=${timestamp}`).then(r => {
                if (!r.ok) throw new Error(`agg_v1: ${r.status}`);
                return r.json();
            }),
            authFetch(`${base}/summary_v1.json?t=${timestamp}`).then(r => {
                if (!r.ok) throw new Error(`summary_v1: ${r.status}`);
                return r.json();
            })
        ]);

        console.log(`✅ Loaded ${agg.ads.length} ads (optimized format)`);

        // Create adapter (assumes DataAdapter class from data_adapter.js is available)
        if (typeof DataAdapter === 'undefined') {
            throw new Error('DataAdapter class not found - ensure data_adapter.js is loaded first');
        }

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
        }, 100); // Start after UI is rendered

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

        // Previous week data - for SaaS, we can compute from 14d-7d
        // (Backend doesn't generate prev_week_compressed.json yet)
        setTimeout(() => {
            try {
                console.log('🔄 Computing previous week from periods...');
                const adapter = window.dataAdapter;
                if (!adapter) {
                    console.warn('No dataAdapter available for prev week computation');
                    return;
                }

                const pIdx7 = adapter.aggData.periods.indexOf('7d');
                const pIdx14 = adapter.aggData.periods.indexOf('14d');
                if (pIdx7 === -1 || pIdx14 === -1) {
                    console.warn('Periods 7d/14d not found; cannot compute prev week');
                    return;
                }

                const computed = [];
                for (let i = 0; i < adapter.aggData.ads.length; i++) {
                    const m7 = adapter.getAggMetrics(i, pIdx7);
                    const m14 = adapter.getAggMetrics(i, pIdx14);

                    // Calculate difference (14d - 7d = prev week)
                    const diffSpend = Math.max(0, (m14.spend - m7.spend));
                    const diffPurch = Math.max(0, (m14.purchases - m7.purchases));
                    const diffPval  = Math.max(0, (m14.purchase_value - m7.purchase_value));
                    const diffImpr  = Math.max(0, (m14.impressions - m7.impressions));
                    const diffClk   = Math.max(0, (m14.clicks - m7.clicks));

                    // Keep only ads with spend or purchases in prev week
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

                // Calculate summary
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

                console.log('✅ Computed prev week from 14d-7d:', computed.length, 'ads');

                if (window.updateComparisonTable) {
                    window.updateComparisonTable();
                }
            } catch (error) {
                console.error('❌ Error computing previous week:', error);
            }
        }, 500); // Compute after initial display

        // Store raw optimized data for direct access if needed
        window.optimizedData = { meta, agg, summary, adapter };

        return true;
    } catch (error) {
        console.error('❌ Error loading optimized data from API:', error);

        // Show user-friendly error
        if (typeof showError === 'function') {
            showError(`Failed to load dashboard data: ${error.message}`);
        }

        return false;
    }
}

// Export for global use
window.loadOptimizedDataFromAPI = loadOptimizedDataFromAPI;
