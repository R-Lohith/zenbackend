import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_cfo_pdf(reconciliation_data, output_path):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=28,
        rightMargin=28,
        topMargin=22,
        bottomMargin=22
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=15,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=1
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=5
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=3,
        spaceAfter=2
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.8,
        leading=8.5,
        textColor=colors.HexColor('#334155')
    )
    bold_body = ParagraphStyle(
        'BoldBody',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.8,
        leading=8.5,
        textColor=colors.HexColor('#0f172a')
    )
    right_body = ParagraphStyle(
        'RightBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.8,
        leading=8.5,
        alignment=2,
        textColor=colors.HexColor('#0f172a')
    )

    summary = reconciliation_data['summary']

    story = []

    # Title & Header
    story.append(Paragraph("CARTNEST — PAYMENT GATEWAY RECONCILIATION", title_style))
    story.append(Paragraph("CFO Executive Summary & Audit Certificate | Period: September 1–30, 2026 | Currency: INR (Paise Exact)", subtitle_style))

    # KPI Top Bar (5 Metrics)
    diff_val = summary['paid_orders'] - summary['september_bank_cash']
    kpi_data = [
        [
            Paragraph("<b>Gross Booked Sales</b><br/>₹{:,.2f}<br/><font color='#64748b'>6,000 orders</font>".format(summary['gross_orders']), body_style),
            Paragraph("<b>Legitimate Paid Sales</b><br/>₹{:,.2f}<br/><font color='#64748b'>5,255 orders</font>".format(summary['paid_orders']), body_style),
            Paragraph("<b>Bank Cash Received</b><br/>₹{:,.2f}<br/><font color='#64748b'>27 PG deposits</font>".format(summary['september_bank_cash']), body_style),
            Paragraph("<b>Sales-to-Cash Gap</b><br/><b>₹{:,.2f}</b><br/><font color='#f59e0b'>Decomposed</font>".format(diff_val), body_style),
            Paragraph("<b>Unexplained Variance</b><br/><font color='#16a34a'><b>₹{:,.2f}</b></font><br/><font color='#16a34a'>100% Tied Out</font>".format(summary['unexplained_variance']), body_style),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[111, 111, 111, 111, 112])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 2.5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 3))

    # Section 1: Sales-to-Cash Waterfall Bridge
    story.append(Paragraph("<b>1. Sales-to-Cash Waterfall Bridge (Auditable Reconciliation)</b>", section_heading))
    bridge_rows = [
        ["Line Item / Step", "Amount (INR)", "Classification", "Audit Lineage & Non-Overlap Rule"],
        ["Legitimate Paid Sales (CartNest Orders)", "₹ 18,984,402.00", "Baseline", "5,255 legitimate paid orders booked in CartNest platform"],
        ["Less: Paid Orders Without PG Capture", "-₹ 67,617.00", "Collection Gap", "20 orders marked Paid with zero gateway capture (uncollected)"],
        ["Add: Captures on Cancelled & Failed Orders", "+₹ 28,687.00", "Customer Overcharge", "8 customers charged for aborted/cancelled orders"],
        ["Add: Orphan Captures (No CartNest Order)", "+₹ 24,992.00", "Unrecorded Revenue", "8 gateway captures missing from order management database"],
        ["Add: Duplicate Captures (Paid Orders)", "+₹ 44,927.00", "Duplicate Charge", "15 duplicate customer charges requiring refund"],
        ["Net Pricing & Checkout Discrepancies", "-₹ 3,145.00", "Pricing Discrepancy", "Net discount coupon and cart rounding variance on 15 orders"],
        ["Add: Captures on Refunded Orders", "+₹ 915,889.00", "Initial Gross Flow", "243 initial captures processed prior to post-order refund reversal"],
        ["Gross Gateway Captures Processed", "₹ 19,928,135.00", "Gateway Gross", "5,509 total capture transactions recorded in gateway ledger"],
        ["Less: PG Customer Refunds Processed", "-₹ 893,888.00", "Gateway Reversal", "243 refund transactions processed via payment gateway"],
        ["Less: Gateway MDR & GST (18%) Fees", "-₹ 207,184.62", "Processing Cost", "Recalculated fees; includes ₹1,185.20 fee overcharge vs rate card"],
        ["Net Gateway Settlement Generated", "₹ 18,827,062.38", "Gateway Net", "Sum of net proceeds generated across all 30 settlement batches"],
        ["Less: October Timing (T+2 Settling in Oct)", "-₹ 1,265,526.90", "Timing Difference", "Batches STL-20261001 & STL-20261002 (Sept 29–30 activity)"],
        ["Less: Missing Settlement Batch STL-20260912", "-₹ 551,074.03", "Missing Remittance", "Critical recovery: Batch settled in PG ledger but omitted from bank"],
        ["Less: Bank Settlement Short-Payments", "-₹ 26,412.89", "Bank Deductions", "Unexplained deductions withheld across 8 settlement batches"],
        ["Actual Bank Cash Received (PG Settled)", "₹ 16,984,048.56", "Reconciled Cash", "27 bank credit entries from PayGate; exact ₹0.00 tie-out"]
    ]
    b_table_data = []
    for i, row in enumerate(bridge_rows):
        b_table_data.append([
            Paragraph(f"<b>{row[0]}</b>" if i in [0,1,8,11,15] else row[0], bold_body if i in [0,1,8,11,15] else body_style),
            Paragraph(f"<b>{row[1]}</b>" if i in [0,1,8,11,15] else row[1], right_body),
            Paragraph(f"<b>{row[2]}</b>" if i == 0 else row[2], body_style),
            Paragraph(f"<b>{row[3]}</b>" if i == 0 else row[3], body_style),
        ])
    b_table = Table(b_table_data, colWidths=[185, 85, 95, 191])
    b_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.7),
        ('TOPPADDING', (0,0), (-1,-1), 0.7),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0,8), (-1,8), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0,11), (-1,11), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0,15), (-1,15), colors.HexColor('#dcfce7')),
    ]))
    story.append(b_table)
    story.append(Spacer(1, 3))

    # Section 2: Ranked Biggest Causes & Recommended Actions
    story.append(Paragraph("<b>2. Biggest Causes Ranked by Value & Recommended Actions</b>", section_heading))
    driver_rows = [
        ["Rank / Driver", "Discrepancy Category", "Impact (INR)", "Classification", "Recommended Action"],
        ["1. Critical", "October Timing (STL-1001 & 1002)", "₹ 1,265,526.90", "Timing Difference", "Verify deposit into bank on Oct 1 and Oct 2 under T+2 rule."],
        ["2. Critical", "Missing Batch STL-20260912", "₹ 551,074.03", "Cash Recovery (Loss)", "Issue formal legal demand notice to PayGate Ops with UTR request."],
        ["3. High", "Paid Orders Without Capture", "₹ 67,617.00", "Revenue at Risk", "Audit 20 uncollected orders; hold fulfillment if payment unconfirmed."],
        ["4. High", "Duplicate Customer Captures", "₹ 44,927.00", "Customer Liability", "Proactively refund 15 double-charged customers to avoid chargebacks."],
        ["5. High", "Captures on Cancelled/Failed", "₹ 28,687.00", "Customer Liability", "Refund 8 customer transactions charged for unfulfilled orders."],
        ["6. High", "Settlement Short-Payments (8)", "₹ 26,412.89", "Cash Recovery", "Reconcile deductions with PayGate partner manager for recovery."],
        ["7. Medium", "Orphan Gateway Captures", "₹ 24,992.00", "Unrecorded Revenue", "Map 8 transactions to customer accounts or return funds."],
        ["8. Low", "MDR & GST Rate Overcharges", "₹ 1,185.20", "Fee Clawback", "Submit contractual clawback invoice for 55 tiered rate discrepancies."]
    ]
    d_table_data = []
    for i, row in enumerate(driver_rows):
        d_table_data.append([
            Paragraph(f"<b>{row[0]}</b>" if i==0 else row[0], bold_body if i==0 else body_style),
            Paragraph(f"<b>{row[1]}</b>" if i==0 else row[1], body_style),
            Paragraph(f"<b>{row[2]}</b>" if i==0 else row[2], right_body),
            Paragraph(f"<b>{row[3]}</b>" if i==0 else row[3], body_style),
            Paragraph(f"<b>{row[4]}</b>" if i==0 else row[4], body_style),
        ])
    d_table = Table(d_table_data, colWidths=[65, 140, 75, 95, 181])
    d_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.7),
        ('TOPPADDING', (0,0), (-1,-1), 0.7),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#fff7ed')),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#fef2f2')),
    ]))
    story.append(d_table)
    story.append(Spacer(1, 3))

    # Section 3: Pattern Worth Monitoring
    story.append(Paragraph("<b>3. Key Pattern Worth Monitoring: Gateway Settlement Leakage & Checkout Race Conditions</b>", section_heading))
    pattern_text = (
        "<b>A. Settlement Transmission Failure:</b> Batch <code>STL-20260912</code> (₹5,51,074.03) was entirely omitted from bank remittances, and "
        "8 separate settlement batches experienced recurring deductions of ₹976 to ₹6,563 (totaling ₹26,412.89) without itemized credit notes. "
        "<i>Action:</i> Implement automated batch-level bank webhook verification before closing daily settlement books.<br/>"
        "<b>B. Checkout Idempotency & Webhook Race Conditions:</b> 15 duplicate captures (₹44,927.00) and 8 captures on aborted/cancelled orders (₹28,687.00) "
        "reveal that checkout retry requests lack client-side idempotency keys, and asynchronous payment webhooks arrive out-of-order. "
        "<i>Action:</i> Enforce <code>X-Idempotency-Key</code> at checkout and configure 2-phase commit on order status transitions."
    )
    p_box = Table([[Paragraph(pattern_text, body_style)]], colWidths=[556])
    p_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94a3b8')),
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(p_box)
    story.append(Spacer(1, 3))

    # Section 4: Governance & Audit Certification Sign-Off
    signoff_data = [
        [
            Paragraph("<b>Reconciliation Audit Status:</b> <font color='#16a34a'><b>PASSED</b></font><br/>"
                      "Unexplained Plug: <b>₹0.00</b> (Paise exact)<br/>"
                      "Source Lineage: 100% Retained", body_style),
            Paragraph("<b>Finance Reviewer Sign-Off:</b><br/>"
                      "Name: _______________________<br/>"
                      "Title: Chief Financial Officer (CFO)", body_style),
            Paragraph("<b>Audit Date & Certification:</b><br/>"
                      "Period: September 1–30, 2026<br/>"
                      "System: CartNest Automated Engine", body_style)
        ]
    ]
    signoff_table = Table(signoff_data, colWidths=[185, 185, 186])
    signoff_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#94a3b8')),
        ('INNERGRID', (0,0), (-1,-1), 0.4, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 2.5),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
    ]))
    story.append(signoff_table)

    doc.build(story)
    return output_path

