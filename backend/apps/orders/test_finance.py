"""Flujo financiero: historial del cliente, ingresos del profesional y gestión del administrador."""
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.models import Service, ServiceCategory
from apps.households.models import Household
from apps.professionals.models import ProfessionalProfile
from apps.service_requests.models import ServiceRequest

from .models import Order, Payment, Refund, Withdrawal

PASSWORD = "Finance-Test-81!"


@override_settings(DEBUG=True)
class FinanceFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = ServiceCategory.objects.create(name="Plomeria", slug="plomeria")
        cls.service = Service.objects.create(
            category=category, name="Reparacion fuga", slug="reparacion-fuga"
        )
        cls.client_user = User.objects.create_user(
            email="client@finance.example", username="fin-client", password=PASSWORD, role=UserRole.CLIENT
        )
        cls.other_client = User.objects.create_user(
            email="other@finance.example", username="fin-other", password=PASSWORD, role=UserRole.CLIENT
        )
        cls.staff = User.objects.create_user(
            email="staff@finance.example", username="fin-staff", password=PASSWORD, role=UserRole.STAFF
        )
        pro_user = User.objects.create_user(
            email="pro@finance.example", username="fin-pro", password=PASSWORD, role=UserRole.PROFESSIONAL
        )
        cls.profile = ProfessionalProfile.objects.create(user=pro_user, display_name="Pedro Pro")
        cls.pro_user = pro_user
        cls.household = Household.objects.create(owner=cls.client_user, label="Casa")

    def make_order(self, price="100000"):
        request = ServiceRequest.objects.create(
            client=self.client_user,
            household=self.household,
            selected_category=self.service.category,
            selected_service=self.service,
        )
        return Order.objects.create(
            service_request=request,
            professional=self.profile,
            client=self.client_user,
            final_price=Decimal(price),
        )

    def as_user(self, user):
        api = APIClient()
        api.force_authenticate(user=user)
        return api

    def pay_and_complete(self, order):
        response = self.as_user(self.client_user).post(f"/api/v1/orders/{order.id}/confirm-demo-payment/")
        self.assertEqual(response.status_code, 200, response.data)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.COMPLETED)

    def test_client_history_lists_payment_with_receipt_data(self):
        order = self.make_order()
        self.pay_and_complete(order)

        rows = self.as_user(self.client_user).get("/api/v1/payments/history/").data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], 100000)
        self.assertEqual(rows[0]["service"], "Reparacion fuga")
        self.assertEqual(rows[0]["professional"], "Pedro Pro")
        self.assertTrue(rows[0]["receipt_available"])
        self.assertEqual(self.as_user(self.other_client).get("/api/v1/payments/history/").data, [])

    def test_commission_split_and_professional_earnings(self):
        order = self.make_order()
        self.pay_and_complete(order)
        order.refresh_from_db()
        self.assertEqual(order.commission_amount, Decimal("10000.00"))
        self.assertEqual(order.professional_amount, Decimal("90000.00"))

        data = self.as_user(self.pro_user).get("/api/v1/professional/earnings/").data
        self.assertEqual(data["summary"]["pending_settlement"], 90000)
        self.assertEqual(data["summary"]["available_balance"], 0)
        self.assertEqual(len(data["incomes"]), 1)
        self.assertEqual(self.as_user(self.client_user).get("/api/v1/professional/earnings/").status_code, 403)

    def test_settlement_withdrawal_and_transfer(self):
        order = self.make_order()
        self.pay_and_complete(order)
        admin = self.as_user(self.staff)

        self.assertEqual(self.as_user(self.client_user).post("/api/v1/admin/payouts/settle/", {"all": True}, format="json").status_code, 403)
        settled = admin.post("/api/v1/admin/payouts/settle/", {"all": True}, format="json")
        self.assertEqual(settled.data["settled"], 1)

        pro = self.as_user(self.pro_user)
        self.assertEqual(pro.get("/api/v1/professional/earnings/").data["summary"]["available_balance"], 90000)
        too_much = pro.post("/api/v1/professional/withdrawals/", {"amount": 95000, "destination": "Bancolombia ahorros 1234"}, format="json")
        self.assertEqual(too_much.status_code, 400)
        created = pro.post("/api/v1/professional/withdrawals/", {"amount": 60000, "destination": "Bancolombia ahorros 1234"}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(pro.get("/api/v1/professional/earnings/").data["summary"]["available_balance"], 30000)

        pay_without_reference = admin.post(f"/api/v1/admin/withdrawals/{created.data['id']}/resolve/", {"action": "pay"}, format="json")
        self.assertEqual(pay_without_reference.status_code, 400)
        paid = admin.post(f"/api/v1/admin/withdrawals/{created.data['id']}/resolve/", {"action": "pay", "reference": "TRF-001"}, format="json")
        self.assertEqual(paid.data["status"], Withdrawal.Status.PAID)
        earnings = pro.get("/api/v1/professional/earnings/").data
        self.assertEqual(len(earnings["transfers"]), 1)
        self.assertEqual(earnings["summary"]["withdrawn_total"], 60000)

    def test_rejected_withdrawal_releases_balance(self):
        order = self.make_order()
        self.pay_and_complete(order)
        self.as_user(self.staff).post("/api/v1/admin/payouts/settle/", {"all": True}, format="json")
        pro = self.as_user(self.pro_user)
        created = pro.post("/api/v1/professional/withdrawals/", {"amount": 50000, "destination": "Nequi 3001234567"}, format="json")
        self.as_user(self.staff).post(f"/api/v1/admin/withdrawals/{created.data['id']}/resolve/", {"action": "reject", "note": "Datos incorrectos"}, format="json")
        self.assertEqual(pro.get("/api/v1/professional/earnings/").data["summary"]["available_balance"], 90000)

    def test_refund_reverts_payment_and_blocks_after_withdrawal(self):
        order = self.make_order()
        self.pay_and_complete(order)
        admin = self.as_user(self.staff)
        admin.post("/api/v1/admin/payouts/settle/", {"all": True}, format="json")
        pro = self.as_user(self.pro_user)
        withdrawal = pro.post("/api/v1/professional/withdrawals/", {"amount": 60000, "destination": "Nequi 3001234567"}, format="json")
        self.assertEqual(withdrawal.status_code, 201)

        refund = admin.post("/api/v1/admin/refunds/", {"order_id": order.id, "reason": "Servicio no prestado"}, format="json")
        self.assertEqual(refund.status_code, 201, refund.data)
        blocked = admin.post(f"/api/v1/admin/refunds/{refund.data['id']}/resolve/", {"action": "approve"}, format="json")
        self.assertEqual(blocked.status_code, 400)

        admin.post(f"/api/v1/admin/withdrawals/{withdrawal.data['id']}/resolve/", {"action": "reject", "note": "Reembolso en curso"}, format="json")
        approved = admin.post(f"/api/v1/admin/refunds/{refund.data['id']}/resolve/", {"action": "approve"}, format="json")
        self.assertEqual(approved.data["status"], Refund.Status.APPROVED)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.REFUNDED)
        self.assertEqual(Payment.objects.get(order=order).status, Payment.Status.REFUNDED)
        self.assertEqual(pro.get("/api/v1/professional/earnings/").data["summary"]["available_balance"], 0)
        self.assertEqual(self.as_user(self.client_user).post(f"/api/v1/orders/{order.id}/confirm-demo-payment/").data["payment_status"], "refunded")

    def test_admin_summary_report_and_permissions(self):
        order = self.make_order()
        self.pay_and_complete(order)
        admin = self.as_user(self.staff)

        summary = admin.get("/api/v1/admin/finance/summary/").data
        self.assertEqual(summary["collected"], 100000)
        self.assertEqual(summary["commissions"], 10000)
        self.assertEqual(summary["eligible_settlement_orders"], 1)

        report = admin.get("/api/v1/admin/finance/report/")
        self.assertEqual(report.data["totals"]["commissions"], 10000)
        csv_report = admin.get("/api/v1/admin/finance/report/?export=csv")
        self.assertEqual(csv_report["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Pedro Pro", csv_report.content.decode())
        self.assertEqual(admin.get("/api/v1/admin/finance/report/?from=nope").status_code, 400)

        for url in ("/api/v1/admin/finance/summary/", "/api/v1/admin/payments/", "/api/v1/admin/withdrawals/", "/api/v1/admin/refunds/"):
            self.assertEqual(self.as_user(self.client_user).get(url).status_code, 403, url)
