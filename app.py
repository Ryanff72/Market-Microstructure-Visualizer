import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import numpy as np
import plotly.graph_objs as go
from websocket_client import CoinbaseWebSocket
from order_book import OrderBook

##################
# Global Vars
##################

orderbook = OrderBook()
ws_client = None

#state for fast interpolation
previous_metrics = {'best_bid': 0, 'best_ask': 0, 'spread': 0, 'mid_price': 0, 'imbalance': 0.5}
target_metrics = {'best_bid': 0, 'best_ask': 0, 'spread': 0, 'mid_price': 0, 'imbalance': 0.5}
interp_step = 0

#method for interpolating vals (makes site look fast haha)
def interpolate_value(old, new, steps=10, current_step = 0):
    if old is None or new is None:
        return new or old or 0
    alpha = min(current_step / steps, 1.0)
    return old + (new-old) *alpha #lin interp formula


# Sleek Dark Mode: Professional trading terminal—clean blacks, subtle grays, precise accents
COLORS = {
    'background': '#0c0c0c',  # Deep black for focus
    'card_bg': '#1a1a1a',     # Subtle gray-black for cards
    'text': '#f0f0f0',        # Clean off-white for readability
    'bid_green': '#10b981',   # Modern emerald green for bids
    'ask_red': '#ef4444',     # Crisp red for asks
    'accent': '#3b82f6',      # Professional blue for highlights
    'grid': 'rgba(55, 65, 81, 0.3)',  # Muted slate grid
}

# Fonts: Inter for everything—modern, highly legible sans-serif
FONTS = {
    'header': '"Inter", sans-serif',
    'body': '"Inter", sans-serif',
}

##################
# Create application
##################

app = dash.Dash(__name__)
app.title = "BTC-USD Market Microstructure Visualizer"

app.config.suppress_callback_exceptions = True

##################
# Layout
##################
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        
        <!-- Google Fonts: Clean modern sans -->
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        
        <style>
            ._dash-loading {
                display: none !important;
            }
            
            ::-webkit-scrollbar {
                width: 6px;
            }
            ::-webkit-scrollbar-track {
                background: #1a1a1a;
            }
            ::-webkit-scrollbar-thumb {
                background: #374151;
                border-radius: 3px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #4b5563;
            }
            
            body {
                font-family: ''' + FONTS['body'] + ''';
                margin: 0;
                padding: 0;
                background-color: ''' + COLORS['background'] + ''';
                color: ''' + COLORS['text'] + ''';
                line-height: 1.5;
            }
            
            h1, h2, h3 {
                font-family: ''' + FONTS['header'] + ''';
                font-weight: 600;
                letter-spacing: -0.025em;
                margin: 0 0 0.5em 0;
            }

            .sleek-card {
                background-color: ''' + COLORS['card_bg'] + ''';
                border: 1px solid ''' + COLORS['grid'] + ''';
                border-radius: 8px;
                padding: 24px;
                transition: border-color 0.2s ease, box-shadow 0.2s ease;
                position: relative;
            }
            .sleek-card:hover {
                border-color: ''' + COLORS['accent'] + ''';
                box-shadow: 0 1px 3px rgba(0,0,0,0.1), 0 4px 12px rgba(0,0,0,0.05);
            }
            
            .sleek-divider {
                border: none;
                height: 1px;
                background-color: ''' + COLORS['grid'] + ''';
                margin: 24px 0;
            }
            
            .metric-label {
                font-size: 12px;
                font-weight: 500;
                color: ''' + COLORS['accent'] + ''';
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 8px;
            }
            
            .metric-value {
                font-size: 32px;
                font-weight: 700;
                line-height: 1.2;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

app.layout = html.Div(style={
    'minHeight': '100vh',
    'padding': '32px',
    'maxWidth': '1600px',
    'margin': '0 auto',
}, children=[

    # Header: Clean title bar
    html.Div([
        html.H1("BTC-USD Microstructure Visualizer",
                style={'color': COLORS['text'], 'textAlign': 'center', 'fontSize': '28px', 'marginBottom': '4px'}),
    ], className='sleek-card', style={'marginBottom': '32px', 'textAlign': 'center'}),

    html.Div(className='sleek-divider'),

    ####################
    # Metrics Grid
    ####################
    html.Div([
        # Best Bid
        html.Div([
            html.Div("Best Bid", className='metric-label'),
            html.Div(id='best-bid-value', children="$0.00", style={
                'color': COLORS['bid_green'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

        # Best Ask
        html.Div([
            html.Div("Best Ask", className='metric-label'),
            html.Div(id='best-ask-value', children="$0.00", style={
                'color': COLORS['ask_red'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

        # Spread
        html.Div([
            html.Div("Spread", className='metric-label'),
            html.Div(id='spread-value', children="$0.00", style={
                'color': COLORS['accent'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

        # Mid Price
        html.Div([
            html.Div("Mid Price", className='metric-label'),
            html.Div(id='mid-price-value', children="$0.00", style={
                'color': COLORS['text'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

        # Imbalance
        html.Div([
            html.Div("Imbalance", className='metric-label'),
            html.Div(id='imbalance-value', children="0.00%", style={
                'color': COLORS['accent'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

    ], style={
        'display': 'grid',
        'gridTemplateColumns': 'repeat(auto-fit, minmax(180px, 1fr))',
        'gap': '16px',
        'marginBottom': '32px',
    }),

    ########################
    # Charts: Side-by-side, compressed
    ########################

    html.Div([
        
        # Order Book Depth Chart
        html.Div([
            html.H3("Order Book Depth", style={
                'color': COLORS['text'], 
                'textAlign': 'center',
                'fontSize': '16px',
                'marginBottom': '16px'
            }),
            dcc.Graph(
                id='orderbook-chart',
                config={'displayModeBar': False},
                style={'height': '300px'}
            )
        ], className='sleek-card', style={'flex': '1', 'marginRight': '16px'}),

        html.Div([
            html.H3("Spread over Time", style={
                'color': COLORS['text'],
                'textAlign': 'center',
                'fontSize' : '16px',
                'marginBottom': '16px'
            }),
            dcc.Graph(
                id='spread-chart',
                config={'displayModeBar': False},
                style={'height': '300px'}
            )
        ], className='sleek-card', style={'flex': '1', 'marginLeft': '16px'}) 
        
    ], style={'display': 'flex', 'gap': '16px', 'marginBottom': '32px'}),

    # Imbalance Gauge
    html.Div([
        html.H3("Order Imbalance", style={
            'color': COLORS['text'], 
            'textAlign': 'center',
            'fontSize': '16px',
            'marginBottom': '16px'
        }),
        html.Div([
            html.Div("Sell Pressure", style={
                'color': COLORS['ask_red'],
                'fontSize': '12px',
                'fontWeight': '500',
                'textAlign': 'left'
            }),
            html.Div(id='imbalance-gauge-value', children="50.0%", style={
                'color': COLORS['text'],
                'fontSize': '18px',
                'fontWeight': '500',
                'textAlign': 'center'
            }),
            html.Div("Buy Pressure", style={
                'color': COLORS['bid_green'],
                'fontSize': '12px',
                'fontWeight': '500',
                'textAlign': 'right'
            }),
        ], style={
            'display': 'flex',
            'justifyContent': 'space-between',
            'marginBottom': '12px'
        }),
        html.Div([
            html.Div(id='imbalance-bar-sell', style={
                'backgroundColor': COLORS['ask_red'],
                'height': '6px',
                'transition': 'width 0.3s ease',
                'borderRadius': '3px',
                'width': '50%',
            }),
            html.Div(id='imbalance-bar-buy', style={
                'backgroundColor': COLORS['bid_green'],
                'height': '6px',
                'transition': 'width 0.3s ease',
                'borderRadius': '3px',
                'width': '50%',
            }),
        ], style={
            'width': '100%',
            'backgroundColor': COLORS['grid'],
            'borderRadius': '3px',
            'overflow': 'hidden',
        })
        
    ], className='sleek-card', style={'marginBottom': '20px'}),

    # Interval component (keep as-is)
    dcc.Interval(
        id='interval-component',
        interval=250,
        n_intervals=0
    ),
])

##################
# Websocket
##################

def handle_websocket_message(msg_type, data):
	if msg_type == "snapshot":
		orderbook.initialize_snapshot(data['bids'], data['asks'])
		print("Orderbook Initialized.")

	elif msg_type == "l2update":
		orderbook.process_update(data['changes'])

def start_websocket():
	global ws_client
	ws_client = CoinbaseWebSocket(on_message_callback=handle_websocket_message)
	ws_client.start()
	print("Websocket Started.")

##################
# Callback
##################

@app.callback(
	[
		Output('best-bid-value', 'children'),
		Output('best-ask-value', 'children'),
		Output('spread-value', 'children'),
		Output('mid-price-value', 'children'),
		Output('imbalance-value', 'children'),
	],
	Input('interval-component', 'n_intervals')
)

def update_metrics(n):
    metrics = orderbook.get_metrics()
    return [
        f"${metrics['best_bid']:,.2f}",
        f"${metrics['best_ask']:,.2f}",
        f"${metrics['spread']:,.2f}",
        f"${metrics['mid_price']:,.2f}",
        f"{metrics['imbalance']:,.1%}",
    ]

@app.callback(
    Output('orderbook-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)

def update_orderbook_chart(n):
    if n % 5 != 0:
        raise dash.exceptions.PreventUpdate
    depth = orderbook.get_depth_snapshot(levels=15)
    bid_prices = [price for price, size in depth['bids']]
    bid_sizes = [size for price, size in depth['bids']]
    ask_prices = [price for price, size in depth['asks']]
    ask_sizes = [size for price, size in depth['asks']]
    bid_sizes = [-size for size in bid_sizes]
    max_volume = max(max(abs(x) for x in bid_sizes), max(abs(x) for x in ask_sizes))
    # make chart
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=bid_prices,
        x=bid_sizes,
        orientation='h',
        name='Bids',
        marker_color=COLORS['bid_green'],
        hovertemplate='Price: $%{y:,.2f}<br>Size: %{x:.4f} BTC'
    ))
    fig.add_trace(go.Bar(
        y=ask_prices,
        x=ask_sizes,
        orientation='h',
        name='Asks',
        marker_color=COLORS['ask_red'],
        hovertemplate='Price: $%{y:,.2f}<br>Size: %{x:.4f} BTC'
    ))
    fig.update_layout(
        plot_bgcolor=COLORS['card_bg'],
        paper_bgcolor=COLORS['card_bg'],
        font={'color': COLORS['text'], 'family': FONTS['body'], 'size': 12},
        showlegend=False,
        margin=dict(l=60, r=40, t=20, b=40),
        xaxis=dict(
            title="Volume (BTC)",
            gridcolor=COLORS['grid'],
            zerolinecolor=COLORS['grid'],
            zerolinewidth=1,
            range=[-max_volume * 1.1, max_volume * 1.1]
        ),
        yaxis=dict(
            title="Price (USD)",
            gridcolor=COLORS['grid'],
            tickformat='$,.0f',
        ),
        hovermode='closest',
        bargap=0.4,
        bargroupgap=0,
    )
    fig.update_traces(
        width=0.6,
        selector=dict(type='bar')
    )
    
    return fig

@app.callback(
    Output('spread-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)

def update_spread_chart(n):
    if n % 5 != 0:
        raise dash.exceptions.PreventUpdate
    fig = go.Figure()
    orderbook.update_history()
    spread_data = list(orderbook.spread_history)
    spread_data=[s for s in spread_data if s is not None]
    x_values = list(range(len(spread_data)- 1, -1, -1))

    fig.add_trace(go.Scatter(
        x=x_values,
        y=spread_data,
        mode='lines',
        name='Spread',
        line=dict(
            color=COLORS['accent'],
            width=2
        ),
        fill='tozeroy',
        fillcolor=f'rgba(59, 130, 246, 0.1)',
        hovertemplate='$%{y:.2f}'
    ))

    #styling
    fig.update_layout(
        plot_bgcolor=COLORS['card_bg'],
        paper_bgcolor=COLORS['card_bg'],
        font={'color': COLORS['text'], 'family': FONTS['body'], 'size': 12},
        showlegend=False,
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            title="Time Ago (Seconds)",
            gridcolor=COLORS['grid'],
            tickformat='d'
        ),
        yaxis=dict(
            title="Spread (USD)",
            gridcolor=COLORS['grid'],
            tickformat='$,.2f',
            range=[0, max(spread_data) * 1.2]
        ),
        hovermode='x unified'
    )
    return fig

@app.callback(
    [
        Output('imbalance-gauge-value', 'children'),
        Output('imbalance-bar-sell', 'style'),
        Output('imbalance-bar-buy', 'style'),
    ],
    Input('interval-component', 'n_intervals')
)

def update_imbalance_gauge(n):
    imbalance = orderbook.get_imbalance()
    if imbalance is None: imbalance = 0.5
    buy_percentage = imbalance * 100
    sell_percentage = (1-imbalance) * 100
    gauge_text = f"{imbalance:.1%}"

    sell_style = {
        'backgroundColor': COLORS['ask_red'],
        'height': '6px',
        'transition': 'width 0.3s ease',
        'borderRadius': '3px',
        'width': f'{sell_percentage}%'
    }

    buy_style = {
        'backgroundColor': COLORS['bid_green'],
        'height': '6px',
        'transition': 'width 0.3s ease',
        'borderRadius': '3px',
        'width': f'{buy_percentage}%'
    }

    return gauge_text, sell_style, buy_style

##################
# Main
##################

if __name__ == '__main__':
	start_websocket()
	app.run(debug=True, host='0.0.0.0', port=8050)