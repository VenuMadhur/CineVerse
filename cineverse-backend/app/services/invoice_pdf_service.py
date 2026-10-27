"""
Invoice PDF Generation (Phase 4, extended in Module 3 Phase 5a).

Renders a professional PDF for an existing Invoice, entirely in-memory
(no file persisted to disk -- Invoice.pdf_path stays unused, exactly
as before this phase; no Docker/volume changes needed). Built with
ReportLab, already a dependency since the initial Module 1/2 scaffold.
ReportLab paginates automatically as needed -- an invoice with several
line items and all of Phase 5a's added detail may span more than one
page.

This service contains zero invoice/customer/subscription/plan/payment
query logic of its own -- every piece of data it needs comes from the
existing repository layer, reused as-is. Company/support/policy
details are all read from settings (app/config/settings.py), never
hardcoded here.

Phase 5a: PDF generation must never depend on a network request. A
company logo is only embedded if COMPANY_LOGO_PATH points to a file
that exists on local disk; otherwise this gracefully falls back to a
styled text header using COMPANY_NAME. COMPANY_LOGO_URL (a remote URL)
is a separate setting used only by HTML email templates, which a mail
client fetches itself -- not used here.
"""
import io
import os
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.invoice import Invoice
from app.repositories.billing_cycle_repository import BillingCycleRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository

BRAND_RED = colors.HexColor("#E50914")
DARK_SLATE = colors.HexColor("#1e293b")
MUTED = colors.HexColor("#64748b")


class InvoicePdfService:
    def __init__(self, db: Session):
        self.db = db
        self.customer_repository = CustomerRepository(db)
        self.subscription_repository = SubscriptionRepository(db)
        self.plan_repository = PlanRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.billing_cycle_repository = BillingCycleRepository(db)

    def generate(self, invoice: Invoice) -> bytes:
        """
        Builds the PDF for an already-loaded, already-ownership-checked
        Invoice (the caller -- see app/api/v1/invoices.py -- is
        responsible for fetching it via InvoiceService.get_invoice,
        which enforces Phase 1D's ownership rules; this method assumes
        that's already happened and just renders).
        """
        customer = self.customer_repository.get_by_id(invoice.customer_id)
        subscription = self.subscription_repository.get_by_id(invoice.subscription_id)
        plan = self.plan_repository.get_by_id(subscription.plan_id) if subscription else None
        payments = self.payment_repository.list_for_invoice(invoice.id)
        latest_payment = payments[0] if payments else None
        billing_cycle = (
            self.billing_cycle_repository.get_by_id(invoice.billing_cycle_id)
            if invoice.billing_cycle_id
            else None
        )
        # The subscription's *currently open* cycle (if any) tells us
        # when it will next renew -- distinct from billing_cycle above,
        # which is the specific period *this* invoice was billed for.
        upcoming_cycle = (
            self.billing_cycle_repository.get_current_for_subscription(invoice.subscription_id)
            if invoice.subscription_id
            else None
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.65 * inch,
            bottomMargin=0.65 * inch,
            leftMargin=0.65 * inch,
            rightMargin=0.65 * inch,
        )
        styles = getSampleStyleSheet()
        elements = []

        elements.extend(self._build_header(styles, invoice))
        elements.append(Spacer(1, 0.3 * inch))
        elements.extend(self._build_customer_block(styles, customer))
        elements.append(Spacer(1, 0.25 * inch))
        elements.append(
            self._build_summary_table(
                plan, invoice, latest_payment, subscription, billing_cycle, upcoming_cycle
            )
        )
        elements.append(Spacer(1, 0.3 * inch))
        elements.extend(self._build_line_items(styles, invoice))
        elements.append(Spacer(1, 0.5 * inch))
        elements.extend(self._build_footer(styles))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Layout sections
    # ------------------------------------------------------------------
    def _build_header(self, styles, invoice: Invoice):
        company_style = ParagraphStyle(
            "Company", parent=styles["Heading1"], textColor=BRAND_RED, fontSize=22, spaceAfter=2
        )
        tagline_style = ParagraphStyle("Tagline", parent=styles["Normal"], textColor=MUTED, fontSize=9)
        company_detail_style = ParagraphStyle(
            "CompanyDetail", parent=styles["Normal"], textColor=MUTED, fontSize=8, leading=11
        )
        right_style = ParagraphStyle(
            "InvoiceMeta", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=10, leading=15
        )

        # Phase 5a: only embeds a logo if a *local* file exists --
        # never fetches one over the network (COMPANY_LOGO_URL is a
        # separate setting, used only by HTML email templates, which a
        # mail client fetches itself, not this PDF generator).
        if settings.COMPANY_LOGO_PATH and os.path.isfile(settings.COMPANY_LOGO_PATH):
            brand_block = [Image(settings.COMPANY_LOGO_PATH, width=1.6 * inch, height=0.5 * inch)]
        else:
            brand_block = [
                Paragraph(settings.COMPANY_NAME, company_style),
                Paragraph("Streaming Billing Platform", tagline_style),
            ]
        brand_block.append(
            Paragraph(
                f"{settings.COMPANY_ADDRESS}<br/>"
                f"{settings.COMPANY_PHONE} &nbsp;|&nbsp; {settings.COMPANY_EMAIL}<br/>"
                f"{settings.COMPANY_WEBSITE} &nbsp;|&nbsp; Tax ID: {settings.COMPANY_TAX_ID}",
                company_detail_style,
            )
        )

        header_table = Table(
            [
                [
                    brand_block,
                    Paragraph(
                        f"<b>Invoice</b><br/>"
                        f"{invoice.invoice_number}<br/>"
                        f"{invoice.created_at.strftime('%B %d, %Y')}",
                        right_style,
                    ),
                ]
            ],
            colWidths=[3.5 * inch, 3.15 * inch],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return [header_table]

    def _build_customer_block(self, styles, customer):
        label_style = ParagraphStyle(
            "SectionLabel", parent=styles["Normal"], textColor=MUTED, fontSize=8, spaceAfter=4
        )
        value_style = ParagraphStyle("SectionValue", parent=styles["Normal"], fontSize=11, leading=15)
        detail_style = ParagraphStyle("SectionDetail", parent=styles["Normal"], fontSize=9, textColor=MUTED, leading=13)

        if customer is None:
            return [Paragraph("BILL TO", label_style), Paragraph("—", value_style)]

        location = ", ".join(filter(None, [customer.address, customer.state, customer.country]))
        elements = [
            Paragraph("BILL TO", label_style),
            Paragraph(customer.name, value_style),
            Paragraph(customer.email, value_style),
        ]
        detail_lines = []
        if customer.phone_number:
            detail_lines.append(customer.phone_number)
        if location:
            detail_lines.append(location)
        detail_lines.append(f"Customer ID: {str(customer.id)[:8]}")
        elements.append(Paragraph(" &nbsp;|&nbsp; ".join(detail_lines), detail_style))
        return elements

    def _build_summary_table(self, plan, invoice: Invoice, latest_payment, subscription, billing_cycle, upcoming_cycle):
        rows = [
            ["Subscription Plan", plan.name if plan else "—"],
            ["Billing Interval", self._billing_interval_label(plan)],
            ["Billing Period", self._billing_period_label(billing_cycle)],
            ["Amount", f"{invoice.total_amount} {invoice.currency}"],
            ["Invoice Status", invoice.status.value.replace("_", " ").title()],
            [
                "Payment Status",
                latest_payment.status.value.replace("_", " ").title() if latest_payment else "No payment yet",
            ],
            ["Payment Date", self._format_date(invoice.paid_at)],
            ["Due Date", self._format_date(invoice.due_date)],
            ["Subscription ID", str(subscription.id)[:8] if subscription else "—"],
            [
                "Renewal Date",
                self._format_date(upcoming_cycle.next_billing_date) if upcoming_cycle else "—",
            ],
        ]
        if latest_payment is not None:
            rows.append(["Transaction ID", latest_payment.gateway_reference or "—"])
            rows.append(["Payment Method", latest_payment.payment_method.replace("_", " ").title()])

        table = Table(rows, colWidths=[2.3 * inch, 4.35 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (0, -1), DARK_SLATE),
                    ("TEXTCOLOR", (1, 0), (1, -1), DARK_SLATE),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
                ]
            )
        )
        return table

    def _build_line_items(self, styles, invoice: Invoice):
        heading_style = ParagraphStyle(
            "LineItemsHeading", parent=styles["Heading3"], fontSize=11, textColor=DARK_SLATE
        )
        header = ["Description", "Type", "Qty", "Unit Price", "Amount"]
        rows = [header]
        for item in invoice.line_items:
            rows.append(
                [
                    item.description,
                    item.item_type.value.replace("_", " ").title(),
                    str(item.quantity),
                    f"{item.unit_price} {invoice.currency}",
                    f"{item.amount} {invoice.currency}",
                ]
            )
        rows.append(["", "", "", "Subtotal", f"{invoice.subtotal} {invoice.currency}"])
        rows.append(["", "", "", "Tax", f"{invoice.tax_amount} {invoice.currency}"])
        rows.append(["", "", "", "Total", f"{invoice.total_amount} {invoice.currency}"])

        table = Table(rows, colWidths=[2.55 * inch, 1.4 * inch, 0.5 * inch, 1.1 * inch, 1.1 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), DARK_SLATE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, DARK_SLATE),
                    ("FONTNAME", (3, -1), (4, -1), "Helvetica-Bold"),
                    ("LINEABOVE", (3, -3), (4, -3), 0.5, colors.HexColor("#e2e8f0")),
                ]
            )
        )
        return [Paragraph("Line Items", heading_style), Spacer(1, 0.1 * inch), table]

    def _build_footer(self, styles):
        heading_style = ParagraphStyle(
            "FooterHeading", parent=styles["Normal"], fontSize=8, textColor=DARK_SLATE,
            fontName="Helvetica-Bold", spaceAfter=2,
        )
        body_style = ParagraphStyle(
            "FooterBody", parent=styles["Normal"], fontSize=8, textColor=MUTED, leading=11, spaceAfter=8,
        )
        generated_style = ParagraphStyle(
            "Generated", parent=styles["Normal"], textColor=MUTED, fontSize=8, alignment=TA_RIGHT,
        )
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        return [
            Paragraph("Payment Terms", heading_style),
            Paragraph(settings.PAYMENT_TERMS, body_style),
            Paragraph("Refund Policy", heading_style),
            Paragraph(settings.REFUND_POLICY, body_style),
            Paragraph(
                f"Questions about this invoice? Contact {settings.SUPPORT_EMAIL} "
                f"or {settings.SUPPORT_PHONE}.",
                body_style,
            ),
            Spacer(1, 0.15 * inch),
            Paragraph(
                f"This is a system-generated invoice. Generated on {generated_at}.", generated_style
            ),
        ]

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_date(value) -> str:
        if value is None:
            return "—"
        return value.strftime("%B %d, %Y")

    @staticmethod
    def _billing_interval_label(plan) -> str:
        if plan is None:
            return "—"
        return plan.billing_interval.value.title()

    @staticmethod
    def _billing_period_label(billing_cycle) -> str:
        if billing_cycle is None:
            return "—"
        start = billing_cycle.cycle_start_date.strftime("%b %d, %Y")
        end = billing_cycle.cycle_end_date.strftime("%b %d, %Y")
        return f"{start} – {end}"
