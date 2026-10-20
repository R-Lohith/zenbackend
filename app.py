import os
import sys
import csv
import io
from flask import Flask, jsonify, request, send_file, make_response
from flask_cors import CORS

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.reconciler import PaymentReconciler
from services.pdf_generator import generate_cfo_pdf
from services.data_loader import paise_to_rupees

dist_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist'))
app = Flask(__name__, static_folder=dist_folder if os.path.exists(dist_folder) else None)
CORS(app)

# Initialize reconciler
reconciler = PaymentReconciler()

@app.route('/api/health', methods=['GET'])
def health_check():
    status = reconciler.loader.check_availability()
    return jsonify({
        'status': 'healthy' if status['all_available'] else 'degraded',
        'files': status['files'],
        'all_available': status['all_available']
    })

@app.route('/api/reconciliation/summary', methods=['GET'])
def get_summary():
    results = reconciler.get_summary()
    return jsonify({
        'summary': results['summary'],
        'availability': reconciler.availability
    })

@app.route('/api/reconciliation/bridge', methods=['GET'])
def get_bridge():
    results = reconciler.get_summary()
    return jsonify({
        'bridge': results['bridge'],
        'summary': results['summary']
    })

@app.route('/api/reconciliation/timeline', methods=['GET'])
def get_timeline():
    results = reconciler.get_summary()
    return jsonify({
        'daily_timeline': results['daily_timeline'],
        'short_paid_batches': results['short_paid_batches'],
        'missing_batches': results['missing_batches'],
        'october_batches': results['october_batches']
    })

@app.route('/api/reconciliation/exceptions', methods=['GET'])
def get_exceptions():
    results = reconciler.get_summary()
    exceptions = results['exceptions']

    # Query params
    exc_type = request.args.get('type')
    severity = request.args.get('severity')
    search = request.args.get('search', '').strip().lower()

    filtered = exceptions
    if exc_type and exc_type != 'ALL':
        filtered = [e for e in filtered if e['type'] == exc_type]
    if severity and severity != 'ALL':
        filtered = [e for e in filtered if e['severity'] == severity]
    if search:
        filtered = [
            e for e in filtered
            if search in e['id'].lower()
            or search in e['entity_id'].lower()
            or search in e['order_id'].lower()
            or search in e['description'].lower()
        ]

    # Pagination
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
    except ValueError:
        page = 1
        page_size = 20

    total_count = len(filtered)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = filtered[start_idx:end_idx]

    return jsonify({
        'total': total_count,
        'page': page,
        'page_size': page_size,
        'items': paginated,
        'types': list(set(e['type'] for e in exceptions)),
        'severities': ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    })

@app.route('/api/reconciliation/fees', methods=['GET'])
def get_fees():
    results = reconciler.get_summary()
    return jsonify({
        'charged_mdr': results['summary']['charged_mdr'],
        'expected_mdr': results['summary']['expected_mdr'],
        'charged_gst': results['summary']['charged_gst'],
        'expected_gst': results['summary']['expected_gst'],
        'fee_overcharge': results['summary']['fee_overcharge'],
        'variance_count': results['summary']['counts']['fee_variances'],
        'sample_variances': results['fee_variance_records']
    })

@app.route('/api/reconciliation/non-pg-bank', methods=['GET'])
def get_non_pg_bank():
    results = reconciler.get_summary()
    return jsonify({
        'non_pg_entries': results['non_pg_bank']
    })

@app.route('/api/reconciliation/download-pdf', methods=['GET'])
def download_pdf():
    results = reconciler.get_summary()
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outputs')
    pdf_path = os.path.join(output_dir, 'cfo_summary.pdf')
    generate_cfo_pdf(results, pdf_path)
    return send_file(
        pdf_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='CartNest_CFO_Reconciliation_Summary_Sep2026.pdf'
    )

@app.route('/api/reconciliation/export-exceptions-csv', methods=['GET'])
def export_exceptions_csv():
    results = reconciler.get_summary()
    exceptions = results['exceptions']

    def escape_csv_val(v):
        s = str(v)
        # Prevent formula injection: prefix with single quote if starts with =, +, -, @
        if s.startswith(('=', '+', '-', '@')):
            return "'" + s
        return s

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Exception_ID', 'Type', 'Severity', 'Entity_ID', 'Order_ID', 'Amount_INR', 'Source_File', 'Source_Row', 'Description', 'Recommended_Action'])

    for e in exceptions:
        writer.writerow([
            escape_csv_val(e['id']),
            escape_csv_val(e['type']),
            escape_csv_val(e['severity']),
            escape_csv_val(e['entity_id']),
            escape_csv_val(e['order_id']),
            f"{e['amount_inr']:.2f}",
            escape_csv_val(e['source_file']),
            escape_csv_val(e['source_row']),
            escape_csv_val(e['description']),
            escape_csv_val(e['recommended_action'])
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=CartNest_Reconciliation_Exceptions_Sep2026.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return response

@app.route('/api/sales-analytics', methods=['GET'])
def get_sales_analytics():
    """Aggregated sales analytics for graphical representation."""
    results = reconciler.get_summary()
    if not results:
        return jsonify({'error': 'No reconciliation data available'}), 503

    cleaned = reconciler.cleaned_data
    df_orders = cleaned['orders']
    df_pg = cleaned['pg']

    # --- 1. Sales by Status (order count + amount) ---
    status_agg = df_orders.groupby('order_status_norm').agg(
        count=('order_id_norm', 'count'),
        amount_paise=('order_amount_paise', 'sum')
    ).reset_index()
    status_summary = []
    for _, row in status_agg.iterrows():
        status_summary.append({
            'status': str(row['order_status_norm']),
            'count': int(row['count']),
            'amount_inr': float(paise_to_rupees(int(row['amount_paise'])))
        })

    # --- 2. Sales by Payment Method ---
    method_agg = df_orders.groupby('payment_method_norm').agg(
        count=('order_id_norm', 'count'),
        amount_paise=('order_amount_paise', 'sum')
    ).reset_index()
    method_summary = []
    for _, row in method_agg.iterrows():
        method_summary.append({
            'method': str(row['payment_method_norm']),
            'count': int(row['count']),
            'amount_inr': float(paise_to_rupees(int(row['amount_paise'])))
        })

    # --- 3. Daily sales trend (ordered by date) ---
    paid_orders = df_orders[df_orders['order_status_norm'] == 'Paid'].copy()
    date_col = 'order_date_iso' if 'order_date_iso' in paid_orders.columns else 'order_date'
    if date_col in paid_orders.columns:
        paid_orders['day'] = paid_orders[date_col].astype(str).str[:10]
        daily = paid_orders.groupby('day').agg(
            orders=('order_id_norm', 'count'),
            amount_paise=('order_amount_paise', 'sum')
        ).reset_index().sort_values('day')
        daily_trend = []
        for _, row in daily.iterrows():
            daily_trend.append({
                'day': str(row['day']),
                'orders': int(row['orders']),
                'amount_inr': float(paise_to_rupees(int(row['amount_paise'])))
            })
    else:
        daily_trend = []

    # --- 4. Top Cities by Sales ---
    if 'city' in df_orders.columns:
        city_agg = paid_orders.groupby('city').agg(
            count=('order_id_norm', 'count'),
            amount_paise=('order_amount_paise', 'sum')
        ).reset_index().sort_values('amount_paise', ascending=False).head(8)
        city_summary = []
        for _, row in city_agg.iterrows():
            city_summary.append({
                'city': str(row['city']),
                'count': int(row['count']),
                'amount_inr': float(paise_to_rupees(int(row['amount_paise'])))
            })
    else:
        city_summary = []

    # --- 5. Conversion Funnel ---
    total_count = int(df_orders['order_id_norm'].count())
    paid_count = int(df_orders[df_orders['order_status_norm'] == 'Paid']['order_id_norm'].count())
    captured_df = df_pg[df_pg['txn_type_norm'] == 'CAPTURE']
    refunded_df = df_pg[df_pg['txn_type_norm'] == 'REFUND']
    captured_count = len(captured_df)
    refunded_count = len(refunded_df)

    total_gross = float(paise_to_rupees(int(df_orders['order_amount_paise'].sum())))
    paid_gross = float(paise_to_rupees(int(df_orders[df_orders['order_status_norm'] == 'Paid']['order_amount_paise'].sum())))
    captured_gross = float(paise_to_rupees(int(captured_df['gross_amount_paise'].sum())))
    net_settled = float(paise_to_rupees(int(captured_df['net_amount_paise'].sum())))

    funnel = [
        {'stage': 'All Orders', 'count': total_count, 'amount_inr': total_gross, 'pct': 100.0},
        {'stage': 'Paid Orders', 'count': paid_count, 'amount_inr': paid_gross,
         'pct': round(paid_count * 100 / total_count, 1) if total_count else 0},
        {'stage': 'PG Captured', 'count': captured_count, 'amount_inr': captured_gross,
         'pct': round(captured_count * 100 / total_count, 1) if total_count else 0},
        {'stage': 'Net Settled', 'count': captured_count, 'amount_inr': net_settled,
         'pct': round(net_settled * 100 / total_gross, 1) if total_gross else 0},
    ]

    return jsonify({
        'status_summary': status_summary,
        'method_summary': method_summary,
        'daily_trend': daily_trend,
        'city_summary': city_summary,
        'funnel': funnel
    })

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if dist_folder and os.path.exists(dist_folder):
        if path != "" and os.path.exists(os.path.join(dist_folder, path)):
            return send_file(os.path.join(dist_folder, path))
        else:
            return send_file(os.path.join(dist_folder, 'index.html'))
    return jsonify({
        'message': 'CartNest Reconciliation Engine API is running. Build frontend with `npm run build` or start Vite dev server.',
        'endpoints': ['/api/health', '/api/reconciliation/summary', '/api/reconciliation/bridge', '/api/reconciliation/timeline', '/api/reconciliation/exceptions', '/api/reconciliation/fees', '/api/reconciliation/download-pdf']
    })

if __name__ == '__main__':
    reconciler.reconcile()
    app.run(host='0.0.0.0', port=5000, debug=False)
