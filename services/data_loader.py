import os
import hashlib
import re
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd

def compute_sha256(filepath):
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def normalize_order_id(val):
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip().upper()
    # Normalize 'ORD-26000130' to 'ORD26000130'
    s = re.sub(r'^ORD\-', 'ORD', s)
    return s

def normalize_text(val):
    if pd.isna(val) or val is None:
        return ""
    return str(val).strip()

def parse_date_to_iso(val):
    if pd.isna(val) or not val:
        return None
    val_str = str(val).strip()
    # Support DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return pd.to_datetime(val_str, format=fmt).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            continue
    try:
        return pd.to_datetime(val_str).strftime('%Y-%m-%d')
    except Exception:
        return None

def parse_to_paise(val):
    if pd.isna(val) or val is None:
        return 0
    val_str = str(val).strip().replace(',', '').replace('₹', '')
    if not val_str:
        return 0
    try:
        d = Decimal(val_str)
        # convert rupees to integer paise using Decimal ROUND_HALF_UP
        paise = int((d * Decimal(100)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        return paise
    except Exception:
        return 0

def paise_to_rupees(paise):
    return float(Decimal(int(paise)) / Decimal(100))

class DataLoader:
    def __init__(self, data_dir=None):
        if data_dir:
            self.data_dir = data_dir
        else:
            # Auto-detect data directory
            candidates = [
                os.path.join(os.path.dirname(__file__), '..', '..', 'data'),
                os.path.join(os.getcwd(), 'data'),
                os.path.join(os.getcwd(), '..', 'data'),
                os.path.join(os.getcwd(), 'data', 'raw')
            ]
            self.data_dir = None
            for c in candidates:
                if os.path.exists(os.path.join(c, 'orders.csv')):
                    self.data_dir = os.path.abspath(c)
                    break
            if not self.data_dir:
                self.data_dir = os.path.abspath(candidates[0])

    def get_file_path(self, filename):
        return os.path.join(self.data_dir, filename)

    def check_availability(self):
        expected_files = ['orders.csv', 'pg_transactions.csv', 'bank_statement.csv', 'mdr_rate_card.csv']
        status = {}
        all_available = True
        for f in expected_files:
            fp = self.get_file_path(f)
            exists = os.path.exists(fp)
            size = os.path.getsize(fp) if exists else 0
            sha = compute_sha256(fp) if exists else None
            status[f] = {
                'available': exists,
                'path': fp,
                'size_bytes': size,
                'sha256': sha
            }
            if not exists:
                all_available = False
        return {
            'data_dir': self.data_dir,
            'all_available': all_available,
            'files': status
        }

    def load_raw_data(self):
        availability = self.check_availability()
        raw_data = {}
        for fname, info in availability['files'].items():
            if info['available']:
                raw_data[fname] = pd.read_csv(info['path'], dtype=str)
            else:
                raw_data[fname] = None
        return raw_data, availability

    def clean_and_normalize(self):
        raw_data, availability = self.load_raw_data()
        dq_issues = []

        if not availability['all_available']:
            return None, availability, dq_issues

        # 1. Orders
        df_orders_raw = raw_data['orders.csv']
        df_orders = df_orders_raw.copy()
        df_orders['source_row'] = df_orders.index + 2  # 1-indexed header is 1
        df_orders['order_id_norm'] = df_orders['order_id'].apply(normalize_order_id)
        df_orders['order_date_iso'] = df_orders['order_date'].apply(parse_date_to_iso)
        df_orders['order_status_norm'] = df_orders['order_status'].apply(normalize_text)
        df_orders['payment_method_norm'] = df_orders['payment_method'].apply(normalize_text)
        df_orders['order_amount_paise'] = df_orders['order_amount'].apply(parse_to_paise)
        df_orders['order_amount_inr'] = df_orders['order_amount_paise'].apply(paise_to_rupees)

        # Check order duplicates
        order_key_dups = df_orders[df_orders.duplicated(subset=['order_id_norm'], keep=False)]
        if not order_key_dups.empty:
            for _, r in order_key_dups.iterrows():
                dq_issues.append({
                    'file': 'orders.csv',
                    'row': int(r['source_row']),
                    'issue_type': 'DUPLICATE_ORDER_ID',
                    'identifier': r['order_id_norm'],
                    'details': f'Order ID {r["order_id_norm"]} duplicated in orders file.'
                })

        # 2. PG Transactions
        df_pg_raw = raw_data['pg_transactions.csv']
        df_pg = df_pg_raw.copy()
        df_pg['source_row'] = df_pg.index + 2
        df_pg['pg_txn_id_norm'] = df_pg['pg_txn_id'].apply(normalize_text)
        df_pg['merchant_order_ref_norm'] = df_pg['merchant_order_ref'].apply(normalize_order_id)
        df_pg['original_payment_id_norm'] = df_pg['original_payment_id'].apply(normalize_text)
        df_pg['txn_date_iso'] = df_pg['txn_date'].apply(parse_date_to_iso)
        df_pg['txn_type_norm'] = df_pg['txn_type'].apply(normalize_text)
        df_pg['payment_method_norm'] = df_pg['payment_method'].apply(normalize_text)
        df_pg['settlement_batch_id_norm'] = df_pg['settlement_batch_id'].apply(normalize_text)
        df_pg['settlement_date_iso'] = df_pg['settlement_date'].apply(parse_date_to_iso)
        
        df_pg['gross_amount_paise'] = df_pg['gross_amount'].apply(parse_to_paise)
        df_pg['mdr_fee_paise'] = df_pg['mdr_fee'].apply(parse_to_paise)
        df_pg['gst_on_fee_paise'] = df_pg['gst_on_fee'].apply(parse_to_paise)
        df_pg['net_amount_paise'] = df_pg['net_amount'].apply(parse_to_paise)

        df_pg['gross_amount_inr'] = df_pg['gross_amount_paise'].apply(paise_to_rupees)
        df_pg['mdr_fee_inr'] = df_pg['mdr_fee_paise'].apply(paise_to_rupees)
        df_pg['gst_on_fee_inr'] = df_pg['gst_on_fee_paise'].apply(paise_to_rupees)
        df_pg['net_amount_inr'] = df_pg['net_amount_paise'].apply(paise_to_rupees)

        # Check PG duplicates on pg_txn_id
        pg_key_dups = df_pg[df_pg.duplicated(subset=['pg_txn_id_norm'], keep=False)]
        if not pg_key_dups.empty:
            for _, r in pg_key_dups.iterrows():
                dq_issues.append({
                    'file': 'pg_transactions.csv',
                    'row': int(r['source_row']),
                    'issue_type': 'DUPLICATE_PG_TXN_ID',
                    'identifier': r['pg_txn_id_norm'],
                    'details': f'PG Transaction ID {r["pg_txn_id_norm"]} duplicated.'
                })

        # 3. Bank Statement
        df_bank_raw = raw_data['bank_statement.csv']
        df_bank = df_bank_raw.copy()
        df_bank['source_row'] = df_bank.index + 2
        df_bank['value_date_iso'] = df_bank['value_date'].apply(parse_date_to_iso)
        df_bank['narration_norm'] = df_bank['narration'].apply(normalize_text)
        df_bank['utr_norm'] = df_bank['utr'].apply(normalize_text)
        df_bank['credit_paise'] = df_bank['credit'].apply(parse_to_paise)
        df_bank['debit_paise'] = df_bank['debit'].apply(parse_to_paise)
        df_bank['credit_inr'] = df_bank['credit_paise'].apply(paise_to_rupees)
        df_bank['debit_inr'] = df_bank['debit_paise'].apply(paise_to_rupees)

        # Extract batch ID if present in narration: STL-YYYYMMDD
        def extract_batch_id(narr):
            m = re.search(r'STL-\d{8}', narr)
            return m.group(0) if m else None

        df_bank['extracted_batch_id'] = df_bank['narration_norm'].apply(extract_batch_id)
        df_bank['is_pg_settlement'] = df_bank['narration_norm'].str.contains('PAYGATE SOLUTIONS', case=False, na=False)

        # 4. MDR Rate Card
        df_mdr_raw = raw_data['mdr_rate_card.csv']
        df_mdr = df_mdr_raw.copy()
        df_mdr['source_row'] = df_mdr.index + 2
        df_mdr['payment_method_norm'] = df_mdr['payment_method'].apply(normalize_text)
        df_mdr['amount_above_paise'] = df_mdr['amount_above'].apply(parse_to_paise)
        df_mdr['amount_up_to_paise'] = df_mdr['amount_up_to'].apply(lambda x: parse_to_paise(x) if pd.notna(x) and str(x).strip() != '' and str(x).strip().lower() != 'nan' else None)
        df_mdr['mdr_pct'] = df_mdr['mdr_pct'].astype(float)
        df_mdr['gst_on_mdr_pct'] = df_mdr['gst_on_mdr_pct'].astype(float)

        cleaned = {
            'orders': df_orders,
            'pg': df_pg,
            'bank': df_bank,
            'mdr': df_mdr
        }

        return cleaned, availability, dq_issues
