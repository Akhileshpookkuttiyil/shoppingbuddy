import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from orders.models import Order, OrderItem
from .models import ReturnRequest, ReturnAttachment, OrderAuditLog
from . import services

logger = logging.getLogger(__name__)

@login_required
@require_POST
def cancel_order_view(request, order_id):
    """Handles customer order cancellation POST requests."""
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    try:
        services.cancel_order(order, request.user)
        messages.success(request, f"Order {order.order_number} has been cancelled successfully.")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception(f"Unexpected error cancelling order {order_id}: {str(e)}")
        messages.error(request, "Failed to cancel order due to an internal error.")

    return redirect('order_detail', order_id=order.id)

@login_required
@require_POST
def request_return_view(request, order_id):
    """Handles customer return request creation (with multiple file uploads)."""
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    reason = request.POST.get('reason')
    description = request.POST.get('description', '')
    order_item_id = request.POST.get('order_item_id')
    images = request.FILES.getlist('images')

    if not reason:
        messages.error(request, "Please specify a reason for the return.")
        return redirect('order_detail', order_id=order.id)

    order_item = None
    if order_item_id:
        order_item = get_object_or_404(OrderItem, pk=order_item_id, order=order)

    try:
        services.request_return(
            order=order,
            user=request.user,
            reason=reason,
            description=description,
            order_item=order_item,
            images=images
        )
        messages.success(request, "Your return request has been submitted successfully and is under review.")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception(f"Unexpected error submitting return for order {order_id}: {str(e)}")
        messages.error(request, "Failed to submit return request due to an internal error.")

    return redirect('order_detail', order_id=order.id)

# --- Admin Dashboard Return Management ---

@staff_member_required
def admin_return_list(request):
    """Lists, filters, searches, and paginates return requests for administrators."""
    queryset = ReturnRequest.objects.filter(is_active=True).select_related(
        'order', 'user', 'order_item'
    ).prefetch_related('attachments')

    status_filter = request.GET.get('status')
    reason_filter = request.GET.get('reason')
    customer_query = request.GET.get('customer')
    search_query = request.GET.get('q')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if reason_filter:
        queryset = queryset.filter(reason=reason_filter)
    if customer_query:
        queryset = queryset.filter(user__username__icontains=customer_query)
    if search_query:
        queryset = queryset.filter(
            models.Q(order__order_number__icontains=search_query) |
            models.Q(user__email__icontains=search_query)
        )
    if start_date_str:
        start_date = parse_date(start_date_str)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
    if end_date_str:
        end_date = parse_date(end_date_str)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/returns/list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'reason_filter': reason_filter,
        'customer_query': customer_query,
        'search_query': search_query,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'status_choices': ReturnRequest.STATUS_CHOICES,
        'reason_choices': ReturnRequest.REASON_CHOICES,
    })

@staff_member_required
def admin_return_detail(request, request_id):
    """Displays return request details and audit history, auto-transitioning REQUESTED status."""
    return_request = get_object_or_404(
        ReturnRequest.objects.select_related('order', 'user', 'order_item').prefetch_related('attachments'),
        pk=request_id,
        is_active=True
    )
    
    if return_request.status == 'REQUESTED':
        from django.db import transaction
        with transaction.atomic():
            locked_req = ReturnRequest.objects.select_for_update().get(pk=return_request.id)
            if locked_req.status == 'REQUESTED':
                old_status = locked_req.status
                locked_req.status = 'UNDER_REVIEW'
                locked_req.save(update_fields=['status'])
                services.create_audit_log(locked_req.order, request.user, "Review Started", old_status, "UNDER_REVIEW")
                return_request.status = 'UNDER_REVIEW'

    audit_history = OrderAuditLog.objects.filter(order=return_request.order)

    return render(request, 'dashboard/returns/detail.html', {
        'return_request': return_request,
        'audit_history': audit_history,
    })

@staff_member_required
@require_POST
def admin_approve(request, request_id):
    """Approves a return request."""
    return_request = get_object_or_404(ReturnRequest, pk=request_id, is_active=True)
    try:
        services.approve_return(return_request, request.user)
        messages.success(request, f"Return request {return_request.id} has been APPROVED.")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception(f"Error approving return {request_id}: {str(e)}")
        messages.error(request, f"Failed to approve return: {str(e)}")

    return redirect('returns_admin:detail', request_id=return_request.id)

@staff_member_required
@require_POST
def admin_reject(request, request_id):
    """Rejects a return request."""
    return_request = get_object_or_404(ReturnRequest, pk=request_id, is_active=True)
    admin_notes = request.POST.get('admin_notes', '')
    try:
        services.reject_return(return_request, request.user, admin_notes)
        messages.success(request, f"Return request {return_request.id} has been REJECTED.")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception(f"Error rejecting return {request_id}: {str(e)}")
        messages.error(request, f"Failed to reject return: {str(e)}")

    return redirect('returns_admin:detail', request_id=return_request.id)

@staff_member_required
@require_POST
def admin_start_refund(request, request_id):
    """Moves return request to refund processing state."""
    return_request = get_object_or_404(ReturnRequest, pk=request_id, is_active=True)
    try:
        services.start_refund(return_request, request.user)
        messages.success(request, f"Refund process started for request {return_request.id}.")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception(f"Error starting refund for return {request_id}: {str(e)}")
        messages.error(request, f"Failed to start refund: {str(e)}")

    return redirect('returns_admin:detail', request_id=return_request.id)

@staff_member_required
@require_POST
def admin_complete_refund(request, request_id):
    """Completes the refund and restores stock levels."""
    return_request = get_object_or_404(ReturnRequest, pk=request_id, is_active=True)
    try:
        services.complete_refund(return_request, request.user)
        messages.success(request, f"Refund completed and inventory restored for request {return_request.id}.")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception(f"Error completing refund for return {request_id}: {str(e)}")
        messages.error(request, f"Failed to complete refund: {str(e)}")

    return redirect('returns_admin:detail', request_id=return_request.id)
