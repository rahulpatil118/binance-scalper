// ============================================================
//  dashboard.js — Frontend Controller
// ============================================================

class Dashboard {
    constructor() {
        this.updateInterval = 1000; // 1 second for real-time updates
        this.chart = null;
        this.isUpdating = false;
        this.tradesOffset = 0;
    }

    async init() {
        console.log('Dashboard initializing...');

        // Initial data load
        await this.updateAll();

        // Load performance chart
        await this.initChart();

        // Load initial trades
        await this.loadTrades();

        // Start auto-update loop
        this.startAutoUpdate();

        // Setup event listeners
        this.setupEventListeners();

        console.log('Dashboard initialized');
    }

    async updateAll() {
        if (this.isUpdating) return;
        this.isUpdating = true;

        try {
            // Show loading spinner
            $('#loading-spinner').show();

            // Parallel API calls for better performance
            const [status, signals, positions, indicators] = await Promise.all([
                this.fetchAPI('/api/status'),
                this.fetchAPI('/api/signals'),
                this.fetchAPI('/api/positions'),
                this.fetchAPI('/api/indicators')
            ]);

            // Update all sections
            if (status) this.updateStatus(status);
            if (signals) this.updateSignals(signals);
            if (positions) this.updatePositions(positions);
            if (indicators) this.updateIndicators(indicators);

            // Update timestamp
            this.updateLastRefresh();

            // Hide loading spinner
            $('#loading-spinner').hide();
        } catch (error) {
            console.error('Update failed:', error);
            this.showError('Failed to update dashboard');
            $('#loading-spinner').hide();
        } finally {
            this.isUpdating = false;
        }
    }

    async fetchAPI(endpoint) {
        try {
            const response = await fetch(endpoint);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`Error fetching ${endpoint}:`, error);
            return null;
        }
    }

    updateStatus(data) {
        // Update header
        $('#symbol').text(data.symbol);
        $('#current-price').text(this.formatPrice(data.price));
        $('#env-badge').text(data.environment);
        $('#mode-badge').text(data.mode + (data.leverage > 1 ? ` ${data.leverage}x` : ''));

        // Update stats cards with animation
        this.animateValue('#capital', data.account.capital, true);
        this.animateValue('#total-pnl', data.account.total_pnl, true);
        this.animateValue('#daily-pnl', data.account.daily_pnl, true);
        this.animateValue('#win-rate', data.account.win_rate, false, '%');
        this.animateValue('#daily-trades', data.account.daily_trades, false);

        // Color code P&L
        $('#total-pnl').css('color', data.account.total_pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)');
        $('#daily-pnl').css('color', data.account.daily_pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)');

        // Win rate color
        const winRate = data.account.win_rate;
        let winRateColor = 'var(--text-primary)';
        if (winRate >= 60) winRateColor = 'var(--accent-green)';
        else if (winRate < 50) winRateColor = 'var(--accent-red)';
        $('#win-rate').css('color', winRateColor);
    }

    updateSignals(data) {
        const combined = data.combined;

        // Update signal display
        $('#signal-value').text(combined.toFixed(4));

        // Direction and color
        let direction = '⚪ HOLD';
        let color = 'var(--text-secondary)';

        if (data.direction === 'BUY') {
            direction = '🟢 BUY';
            color = 'var(--accent-green)';
        } else if (data.direction === 'SELL') {
            direction = '🔴 SELL';
            color = 'var(--accent-red)';
        }

        $('#signal-direction').text(direction);
        $('#signal-value').css('color', color);

        // Signal meter indicator position (map [-1, 1] to [0%, 100%])
        const position = ((combined + 1) / 2) * 100;
        $('#signal-indicator').css('left', `${position}%`);

        // Update strategy scores
        for (const [strategy, score] of Object.entries(data.strategies)) {
            const width = ((score + 1) / 2) * 100;
            $(`#bar-${strategy}`).css('width', `${width}%`);
            $(`#score-${strategy}`).text(score.toFixed(2));

            // Color code bars
            if (score > 0) {
                $(`#bar-${strategy}`).css('background', 'linear-gradient(90deg, var(--accent-green), #00b86e)');
            } else if (score < 0) {
                $(`#bar-${strategy}`).css('background', 'linear-gradient(90deg, var(--accent-red), #d93850)');
            } else {
                $(`#bar-${strategy}`).css('background', 'var(--text-dim)');
            }
        }
    }

    updatePositions(data) {
        const container = $('#positions-container');
        $('#positions-count').text(data.count);

        if (data.count === 0) {
            container.html('<p class="empty-message">No open positions</p>');
            return;
        }

        container.empty();

        for (const pos of data.positions) {
            const card = this.createPositionCard(pos);
            container.append(card);
        }
    }

    createPositionCard(pos) {
        const pnlColor = pos.unrealised_pnl >= 0 ? 'green' : 'red';
        const sideClass = pos.side.toLowerCase();
        const timeAgo = this.formatDuration(pos.duration_sec);

        return `
            <div class="position-card ${sideClass}">
                <div class="pos-header">
                    <span class="pos-side">${pos.side}</span>
                    <span class="pos-symbol">${pos.symbol}</span>
                    <span class="pos-time">${timeAgo}</span>
                </div>
                <div class="pos-price">Entry: ${this.formatPrice(pos.entry_price)}</div>
                <div class="pos-pnl ${pnlColor}">
                    ${pos.unrealised_pnl >= 0 ? '+' : ''}${this.formatMoney(pos.unrealised_pnl)}
                    (${pos.unrealised_pct >= 0 ? '+' : ''}${pos.unrealised_pct.toFixed(2)}%)
                </div>
                <div class="pos-levels">
                    SL: ${this.formatPrice(pos.stop_loss)} | TP: ${this.formatPrice(pos.take_profit)}
                </div>
            </div>
        `;
    }

    updateIndicators(data) {
        if (!data.indicators) return;

        const ind = data.indicators;

        $('#ind-rsi').text(ind.rsi.toFixed(1));
        $('#ind-ema-fast').text(this.formatPrice(ind.ema_fast));
        $('#ind-ema-slow').text(this.formatPrice(ind.ema_slow));
        $('#ind-macd').text(ind.macd_hist.toFixed(2));
        $('#ind-bb-pct').text((ind.bb_pct * 100).toFixed(1) + '%');
        $('#ind-atr').text((ind.atr_pct * 100).toFixed(2) + '%');
        $('#ind-adx').text(ind.adx.toFixed(1));
        $('#ind-stoch').text(ind.stoch_k.toFixed(1));
        $('#ind-vwap').text(this.formatPrice(ind.vwap));
        $('#ind-vol').text(ind.vol_ratio.toFixed(2) + 'x');

        // Color code RSI
        const rsi = ind.rsi;
        let rsiColor = 'var(--text-primary)';
        if (rsi < 35) rsiColor = 'var(--accent-green)';
        else if (rsi > 65) rsiColor = 'var(--accent-red)';
        $('#ind-rsi').css('color', rsiColor);

        // Color code ADX (trend strength)
        const adx = ind.adx;
        let adxColor = 'var(--text-primary)';
        if (adx >= 25) adxColor = 'var(--accent-green)';  // Strong trend
        else if (adx < 20) adxColor = 'var(--accent-red)'; // Weak/choppy
        $('#ind-adx').css('color', adxColor);
    }

    async initChart() {
        try {
            const data = await this.fetchAPI('/api/performance');
            if (!data || !data.chart_data) return;

            const ctx = document.getElementById('performance-chart').getContext('2d');

            const equityCurve = data.chart_data.equity_curve || [];

            this.chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: equityCurve.map(d => new Date(d.timestamp).toLocaleTimeString()),
                    datasets: [{
                        label: 'Account Equity',
                        data: equityCurve.map(d => d.capital),
                        borderColor: 'rgb(0, 208, 132)',
                        backgroundColor: 'rgba(0, 208, 132, 0.1)',
                        tension: 0.4,
                        fill: true,
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    scales: {
                        x: {
                            display: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: '#848e9c' }
                        },
                        y: {
                            display: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: {
                                color: '#848e9c',
                                callback: function(value) {
                                    return '$' + value.toLocaleString();
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(26, 31, 46, 0.95)',
                            titleColor: '#eaecef',
                            bodyColor: '#eaecef',
                            borderColor: '#2b3139',
                            borderWidth: 1,
                            padding: 12,
                            callbacks: {
                                label: function(context) {
                                    return 'Capital: $' + context.parsed.y.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });

            // Update performance summary
            if (data.summary) {
                $('#perf-total-trades').text(data.summary.total_trades || 0);
                $('#perf-wl').text(`${data.summary.wins || 0} / ${data.summary.losses || 0}`);
                $('#perf-avg-win').text(this.formatMoney(data.summary.avg_win || 0));
                $('#perf-avg-loss').text(this.formatMoney(data.summary.avg_loss || 0));
                $('#perf-profit-factor').text((data.summary.profit_factor || 0).toFixed(2));
                $('#perf-best').text(this.formatMoney(data.summary.best_trade || 0));

                // Color code
                $('#perf-avg-win').css('color', 'var(--accent-green)');
                $('#perf-avg-loss').css('color', 'var(--accent-red)');
                $('#perf-best').css('color', 'var(--accent-green)');
            }
        } catch (error) {
            console.error('Chart initialization failed:', error);
        }
    }

    async loadTrades(append = false) {
        try {
            const data = await this.fetchAPI(`/api/trades?limit=20&offset=${append ? this.tradesOffset : 0}`);
            if (!data || !data.trades) return;

            const tbody = $('#trades-body');

            if (!append) {
                tbody.empty();
                this.tradesOffset = 0;
            }

            if (data.trades.length === 0) {
                if (!append) {
                    tbody.html('<tr><td colspan="7" class="empty-message">No trades yet</td></tr>');
                }
                return;
            }

            for (const trade of data.trades) {
                const row = this.createTradeRow(trade);
                tbody.append(row);
            }

            this.tradesOffset += data.trades.length;

            // Hide "Load More" button if no more trades
            if (this.tradesOffset >= data.total) {
                $('#load-more-trades').hide();
            } else {
                $('#load-more-trades').show();
            }
        } catch (error) {
            console.error('Failed to load trades:', error);
        }
    }

    createTradeRow(trade) {
        const pnlClass = trade.pnl >= 0 ? 'profit' : 'loss';
        const time = new Date(trade.timestamp).toLocaleTimeString();

        return `
            <tr class="${pnlClass}">
                <td>${time}</td>
                <td>${trade.side}</td>
                <td>${this.formatPrice(trade.entry_price)}</td>
                <td>${this.formatPrice(trade.exit_price)}</td>
                <td>${trade.pnl >= 0 ? '+' : ''}${this.formatMoney(trade.pnl)}</td>
                <td>${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%</td>
                <td>${trade.reason}</td>
            </tr>
        `;
    }

    startAutoUpdate() {
        setInterval(() => {
            this.updateAll();
        }, this.updateInterval);
    }

    setupEventListeners() {
        $('#load-more-trades').on('click', () => {
            this.loadTrades(true);
        });
    }

    animateValue(selector, newValue, isMoney = false, suffix = '') {
        const el = $(selector);
        const oldValue = parseFloat(el.text().replace(/[^0-9.-]/g, '')) || 0;

        $({value: oldValue}).animate({value: newValue}, {
            duration: 500,
            easing: 'swing',
            step: function() {
                if (isMoney) {
                    el.text('$' + this.value.toFixed(2));
                } else {
                    el.text(this.value.toFixed(2) + suffix);
                }
            }
        });
    }

    formatPrice(price) {
        return '$' + price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    }

    formatMoney(amount) {
        return '$' + amount.toFixed(2);
    }

    formatDuration(seconds) {
        if (seconds < 60) return `${seconds}s ago`;
        if (seconds < 3600) return `${Math.floor(seconds/60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds/3600)}h ago`;
        return `${Math.floor(seconds/86400)}d ago`;
    }

    updateLastRefresh() {
        $('#last-update').text(new Date().toLocaleTimeString());
    }

    showError(message) {
        console.error(message);
        // Could add toast notification here
    }
}

// Initialize dashboard when DOM is ready
$(document).ready(() => {
    const dashboard = new Dashboard();
    dashboard.init();
});
