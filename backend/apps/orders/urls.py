from django.urls import path
from rest_framework.routers import DefaultRouter

from .finance_views import (
    AdminFinanceReportView,
    AdminFinanceSummaryView,
    AdminPaymentListView,
    AdminPaymentVerifyView,
    AdminPayoutListView,
    AdminPayoutSettleView,
    AdminRefundListView,
    AdminRefundResolveView,
    AdminWithdrawalListView,
    AdminWithdrawalResolveView,
    ClientPaymentHistoryView,
    PaymentHoldView,
    ProfessionalEarningsView,
    ProfessionalWithdrawalView,
)
from .views import OrderViewSet, ReviewViewSet, WompiEventsView

router = DefaultRouter()
router.register("orders", OrderViewSet, basename="order")
router.register("reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path("payments/wompi/events/", WompiEventsView.as_view(), name="wompi-events"),
    path("payments/history/", ClientPaymentHistoryView.as_view(), name="payment-history"),
    path("payments/hold/", PaymentHoldView.as_view(), name="payment-hold"),
    path("professional/earnings/", ProfessionalEarningsView.as_view(), name="professional-earnings"),
    path("professional/withdrawals/", ProfessionalWithdrawalView.as_view(), name="professional-withdrawals"),
    path("admin/payments/", AdminPaymentListView.as_view(), name="admin-payments"),
    path("admin/payments/<int:pk>/verify/", AdminPaymentVerifyView.as_view(), name="admin-payment-verify"),
    path("admin/finance/summary/", AdminFinanceSummaryView.as_view(), name="admin-finance-summary"),
    path("admin/finance/report/", AdminFinanceReportView.as_view(), name="admin-finance-report"),
    path("admin/payouts/", AdminPayoutListView.as_view(), name="admin-payouts"),
    path("admin/payouts/settle/", AdminPayoutSettleView.as_view(), name="admin-payouts-settle"),
    path("admin/withdrawals/", AdminWithdrawalListView.as_view(), name="admin-withdrawals"),
    path("admin/withdrawals/<int:pk>/resolve/", AdminWithdrawalResolveView.as_view(), name="admin-withdrawal-resolve"),
    path("admin/refunds/", AdminRefundListView.as_view(), name="admin-refunds"),
    path("admin/refunds/<int:pk>/resolve/", AdminRefundResolveView.as_view(), name="admin-refund-resolve"),
] + router.urls
