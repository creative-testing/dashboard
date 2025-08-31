/**
 * Adaptateur pour convertir les données columnaires optimisées
 * vers le format attendu par le dashboard original
 */

class DataAdapter {
    constructor(metaData, aggData, summaryData) {
        this.metaData = metaData;
        this.aggData = aggData;
        this.summaryData = summaryData;
        this.adIndexMap = {};
        
        // Build index map
        aggData.ads.forEach((adId, idx) => {
            this.adIndexMap[adId] = idx;
        });
    }
    
    // Get metrics for a specific ad and period
    getAggMetrics(adIdx, periodIdx) {
        const P = this.aggData.periods.length;  // 5
        const M = this.aggData.metrics.length;  // 6
        const base = adIdx * (P * M) + periodIdx * M;
        
        const impr = this.aggData.values[base + 0];
        const clk = this.aggData.values[base + 1];
        const purch = this.aggData.values[base + 2];
        const spend = this.aggData.values[base + 3] / this.aggData.scales.money;
        const pval = this.aggData.values[base + 4] / this.aggData.scales.money;
        const reach = this.aggData.values[base + 5];
        
        // Calculate derived metrics
        const ctr = impr > 0 ? (clk / impr) * 100 : 0;
        const roas = spend > 0 ? (pval / spend) : 0;
        const cpa = purch > 0 ? (spend / purch) : 0;
        
        return { 
            impressions: impr, 
            clicks: clk, 
            purchases: purch, 
            spend, 
            purchase_value: pval, 
            reach, 
            ctr, 
            roas, 
            cpa 
        };
    }
    
    // Convert to old format for a specific period
    convertToOldFormat(period) {
        const periodIdx = this.aggData.periods.indexOf(period);
        if (periodIdx === -1) {
            console.error(`Period ${period} not found`);
            return null;
        }
        
        const ads = [];
        const accountTotals = {};
        const formatCounts = {};
        
        // Process each ad
        for (let i = 0; i < this.aggData.ads.length; i++) {
            const metrics = this.getAggMetrics(i, periodIdx);
            
            // Skip ads with no spend for performance
            // Note: This means the ad count shown is "ads with spend" not "all ads"
            // For Petcare example: 7d shows 96 ads, 14d also shows 96 because 
            // the SAME 96 ads have spend in both periods (plus others not shown when filtered)
            if (metrics.spend === 0) continue;
            
            const adMeta = this.metaData.ads[i];
            const campaign = this.metaData.campaigns[adMeta.cid] || {};
            const adset = this.metaData.adsets[adMeta.aid] || {};
            const account = this.metaData.accounts[adMeta.acc] || {};
            
            // Build ad object in old format
            const ad = {
                ad_id: adMeta.id,
                ad_name: adMeta.name,
                campaign_name: campaign.name || '',
                campaign_id: adMeta.cid,
                adset_name: adset.name || '',
                adset_id: adMeta.aid,
                account_name: account.name || '',
                account_id: adMeta.acc,
                impressions: metrics.impressions,
                spend: parseFloat(metrics.spend.toFixed(2)),  // Keep as number
                clicks: metrics.clicks,
                reach: metrics.reach,
                purchases: metrics.purchases,
                purchase_value: parseFloat(metrics.purchase_value.toFixed(2)),  // Keep as number
                ctr: metrics.ctr,
                roas: metrics.roas,
                cpa: metrics.cpa,
                effective_status: adMeta.status,
                format: adMeta.format,
                media_url: adMeta.media,
                created_time: adMeta.ct
            };
            
            ads.push(ad);
            
            // Accumulate account totals
            if (!accountTotals[account.name]) {
                accountTotals[account.name] = {
                    spend: 0,
                    impressions: 0,
                    clicks: 0,
                    purchases: 0,
                    purchase_value: 0
                };
            }
            accountTotals[account.name].spend += metrics.spend;
            accountTotals[account.name].impressions += metrics.impressions;
            accountTotals[account.name].clicks += metrics.clicks;
            accountTotals[account.name].purchases += metrics.purchases;
            accountTotals[account.name].purchase_value += metrics.purchase_value;
            
            // Count formats
            formatCounts[adMeta.format] = (formatCounts[adMeta.format] || 0) + 1;
        }
        
        // Build account summary
        const account_summary = Object.entries(accountTotals).map(([name, totals]) => ({
            account_name: name,
            total_spend: parseFloat(totals.spend.toFixed(2)),
            total_impressions: totals.impressions,
            total_clicks: totals.clicks,
            total_purchases: totals.purchases,
            total_purchase_value: parseFloat(totals.purchase_value.toFixed(2)),
            roas: parseFloat(totals.spend > 0 ? (totals.purchase_value / totals.spend).toFixed(2) : '0.00')
        }));
        
        // Build format distribution
        const totalAds = ads.length;
        const format_distribution = {};
        Object.entries(formatCounts).forEach(([format, count]) => {
            format_distribution[format.toLowerCase()] = {
                count: count,
                percentage: ((count / totalAds) * 100).toFixed(1)
            };
        });
        
        // Calculate summary statistics needed by dashboard
        const totalSpend = ads.reduce((sum, ad) => sum + parseFloat(ad.spend), 0);
        const totalRevenue = ads.reduce((sum, ad) => sum + parseFloat(ad.purchase_value), 0);
        const totalPurchases = ads.reduce((sum, ad) => sum + ad.purchases, 0);
        const totalImpressions = ads.reduce((sum, ad) => sum + ad.impressions, 0);
        const totalClicks = ads.reduce((sum, ad) => sum + ad.clicks, 0);
        const totalReach = ads.reduce((sum, ad) => sum + ad.reach, 0);
        
        return {
            period: period,
            ads: ads,
            account_summary: account_summary,
            format_distribution: format_distribution,
            summary: {
                total_spend: totalSpend,
                total_revenue: totalRevenue,
                total_purchases: totalPurchases,
                total_impressions: totalImpressions,
                total_clicks: totalClicks,
                total_reach: totalReach,
                avg_roas: totalSpend > 0 ? (totalRevenue / totalSpend) : 0,
                avg_cpa: totalPurchases > 0 ? (totalSpend / totalPurchases) : 0,
                avg_ctr: totalImpressions > 0 ? (totalClicks / totalImpressions * 100) : 0
            }
        };
    }
}

// Global function to load optimized data and convert to old format
async function loadOptimizedData() {
    try {
        console.log('📦 Loading optimized data...');
        
        // Load all optimized files
        const [meta, agg, summary] = await Promise.all([
            fetch('./data/optimized/meta_v1.json').then(r => r.json()),
            fetch('./data/optimized/agg_v1.json').then(r => r.json()),
            fetch('./data/optimized/summary_v1.json').then(r => r.json())
        ]);
        
        console.log(`✅ Loaded ${agg.ads.length} ads (optimized format)`);
        
        // Create adapter
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
        
        // Load REAL previous week data IN BACKGROUND (don't block initial display)
        setTimeout(async () => {
            try {
                console.log('📥 Loading previous week data in background...');
                // Try compressed version first, fallback to original
                let prevWeekResponse = await fetch('./data/optimized/prev_week_compressed.json');
                if (!prevWeekResponse.ok) {
                    prevWeekResponse = await fetch('./data/optimized/prev_week_original.json');
                }
                console.log('Prev week fetch response:', prevWeekResponse.status);
                if (prevWeekResponse.ok) {
                    const prevWeekRawData = await prevWeekResponse.json();
                console.log('Prev week raw data loaded:', prevWeekRawData.ads ? prevWeekRawData.ads.length : 0, 'ads');
                
                // Aggregate the previous week data by ad_id (same as we do for current data)
                const aggregatedPrevWeek = {};
                prevWeekRawData.ads.forEach(ad => {
                    const id = ad.ad_id;
                    if (!aggregatedPrevWeek[id]) {
                        aggregatedPrevWeek[id] = {
                            ...ad,
                            impressions: 0,
                            clicks: 0,
                            purchases: 0,
                            spend: 0,
                            purchase_value: 0,
                            reach: 0
                        };
                    }
                    aggregatedPrevWeek[id].impressions += parseInt(ad.impressions || 0);
                    aggregatedPrevWeek[id].clicks += parseInt(ad.clicks || 0);
                    aggregatedPrevWeek[id].purchases += parseInt(ad.purchases || 0);
                    aggregatedPrevWeek[id].spend += parseFloat(ad.spend || 0);
                    aggregatedPrevWeek[id].purchase_value += parseFloat(ad.purchase_value || 0);
                    aggregatedPrevWeek[id].reach += parseInt(ad.reach || 0);
                });
                
                const prevAds = Object.values(aggregatedPrevWeek);
                window.prevWeekData = {
                    period: "prev_week",
                    ads: prevAds
                };
                
                // Calculate summary for prev week
                const totals = prevAds.reduce((acc, ad) => ({
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
                
                console.log('✅ Loaded REAL previous week data:', prevAds.length, 'ads');
                
                // Trigger update of comparison table if dashboard is already loaded
                if (window.updateComparisonTable) {
                    window.updateComparisonTable();
                }
            } else {
                console.error('❌ Previous week data not OK, status:', prevWeekResponse.status);
            }
        } catch (error) {
            console.error('❌ Error loading previous week data:', error);
        }
        }, 500); // Load after initial display
        
        // Also store raw optimized data for direct access if needed
        window.optimizedData = { meta, agg, summary, adapter };
        
        return true;
    } catch (error) {
        console.error('❌ Error loading optimized data:', error);
        return false;
    }
}